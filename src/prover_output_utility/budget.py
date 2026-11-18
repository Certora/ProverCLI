# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
How many prover jobs and prover minutes a group of cloud jobs has used, against a budget.

The jobs are the ones the data API lists for the group (``certoraRun --group_id``), read in one
request. A finished job counts its runtime on the server, rounded up to whole minutes. A job not
yet finished counts ``reserve`` minutes or its time so far, whichever is larger: never less than it
has used, but less than it will use if it runs past ``reserve``. The use is also broken down by
the first word of each job's ``msg``. A job submitted moments ago may not be listed yet.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Usage:
    jobs: int = 0
    minutes: int = 0
    running: int = 0


@dataclass
class BudgetUsage:
    """Budget, use, what is left, use per ``msg`` prefix, and whether ``more_jobs`` more fit."""

    group_id: str
    max_jobs: int
    max_minutes: int
    reserve_minutes: int
    used: Usage
    more_jobs: int = 0
    by_msg: Dict[str, Usage] = field(default_factory=dict)

    @property
    def left_jobs(self) -> int:
        return self.max_jobs - self.used.jobs

    @property
    def left_minutes(self) -> int:
        return self.max_minutes - self.used.minutes

    @property
    def fits(self) -> bool:
        return self.more_jobs <= self.left_jobs and self.more_jobs * self.reserve_minutes <= self.left_minutes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "budget": {"jobs": self.max_jobs, "minutes": self.max_minutes},
            "reserve_minutes": self.reserve_minutes,
            "used": vars(self.used),
            "left": {"jobs": self.left_jobs, "minutes": self.left_minutes},
            "more_jobs": self.more_jobs,
            "fits": self.fits,
            "by_msg": {prefix: vars(u) for prefix, u in self.by_msg.items()},
        }


def _time(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def job_minutes(job: Dict[str, Any], reserve: int, now: datetime) -> tuple[int, bool]:
    """A listed job's minutes, and whether it has finished."""
    start, finish = _time(job.get("start_time")), _time(job.get("finish_time"))
    if finish:
        return (math.ceil((finish - start).total_seconds() / 60) if start else 0), True
    elapsed = math.ceil((now - start).total_seconds() / 60) if start else 0
    return max(elapsed, reserve), False


def budget_usage(
    api: Any,
    group_id: str,
    max_jobs: int,
    max_minutes: int,
    reserve: int = 30,
    more_jobs: int = 0,
    days_back: int = 365,
) -> BudgetUsage:
    now = datetime.now(timezone.utc)
    jobs: List[Dict[str, Any]] = api.data_fetcher.fetch_group_jobs(
        group_id, (now - timedelta(days=days_back)).isoformat(), now.isoformat()
    )
    usage = BudgetUsage(group_id, max_jobs, max_minutes, reserve, Usage(), more_jobs)
    for job in jobs:
        minutes, final = job_minutes(job, reserve, now)
        prefix = (job.get("msg") or "").split(" ", 1)[0] or "(no msg)"
        for u in (usage.used, usage.by_msg.setdefault(prefix, Usage())):
            u.jobs += 1
            u.minutes += minutes
            u.running += not final
    usage.by_msg = dict(sorted(usage.by_msg.items(), key=lambda kv: -kv[1].minutes))
    return usage


def format_budget_text(u: BudgetUsage) -> str:
    lines = [
        f"group   {u.group_id}",
        f"budget  {u.max_jobs} jobs, {u.max_minutes} min",
        f"used    {u.used.jobs} jobs, {u.used.minutes} min "
        f"({u.used.running} running, counted at {u.reserve_minutes} min or their time so far)",
        f"left    {u.left_jobs} jobs, {u.left_minutes} min",
    ]
    if u.more_jobs:
        verdict = "fit" if u.fits else "do NOT fit"
        lines.append(f"{u.more_jobs} more jobs (up to {u.more_jobs * u.reserve_minutes} min) {verdict}")
    for prefix, p in u.by_msg.items():
        lines.append(f"  {prefix:44} {p.jobs:4} jobs {p.minutes:6} min {p.running:3} running")
    return "\n".join(lines)
