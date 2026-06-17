# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Compatibility layer for the refactored Prover API.

This module maintains backward compatibility while using the new modular structure.
"""

# Import from new locations
from .api import ProverOutputAPI
from .models import (
    AssertType,
    BreadcrumbInfo,
    CallResolutionInfo,
    CalltraceInfo,
    CheckResult,
    JobInfo,
    NodeStatus,
    SourceLocation,
    TreeViewData,
)

# Re-export for backward compatibility
__all__ = [
    "ProverOutputAPI",
    "CallResolutionInfo",
    "AssertType",
    "CheckResult",
    "CalltraceInfo",
    "BreadcrumbInfo",
    "JobInfo",
    "TreeViewData",
    "NodeStatus",
    "SourceLocation",
]
