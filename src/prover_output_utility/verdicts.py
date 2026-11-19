# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
A job's verdicts, rule by rule, with a counterexample for every violation.

The verdicts are the job's leaf checks: one per method of a parametric rule or invariant, and one
per assertion. A rule's top-level node only summarizes them. It can read ERROR while one of its
methods is VIOLATED, or VIOLATED while other methods are SANITY_FAILED, and it carries no
counterexample file, so the leaves are what to read.

A failed vacuity check (``rule_not_vacuous``, status SANITY_FAILED) is a verdict too. For a method
of a parametric rule the prover also marks the method SANITY_FAILED, but for a rule split into
sub-checks (a ``satisfy``, auto-generated assertions) the vacuity check is the only place it shows,
so it is added as a leaf of its own wherever its rule or method is not already SANITY_FAILED.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .counterexample import TRACE_SHAPES, render_counterexample
from .job_report import JobReport
from .models import CheckResult, NodeStatus, NodeType

VACUITY_CHECK = "rule_not_vacuous"


def _failed_vacuity_checks(api: Any, job_input: str, leaves: List[CheckResult]) -> List[CheckResult]:
    """The failed vacuity checks no leaf already reports as SANITY_FAILED."""
    reported = {(c.rule_name, c.method_name) for c in leaves if c.status == NodeStatus.SANITY_FAILED}
    return [
        c
        for c in api.get_all_checks(job_input, include_rule_not_vacuous=True)
        if c.node_type == NodeType.SANITY
        and c.assert_message == VACUITY_CHECK
        and c.status == NodeStatus.SANITY_FAILED
        and (c.rule_name, c.method_name) not in reported
    ]


@dataclass
class RuleVerdicts:
    """One rule's leaf statuses counted, and the leaves worth naming: none when every leaf is
    VERIFIED; otherwise every leaf that is not, plus the VERIFIED ones that are not methods (a
    rule's sub-checks, which the counts alone would leave unnamed)."""

    counts: Dict[str, int] = field(default_factory=dict)
    leaves: List[CheckResult] = field(default_factory=list)


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
                    "leaves": [
                        {"method": c.method_name, "status": c.status.value, "assert": c.assert_message}
                        for c in r.leaves
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
    leaves += _failed_vacuity_checks(api, job_input, leaves)
    result = JobVerdicts(job_id=job_input, report=api.get_job_report(job_input))

    by_rule: Dict[str, List[CheckResult]] = {}
    for leaf in leaves:
        by_rule.setdefault(leaf.rule_name, []).append(leaf)
    for name, rule_leaves in by_rule.items():
        failed = any(not c.is_verified for c in rule_leaves)
        result.rules[name] = RuleVerdicts(
            counts=dict(Counter(c.status.value for c in rule_leaves).most_common()),
            leaves=[c for c in rule_leaves if not c.is_verified or (failed and not c.method_name)],
        )

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
    """One line per rule with its leaf statuses counted, a line per listed leaf, then each
    counterexample."""
    lines = [f"job {verdicts.report.job_status.value}"]
    for name, rule in verdicts.rules.items():
        lines.append(name + "\t" + ", ".join(f"{s} {n}" for s, n in rule.counts.items()))
        for leaf in rule.leaves:
            where = leaf.method_name or leaf.assert_message or ""
            if where and where != name:
                lines.append(f"\t{where}\t{leaf.status.value}")
    for cex in verdicts.counterexamples:
        lines.append("")
        lines.append(f"== {cex.rule} {cex.method or ''}".rstrip())
        lines.append(cex.counterexample)
    return "\n".join(lines)
