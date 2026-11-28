"""FR-002 – API tự sinh tài liệu khớp hợp đồng contracts/openapi.yaml (path + phương thức)."""

from __future__ import annotations

from pathlib import Path

import yaml

from nichepilot.main import create_app
from tests.api_helpers import make_settings

CONTRACT = (
    Path(__file__).resolve().parents[3] / "specs" / "001-foundation-ai-infrastructure" / "contracts" / "openapi.yaml"
)
E1_CONTRACT = CONTRACT.parents[2] / "002-niche-discovery" / "contracts" / "openapi.yaml"
E2_CONTRACT = CONTRACT.parents[2] / "003-product-affiliate-discovery" / "contracts" / "openapi.yaml"
E3_CONTRACT = CONTRACT.parents[2] / "004-keyword-audience-research" / "contracts" / "openapi.yaml"
E4_CONTRACT = CONTRACT.parents[2] / "005-bilingual-dashboard" / "contracts" / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def _ops(path: Path) -> set[tuple[str, str]]:
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {(p, m) for p, ops in contract["paths"].items() for m in ops if m in METHODS}


def test_TC_FR002_10_routes_match_contract() -> None:
    app = create_app(settings=make_settings("postgresql+psycopg://u:p@localhost:1/x"), check_database=False)
    impl = {(p, m) for p, ops in app.openapi()["paths"].items() for m in ops if m in METHODS}
    expected = _ops(CONTRACT)
    e1 = _ops(E1_CONTRACT)  # E1 triển khai dần theo user story; mọi endpoint E1 đã có phải nằm trong hợp đồng E1
    assert sorted(expected - impl) == [], "endpoint trong hợp đồng chưa được triển khai"
    e2 = _ops(E2_CONTRACT)  # E2: toàn bộ hợp đồng phải được triển khai
    assert sorted(e2 - impl) == [], "endpoint E2 trong hợp đồng chưa được triển khai"
    e3 = _ops(E3_CONTRACT)  # E3: toàn bộ hợp đồng phải được triển khai
    assert sorted(e3 - impl) == [], "endpoint E3 trong hợp đồng chưa được triển khai"
    e4 = _ops(E4_CONTRACT)  # E4: toàn bộ hợp đồng phải được triển khai
    assert sorted(e4 - impl) == [], "endpoint E4 trong hợp đồng chưa được triển khai"
    assert sorted(impl - expected - e1 - e2 - e3 - e4) == [], "endpoint triển khai nhưng không có trong hợp đồng"
