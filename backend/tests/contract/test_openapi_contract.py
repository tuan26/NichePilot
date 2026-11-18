"""FR-002 – API tự sinh tài liệu khớp hợp đồng contracts/openapi.yaml (path + phương thức)."""

from __future__ import annotations

from pathlib import Path

import yaml

from nichepilot.main import create_app
from tests.api_helpers import make_settings

CONTRACT = (
    Path(__file__).resolve().parents[3] / "specs" / "001-foundation-ai-infrastructure" / "contracts" / "openapi.yaml"
)
METHODS = {"get", "post", "put", "patch", "delete"}


def test_TC_FR002_10_routes_match_contract() -> None:
    app = create_app(settings=make_settings("postgresql+psycopg://u:p@localhost:1/x"), check_database=False)
    impl = {(p, m) for p, ops in app.openapi()["paths"].items() for m in ops if m in METHODS}
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    expected = {(p, m) for p, ops in contract["paths"].items() for m in ops if m in METHODS}
    assert sorted(expected - impl) == [], "endpoint trong hợp đồng chưa được triển khai"
    assert sorted(impl - expected) == [], "endpoint triển khai nhưng không có trong hợp đồng"
