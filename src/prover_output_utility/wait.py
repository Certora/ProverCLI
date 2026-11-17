# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Wait, for a bounded time, until a set of prover jobs has stopped.

Each target is a job id, a job link, or the log of a ``certoraRun`` call: a path ending in ``.log``
or a glob of such paths (expanded here, so it can be passed quoted; it may match nothing yet). A
log is read for the last job link it printed. A log with no link yet means the job is still being
submitted while the submitting process (``pid_file``) is alive, and was never submitted once it
has exited. While that process is alive the wait does not end, since the parts it has not reached
have no log yet.
"""

from __future__ import annotations

import glob
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .api.url_utils import find_job_ids

SUBMITTING = "SUBMITTING"
NOT_SUBMITTED = "NOT_SUBMITTED"
CHECK_FAILED = "CHECK_FAILED"


@dataclass
class WaitRow:
    """One target: its name, its job id (None before the job exists) and its status."""

    target: str
    job_id: Optional[str]
    status: str
    final: bool


@dataclass
class WaitResult:
    ended: bool
    jobs: List[WaitRow] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"ended": self.ended, "jobs": [asdict(r) for r in self.jobs]}


def _alive(pid_file: Optional[str]) -> bool:
    if not pid_file:
        return False
    try:
        os.kill(int(Path(pid_file).read_text().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def _is_glob(target: str) -> bool:
    return any(ch in target for ch in "*?[")


def _log_row(path: Path, submitting: bool) -> WaitRow:
    ids = find_job_ids(path.read_text(errors="replace")) if path.is_file() else []
    if not ids:
        status = SUBMITTING if submitting else NOT_SUBMITTED
        return WaitRow(path.stem, None, status, final=not submitting)
    return WaitRow(path.stem, ids[-1], "", final=False)


def check_targets(api: Any, targets: List[str], pid_file: Optional[str] = None) -> List[WaitRow]:
    """One row per job: a job id or link is one, a log is one, a glob is one per matching log."""
    submitting = _alive(pid_file)
    rows: List[WaitRow] = []
    for target in targets:
        if _is_glob(target):
            matches = sorted(glob.glob(target))
            if not matches:
                rows.append(_log_row(Path(target), submitting))
            rows.extend(_log_row(Path(m), submitting) for m in matches)
        elif target.endswith(".log"):
            rows.append(_log_row(Path(target), submitting))
        else:
            rows.append(WaitRow(target, target, "", final=False))
    for row in rows:
        if row.job_id is None:
            continue
        try:
            status = api.get_job_status(row.job_id)
            row.status, row.final = status.value, status.is_final
        except Exception:
            row.status, row.final = CHECK_FAILED, False
    return rows


def wait_for_targets(
    api: Any,
    targets: List[str],
    timeout: float,
    interval: float = 30,
    pid_file: Optional[str] = None,
) -> WaitResult:
    """Check the targets every ``interval`` seconds until every one has stopped or ``timeout``
    seconds have passed. ``ended`` says which."""
    deadline = time.monotonic() + timeout
    while True:
        rows = check_targets(api, targets, pid_file)
        ended = all(r.final for r in rows) and not _alive(pid_file)
        if ended or time.monotonic() + interval > deadline:
            return WaitResult(ended=ended, jobs=rows)
        time.sleep(interval)


def format_wait_text(result: WaitResult) -> str:
    lines = [f"{r.target} {r.job_id or '-'} {r.status}" for r in result.jobs]
    lines.append("ENDED" if result.ended else "RUNNING")
    return "\n".join(lines)
