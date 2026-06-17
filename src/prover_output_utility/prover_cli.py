#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Command line interface for ProverOutputUtility.
Comprehensive CLI that provides full access to Certora Prover job data.
"""

import argparse
import json
import os
import sys

from .api import ProverOutputAPI
from .breadcrumb import format_breadcrumbs_text
from .exceptions import AuthenticationError, JobNotFoundError, ProverAPIError
from .group_summary import build_group_summary, extract_group_id, format_text as format_group_text
from .models import CalltraceInfo, CheckResult, ParsedAlert
from .sighash import handle_sighash_command


def format_check_result(check_result: CheckResult, index: int) -> str:
    """Format a check_result for text output."""
    status_icon = "❌" if check_result.is_violated else "✅" if check_result.is_verified else "⚠️"

    lines = [
        f"\n  {index}. {status_icon} Rule: {check_result.rule_name}",
        f"     Method: {check_result.method_name}",
        f"     Assert: {check_result.assert_message}",
        f"     Status: {check_result.status.value if hasattr(check_result.status, 'value') else check_result.status}",
    ]

    if check_result.output_files:
        output_file = check_result.output_files[0]
        lines.append(f"     Output Files: {check_result.output_files}")
        lines.append(f"     (use --calltrace '{output_file}' to get trace)")
    elif check_result.ui_id:
        lines.append(f"     UI ID: {check_result.ui_id} (no output files available)")

    if check_result.debug_trace_file:
        lines.append(f"     Debug Trace (DAP): {check_result.debug_trace_file}")
        lines.append(f"     (use --breadcrumbs '{check_result.debug_trace_file}' for execution trace)")

    if check_result.source_location:
        lines.append(f"     Location: {check_result.source_location}")

    return "\n".join(lines)


def format_alert(alert: ParsedAlert, index: int) -> str:
    """Format an alert for text output."""
    severity_icon = "❌" if alert.severity == "ERROR" else "⚠️" if alert.severity == "WARNING" else "ℹ️"

    lines = [
        f"\n  {index}. {severity_icon} [{alert.alert_type.value}] {alert.severity}",
        f"     Message: {alert.message}",
    ]

    if alert.jump_to_definition:
        lines.append(f"     Location: {alert.jump_to_definition}")

    if alert.hint:
        lines.append(f"     Hint: {alert.hint}")

    if alert.url:
        lines.append(f"     URL: {alert.url}")

    return "\n".join(lines)


def format_calltrace_summary(calltrace: CalltraceInfo) -> str:
    """Format calltrace data for text output."""
    lines = [
        f"Job ID: {calltrace.job_id}",
        f"Output File: {calltrace.output_file}",
    ]

    if calltrace.rule_name:
        lines.append(f"Rule: {calltrace.rule_name}")

    trace_data = calltrace.trace_data
    lines.append(f"Calltrace data ({len(trace_data)} keys):")

    if isinstance(trace_data, dict):
        for key, value in list(trace_data.items())[:10]:  # Show first 10 keys
            if isinstance(value, (dict, list)):
                lines.append(f"  {key}: {type(value).__name__} ({len(value)} items)")
            else:
                value_str = str(value)[:50]
                if len(str(value)) > 50:
                    value_str += "..."
                lines.append(f"  {key}: {value_str}")

        if len(trace_data) > 10:
            lines.append(f"  ... and {len(trace_data) - 10} more keys")
    else:
        lines.append(f"  Raw data: {str(trace_data)[:200]}...")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract violated rules and other data from Certora Prover jobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Authentication check
  %(prog)s --who-am-i

  # Remote jobs
  %(prog)s --job-id 12345
  %(prog)s --job-url "https://prover.certora.com/output/12345/..."
  %(prog)s --job-id 12345 --output violations.json
  %(prog)s --job-id 12345 --status-only
  %(prog)s --job-id 12345 --check-running
  %(prog)s --job-id 12345 --all-checks
  %(prog)s --job-id 12345 --leaf-checks
  %(prog)s --job-id 12345 --calltrace 'some/output/file.json'
  %(prog)s --job-id 12345 --breadcrumbs 'dap_calltrace_56-certora-dap.json'
  %(prog)s --job-id 12345 --statsdata
  %(prog)s --job-id 12345 --full-report
  %(prog)s --job-id 12345 --full-report --format json
  %(prog)s --cancel 12345 67890

  # Group summary
  %(prog)s --group-id b78ea54a-a924-4f05-b1a7-58b29c1585ae
  %(prog)s --group-id "https://prover.certora.com/?groupIds=b78ea54a-..." --format json

  # Recent jobs
  %(prog)s --recent-jobs --limit 10 --days-back 3
  %(prog)s --recent-jobs --my-jobs-only --format json

  # Sighash computation and lookup
  %(prog)s --sighash "transfer(address,uint256)"
  %(prog)s --sighash "0xa9059cbb"
  %(prog)s --sighash "function foo(bool[] calldata booboo) internal view"

  # Local emv-* folders
  %(prog)s --local-path "./emv-1-certora-19-Aug--13-09"
  %(prog)s --local-path "/path/to/emv-1-certora-19-Aug--13-09" --output results.json
  %(prog)s --local-path "./emv-1-certora-19-Aug--13-09" --calltrace 'rule_output_58.json'
  %(prog)s --local-path "./emv-1-certora-19-Aug--13-09" --statsdata

Environment Variables:
  CERTORAKEY    Your Certora API key (required if cert_cli_login not available)
        """,
    )

    job_group = parser.add_mutually_exclusive_group(required=False)
    job_group.add_argument("--job-id", help="Prover job ID")
    job_group.add_argument("--job-url", help="Prover job URL")
    job_group.add_argument("--local-path", help="Local emv-* folder path")
    job_group.add_argument(
        "--cancel",
        nargs="+",
        metavar="JOB",
        help="Cancel jobs (provide job URLs or IDs)",
    )
    job_group.add_argument(
        "--who-am-i", action="store_true", help="Get current user authentication information"
    )
    job_group.add_argument(
        "--group-id",
        help="Group ID (UUID) or prover.certora.com URL with groupIds parameter. "
        "Summarizes all runs in the group.",
    )
    job_group.add_argument(
        "--sighash",
        help="Compute or lookup a function sighash. "
        "Pass a signature like 'transfer(address,uint256)' to compute its sighash, "
        "or pass a 4-byte hex like '0xa9059cbb' to look up matching signatures.",
    )
    job_group.add_argument(
        "--recent-jobs",
        action="store_true",
        help="List recent jobs from the data API. "
        "Use --days-back, --limit, --my-jobs-only to refine.",
    )

    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--status-only", action="store_true", help="Only get job status")
    parser.add_argument(
        "--check-running",
        action="store_true",
        help="Check if job is still running (finish_time is null)",
    )
    parser.add_argument("--calltrace", help="Get calltrace for specific output file path")
    parser.add_argument("--breadcrumbs", help="Get breadcrumb trace from DAP file")
    parser.add_argument("--statsdata", action="store_true", help="Get statsdata.json for the job")
    parser.add_argument(
        "--all-checks",
        action="store_true",
        help="Get all checks including tree nodes (both successful and failed)",
    )
    parser.add_argument(
        "--leaf-checks",
        action="store_true",
        help="Get only leaf checks/assertions (both successful and failed)",
    )
    parser.add_argument(
        "--alerts",
        action="store_true",
        help="Get alerts from the alert report",
    )
    parser.add_argument(
        "--full-report",
        action="store_true",
        help=(
            "Get the full structured job report (violated/timeout/error/verified rules, "
            "alerts, call resolutions, duration) as a single JSON object. Equivalent to "
            "ProverOutputAPI.get_job_report() and intended as the one-shot triage call."
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument(
        "--days-back",
        type=int,
        default=365,
        help="How many days back to search (default: 365). Used with --group-id and --recent-jobs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max jobs to return (default: 100, capped at 100 by the API). Used with --recent-jobs.",
    )
    parser.add_argument(
        "--my-jobs-only",
        action="store_true",
        help="When listing recent jobs, only include the authenticated user's jobs (default: all users).",
    )

    args = parser.parse_args()

    # Handle --sighash early (doesn't need job input or authentication)
    if args.sighash:
        try:
            result = handle_sighash_command(args.sighash)

            if args.output:
                with open(args.output, "w") as f:
                    json.dump(result, f, indent=2)
                print(f"Sighash result written to {args.output}")
            elif args.format == "json":
                print(json.dumps(result, indent=2))
            else:
                if result["type"] == "signature_hash":
                    print(f"Input: {result['input']}")
                    print(f"Normalized: {result['normalized_signature']}")
                    print(f"Sighash: {result['sighash']}")
                else:
                    print(f"Sighash: {result['sighash']}")
                    if result["signatures"]:
                        print(f"Found {len(result['signatures'])} matching signature(s):")
                        for sig in result["signatures"]:
                            print(f"  - {sig}")
                    else:
                        print("No matching signatures found in 4byte.directory")
            return
        except ValueError as e:
            print(f"❌ Invalid signature: {e}", file=sys.stderr)
            sys.exit(1)
        except RuntimeError as e:
            print(f"❌ Lookup failed: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle who-am-i early (doesn't need job input)
    if args.who_am_i:
        try:
            api = ProverOutputAPI(use_local=False)
            user_info = api.who_am_i()

            if args.format == "json":
                print(json.dumps(user_info, indent=2))
            else:
                print("\nAuthentication Status:")
                print(f"  ✅ Authenticated successfully")
                if "email" in user_info:
                    print(f"  Email: {user_info['email']}")
                if "user_id" in user_info:
                    print(f"  User ID: {user_info['user_id']}")
                if "username" in user_info:
                    print(f"  Username: {user_info['username']}")
                for key, value in user_info.items():
                    if key not in ["email", "user_id", "username"]:
                        print(f"  {key}: {value}")
            return
        except AuthenticationError as e:
            print(f"\n❌ Authentication failed: {e}", file=sys.stderr)
            print("\nTry deleting stored credentials and logging in again.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Check for authentication
    if not os.getenv("CERTORAKEY"):
        # Try to use cert_cli_login if available
        try:
            from certora_login import login  # noqa: F401

            # cert_cli_login will handle authentication
        except ImportError:
            print("Error: CERTORAKEY environment variable not set", file=sys.stderr)
            print(
                "Please set it with: export CERTORAKEY='your-api-key'",
                file=sys.stderr,
            )
            sys.exit(1)

    # Handle --group-id (after auth check, doesn't need job input)
    if args.group_id:
        try:
            group_id = extract_group_id(args.group_id)
            api = ProverOutputAPI(use_local=False)
            summary = build_group_summary(api, group_id, days_back=args.days_back)

            if args.format == "json":
                output = json.dumps(summary.to_dict(), indent=2)
            else:
                output = format_group_text(summary)

            if args.output:
                with open(args.output, "w") as f:
                    f.write(output)
                    f.write("\n")
                print(f"Group summary written to {args.output}")
            else:
                print(output)
            return
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}", file=sys.stderr)
            sys.exit(1)
        except ProverAPIError as e:
            print(f"❌ API error: {e}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"❌ Invalid group ID: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle --recent-jobs (after auth check, doesn't need job input)
    if args.recent_jobs:
        try:
            api = ProverOutputAPI(use_local=False)
            jobs = api.list_recent_jobs(
                days_back=args.days_back,
                limit=args.limit,
                all_users=not args.my_jobs_only,
            )
            result = {
                "action": "list_recent_jobs",
                "days_back": args.days_back,
                "limit": args.limit,
                "all_users": not args.my_jobs_only,
                "count": len(jobs),
                "jobs": [j.to_dict() for j in jobs],
            }

            if args.output:
                with open(args.output, "w") as f:
                    json.dump(result, f, indent=2)
                print(f"Found {len(jobs)} recent jobs. Results written to {args.output}")
            elif args.format == "json":
                print(json.dumps(result, indent=2))
            else:
                scope = "my jobs" if args.my_jobs_only else "all users"
                print(f"Recent jobs (last {args.days_back} days, {scope}): {len(jobs)} found")
                for j in jobs:
                    status = j.status.value if hasattr(j.status, "value") else j.status
                    print(f"  - {j.job_id}  [{status}]  {j.start_time or ''}")
            return
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}", file=sys.stderr)
            sys.exit(1)
        except ProverAPIError as e:
            print(f"❌ API error: {e}", file=sys.stderr)
            sys.exit(1)

    # Check that we have a job input (unless it's who-am-i or sighash which were handled above)
    if not args.cancel and not (args.job_id or args.job_url or args.local_path):
        parser.error(
            "Please provide either --job-id, --job-url, --local-path, --cancel, --group-id, --sighash, --recent-jobs, or --who-am-i"
        )

    # Handle cancel case differently since it takes multiple inputs
    if args.cancel:
        job_inputs = args.cancel
        if args.verbose:
            print(f"Cancelling {len(job_inputs)} jobs: {job_inputs}")
    else:
        job_input = args.job_id or args.job_url or args.local_path
        if args.verbose:
            print(f"Processing job: {job_input}")

    try:
        # Initialize API - auto-detect if local path is provided
        use_local = args.local_path is not None
        api = ProverOutputAPI(use_local=use_local)

        if args.cancel:
            # Cancel jobs
            cancel_result = api.cancel_jobs(job_inputs)
            result = {
                "action": "cancel",
                "requested_jobs": len(job_inputs),
                "jobs": job_inputs,
                "result": cancel_result,
            }

        elif args.status_only:
            # Just get job status
            status = api.get_job_status(job_input)
            result = {"job_id": job_input, "status": status}

        elif args.check_running:
            # Check if job is running
            job_info = api.get_job_info(job_input)
            result = {
                "job_id": job_info.job_id,
                "is_running": job_info.is_running,
                "status": job_info.status,
                "finish_time": job_info.finish_time,
            }

        elif args.calltrace:
            # Get calltrace for specific file
            calltrace = api.get_calltrace(job_input, args.calltrace)
            result = calltrace.to_dict()

        elif args.breadcrumbs:
            # Get breadcrumb trace
            breadcrumbs = api.get_breadcrumbs(job_input, args.breadcrumbs)
            result = breadcrumbs.to_dict()

        elif args.statsdata:
            # Get statsdata.json
            statsdata = api.get_statsdata(job_input)
            result = {"job_id": job_input, "statsdata": statsdata}

        elif args.all_checks:
            # Get all checks (both successful and failed)
            all_checks = api.get_all_checks(job_input)
            result = {
                "job_id": job_input,
                "checks_count": len(all_checks),
                "checks": [c.to_dict() for c in all_checks],
            }

        elif args.leaf_checks:
            # Get only leaf checks (both successful and failed)
            leaf_checks = api.get_leaf_checks(job_input)
            result = {
                "job_id": job_input,
                "checks_count": len(leaf_checks),
                "checks": [c.to_dict() for c in leaf_checks],
            }

        elif args.alerts:
            # Get alerts from alert report
            alerts = api.get_alerts(job_input)
            result = {
                "job_id": job_input,
                "alerts_count": len(alerts),
                "alerts": [a.to_dict() for a in alerts],
            }

        elif args.full_report:
            # Get the full structured job report — one-shot triage call.
            report = api.get_job_report(job_input)
            result = {"job_id": job_input, "report": report.to_dict()}

        else:
            # Get violated rules (default behavior)
            violations = api.get_violated_rules(job_input)

            # For backward compatibility, convert to dict format
            result = {
                "job_id": job_input,
                "assert_nodes_count": len(violations),
                "assert_nodes": [v.to_dict() for v in violations],
            }

        # Output results
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)

            if args.cancel:
                print(
                    f"Cancel request sent for {result['requested_jobs']} jobs. Results written to {args.output}"
                )
            elif args.status_only:
                print(f"Job status: {result['status']}. Results written to {args.output}")
            elif args.check_running:
                print(
                    f"Job running status: {result['is_running']}. Results written to {args.output}"
                )
            elif args.statsdata:
                print(f"✅ Statsdata retrieved. Results written to {args.output}")
            elif args.all_checks:
                count = result.get("checks_count", 0)
                print(f"Found {count} checks (all tree nodes). Results written to {args.output}")
            elif args.leaf_checks:
                count = result.get("checks_count", 0)
                print(f"Found {count} checks (leaf nodes only). Results written to {args.output}")
            elif args.alerts:
                count = result.get("alerts_count", 0)
                print(f"Found {count} alerts. Results written to {args.output}")
            elif args.full_report:
                print(f"✅ Full report retrieved. Results written to {args.output}")
            else:
                count = result.get("assert_nodes_count", 0)
                print(f"Found {count} violations. Results written to {args.output}")

        elif args.format == "json":
            print(json.dumps(result, indent=2))

        else:
            # Text output
            if args.cancel:
                print(f"✅ Cancel request sent for {result['requested_jobs']} jobs")
                cancel_result = result.get("result", {})
                if args.verbose and cancel_result:
                    print("API Response:")
                    print(json.dumps(cancel_result, indent=2))

            elif args.status_only:
                print(f"Job {job_input} status: {result['status']}")

            elif args.check_running:
                status_text = "still running" if result["is_running"] else "completed"
                print(f"Job {result['job_id']} is {status_text}")
                if result.get("finish_time"):
                    print(f"Finished at: {result['finish_time']}")

            elif args.calltrace:
                # Recreate CalltraceInfo from result for formatting
                calltrace = CalltraceInfo(
                    job_id=result["job_id"],
                    output_file=result["output_file"],
                    trace_data=result["calltrace"],
                    rule_name=result.get("rule_name"),
                )
                print(format_calltrace_summary(calltrace))

            elif args.breadcrumbs:
                if format_breadcrumbs_text:
                    breadcrumbs_text = format_breadcrumbs_text(result)
                    print(breadcrumbs_text)
                else:
                    print(f"Job ID: {job_input}")
                    print(f"DAP File: {args.breadcrumbs}")
                    print("Breadcrumb functionality not available - missing format function")

            elif args.statsdata:
                print(f"Job ID: {job_input}")
                print(f"✅ Retrieved statsdata.json ({len(result['statsdata'])} keys)")
                if args.verbose:
                    print("Stats data summary:")
                    for key, value in list(result["statsdata"].items())[:5]:
                        if isinstance(value, (dict, list)):
                            print(f"  {key}: {type(value).__name__} ({len(value)} items)")
                        else:
                            value_str = str(value)[:50]
                            if len(str(value)) > 50:
                                value_str += "..."
                            print(f"  {key}: {value_str}")
                    if len(result["statsdata"]) > 5:
                        print(f"  ... and {len(result['statsdata']) - 5} more keys")
                    print("Use --format json to see full data")

            elif args.all_checks:
                # Show all checks (both successful and failed)
                print(f"Job ID: {job_input}")
                print(f"All Checks Found: {result['checks_count']} (all tree nodes)")

                if result["checks"]:
                    print("\nAll Checks:")
                    checks = [CheckResult.from_dict(c) for c in result["checks"]]
                    for i, check in enumerate(checks, 1):
                        print(format_check_result(check, i))
                else:
                    print("\n⚠️ No checks found!")

            elif args.leaf_checks:
                # Show only leaf checks (both successful and failed)
                print(f"Job ID: {job_input}")
                print(f"Leaf Checks Found: {result['checks_count']} (leaf nodes only)")

                if result["checks"]:
                    print("\nLeaf Checks:")
                    checks = [CheckResult.from_dict(c) for c in result["checks"]]
                    for i, check in enumerate(checks, 1):
                        print(format_check_result(check, i))
                else:
                    print("\n⚠️ No leaf checks found!")

            elif args.alerts:
                # Show alerts
                print(f"Job ID: {job_input}")
                print(f"Alerts Found: {result['alerts_count']}")

                if result["alerts"]:
                    print("\nAlerts:")
                    alerts = [ParsedAlert.from_dict(a) for a in result["alerts"]]
                    for i, alert in enumerate(alerts, 1):
                        print(format_alert(alert, i))
                else:
                    print("\n✅ No alerts found!")

            elif args.full_report:
                # Summary view of the full report. Full content via --format json.
                report = result["report"]
                rules = report.get("rules", {})
                calls = report.get("calls", {})
                alerts_by_type = report.get("alerts_by_type", {})
                print(f"Job ID: {job_input}")
                print(f"Status: {report.get('job_status')}    Duration: {report.get('duration')}s")
                print(
                    f"Rules: violated={len(rules.get('violated', []))} "
                    f"timeout={len(rules.get('timeout', []))} "
                    f"error={len(rules.get('error', []))} "
                    f"verified={len(rules.get('verified', []))} "
                    f"other={len(rules.get('other', []))}"
                )
                print(
                    f"Calls: unresolved={len(calls.get('unresolved', []))} "
                    f"resolved={len(calls.get('resolved', []))}"
                )
                if alerts_by_type:
                    print("Alerts:")
                    for atype, alist in alerts_by_type.items():
                        print(f"  {atype}: {len(alist)}")
                else:
                    print("Alerts: none")
                print("\nUse --format json for full content.")

            else:
                # Default: show violations
                print(f"Job ID: {job_input}")
                print(f"Assert Nodes Found: {result['assert_nodes_count']}")

                if result["assert_nodes"]:
                    print("\nAssert Nodes:")
                    # Recreate CheckResult objects for nice formatting
                    violations = [CheckResult.from_dict(v) for v in result["assert_nodes"]]
                    for i, violation in enumerate(violations, 1):
                        print(format_check_result(violation, i))
                else:
                    print("\n✅ No assert nodes found!")

    except AuthenticationError:
        print("❌ Authentication failed - check your CERTORAKEY", file=sys.stderr)
        sys.exit(1)

    except JobNotFoundError as e:
        print(f"❌ Job not found: {e}", file=sys.stderr)
        sys.exit(1)

    except ProverAPIError as e:
        print(f"❌ API error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
