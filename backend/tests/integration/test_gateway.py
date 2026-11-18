"""T058, T061, T062 – AI Gateway với PostgreSQL thật (FR-012…FR-019c, FR-047, SC-005, AI-07).

Dùng MockAIProvider và FakePaidProvider (test double đóng vai provider có phí – KHÔNG gọi mạng).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.ai.gateway import AIGateway, CallContext
from nichepilot.ai.providers.base import LLMMessage
from nichepilot.ai.providers.mock import MockAIProvider
from nichepilot.core.errors import AppError
from tests.api_helpers import make_settings
from tests.fakes.providers import FakePaidProvider
from tests.integration.budget_helpers import insert_job, restore_budget_defaults, set_setting

pytestmark = [pytest.mark.integration, pytest.mark.mock]


class Out(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]
    note: str


MSG = [LLMMessage(role="user", content="hello")]


@pytest.fixture
async def env(clean_db: AsyncEngine, migrated_db: str) -> AsyncIterator[tuple[AsyncEngine, str]]:
    yield clean_db, migrated_db
    await restore_budget_defaults(clean_db)
    await set_setting(clean_db, "billing.error_responses_not_billed_verified", '{"anthropic": false, "openai": false}')
    async with clean_db.begin() as conn:
        await conn.execute(
            text(
                "UPDATE ai_models SET verified=false, verification_source=NULL, verified_at=NULL"
                " WHERE provider='anthropic'"
            )
        )
        await conn.execute(text("UPDATE model_pricing SET verified=false WHERE provider='anthropic'"))
        await conn.execute(
            text(
                "UPDATE model_task_profiles SET provider='anthropic', fallback_provider=NULL, fallback_model=NULL,"
                " fallback_on='{}'"
            )
        )


def _gw(
    engine: AsyncEngine, db_url: str, *, providers: dict[str, object] | None = None, **settings: object
) -> AIGateway:
    s = make_settings(db_url, **settings)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    return AIGateway(s, sm, providers or {"mock": MockAIProvider()}, backoff_base_s=0)  # type: ignore[arg-type]


async def _rows(engine: AsyncEngine, sql: str) -> list[tuple[object, ...]]:
    async with engine.connect() as conn:
        return [tuple(r) for r in (await conn.execute(text(sql))).all()]


async def _verify_anthropic(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE ai_models SET verified=true, verification_source='test fixture', verified_at=now(),"
                " supports_structured_output=true, supports_tools=true, supports_effort=true WHERE provider='anthropic'"
            )
        )
        await conn.execute(text("UPDATE model_pricing SET verified=true WHERE provider='anthropic'"))


async def test_TC_FR018_09_mock_call_records_mock_usage(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine)
    res = await _gw(engine, url).call(
        "system.diagnostic", system="s", messages=MSG, output_model=Out, ctx=CallContext(job_id=job, seed="a")
    )
    assert res.parsed == {"status": "ok", "note": "[MOCK] note"} and res.data_origin == "MOCK"
    rows = await _rows(engine, "SELECT provider, model, data_origin, billing_status, outcome FROM ai_usage_logs")
    assert rows == [("mock", "mock-model", "MOCK", "BILLED", "SUCCESS")]
    assert await _rows(engine, "SELECT status FROM budget_reservations") == [("SETTLED",)]


async def test_TC_FR018f_04_runtime_guard_rejects_mock_in_production(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine)
    gw = _gw(engine, url, ai_provider_override=None, app_env="production")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE model_task_profiles SET provider='mock', model='mock-model' WHERE task_type='system.diagnostic'"
            )
        )
    with pytest.raises(AppError) as exc:
        await gw.call("system.diagnostic", system="s", messages=MSG, output_model=Out, ctx=CallContext(job_id=job))
    assert exc.value.code == "MOCK_NOT_ALLOWED"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE model_task_profiles SET provider='anthropic', model='claude-haiku-5-5'"
                " WHERE task_type='system.diagnostic'"
            )
        )
    fake = FakePaidProvider()
    with pytest.raises(AppError) as exc2:  # mock_scenario với provider thật → từ chối, không gửi
        await _gw(engine, url, providers={"anthropic": fake}, ai_provider_override=None).call(
            "system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job, mock_scenario="success")
        )
    assert exc2.value.code == "MOCK_NOT_ALLOWED" and fake.calls == 0


async def test_TC_SC005_01_schema_invalid_retried_then_rejected_not_stored(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine)
    with pytest.raises(AppError) as exc:
        await _gw(engine, url).call(
            "system.diagnostic",
            system="s",
            messages=MSG,
            output_model=Out,
            ctx=CallContext(job_id=job, mock_scenario="schema_invalid"),
        )
    assert exc.value.code == "AI_SCHEMA_INVALID"
    # schema_retry_max mặc định 2 → 3 lần gọi, đều tính phí (đã có usage)
    assert len(await _rows(engine, "SELECT 1 FROM ai_usage_logs WHERE outcome='SCHEMA_INVALID'")) == 3


async def test_TC_FR017_02_refusal_not_retried_no_fallback(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine)
    with pytest.raises(AppError) as exc:
        await _gw(engine, url).call(
            "system.diagnostic",
            system="s",
            messages=MSG,
            output_model=Out,
            ctx=CallContext(job_id=job, mock_scenario="refusal"),
        )
    assert exc.value.code == "AI_REFUSED" and exc.value.params["refusal_category"] == "mock_policy"
    assert await _rows(engine, "SELECT outcome, refusal_category, is_fallback FROM ai_usage_logs") == [
        ("REFUSED", "mock_policy", False)
    ]


async def test_TC_FR014_03_transient_errors_retried_then_failed(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine)
    with pytest.raises(AppError) as exc:
        await _gw(engine, url).call(
            "system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job, mock_scenario="timeout")
        )
    assert exc.value.code == "PROVIDER_TIMEOUT"
    assert (
        await _rows(engine, "SELECT status, release_reason FROM budget_reservations ORDER BY created_at")
        == [("RELEASED", "NOT_SENT")] * 3
    )
    ok = await _gw(engine, url).call(
        "system.diagnostic",
        system="s",
        messages=MSG,
        output_model=Out,
        ctx=CallContext(job_id=job, mock_scenario="fail_n_then_success:timeout:2", seed="x"),
    )
    assert ok.parsed is not None


async def test_TC_FR014_04_auth_error_not_retried(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine)
    with pytest.raises(AppError) as exc:
        await _gw(engine, url).call(
            "system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job, mock_scenario="auth_error")
        )
    assert exc.value.code == "PROVIDER_AUTH_ERROR"
    assert len(await _rows(engine, "SELECT 1 FROM ai_usage_logs")) == 1


async def test_TC_FR047_04_billing_classification(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine, budget_limit="10.00")
    gw = _gw(engine, url)
    with pytest.raises(AppError):
        await gw.call(
            "system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job, mock_scenario="network_error")
        )
    with pytest.raises(AppError):  # mock mặc định coi phản hồi lỗi là không tính phí (đã "xác minh" nội bộ)
        await gw.call(
            "system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job, mock_scenario="provider_error")
        )
    rows = await _rows(engine, "SELECT status, COALESCE(release_reason, uncertain_reason) FROM budget_reservations")
    assert set(rows) == {("RELEASED", "NOT_SENT"), ("RELEASED", "ERROR_RESPONSE_NOT_BILLED")}
    billing = await _rows(engine, "SELECT DISTINCT billing_status FROM ai_usage_logs")
    assert billing == [("NOT_BILLED",)]


async def test_TC_FR019_01_paid_calls_disabled_blocks_before_send(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    await _verify_anthropic(engine)
    job = await insert_job(engine, origin="REAL")
    fake = FakePaidProvider()
    gw = _gw(engine, url, providers={"anthropic": fake}, ai_provider_override=None, ai_paid_calls_enabled=False)
    with pytest.raises(AppError) as exc:
        await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
    assert exc.value.code == "PAID_CALLS_DISABLED"
    assert fake.calls == 0
    assert await _rows(engine, "SELECT COUNT(*) FROM budget_reservations") == [(0,)]


async def test_TC_FR019c_01_unverified_model_or_pricing_blocks_paid_call(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine, origin="REAL")
    fake = FakePaidProvider()
    gw = _gw(engine, url, providers={"anthropic": fake}, ai_provider_override=None, ai_paid_calls_enabled=True)
    with pytest.raises(AppError) as exc:
        await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
    assert exc.value.code == "MODEL_NOT_VERIFIED"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE ai_models SET verified=true, verification_source='t', verified_at=now(), supports_structured_output=true,"
                " supports_tools=true, supports_effort=true WHERE provider='anthropic'"
            )
        )
    with pytest.raises(AppError) as exc2:
        await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
    assert exc2.value.code == "PRICING_NOT_VERIFIED"
    assert fake.calls == 0


async def test_TC_FR047_05_real_paid_call_with_unverified_error_policy_is_uncertain(
    env: tuple[AsyncEngine, str],
) -> None:
    engine, url = env
    await _verify_anthropic(engine)
    job = await insert_job(engine, origin="REAL")
    fake = FakePaidProvider(fail_with="rate_limit")
    gw = _gw(engine, url, providers={"anthropic": fake}, ai_provider_override=None, ai_paid_calls_enabled=True)
    with pytest.raises(Exception) as exc:
        await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
    assert getattr(exc.value, "code", None) in {"UNCERTAIN_RESERVATION_LIMIT", "PROVIDER_RATE_LIMITED"}
    rows = await _rows(engine, "SELECT status, uncertain_reason FROM budget_reservations")
    assert rows and all(r == ("UNCERTAIN", "ERROR_BILLING_UNVERIFIED") for r in rows)
    assert await _rows(engine, "SELECT DISTINCT data_origin FROM ai_usage_logs") == [("REAL",)]


async def test_TC_AI07_01_fallback_only_for_configured_unavailable(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    await _verify_anthropic(engine)
    await set_setting(engine, "billing.error_responses_not_billed_verified", '{"anthropic": true, "openai": true}')
    job = await insert_job(engine, origin="REAL")
    primary = FakePaidProvider(fail_with="provider_error")
    backup = FakePaidProvider(name="openai")
    gw = _gw(
        engine,
        url,
        providers={"anthropic": primary, "openai": backup},
        ai_provider_override=None,
        ai_paid_calls_enabled=True,
    )
    with pytest.raises(AppError):  # chưa cấu hình dự phòng → không tự chuyển
        await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
    assert backup.calls == 0
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ai_models (provider, model_id, verified, verification_source, verified_at, supports_structured_output, supports_tools, supports_effort) VALUES ('openai','gpt-fallback',true,'t',now(),true,true,true) ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO model_pricing (provider, model, version, input_per_mtok, output_per_mtok, source_note, verified) VALUES ('openai','gpt-fallback',1,1,1,'t',true) ON CONFLICT DO NOTHING"
            )
        )
        await conn.execute(
            text(
                "UPDATE model_task_profiles SET fallback_provider='openai', fallback_model='gpt-fallback', fallback_on='{PROVIDER_UNAVAILABLE}' WHERE task_type='system.diagnostic'"
            )
        )
    res = await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
    assert res.is_fallback and res.provider == "openai" and backup.calls == 1
    assert (True,) in await _rows(engine, "SELECT is_fallback FROM ai_usage_logs")


async def test_TC_FR013_01_structured_output_validated_before_return(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    job = await insert_job(engine)
    result = await _gw(engine, url).call(
        "system.diagnostic", system="s", messages=MSG, output_model=Out, ctx=CallContext(job_id=job)
    )
    assert result.schema_valid is True and result.parsed is not None
    Out.model_validate(result.parsed)  # kết quả trả cho agent luôn khớp schema


async def test_TC_FR013_02_invalid_output_never_stored(env: tuple[AsyncEngine, str], migrated_db: str) -> None:
    from tests.api_helpers import api_client, csrf_headers, run_worker_once, setup_owner

    engine, _ = env
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "system.diagnostic", "params": {"mock_scenario": "schema_invalid"}},
            headers=csrf_headers(client),
        )
        await run_worker_once(client)
        job = (await client.get(f"/api/v1/jobs/{r.json()['id']}")).json()
        steps = (await client.get(f"/api/v1/jobs/{job['id']}/steps")).json()
    assert job["status"] == "FAILED" and job["status_reason_code"] == "AI_SCHEMA_INVALID" and job["result"] is None
    failed = [s for s in steps if s["error_code"] == "AI_SCHEMA_INVALID"]
    assert failed and all(s["output"] is None for s in failed)  # output sai schema không được lưu
    rows = await _rows(engine, "SELECT COUNT(*) FROM ai_usage_logs WHERE outcome = 'SCHEMA_INVALID'")
    assert rows[0][0] >= 1  # nhưng chi phí của lời gọi vẫn được ghi nhận


class _CountFails(FakePaidProvider):
    async def count_input_tokens(self, req: object) -> int:  # type: ignore[override]
        from nichepilot.ai.providers.base import ProviderNetworkError

        raise ProviderNetworkError("fake: count_tokens không khả dụng", sent=False)


async def test_TC_FR043_12_paid_call_fails_closed_when_tokens_cannot_be_counted(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    await _verify_anthropic(engine)
    job = await insert_job(engine, origin="REAL")
    fake = _CountFails()
    gw = _gw(engine, url, providers={"anthropic": fake}, ai_provider_override=None, ai_paid_calls_enabled=True)
    with pytest.raises(AppError) as exc:
        await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
    assert exc.value.code == "COST_ESTIMATE_UNAVAILABLE"
    assert fake.calls == 0  # không gửi lời gọi có phí
    assert await _rows(engine, "SELECT COUNT(*) FROM budget_reservations") == [(0,)]


async def test_TC_FR043_13_paid_call_fails_closed_on_zero_price(env: tuple[AsyncEngine, str]) -> None:
    from tests.config_snapshot import restore, snapshot

    engine, url = env
    snap = await snapshot(engine)
    try:
        await _verify_anthropic(engine)
        async with engine.begin() as conn:  # thêm phiên bản giá mới (append-only) có giá input = 0
            await conn.execute(
                text(
                    "INSERT INTO model_pricing (provider, model, version, input_per_mtok, output_per_mtok, source_note,"
                    " verified) SELECT provider, model, MAX(version) + 1, 0, 0.50, 'test: giá lỗi', true"
                    " FROM model_pricing WHERE provider = 'anthropic' AND model = 'claude-haiku-5-5' GROUP BY 1, 2"
                )
            )
        job = await insert_job(engine, origin="REAL")
        fake = FakePaidProvider()
        gw = _gw(engine, url, providers={"anthropic": fake}, ai_provider_override=None, ai_paid_calls_enabled=True)
        with pytest.raises(AppError) as exc:
            await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
        assert exc.value.code == "COST_ESTIMATE_UNAVAILABLE"
        assert fake.calls == 0
    finally:
        await restore(engine, snap)


async def test_TC_FR043_14_unverified_price_blocks_before_reservation(env: tuple[AsyncEngine, str]) -> None:
    engine, url = env
    await _verify_anthropic(engine)
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE model_pricing SET verified=false WHERE provider='anthropic'"))
    job = await insert_job(engine, origin="REAL")
    fake = FakePaidProvider()
    gw = _gw(engine, url, providers={"anthropic": fake}, ai_provider_override=None, ai_paid_calls_enabled=True)
    with pytest.raises(AppError) as exc:
        await gw.call("system.diagnostic", system="s", messages=MSG, ctx=CallContext(job_id=job))
    assert exc.value.code == "PRICING_NOT_VERIFIED"
    assert fake.calls == 0
    assert await _rows(engine, "SELECT COUNT(*) FROM budget_reservations") == [(0,)]
