"""T073 – PII đầu-cuối (FR-012a, FR-012b, FR-012c, SC-016): sau một lượt MOCK có trang chứa PII GIẢ, 0 mẫu PII trong MỌI bảng
DB (gồm tool_executions, audit_logs, agent_jobs.checkpoint, job_steps), log, và prompt gửi AI; đoạn NEEDS_REVIEW (PII không chắc
nhận diện được) không được lưu, không được gửi AI. Không chứng minh PII engine trên dữ liệu thật/ngôn ngữ khác tiếng Anh."""

from __future__ import annotations

import pytest
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.modules.discovery.fingerprint import url_hash
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, NAMES_PAGE, PII_PAGE, run_discovery, set_search
from tests.fakes.discovery_ai import ScriptedDiscoveryAI

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]

PROFILE = "https://forum.example/user/groomfixer99"
PII_SAMPLES = (
    "owner.fake@example.com",
    "202-555-0143",
    "2025550143",
    "groomfixer99",
    "Taylor Brennan",
    "Brennan",
    "Morgan",
    "Priya",
    "Raman",
    "Jordan Ellis",
)
NEEDS_REVIEW_TEXT = ("Every tutor keeps a separate calendar", "tutoring centre loses students")


async def _dump_all_tables(engine: AsyncEngine) -> dict[str, str]:
    async with engine.connect() as conn:
        tables = (
            (
                await conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename NOT LIKE 'procrastinate%'"
                        " AND tablename <> 'alembic_version'"
                    )
                )
            )
            .scalars()
            .all()
        )
        out: dict[str, str] = {}
        for t in tables:
            rows = (await conn.execute(text(f'SELECT row_to_json(x)::text FROM "{t}" x'))).scalars().all()  # noqa: S608
            out[t] = "\n".join(rows)
        jobs = (await conn.execute(text("SELECT args::text FROM procrastinate_jobs"))).scalars().all()
        out["procrastinate_jobs"] = "\n".join(jobs)
    return out


async def _run_with_pii(migrated_db: str, clean_db: AsyncEngine) -> tuple[dict[str, object], ScriptedDiscoveryAI, list]:
    ai = ScriptedDiscoveryAI()
    with structlog.testing.capture_logs() as logs:
        async with discovery_client(migrated_db, ai=ai) as client:
            await allow_test_source(clean_db)
            set_search(client, [PII_PAGE, PROFILE, NAMES_PAGE, FORUM])
            run = await run_discovery(client)
    return run, ai, logs


async def test_TC_E1_FR012a_07_TC_E1_SC016_02_no_pii_in_db_logs_checkpoint_or_prompts(
    clean_db: AsyncEngine, migrated_db: str, capsys: pytest.CaptureFixture[str]
) -> None:
    run, ai, logs = await _run_with_pii(migrated_db, clean_db)
    assert run["job"]["status"] == "SUCCEEDED", run
    dump = await _dump_all_tables(clean_db)
    assert "[EMAIL]" in dump["research_evidence"] and "[PHONE]" in dump["research_evidence"]
    assert "[USER]" in dump["research_evidence"]
    # "Posted by Taylor Brennan" → "Posted by [PERSON]" (đoạn ngắn, không thành bằng chứng nhưng có trong output tool đã lưu)
    assert "[PERSON]" in dump["tool_executions"]
    leaks = {(t, p) for t, body in dump.items() for p in PII_SAMPLES if p in body}
    assert leaks == set(), f"PII chưa che trong DB: {sorted(leaks)}"
    log_text = "\n".join(str(e) for e in logs) + capsys.readouterr().out
    assert [p for p in PII_SAMPLES if p in log_text] == []
    prompts = ai.prompt_text()
    assert ai.requests_for("discovery.extract"), "phải có lời gọi extract để kiểm tra prompt"
    assert [p for p in PII_SAMPLES if p in prompts] == []
    assert "[EMAIL]" in prompts or "[PHONE]" in prompts  # nội dung pain point vẫn được giữ, chỉ PII bị thay


async def test_TC_E1_FR012b_03_uncertain_pii_segments_not_stored_nor_sent(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    run, ai, _ = await _run_with_pii(migrated_db, clean_db)
    assert run["metrics"]["needs_review_segments"] >= 2  # "Thanks, Morgan" + câu chứa "Priya Raman"
    dump = await _dump_all_tables(clean_db)
    everything = "\n".join(dump.values()) + ai.prompt_text()
    assert [t for t in NEEDS_REVIEW_TEXT if t in everything] == []
    async with clean_db.connect() as conn:
        statuses = (await conn.execute(text("SELECT DISTINCT redaction_status FROM research_evidence"))).scalars().all()
    assert statuses == ["REDACTED"]  # NEEDS_REVIEW không bao giờ được lưu dạng nội dung


async def test_TC_E1_FR012c_01_no_personal_profiles_or_contact_lists(clean_db: AsyncEngine, migrated_db: str) -> None:
    await _run_with_pii(migrated_db, clean_db)
    async with clean_db.connect() as conn:
        fetched = (await conn.execute(text("SELECT url_hash FROM page_fetch_log"))).scalars().all()
        urls = (await conn.execute(text("SELECT url FROM research_sources"))).scalars().all()
    assert url_hash(PROFILE) not in fetched  # URL hồ sơ cá nhân không được thu thập
    assert not [u for u in urls if "/user/" in u]
    dump = await _dump_all_tables(clean_db)
    assert "@example.com" not in "\n".join(dump.values())  # không còn email nào → không thể lập danh sách liên hệ
