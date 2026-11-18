"""JobStateMachine (T098 – FR-030; data-model.md §7). Mọi chuyển trạng thái job phải hợp lệ theo bảng dưới."""

from __future__ import annotations

from nichepilot.core.errors import AppError

ALLOWED: dict[str, set[str]] = {
    "QUEUED": {"RUNNING", "CANCELLED"},
    "RUNNING": {"SUCCEEDED", "FAILED", "RETRY_SCHEDULED", "PAUSED", "PAUSED_BUDGET", "CANCELLED"},
    "RETRY_SCHEDULED": {"RUNNING", "CANCELLED"},
    "PAUSED": {"QUEUED", "CANCELLED"},
    "PAUSED_BUDGET": {"QUEUED", "CANCELLED"},
    "FAILED": {"QUEUED"},  # chỉ qua retry thủ công
    "SUCCEEDED": set(),
    "CANCELLED": set(),
}
TERMINAL = {status for status, targets in ALLOWED.items() if not targets}


def can_transition(src: str, dst: str) -> bool:
    return dst in ALLOWED.get(src, set())


def check_transition(src: str, dst: str) -> None:
    if not can_transition(src, dst):
        raise AppError("INVALID_JOB_TRANSITION", params={"from": src, "to": dst})
