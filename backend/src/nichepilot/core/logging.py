"""Structured logging (T025 – FR-050, FR-057).

- JSON qua structlog cho cả log của ứng dụng và log thư viện (stdlib), cùng một chuỗi processor.
- Redaction: che giá trị secret đã nạp, mẫu khóa API phổ biến và các khóa nhạy cảm (password, token…).
- Ghi song song stdout (bản sao để xem nhanh) và file JSON Lines theo ngày `app-YYYY-MM-DD.jsonl`
  trong `LOG_DIR` – bản lưu chính, chỉ bị xóa khi quá hạn lưu (≥ 90 ngày, xem jobs.maintenance).
"""

from __future__ import annotations

import logging
import re
import sys
import threading
from collections.abc import Iterable, MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

import structlog

MASK = "***"
SENSITIVE_KEY_PATTERN = re.compile(
    r"(pass(word)?|secret|token|api[_-]?key|authorization|cookie|credential)", re.IGNORECASE
)
SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-(proj-)?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(postgres(ql)?(\+\w+)?://[^:/\s]+:)[^@\s]+(@)"),
]

_known_secrets: list[str] = []


def redact(value: str, known_secrets: Iterable[str]) -> str:
    """Che secret trong một chuỗi."""
    for secret in sorted(known_secrets, key=len, reverse=True):
        if secret:
            value = value.replace(secret, MASK)
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 4:
            value = pattern.sub(lambda m: f"{m.group(1)}{MASK}{m.group(4)}", value)
        else:
            value = pattern.sub(MASK, value)
    return value


def _redact_obj(obj: Any, secrets: list[str]) -> Any:
    if isinstance(obj, str):
        return redact(obj, secrets)
    if isinstance(obj, dict):
        return {
            k: (MASK if isinstance(k, str) and SENSITIVE_KEY_PATTERN.search(k) else _redact_obj(v, secrets))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_redact_obj(v, secrets) for v in obj]
    return obj


def redact_payload(obj: Any) -> Any:
    """Che secret và khóa nhạy cảm trong dữ liệu lưu trữ (audit before/after, tool input/output)."""
    return _redact_obj(obj, _known_secrets)


def redaction_processor(_logger: Any, _name: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    redacted = _redact_obj(dict(event_dict), _known_secrets)
    event_dict.clear()
    event_dict.update(redacted)
    return event_dict


class DailyFileHandler(logging.Handler):
    """Ghi mỗi bản ghi vào file theo ngày UTC; không tự xóa file (retention do tác vụ bảo trì xử lý)."""

    def __init__(self, directory: Path) -> None:
        super().__init__()
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._date: str | None = None
        self._stream: TextIO | None = None

    def _stream_for_today(self) -> TextIO:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if today != self._date or self._stream is None:
            if self._stream is not None:
                self._stream.close()
            self._stream = (self.directory / f"app-{today}.jsonl").open("a", encoding="utf-8")
            self._date = today
        return self._stream

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            with self._lock:
                stream = self._stream_for_today()
                stream.write(line + "\n")
                stream.flush()
        except Exception:  # pragma: no cover – không để lỗi ghi log làm sập ứng dụng
            self.handleError(record)

    def close(self) -> None:
        with self._lock:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        super().close()


def _shared_processors() -> list[Any]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.ExtraAdder(),
    ]


def configure_logging(
    *,
    level: str = "INFO",
    fmt: str = "json",
    log_dir: Path | None = None,
    secret_values: Iterable[str] = (),
) -> None:
    """Cấu hình logging toàn cục; gọi được nhiều lần (mỗi lần thay toàn bộ handler)."""
    _known_secrets[:] = [s for s in secret_values if s]

    renderer: Any = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_shared_processors(),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            redaction_processor,
            renderer,
        ],
    )
    file_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_shared_processors(),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            redaction_processor,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)
    if log_dir is not None:
        file_handler = DailyFileHandler(Path(log_dir))
        file_handler.setFormatter(file_formatter)
        root.addHandler(file_handler)
    root.setLevel(level)
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    structlog.configure(
        processors=[*_shared_processors(), structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def bind_context(**values: Any) -> None:
    structlog.contextvars.bind_contextvars(**values)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)
