# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
A job's verdicts, rule by rule, with a counterexample for every violation.

The verdicts are the job's leaf checks: one per method of a parametric rule or invariant, and one
per assertion. A rule's top-level node only summarizes them. It can read ERROR while one of its
methods is VIOLATED, or VIOLATED while other methods are SANITY_FAILED, and it carries no
counterexample file, so the leaves are what to read.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .counterexample import TRACE_SHAPES, render_counterexample
from .job_report import JobReport
from .models import CheckResult


@dataclass
class RuleVerdicts:
    """One rule's leaf statuses counted, and the leaves that are not VERIFIED."""

    counts: Dict[str, int] = field(default_factory=dict)
    not_verified: List[CheckResult] = field(default_factory=list)


@dataclass
class RenderedCounterexample:
    rule: str
    method: Optional[str]
    output_file: str
    counterexample: str


@dataclass
class JobVerdicts:
    """A job's verdicts per rule, its rendered counterexamples, and its full report."""

    job_id: str
    report: JobReport
    rules: Dict[str, RuleVerdicts] = field(default_factory=dict)
    counterexamples: List[RenderedCounterexample] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_status": self.report.job_status.value,
            "rules": {
                name: {
                    "counts": r.counts,
                    "not_verified": [
                        {"method": c.method_name, "status": c.status.value, "assert": c.assert_message}
                        for c in r.not_verified
                    ],
                }
                for name, r in self.rules.items()
            },
            "counterexamples": [vars(c) for c in self.counterexamples],
            "report": self.report.to_dict(),
        }


def job_verdicts(api: Any, job_input: str, chain: str) -> JobVerdicts:
    """Read the job's leaf checks and render the counterexample of every violated one."""
    shape = TRACE_SHAPES[chain]
    leaves: List[CheckResult] = api.get_leaf_checks(job_input)
    result = JobVerdicts(job_id=job_input, report=api.get_job_report(job_input))

    counts: Dict[str, Counter] = {}
    for leaf in leaves:
        counts.setdefault(leaf.rule_name, Counter())[leaf.status.value] += 1
        rule = result.rules.setdefault(leaf.rule_name, RuleVerdicts())
        if not leaf.is_verified:
            rule.not_verified.append(leaf)
    for name, c in counts.items():
        result.rules[name].counts = dict(c.most_common())

    seen = set()
    for leaf in leaves:
        if not leaf.is_violated:
            continue
        for name in leaf.output_files or []:
            if name in seen:
                continue
            seen.add(name)
            dump = api.get_calltrace(job_input, name).trace_data
            rendered = render_counterexample(dump, shape) if isinstance(dump, dict) else None
            if rendered:
                result.counterexamples.append(
                    RenderedCounterexample(leaf.rule_name, leaf.method_name, name, rendered)
                )
    return result


def format_verdicts_text(verdicts: JobVerdicts) -> str:
    """One line per rule with its leaf statuses counted, a line per leaf that is not VERIFIED, then
    each counterexample."""
    lines = [f"job {verdicts.report.job_status.value}"]
    for name, rule in verdicts.rules.items():
        lines.append(name + "\t" + ", ".join(f"{s} {n}" for s, n in rule.counts.items()))
        for leaf in rule.not_verified:
            where = leaf.method_name or leaf.assert_message or ""
            if where and where != name:
                lines.append(f"\t{where}\t{leaf.status.value}")
    for cex in verdicts.counterexamples:
        lines.append("")
        lines.append(f"== {cex.rule} {cex.method or ''}".rstrip())
        lines.append(cex.counterexample)
    return "\n".join(lines)
