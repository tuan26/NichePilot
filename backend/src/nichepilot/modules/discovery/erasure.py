"""Erasure ledger – xóa bằng chứng bền vững và áp dụng lại sau restore (FR-013e, FR-013f; research R-09; X4).

Sổ `ledger.jsonl` (volume riêng, KHÔNG nằm trong dump PostgreSQL): dòng đầu là genesis `{ledger_id}`; mỗi dòng sau
`{seq, target_type, target_id, content_hash, url_hash, requested_by, erased_at, prev_hash, hash}` với
`hash = sha256(prev_hash ‖ payload)` → phát hiện mất/sửa dòng. Không chứa nội dung hay PII (chỉ ID, hash, thời điểm).

`apply_erasure_ledger` (strict) chạy trong service `migrate` và sau `make restore`; mọi lỗi → rollback, `BLOCKED`, mã
lỗi;
API E1 trả 503 và agent E1 dừng ở `preflight` cho tới khi áp dụng thành công.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.core.errors import AppError
from nichepilot.core.logging import get_logger
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.discovery import analysis, evaluation
from nichepilot.modules.discovery.fingerprint import url_hash as compute_url_hash

log = get_logger(__name__)
LEDGER_FILE = "ledger.jsonl"
TargetType = Literal["EVIDENCE", "SOURCE"]


class LedgerError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    target_type: str
    target_id: str
    content_hash: str | None
    url_hash: str | None
    requested_by: str | None
    erased_at: str
    prev_hash: str
    hash: str


def _digest(prev: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256((prev + body).encode("utf-8")).hexdigest()


def _genesis_hash(ledger_id: str) -> str:
    return hashlib.sha256(f"genesis:{ledger_id}".encode()).hexdigest()


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Ledger:
    def __init__(self, directory: Path) -> None:
        self.dir = Path(directory)
        self.path = self.dir / LEDGER_FILE

    def exists(self) -> bool:
        return self.path.is_file()

    def init(self, ledger_id: uuid.UUID) -> dict[str, Any]:
        if self.exists():
            raise LedgerError("LEDGER_EXISTS")
        self.dir.mkdir(parents=True, exist_ok=True)
        genesis = {
            "type": "genesis",
            "ledger_id": str(ledger_id),
            "created_at": datetime.now(UTC).isoformat(),
            "hash": _genesis_hash(str(ledger_id)),
        }
        with open(self.path, "x", encoding="utf-8") as f:
            f.write(json.dumps(genesis, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        _fsync_dir(self.dir)
        return genesis

    def read(self) -> tuple[dict[str, Any], list[LedgerEntry]]:
        if not self.exists():
            raise LedgerError("LEDGER_MISSING")
        lines = [ln for ln in self.path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            raise LedgerError("LEDGER_CORRUPT", "empty")
        try:
            genesis = json.loads(lines[0])
            if genesis.get("type") != "genesis" or genesis.get("hash") != _genesis_hash(str(genesis["ledger_id"])):
                raise LedgerError("LEDGER_CORRUPT", "genesis")
            prev = str(genesis["hash"])
            entries: list[LedgerEntry] = []
            for expected_seq, line in enumerate(lines[1:], start=1):
                doc = json.loads(line)
                claimed = doc.pop("hash")
                if doc.get("seq") != expected_seq or doc.get("prev_hash") != prev or _digest(prev, doc) != claimed:
                    raise LedgerError("LEDGER_CORRUPT", f"seq {expected_seq}")
                entries.append(
                    LedgerEntry(
                        seq=int(doc["seq"]),
                        target_type=str(doc.get("target_type")),
                        target_id=str(doc.get("target_id")),
                        content_hash=doc.get("content_hash"),
                        url_hash=doc.get("url_hash"),
                        requested_by=doc.get("requested_by"),
                        erased_at=str(doc.get("erased_at") or genesis["created_at"]),
                        prev_hash=prev,
                        hash=claimed,
                    )
                )
                prev = claimed
        except (ValueError, KeyError, TypeError) as exc:
            raise LedgerError("LEDGER_CORRUPT", type(exc).__name__) from None
        return genesis, entries

    def tail(self) -> tuple[int, str]:
        genesis, entries = self.read()
        return (entries[-1].seq, entries[-1].hash) if entries else (0, str(genesis["hash"]))

    def _append_raw(self, fields: dict[str, Any]) -> LedgerEntry:
        """Ghi một dòng (đã khóa file, fsync). `fields` chỉ chứa định danh/hash – KHÔNG nội dung."""
        with open(self.path, "a+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                seq, prev = self.tail()
                payload = {
                    "seq": seq + 1,
                    "prev_hash": prev,
                    "erased_at": datetime.now(UTC).isoformat(),
                    **fields,
                }
                digest = _digest(prev, payload)
                f.write(json.dumps({**payload, "hash": digest}, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        _fsync_dir(self.dir)
        return LedgerEntry(
            seq=payload["seq"],
            target_type=str(payload.get("target_type")),
            target_id=str(payload.get("target_id")),
            content_hash=payload.get("content_hash"),
            url_hash=payload.get("url_hash"),
            requested_by=payload.get("requested_by"),
            erased_at=payload["erased_at"],
            prev_hash=prev,
            hash=digest,
        )

    def append(
        self,
        target_type: TargetType,
        target_id: uuid.UUID,
        *,
        content_hash: str | None,
        url_hash: str | None,
        requested_by: uuid.UUID | None,
    ) -> LedgerEntry:
        if not self.exists():
            raise LedgerError("LEDGER_MISSING")
        return self._append_raw(
            {
                "target_type": target_type,
                "target_id": str(target_id),
                "content_hash": content_hash,
                "url_hash": url_hash,
                "requested_by": str(requested_by) if requested_by else None,
            }
        )


@dataclass(frozen=True)
class LedgerApplyResult:
    applied: int
    tail_seq: int
    ledger_id: str


@dataclass(frozen=True)
class LedgerHealth:
    status: Literal["OK", "BLOCKED", "OUT_OF_SYNC"]
    applied_seq: int
    ledger_tail_seq: int | None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


async def apply_entry(session: AsyncSession, entry: LedgerEntry) -> None:
    """Xóa nội dung của đích (idempotent). Đích không tồn tại (backup cũ hơn bằng chứng) → không có gì để xóa."""
    if entry.target_type == "EVIDENCE":
        await session.execute(
            text(
                "UPDATE research_evidence SET excerpt = NULL, value = NULL, lifecycle_status = 'ERASED',"
                " erased_at = COALESCE(erased_at, CAST(:t AS timestamptz)), updated_at = now()"
                " WHERE id = CAST(:i AS uuid) AND lifecycle_status = 'ACTIVE'"
            ),
            {"i": entry.target_id, "t": entry.erased_at},
        )
    elif entry.target_type == "SOURCE":
        marker = f"erased:{entry.url_hash or hashlib.sha256(entry.target_id.encode()).hexdigest()}"
        await session.execute(
            text(
                "UPDATE research_evidence SET excerpt = NULL, value = NULL, lifecycle_status = 'ERASED',"
                " erased_at = COALESCE(erased_at, CAST(:t AS timestamptz)), updated_at = now()"
                " WHERE source_id = CAST(:i AS uuid) AND lifecycle_status = 'ACTIVE'"
            ),
            {"i": entry.target_id, "t": entry.erased_at},
        )
        await session.execute(
            text(
                "UPDATE research_sources SET url = :m, canonical_url = :m, title = NULL, publisher = NULL,"
                " lifecycle_status = 'ERASED', erased_at = COALESCE(erased_at, CAST(:t AS timestamptz)),"
                " updated_at = now() WHERE id = CAST(:i AS uuid) AND lifecycle_status = 'ACTIVE'"
            ),
            {"i": entry.target_id, "t": entry.erased_at, "m": marker},
        )
    else:
        raise ValueError(f"target_type không hợp lệ: {entry.target_type}")
    await session.execute(
        text("UPDATE evidence_erasure_requests SET applied_at = COALESCE(applied_at, now()) WHERE ledger_seq = :s"),
        {"s": entry.seq},
    )


async def _affected_by(session: AsyncSession, entry: LedgerEntry) -> list[uuid.UUID]:
    if entry.target_type == "EVIDENCE":
        ids = [uuid.UUID(entry.target_id)]
    else:
        ids = [
            uuid.UUID(str(r[0]))
            for r in (
                await session.execute(
                    text("SELECT id FROM research_evidence WHERE source_id = CAST(:s AS uuid)"), {"s": entry.target_id}
                )
            ).all()
        ]
    return await analysis.affected_niches(session, ids)


async def _block(sm: async_sessionmaker[AsyncSession], code: str) -> None:
    async with sm() as s, s.begin():
        await s.execute(
            text(
                "UPDATE erasure_ledger_state SET status = 'BLOCKED', last_error = :e, checked_at = now(),"
                " updated_at = now()"
            ),
            {"e": code[:500]},
        )
    log.error("erasure_ledger.blocked", code=code)


async def apply_erasure_ledger(
    sm: async_sessionmaker[AsyncSession], ledger: Ledger, *, strict: bool = True
) -> LedgerApplyResult:
    """Áp dụng các yêu cầu xóa chưa có trong DB, trong MỘT transaction. Lỗi → rollback + BLOCKED + LedgerError."""
    try:
        async with sm() as s, s.begin():
            state = (
                (await s.execute(text("SELECT * FROM erasure_ledger_state WHERE id = 1 FOR UPDATE"))).mappings().one()
            )
            if not ledger.exists():
                pending = (await s.execute(text("SELECT count(*) FROM evidence_erasure_requests"))).scalar_one()
                if state["ledger_id"] is not None or pending:
                    raise LedgerError("LEDGER_MISSING")
                lid = uuid.uuid4()
                ledger.init(lid)  # cài mới: khởi tạo sổ
                await s.execute(
                    text(
                        "UPDATE erasure_ledger_state SET ledger_id = :l, applied_seq = 0, applied_hash = NULL,"
                        " status = 'OK', last_error = NULL, checked_at = now(), updated_at = now()"
                    ),
                    {"l": lid},
                )
                log.info("erasure_ledger.initialized")
                return LedgerApplyResult(0, 0, str(lid))
            genesis, entries = ledger.read()
            lid_str = str(genesis["ledger_id"])
            if state["ledger_id"] is not None and str(state["ledger_id"]) != lid_str:
                raise LedgerError("LEDGER_ID_MISMATCH")
            applied_seq = int(state["applied_seq"])
            tail = entries[-1].seq if entries else 0
            if applied_seq > tail:
                raise LedgerError("LEDGER_OLDER_THAN_DB")
            if applied_seq > 0 and entries[applied_seq - 1].hash != state["applied_hash"]:
                raise LedgerError("LEDGER_HASH_MISMATCH")
            todo = [e for e in entries if e.seq > applied_seq]
            try:
                affected: set[uuid.UUID] = set()
                for entry in todo:
                    affected.update(await _affected_by(s, entry))
                    await apply_entry(s, entry)
                # bằng chứng bị xóa (lại) → tính lại ngách liên quan TRƯỚC khi dữ liệu được dùng (FR-013e/f), không AI
                for niche_id in sorted(affected, key=str):
                    await evaluation.evaluate_and_store(s, niche_id, computed_without_ai=True)
            except Exception as exc:
                raise LedgerError("LEDGER_APPLY_FAILED", type(exc).__name__) from None
            await s.execute(
                text(
                    "UPDATE erasure_ledger_state SET ledger_id = :l, applied_seq = :q, applied_hash = :h,"
                    " status = 'OK', last_error = NULL, checked_at = now(), updated_at = now()"
                ),
                {"l": uuid.UUID(lid_str), "q": tail, "h": entries[-1].hash if entries else None},
            )
            if todo:
                log.info("erasure_ledger.reapplied", applied=len(todo), tail_seq=tail)
            return LedgerApplyResult(len(todo), tail, lid_str)
    except LedgerError as exc:
        await _block(sm, exc.code)
        raise
    except OSError as exc:  # volume không đọc/ghi được (quyền, đĩa đầy…) → thất bại an toàn, mã lỗi rõ ràng
        await _block(sm, "LEDGER_IO_ERROR")
        raise LedgerError("LEDGER_IO_ERROR", type(exc).__name__) from None


LedgerTail = tuple[int, str] | LedgerError


def read_tail(ledger: Ledger) -> LedgerTail:
    try:
        return ledger.tail()
    except LedgerError as exc:
        return exc
    except OSError:
        return LedgerError("LEDGER_IO_ERROR")


async def ledger_health(
    sm: async_sessionmaker[AsyncSession], ledger: Ledger, *, tail: LedgerTail | None = None
) -> LedgerHealth:
    """Trạng thái DB đọc MỖI lần (sau restore, `BLOCKED` có hiệu lực ngay); `tail` (đọc file sổ) có thể được cache."""
    async with sm() as s:
        state = (await s.execute(text("SELECT * FROM erasure_ledger_state WHERE id = 1"))).mappings().one()
    applied = int(state["applied_seq"])
    if state["status"] == "BLOCKED":
        return LedgerHealth("BLOCKED", applied, None, state["last_error"])
    if state["ledger_id"] is None:
        return LedgerHealth("OUT_OF_SYNC", applied, None, "LEDGER_NOT_INITIALIZED")
    t = tail if tail is not None else read_tail(ledger)
    if isinstance(t, LedgerError):
        return LedgerHealth("OUT_OF_SYNC", applied, None, t.code)
    tail_seq, tail_hash = t
    if tail_seq != applied or (applied > 0 and tail_hash != state["applied_hash"]):
        return LedgerHealth("OUT_OF_SYNC", applied, tail_seq, "LEDGER_NOT_APPLIED")
    return LedgerHealth("OK", applied, tail_seq)


# ---------------------------------------------------------------------------------------------------------------------
# EvidenceErasureService (T082; internal-interfaces §4): ghi sổ → transaction DB → (API) job `discovery.recompute`
# ---------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ErasureResult:
    erasure_id: uuid.UUID
    ledger_seq: int
    target_type: str
    target_id: uuid.UUID
    evidence_ids: list[uuid.UUID]
    affected_niche_ids: list[uuid.UUID]


class EvidenceErasureService:
    """Xóa một bằng chứng (EVIDENCE) hoặc mọi bằng chứng của nguồn (SOURCE) theo yêu cầu hợp lệ (FR-013e).

    Thứ tự bền vững (X4): khóa `erasure_ledger_state` (tuần tự hóa mọi lần xóa/áp dụng sổ) → kiểm tra sổ đồng bộ với
    DB → ghi
    dòng sổ (fsync; lỗi I/O → `ERASURE_LEDGER_WRITE_FAILED`, DB không đổi) → trong CÙNG transaction: xóa nội dung, ghi
    `evidence_erasure_requests`, audit (không nội dung), cập nhật `applied_seq`, tính lại ngưỡng của các ngách liên
    quan (đồng
    bộ, không AI). Lỗi DB sau khi đã ghi sổ → rollback; sổ đi trước DB → cổng 503 cho tới lần `apply_erasure_ledger`
    kế tiếp
    (idempotent) hoàn tất việc xóa.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], ledger: Ledger) -> None:
        self.sessionmaker = sessionmaker
        self.ledger = ledger

    async def erase(
        self,
        evidence_id: uuid.UUID,
        *,
        scope: TargetType,
        reason: str,
        actor_id: uuid.UUID,
        request_id: str | None = None,
    ) -> ErasureResult:
        async with self.sessionmaker() as s, s.begin():
            state = (
                (await s.execute(text("SELECT * FROM erasure_ledger_state WHERE id = 1 FOR UPDATE"))).mappings().one()
            )
            ev = (
                await s.execute(
                    text("SELECT id, source_id, content_hash, lifecycle_status FROM research_evidence WHERE id = :i"),
                    {"i": evidence_id},
                )
            ).first()
            if ev is None:
                raise AppError("EVIDENCE_NOT_FOUND")
            if scope == "EVIDENCE":
                if ev.lifecycle_status != "ACTIVE":
                    raise AppError("EVIDENCE_ALREADY_ERASED")
                target_id, chash, uhash = uuid.UUID(str(ev.id)), ev.content_hash, None
                evidence_ids = [target_id]
            else:
                if ev.source_id is None:
                    raise AppError("EVIDENCE_NOT_FOUND")
                src = (
                    await s.execute(
                        text("SELECT id, url, content_hash, lifecycle_status FROM research_sources WHERE id = :i"),
                        {"i": ev.source_id},
                    )
                ).one()
                if src.lifecycle_status != "ACTIVE":
                    raise AppError("EVIDENCE_ALREADY_ERASED")
                target_id, chash, uhash = uuid.UUID(str(src.id)), src.content_hash, compute_url_hash(src.url)
                evidence_ids = [
                    uuid.UUID(str(r[0]))
                    for r in (
                        await s.execute(
                            text(
                                "SELECT id FROM research_evidence WHERE source_id = :s AND lifecycle_status = 'ACTIVE'"
                            ),
                            {"s": target_id},
                        )
                    ).all()
                ]
            if state["status"] != "OK":
                raise AppError("ERASURE_LEDGER_NOT_APPLIED")
            try:
                tail_seq, _ = self.ledger.tail()
            except OSError:
                raise AppError("ERASURE_LEDGER_WRITE_FAILED") from None
            except LedgerError:
                raise AppError("ERASURE_LEDGER_NOT_APPLIED") from None
            if tail_seq != int(state["applied_seq"]):  # sổ và DB lệch nhau → không ghi thêm cho tới khi áp dụng sổ
                raise AppError("ERASURE_LEDGER_NOT_APPLIED")
            niches = await analysis.affected_niches(s, evidence_ids)
            try:
                entry = self.ledger.append(scope, target_id, content_hash=chash, url_hash=uhash, requested_by=actor_id)
            except OSError:
                log.error("erasure.ledger_write_failed", target_type=scope)
                raise AppError("ERASURE_LEDGER_WRITE_FAILED") from None
            except LedgerError as exc:
                log.error("erasure.ledger_write_failed", target_type=scope, code=exc.code)
                raise AppError("ERASURE_LEDGER_NOT_APPLIED") from None
            await apply_entry(s, entry)
            erasure_id = (
                await s.execute(
                    text(
                        "INSERT INTO evidence_erasure_requests (target_type, target_id, content_hash, reason,"
                        " requested_by, applied_at, ledger_seq) VALUES (:t, :i, :h, :r, :u, now(), :q) RETURNING id"
                    ),
                    {"t": scope, "i": target_id, "h": chash, "r": reason, "u": actor_id, "q": entry.seq},
                )
            ).scalar_one()
            await record_audit(
                s,
                action="evidence.erased",
                actor_type="USER",
                actor_id=actor_id,
                entity_type="research_source" if scope == "SOURCE" else "research_evidence",
                entity_id=target_id,
                after={  # chỉ định danh + lý do – KHÔNG nội dung/URL đã xóa (FR-013e)
                    "scope": scope,
                    "reason": reason,
                    "ledger_seq": entry.seq,
                    "evidence_count": len(evidence_ids),
                    "affected_niches": len(niches),
                },
                request_id=request_id,
            )
            await s.execute(
                text(
                    "UPDATE erasure_ledger_state SET applied_seq = :q, applied_hash = :h, checked_at = now(),"
                    " updated_at = now() WHERE id = 1"
                ),
                {"q": entry.seq, "h": entry.hash},
            )
            for niche_id in niches:  # tính lại đồng bộ: ngưỡng, Opportunity, Confidence (không AI)
                await evaluation.evaluate_and_store(s, niche_id, computed_without_ai=True)
        log.info("evidence.erased", target_type=scope, ledger_seq=entry.seq, affected_niches=len(niches))
        return ErasureResult(
            erasure_id=uuid.UUID(str(erasure_id)),
            ledger_seq=entry.seq,
            target_type=scope,
            target_id=target_id,
            evidence_ids=evidence_ids,
            affected_niche_ids=niches,
        )
