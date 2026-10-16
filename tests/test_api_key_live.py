# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""A live check that an organization API key alone reaches the API.

This is the test continuous integration runs with a real key and no stored
credentials. It skips wherever no key is configured, so a developer machine and
a fork both stay green without one.

It reads and never writes: it resolves the caller and reads one finished job.
"""

import os

import pytest

from prover_output_utility.api import ProverOutputAPI
from prover_output_utility.auth import organization_api_key

pytestmark = pytest.mark.skipif(
    organization_api_key() is None,
    reason="no organization API key configured for this environment",
)

# A finished job the key's organization can read. Override per environment with
# PROVER_CLI_LIVE_JOB_ID so the check does not depend on one fixed run forever.
DEFAULT_JOB_ID = os.environ.get("PROVER_CLI_LIVE_JOB_ID", "")


def test_the_key_identifies_its_owner() -> None:
    api = ProverOutputAPI(enable_cache=False)
    who = api.who_am_i()
    assert who, "the API returned no identity for the key"
    assert who.get("email"), f"no email on the resolved identity: {sorted(who)}"


@pytest.mark.skipif(not DEFAULT_JOB_ID, reason="PROVER_CLI_LIVE_JOB_ID is not set")
def test_the_key_reads_a_finished_job() -> None:
    api = ProverOutputAPI(enable_cache=False)
    report = api.get_job_report(DEFAULT_JOB_ID)
    assert report is not None, f"no report for job {DEFAULT_JOB_ID}"
