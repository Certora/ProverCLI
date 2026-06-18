# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Structured analysis of a prover job's results.

Provides JobReport and JobAnalyzer for extracting setup quality issues from a job:
unresolved calls, timeout rules, error/unknown rules, sanity failures, and alerts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .models import AlertType, CallResolutionInfo, CheckResult, JobStatus, NodeStatus, ParsedAlert

if TYPE_CHECKING:
    from .api.main import ProverOutputAPI


@dataclass
class JobReport:
    """Structured summary of a prover job's results.

    All checks and call resolutions are kept in full. Filtered views (timeout_rules,
    error_rules, unresolved_calls) are provided as properties.
    """

    job_url: str
    checks: List[CheckResult] = field(default_factory=list)
    calls: List[CallResolutionInfo] = field(default_factory=list)
    alerts_by_type: Dict[AlertType, List[ParsedAlert]] = field(default_factory=dict)
    duration: Optional[float] = None  # Total job runtime in seconds
    job_status: JobStatus = JobStatus.UNKNOWN

    @property
    def timeout_rules(self) -> List[CheckResult]:
        return [c for c in self.checks if c.status == NodeStatus.TIMEOUT]

    @property
    def error_rules(self) -> List[CheckResult]:
        return [c for c in self.checks if c.status in (NodeStatus.ERROR, NodeStatus.UNKNOWN)]

    @property
    def violated_rules(self) -> List[CheckResult]:
        return [c for c in self.checks if c.status == NodeStatus.VIOLATED]

    @property
    def verified_rules(self) -> List[CheckResult]:
        return [c for c in self.checks if c.status == NodeStatus.VERIFIED]

    @property
    def other_rules(self) -> List[CheckResult]:
        _known = {NodeStatus.TIMEOUT, NodeStatus.ERROR, NodeStatus.UNKNOWN, NodeStatus.VIOLATED, NodeStatus.VERIFIED}
        return [c for c in self.checks if c.status not in _known]

    @property
    def unresolved_calls(self) -> List[CallResolutionInfo]:
        # calls with is_warning correspond to what shows up with a red box in frontend
        # they're truly unresolved and not handled through e.g. summarization
        return [c for c in self.calls if c.is_warning]

    @property
    def resolved_calls(self) -> List[CallResolutionInfo]:
        # if a call is not marked with is_warning, it has been handled, 
        # typically with explicit summarization and we can consider it resolved 
        # even if the prover did not manage to resolve it on its own
        return [c for c in self.calls if not c.is_warning]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_url": self.job_url,
            "duration": self.duration,
            "job_status": self.job_status.value,
            "calls": {
                "unresolved": [c.to_dict() for c in self.unresolved_calls],
                "resolved": [c.to_dict() for c in self.resolved_calls],
            },
            "rules": {
                "timeout": [c.to_dict() for c in self.timeout_rules],
                "error": [c.to_dict() for c in self.error_rules],
                "violated": [c.to_dict() for c in self.violated_rules],
                "verified": [c.to_dict() for c in self.verified_rules],
                "other": [c.to_dict() for c in self.other_rules],
            },
            "alerts_by_type": {
                alert_type.value: [a.to_dict() for a in alerts]
                for alert_type, alerts in self.alerts_by_type.items()
            },
        }


class JobAnalyzer:
    """Analyzes a prover job and returns a structured JobReport."""

    def __init__(self, api: ProverOutputAPI) -> None:
        self._api = api

    def analyze(self, job_input: str) -> JobReport:
        """Fetch job data and populate a JobReport with all results."""
        report = JobReport(job_url=job_input)

        job_info = self._api.get_job_info(job_input)
        report.duration = job_info.runtime
        report.job_status = job_info.status
        report.calls = self._api.get_call_resolutions(job_input)

        for alert in self._api.get_alerts(job_input):
            report.alerts_by_type.setdefault(alert.alert_type, []).append(alert)

        report.checks = self._api.get_all_checks(job_input, include_rule_not_vacuous=True)

        return report
