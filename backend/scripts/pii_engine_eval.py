#!/usr/bin/env python3
"""Đo chất lượng PiiEngine trên tập có nhãn (T131 – FR-012a, FR-032, SC-016; quyết định A1 sau analyze cuối).

Phân loại mỗi mẫu:
- Mẫu có PII: "bắt được" nếu kết quả không phải REDACTED (NEEDS_REVIEW/UNSAFE), hoặc REDACTED nhưng mọi giá trị PII đã biến mất.
  Ngược lại là false negative (FN) – PII lọt vào văn bản có thể gửi AI.
- Mẫu không có PII: NEEDS_REVIEW/UNSAFE là cảnh báo sai (false positive, FP); REDACTED là đúng (TN).
Chỉ in số liệu và loại nguy cơ – không in nội dung mẫu. Không tự đổi engine: kết quả để chủ sở hữu quyết định.

Chạy: `uv run python scripts/pii_engine_eval.py [--engine regex-phone] [--data tests/fixtures/discovery/pii_labeled.jsonl]`
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "discovery" / "pii_labeled.jsonl"


@dataclass
class EvalResult:
    engine: str
    total: int = 0
    with_pii: int = 0
    without_pii: int = 0
    needs_review: int = 0
    unsafe: int = 0
    true_positive: int = 0
    false_negative: int = 0
    false_positive: int = 0
    true_negative: int = 0
    fn_indexes: list[int] = field(default_factory=list)
    fp_indexes: list[int] = field(default_factory=list)

    @property
    def needs_review_rate(self) -> float:
        return round(self.needs_review / self.total, 4) if self.total else 0.0

    @property
    def false_positive_rate(self) -> float:
        return round(self.false_positive / self.without_pii, 4) if self.without_pii else 0.0

    @property
    def false_negative_rate(self) -> float:
        return round(self.false_negative / self.with_pii, 4) if self.with_pii else 0.0

    def summary(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "total": self.total,
            "with_pii": self.with_pii,
            "without_pii": self.without_pii,
            "needs_review": self.needs_review,
            "unsafe": self.unsafe,
            "needs_review_rate": self.needs_review_rate,
            "true_positive": self.true_positive,
            "false_negative": self.false_negative,
            "false_positive": self.false_positive,
            "true_negative": self.true_negative,
            "false_negative_rate": self.false_negative_rate,
            "false_positive_rate": self.false_positive_rate,
            "fn_sample_indexes": self.fn_indexes,
            "fp_sample_indexes": self.fp_indexes,
        }


def evaluate(engine: object, data: Path = DEFAULT_DATA) -> EvalResult:
    from nichepilot.tools.privacy.pii import PiiEngine

    eng: PiiEngine = engine  # type: ignore[assignment]
    res = EvalResult(engine=eng.name)
    rows = [json.loads(line) for line in data.read_text(encoding="utf-8").splitlines() if line.strip()]
    samples = [r for r in rows if "text" in r]
    for idx, row in enumerate(samples):
        out = eng.redact(row["text"], language=row["language"], country=row["country"])
        res.total += 1
        res.needs_review += out.status == "NEEDS_REVIEW"
        res.unsafe += out.status == "UNSAFE"
        flagged = out.status != "REDACTED"
        if row["pii_values"]:
            res.with_pii += 1
            leaked = (not flagged) and any(v in out.text for v in row["pii_values"])
            if leaked:
                res.false_negative += 1
                res.fn_indexes.append(idx)
            else:
                res.true_positive += 1
        else:
            res.without_pii += 1
            if flagged:
                res.false_positive += 1
                res.fp_indexes.append(idx)
            else:
                res.true_negative += 1
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", default="regex-phone")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = ap.parse_args(argv)
    from nichepilot.core.discovery_config import DiscoverySettings
    from nichepilot.tools.privacy.pii import select_pii_engine

    engine = select_pii_engine(DiscoverySettings(pii_engine=args.engine, pii_approved_engines=args.engine))
    print(json.dumps(evaluate(engine, args.data).summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
