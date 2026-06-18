#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Example usage of ProverCLI API.
"""

import os

from .exceptions import AuthenticationError, JobNotFoundError, ProverAPIError
from .prover_api import ProverOutputAPI


def main() -> None:
    """
    Example usage of the ProverCLI API.
    """
    # Check if CERTORAKEY is set
    if not os.getenv("CERTORAKEY"):
        print("Error: CERTORAKEY environment variable not set")
        print("Please set it with: export CERTORAKEY='your-api-key'")
        return

    # Initialize the API
    try:
        api = ProverOutputAPI()
        print("✓ ProverOutputAPI initialized successfully")
    except AuthenticationError as e:
        print(f"Authentication error: {e}")
        return

    # Example job inputs (replace with actual job URLs/IDs)
    example_inputs = [
        "12345",  # Job ID
        "https://prover.certora.com/output/12345/some-path",  # Job URL
    ]

    for job_input in example_inputs:
        print(f"\n--- Processing job: {job_input} ---")

        try:
            # Get violated rules with assert messages
            violated_rules = api.get_violated_rules(job_input)

            if violated_rules:
                print(f"Found {len(violated_rules)} violated rules:")

                for violation in violated_rules:
                    print(f"\n  ❌ Rule: {violation['rule_name']}")
                    print(f"     Method: {violation['method_name']}")
                    print(f"     Assert: {violation['assert_message']}")
                    print(f"     Status: {violation['status']}")

                    if violation.get("ui_id"):
                        print(f"     UI ID: {violation['ui_id']}")

                    if violation.get("jump_to_definition"):
                        jump_to = violation["jump_to_definition"]
                        if isinstance(jump_to, dict) and jump_to.get("file"):
                            print(f"     Location: {jump_to['file']}:{jump_to.get('line', 'N/A')}")
            else:
                print("✅ No violated rules found!")

            # Also get basic job status
            status = api.get_job_status(job_input)
            print(f"\nJob Status: {status}")

        except JobNotFoundError:
            print(f"❌ Job not found: {job_input}")
        except AuthenticationError:
            print(f"❌ Authentication failed for job: {job_input}")
        except ProverAPIError as e:
            print(f"❌ API error for job {job_input}: {e}")
        except Exception as e:
            print(f"❌ Unexpected error for job {job_input}: {e}")

    # Example: Get job status without full parsing
    print("\n--- Quick Status Check ---")
    try:
        status = api.get_job_status("12345")
        print(f"Job 12345 status: {status}")
    except Exception as e:
        print(f"Could not get status: {e}")

    # Example: List recent jobs
    print("\n--- Recent Jobs ---")
    try:
        recent_jobs = api.list_recent_jobs(limit=3)
        for job in recent_jobs:
            print(f"Job {job.get('id', 'N/A')}: {job.get('status', 'N/A')}")
    except Exception as e:
        print(f"Could not list recent jobs: {e}")


if __name__ == "__main__":
    main()
