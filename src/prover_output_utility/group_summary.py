#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Utility to summarize all runs in a Certora Prover group.

Takes a group ID and outputs a breakdown of:
- Verified vs violated vs failed runs
- Rule names for each category
- Failure details for non-successful runs

Usage:
  prover-group-summary b78ea54a-a924-4f05-b1a7-58b29c1585ae
  prover-group-summary "https://prover.certora.com/?groupIds=b78ea54a-a924-4f05-b1a7-58b29c1585ae"
  prover-group-summary b78ea54a-a924-4f05-b1a7-58b29c1585ae --format json
  prover-group-summary b78ea54a-a924-4f05-b1a7-58b29c1585ae -o summary.json
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .api import ProverOutputAPI
from .api.data_fetcher import _default_prover_base_url, default_api_base_url
from .exceptions import AuthenticationError, ProverAPIError
from .models import JobStatus, NodeStatus, convert_job_status

DATA_API_BASE = default_api_base_url()
PROVER_BASE = _default_prover_base_url()


@dataclass
class RunResult:
    """Result of a single run in the group."""

    job_id: str
    output_url: str
    rule_name: Optional[str] = None
    status: NodeStatus = NodeStatus.UNKNOWN
    failure_reason: Optional[str] = None
    assert_message: Optional[str] = None
    job_status: Optional[JobStatus] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "job_id": self.job_id,
            "output_url": self.output_url,
            "status": self.status.value,
        }
        if self.rule_name:
            d["rule_name"] = self.rule_name
        if self.failure_reason:
            d["failure_reason"] = self.failure_reason
        if self.assert_message:
            d["assert_message"] = self.assert_message
        if self.job_status:
            d["job_status"] = self.job_status.value
        return d


@dataclass
class GroupSummary:
    """Summary of all runs in a group."""

    group_id: str
    total: int = 0
    verified: List[RunResult] = field(default_factory=list)
    violated: List[RunResult] = field(default_factory=list)
    failed: List[RunResult] = field(default_factory=list)
    timeout: List[RunResult] = field(default_factory=list)
    running: List[RunResult] = field(default_factory=list)
    unknown: List[RunResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "total": self.total,
            "counts": {
                "verified": len(self.verified),
                "violated": len(self.violated),
                "failed": len(self.failed),
                "timeout": len(self.timeout),
                "running": len(self.running),
                "unknown": len(self.unknown),
            },
            "verified": [r.to_dict() for r in self.verified],
            "violated": [r.to_dict() for r in self.violated],
            "failed": [r.to_dict() for r in self.failed],
            "timeout": [r.to_dict() for r in self.timeout],
            "running": [r.to_dict() for r in self.running],
            "unknown": [r.to_dict() for r in self.unknown],
        }


def extract_group_id(input_str: str) -> str:
    """Extract group ID from a URL or return as-is if already an ID."""
    # Check if it's a URL
    if input_str.startswith("http"):
        parsed = urlparse(input_str)
        params = parse_qs(parsed.query)
        group_ids = params.get("groupIds", [])
        if group_ids:
            return group_ids[0]
        raise ValueError(
            f"Could not extract groupIds from URL: {input_str}"
        )

    # Validate UUID-like format
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    if uuid_pattern.match(input_str):
        return input_str

    raise ValueError(
        f"Invalid group ID format: {input_str}. "
        "Expected a UUID or a prover.certora.com URL with groupIds parameter."
    )


def fetch_group_jobs(
    api: ProverOutputAPI,
    group_id: str,
    created_after: str,
    created_before: str,
) -> List[Dict[str, Any]]:
    """Fetch all jobs in a group from the data API.

    The data API requires createdAfter/createdBefore params for the groupIds filter to work.
    """
    return api.data_fetcher.fetch_group_jobs(group_id, created_after, created_before)


def classify_run(api: ProverOutputAPI, job: Dict[str, Any]) -> RunResult:
    """Classify a single job run by checking its leaf results."""
    job_id = job["id"]
    output_url = job.get("output_url", "")
    job_status = convert_job_status(job.get("job_status", "UNKNOWN"))

    result = RunResult(
        job_id=job_id,
        output_url=output_url,
        job_status=job_status,
    )

    # If the job itself failed, classify as FAILED and try to get details
    if job_status == JobStatus.FAILED:
        result.status = NodeStatus.ERROR
        try:
            logs = api.get_console_logs(job_id)
            lines = [l.strip() for l in logs.strip().split("\n") if l.strip()]
            # Look for error indicators in reverse order (last messages most relevant)
            for line in reversed(lines):
                if any(kw in line.lower() for kw in ["error", "exception", "failed", "fatal"]):
                    result.failure_reason = line
                    break
            if not result.failure_reason:
                # Use last non-empty meaningful line
                meaningful = [
                    l for l in lines
                    if not l.startswith("[") and not l.startswith("Start ") and "WARN" not in l
                ]
                if meaningful:
                    result.failure_reason = meaningful[-1]
        except Exception:
            result.failure_reason = "Could not retrieve failure details"
        return result

    # Job succeeded at infrastructure level - check rule-level results
    try:
        leaves = api.get_leaf_checks(job_id)
        if not leaves:
            result.status = NodeStatus.UNKNOWN
            result.failure_reason = "No leaf checks found in tree view"
            return result

        leaf = leaves[0]
        result.rule_name = leaf.rule_name
        result.status = leaf.status

        if result.status == NodeStatus.VIOLATED:
            result.assert_message = leaf.assert_message
        elif result.status == NodeStatus.TIMEOUT:
            result.failure_reason = f"Rule timed out: {leaf.rule_name}"
        elif result.status == NodeStatus.ERROR:
            result.failure_reason = f"Rule error: {leaf.assert_message or leaf.rule_name}"

    except Exception as e:
        result.status = NodeStatus.ERROR
        result.failure_reason = f"Failed to retrieve rule results: {e}"

    return result


