"""T013 – Structured logging, redaction, file log theo ngày (FR-050, FR-057, SC-008)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest
import structlog

from nichepilot.core.logging import bind_context, clear_context, configure_logging, redact

SECRET = "sk-ant-api03-SUPERSECRETVALUE1234567890"


def _lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_TC_FR050_01_redact_patterns_and_known_secrets() -> None:
    known = ["my-database-password-xyz"]
    assert "my-database-password-xyz" not in redact("pw=my-database-password-xyz", known)
    assert "sk-ant-" not in redact(f"key {SECRET}", [])
    assert "sk-proj-abcdefghijklmnop" not in redact("key sk-proj-abcdefghijklmnop", [])
    assert "abc.def.ghi" not in redact("Authorization: Bearer abc.def.ghi", [])
    assert redact("không có gì nhạy cảm", []) == "không có gì nhạy cảm"


def test_TC_FR050_02_json_log_to_stdout_and_daily_file_redacted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(level="INFO", fmt="json", log_dir=tmp_path, secret_values=["db-pass-123456"])
    log = structlog.get_logger("test")
    bind_context(request_id="req-1", job_id="job-1", step_id="step-1")
    try:
        log.info("calling provider", api_key=SECRET, note="password db-pass-123456 inside")
        logging.getLogger("thirdparty").warning("lib says %s", SECRET)
    finally:
        clear_context()

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    log_file = tmp_path / f"app-{today}.jsonl"
    assert log_file.exists()
    file_text = log_file.read_text()
    out = capsys.readouterr().out
    for text_ in (file_text, out):
        assert SECRET not in text_
        assert "db-pass-123456" not in text_
    records = _lines(log_file)
    ours = next(r for r in records if r.get("event") == "calling provider")
    assert ours["request_id"] == "req-1"
    assert ours["job_id"] == "job-1"
    assert ours["step_id"] == "step-1"
    assert ours["api_key"] == "***"
    assert ours["level"] == "info"
    assert "timestamp" in ours
    assert any(r.get("logger") == "thirdparty" for r in records)


def test_TC_FR057_02_sensitive_keys_masked_recursively(tmp_path: Path) -> None:
    configure_logging(level="INFO", fmt="json", log_dir=tmp_path, secret_values=[])
    structlog.get_logger("t").info("nested", payload={"headers": {"authorization": "x"}, "password": "y", "ok": 1})
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    rec = next(r for r in _lines(tmp_path / f"app-{today}.jsonl") if r.get("event") == "nested")
    payload = rec["payload"]
    assert isinstance(payload, dict)
    assert payload["password"] == "***"
    assert payload["headers"] == {"authorization": "***"}
    assert payload["ok"] == 1
