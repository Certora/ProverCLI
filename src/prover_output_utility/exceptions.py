# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Custom exceptions for ProverCLI.
"""


class ProverAPIError(Exception):
    """Base exception for Prover API errors."""

    pass


class AuthenticationError(ProverAPIError):
    """Raised when authentication fails."""

    pass


class JobNotFoundError(ProverAPIError):
    """Raised when a job is not found."""

    pass


class ParseError(ProverAPIError):
    """Raised when output parsing fails."""

    pass


class InvalidJobError(ProverAPIError):
    """Raised when job input is invalid."""

    pass


class APITimeoutError(ProverAPIError):
    """Raised when API request times out."""

    pass