def build_group_summary(api: ProverOutputAPI, group_id: str, days_back: int = 365) -> GroupSummary:
    """Build a full summary for a group."""
    now = datetime.now(timezone.utc)
    created_before = now.isoformat()
    created_after = (now - timedelta(days=days_back)).isoformat()
    jobs = fetch_group_jobs(api, group_id, created_after, created_before)
    summary = GroupSummary(group_id=group_id, total=len(jobs))

    for job in sorted(jobs, key=lambda j: j.get("created_at", "")):
        result = classify_run(api, job)

        if result.status == NodeStatus.VERIFIED:
            summary.verified.append(result)
        elif result.status == NodeStatus.VIOLATED:
            summary.violated.append(result)
        elif result.status == NodeStatus.ERROR:
            summary.failed.append(result)
        elif result.status == NodeStatus.TIMEOUT:
            summary.timeout.append(result)
        elif result.status == NodeStatus.RUNNING:
            summary.running.append(result)
        else:
            summary.unknown.append(result)

    return summary


def format_text(summary: GroupSummary) -> str:
    """Format summary as human-readable text."""
    lines: List[str] = []

    lines.append(f"Group: {summary.group_id}")
    lines.append(f"URL:   {PROVER_BASE}/?groupIds={summary.group_id}")
    lines.append(f"Total: {summary.total} runs")
    lines.append("")
    lines.append(
        f"  Verified: {len(summary.verified)}"
        f"  |  Violated: {len(summary.violated)}"
        f"  |  Failed: {len(summary.failed)}"
    )
    extra_parts = []
    if summary.timeout:
        extra_parts.append(f"Timeout: {len(summary.timeout)}")
    if summary.running:
        extra_parts.append(f"Running: {len(summary.running)}")
    if summary.unknown:
        extra_parts.append(f"Unknown: {len(summary.unknown)}")
    if extra_parts:
        lines.append(f"  {' | '.join(extra_parts)}")

    def _format_section(title: str, runs: List[RunResult], show_detail: bool = False) -> None:
        if not runs:
            return
        lines.append("")
        lines.append(f"--- {title} ({len(runs)}) ---")
        for r in runs:
            label = r.rule_name or r.job_id
            lines.append(f"  {label}")
            if show_detail and r.failure_reason:
                lines.append(f"    Reason: {r.failure_reason}")
            lines.append(f"    {r.output_url}")

    _format_section("VERIFIED", summary.verified)
    _format_section("VIOLATED", summary.violated)
    _format_section("FAILED", summary.failed, show_detail=True)
    _format_section("TIMEOUT", summary.timeout, show_detail=True)
    _format_section("RUNNING", summary.running)
    _format_section("UNKNOWN", summary.unknown, show_detail=True)

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize all runs in a Certora Prover group",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s b78ea54a-a924-4f05-b1a7-58b29c1585ae
  %(prog)s "https://prover.certora.com/?groupIds=b78ea54a-a924-4f05-b1a7-58b29c1585ae"
  %(prog)s b78ea54a-a924-4f05-b1a7-58b29c1585ae --format json
  %(prog)s b78ea54a-a924-4f05-b1a7-58b29c1585ae -o summary.json
        """,
    )
    parser.add_argument(
        "group",
        help="Group ID (UUID) or prover.certora.com URL with groupIds parameter",
    )
    parser.add_argument("--output", "-o", help="Write output to file")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format (default: text)"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=365,
        help="How many days back to search for jobs (default: 365)",
    )

    args = parser.parse_args()

    try:
        group_id = extract_group_id(args.group)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        api = ProverOutputAPI()
        summary = build_group_summary(api, group_id, days_back=args.days_back)
    except AuthenticationError as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)
    except ProverAPIError as e:
        print(f"API error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        output = json.dumps(summary.to_dict(), indent=2)
    else:
        output = format_text(summary)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
            f.write("\n")
        print(f"Summary written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
