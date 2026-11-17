# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
How many prover jobs and prover minutes a directory of certoraRun logs has used, against a budget.

The jobs are the job links in ``<logs>/*.log``. Each job is counted once, in the group of the first
log that names it. A log's group is its name with a trailing ``_run<N>`` (or ``_r<M>run<N>``) and
then a trailing ``-p<K>`` removed, so ``spec-p2_run3.log`` and ``spec_run1.log`` are both group
``spec``; a log named any other way is a group of its own.

A finished job counts its runtime on the server, rounded up to whole minutes. A job not yet
finished counts ``reserve`` minutes or its time so far, whichever is larger: never less than it has
used, but less than it will use if it runs past ``reserve``. Finished jobs are cached in
``<logs>/.budget_cache.json``.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .api.url_utils import find_job_ids

CACHE_NAME = ".budget_cache.json"


@dataclass
class Usage:
    jobs: int = 0
    minutes: int = 0
    running: int = 0


@dataclass
class BudgetUsage:
    """Budget, use, what is left, use per log group, and whether ``more_jobs`` more fit."""

    max_jobs: int
    max_minutes: int
    reserve_minutes: int
    used: Usage
    more_jobs: int = 0
    groups: Dict[str, Usage] = field(default_factory=dict)

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
            "budget": {"jobs": self.max_jobs, "minutes": self.max_minutes},
            "reserve_minutes": self.reserve_minutes,
            "used": vars(self.used),
            "left": {"jobs": self.left_jobs, "minutes": self.left_minutes},
            "more_jobs": self.more_jobs,
            "fits": self.fits,
            "groups": {name: vars(u) for name, u in self.groups.items()},
        }


def group_of(log: Path) -> str:
    """``spec-p2_run3.log``, ``spec_r2run3.log`` and ``spec_run1.log`` belong to group ``spec``."""
    name = re.sub(r"_(?:r\d+)?run\d+$", "", log.stem)
    return re.sub(r"-p\d+$", "", name)


def jobs_in_logs(logs: Path) -> Dict[str, str]:
    """job id -> group of the first log that names it."""
    jobs: Dict[str, str] = {}
    for log in sorted(logs.glob("*.log")):
        for job_id in find_job_ids(log.read_text(errors="replace")):
            jobs.setdefault(job_id, group_of(log))
    return jobs


def _read_cache(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _write_cache(path: Path, cache: Dict[str, Any]) -> None:
    """Replace the cache file in one step, so a concurrent reader never sees half of it."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(cache, f, indent=1)
    os.replace(tmp, path)


def job_minutes(api: Any, job_ids: List[str], logs: Path, reserve: int) -> Dict[str, Dict[str, Any]]:
    """job id -> {minutes, final}."""
    cache_file = logs / CACHE_NAME
    cache = _read_cache(cache_file)
    now = datetime.now(timezone.utc)
    out: Dict[str, Dict[str, Any]] = {}
    for job_id in job_ids:
        if job_id in cache:
            out[job_id] = cache[job_id]
            continue
        try:
            info = api.get_job_info(job_id)
        except Exception:
            # A failed lookup must not make the run look cheaper than it is.
            out[job_id] = {"minutes": reserve, "final": False}
            continue
        if info.is_completed:
            runtime = info.runtime
            out[job_id] = cache[job_id] = {
                "minutes": math.ceil(runtime / 60) if runtime is not None else 0,
                "final": True,
            }
        else:
            start = info.start_time
            elapsed = (
                math.ceil((now - datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds() / 60)
                if start
                else 0
            )
            out[job_id] = {"minutes": max(elapsed, reserve), "final": False}
    _write_cache(cache_file, cache)
    return out


def budget_usage(
    api: Any,
    logs: Path,
    max_jobs: int,
    max_minutes: int,
    reserve: int = 30,
    more_jobs: int = 0,
) -> BudgetUsage:
    jobs = jobs_in_logs(logs)
    minutes = job_minutes(api, list(jobs), logs, reserve)
    usage = BudgetUsage(max_jobs, max_minutes, reserve, Usage(), more_jobs)
    for job_id, group in jobs.items():
        m = minutes[job_id]
        for u in (usage.used, usage.groups.setdefault(group, Usage())):
            u.jobs += 1
            u.minutes += m["minutes"]
            u.running += not m["final"]
    usage.groups = dict(sorted(usage.groups.items(), key=lambda kv: -kv[1].minutes))
    return usage


def format_budget_text(u: BudgetUsage) -> str:
    lines = [
        f"budget  {u.max_jobs} jobs, {u.max_minutes} min",
        f"used    {u.used.jobs} jobs, {u.used.minutes} min "
        f"({u.used.running} running, counted at {u.reserve_minutes} min or their time so far)",
        f"left    {u.left_jobs} jobs, {u.left_minutes} min",
    ]
    if u.more_jobs:
        verdict = "fit" if u.fits else "do NOT fit"
        lines.append(f"{u.more_jobs} more jobs (up to {u.more_jobs * u.reserve_minutes} min) {verdict}")
    for group, p in u.groups.items():
        lines.append(f"  {group:44} {p.jobs:4} jobs {p.minutes:6} min {p.running:3} running")
    return "\n".join(lines)
