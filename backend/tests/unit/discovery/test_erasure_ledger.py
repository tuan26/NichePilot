"""T015 – Erasure ledger: genesis, hash chain, fsync, chỉ thêm (FR-013f; research R-09; X4)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from nichepilot.modules.discovery.erasure import Ledger, LedgerError

pytestmark = pytest.mark.discovery


def test_TC_E1_FR013f_01_chain_append_and_tamper_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synced: list[int] = []
    import os

    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(fd), real_fsync(fd)))
    ledger = Ledger(tmp_path)
    assert not ledger.exists()
    lid = uuid.uuid4()
    ledger.init(lid)
    e1 = ledger.append("EVIDENCE", uuid.uuid4(), content_hash="a" * 64, url_hash=None, requested_by=uuid.uuid4())
    e2 = ledger.append("SOURCE", uuid.uuid4(), content_hash=None, url_hash="b" * 64, requested_by=uuid.uuid4())
    assert (e1.seq, e2.seq) == (1, 2) and e2.prev_hash == e1.hash
    assert synced  # fsync đã được gọi
    genesis, entries = ledger.read()
    assert genesis["ledger_id"] == str(lid) and [e.seq for e in entries] == [1, 2]
    assert ledger.tail() == (2, e2.hash)
    raw = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    assert "excerpt" not in raw and "reason" not in raw  # sổ không chứa nội dung/PII
    # sửa một dòng → phát hiện hỏng chuỗi hash
    lines = raw.splitlines()
    doc = json.loads(lines[1])
    doc["target_id"] = str(uuid.uuid4())
    lines[1] = json.dumps(doc)
    (tmp_path / "ledger.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(LedgerError) as exc:
        ledger.read()
    assert exc.value.code == "LEDGER_CORRUPT"
    with pytest.raises(LedgerError):
        Ledger(tmp_path).init(uuid.uuid4())  # không ghi đè sổ đã tồn tại
