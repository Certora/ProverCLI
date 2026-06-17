# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
ProverOutputUtility - Python API for parsing Certora Prover outputs.

This module provides an easy-to-use API for fetching and parsing outputs from the Certora Prover.
Supports both job URLs and job IDs as input.
"""

from .api.data_fetcher import default_api_base_url
from .auth import cloud_server_for_env, prover_frontend_url, resolve_login_env
from .prover_api import ProverOutputAPI
from .models import (
    AlertType,
    AssertType,
    CheckResult,
    JobStatus,
    NodeStatus,
    NodeType,
    ParsedAlert,
)
from .job_report import JobAnalyzer, JobReport

__version__ = "1.0.0"
__all__ = [
    "ProverOutputAPI",
    "AlertType",
    "AssertType",
    "CheckResult",
    "JobStatus",
    "NodeStatus",
    "NodeType",
    "ParsedAlert",
    "JobAnalyzer",
    "JobReport",
    "resolve_login_env",
    "cloud_server_for_env",
    "prover_frontend_url",
    "default_api_base_url",
]
