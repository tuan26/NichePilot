"""FR-072 – Test tự động không cần API key thật, không phát sinh chi phí; test live tách riêng, có trần chi phí."""

from __future__ import annotations

import socket
import tomllib
from pathlib import Path

import pytest

from tests.conftest import OutboundNetworkBlockedError

BACKEND = Path(__file__).resolve().parents[2]


def test_TC_FR072_01_live_tests_excluded_by_default() -> None:
    cfg = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]
    assert "-m 'not live'" in cfg["addopts"]
    live_files = list((BACKEND / "tests" / "live").glob("test_*.py"))
    assert live_files and all("pytest.mark.live" in f.read_text(encoding="utf-8") for f in live_files)
    guard = (BACKEND / "tests" / "live" / "conftest.py").read_text(encoding="utf-8")
    assert "AI_PAID_CALLS_ENABLED" in guard and "NICHEPILOT_LIVE_MAX_USD" in guard  # trần chi phí bắt buộc


def test_TC_FR072_02_outbound_network_blocked_in_automated_tests() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OutboundNetworkBlockedError):
            s.connect(("1.1.1.1", 443))
    finally:
        s.close()
