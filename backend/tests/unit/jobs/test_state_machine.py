"""T092 – JobStateMachine (FR-030; data-model.md §7)."""

from __future__ import annotations

import itertools

import pytest

from nichepilot.core.errors import AppError
from nichepilot.jobs.state_machine import ALLOWED, TERMINAL, can_transition, check_transition

STATUSES = ["QUEUED", "RUNNING", "PAUSED", "PAUSED_BUDGET", "RETRY_SCHEDULED", "SUCCEEDED", "FAILED", "CANCELLED"]

EXPECTED = {
    ("QUEUED", "RUNNING"),
    ("QUEUED", "CANCELLED"),
    ("RUNNING", "SUCCEEDED"),
    ("RUNNING", "FAILED"),
    ("RUNNING", "RETRY_SCHEDULED"),
    ("RUNNING", "PAUSED"),
    ("RUNNING", "PAUSED_BUDGET"),
    ("RUNNING", "CANCELLED"),
    ("RETRY_SCHEDULED", "RUNNING"),
    ("RETRY_SCHEDULED", "CANCELLED"),
    ("PAUSED", "QUEUED"),
    ("PAUSED", "CANCELLED"),
    ("PAUSED_BUDGET", "QUEUED"),
    ("PAUSED_BUDGET", "CANCELLED"),
    ("FAILED", "QUEUED"),
}


def test_TC_FR030_01_allowed_transitions_match_data_model() -> None:
    assert {(a, b) for a, targets in ALLOWED.items() for b in targets} == EXPECTED


@pytest.mark.parametrize(("src", "dst"), list(itertools.product(STATUSES, STATUSES)))
def test_TC_FR030_02_every_pair_checked(src: str, dst: str) -> None:
    if (src, dst) in EXPECTED:
        assert can_transition(src, dst)
        check_transition(src, dst)
    else:
        assert not can_transition(src, dst)
        with pytest.raises(AppError) as exc:
            check_transition(src, dst)
        assert exc.value.code == "INVALID_JOB_TRANSITION"
        assert exc.value.params == {"from": src, "to": dst}


def test_TC_FR030_03_terminal_states() -> None:
    assert TERMINAL == {"SUCCEEDED", "CANCELLED"}
    for t in TERMINAL:
        assert ALLOWED.get(t, set()) == set()
