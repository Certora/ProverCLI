# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Wait, for a bounded time, until a set of prover jobs has stopped.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

#: The status of a job whose status request failed. It does not end the wait.
CHECK_FAILED = "CHECK_FAILED"


@dataclass
class WaitRow:
    """One job, as given (id or link), with its status."""

    target: str
    status: str
    final: bool


@dataclass
class WaitResult:
    ended: bool
    jobs: List[WaitRow] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"ended": self.ended, "jobs": [asdict(r) for r in self.jobs]}


def check_jobs(api: Any, jobs: List[str]) -> List[WaitRow]:
    """One row per job id or job link."""
    rows = []
    for job in jobs:
        try:
            status = api.get_job_status(job)
            rows.append(WaitRow(job, status.value, status.is_final))
        except Exception:
            rows.append(WaitRow(job, CHECK_FAILED, False))
    return rows


def wait_for_jobs(api: Any, jobs: List[str], timeout: float, interval: float = 30) -> WaitResult:
    """Check the jobs every ``interval`` seconds until every one has stopped or ``timeout`` seconds
    have passed. ``ended`` says which."""
    deadline = time.monotonic() + timeout
    while True:
        rows = check_jobs(api, jobs)
        ended = all(r.final for r in rows)
        if ended or time.monotonic() + interval > deadline:
            return WaitResult(ended=ended, jobs=rows)
        time.sleep(interval)


def format_wait_text(result: WaitResult) -> str:
    lines = [f"{r.target} {r.status}" for r in result.jobs]
    lines.append("ENDED" if result.ended else "RUNNING")
    return "\n".join(lines)
