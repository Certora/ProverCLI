# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

from dataclasses import dataclass, field
from typing import List

import pytest

from prover_output_utility import wait
from prover_output_utility.models import JobStatus


@dataclass
class FakeClock:
    now: float = 0.0
    sleeps: List[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeApi:
    """Answers RUNNING until ``final_after`` seconds of the fake clock have passed."""

    def __init__(self, clock: FakeClock, final_after: float = float("inf")):
        self.clock = clock
        self.final_after = final_after
        self.checks: List[float] = []

    def get_job_status(self, job: str) -> JobStatus:
        self.checks.append(self.clock.now)
        return JobStatus.SUCCEEDED if self.clock.now >= self.final_after else JobStatus.RUNNING


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    clock = FakeClock()
    monkeypatch.setattr(wait.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(wait.time, "sleep", clock.sleep)
    return clock


def test_timeout_shorter_than_interval_still_waits(clock: FakeClock) -> None:
    api = FakeApi(clock)
    result = wait.wait_for_jobs(api, ["1"], timeout=10, interval=30)
    assert clock.sleeps == [10]
    assert api.checks == [0, 10]
    assert not result.ended


def test_last_check_is_at_the_deadline(clock: FakeClock) -> None:
    api = FakeApi(clock)
    result = wait.wait_for_jobs(api, ["1"], timeout=70, interval=30)
    assert clock.sleeps == [30, 30, 10]
    assert api.checks == [0, 30, 60, 70]
    assert not result.ended


def test_returns_once_every_job_has_stopped(clock: FakeClock) -> None:
    api = FakeApi(clock, final_after=45)
    result = wait.wait_for_jobs(api, ["1", "2"], timeout=600, interval=30)
    assert clock.sleeps == [30, 30]
    assert result.ended
    assert [r.status for r in result.jobs] == [JobStatus.SUCCEEDED.value] * 2
