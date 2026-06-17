# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
URL and job ID extraction utilities.
"""

import os
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

from ..exceptions import ProverAPIError


def extract_job_id(job_input: str) -> str:
    """
    Extract job ID from either a URL or direct job ID.

    Args:
        job_input: Job URL or job ID

    Returns:
        Job ID string

    Raises:
        ProverAPIError: If job ID cannot be extracted
    """
    if job_input.startswith("http"):
        return extract_job_id_from_url(job_input)

    # Otherwise assume it's a direct job ID
    # Strip query params if present (e.g., hash?anonymousKey=...)
    clean = job_input.split("?")[0]
    if re.match(r"^[a-zA-Z0-9_-]+$", clean):
        return clean

    raise ProverAPIError(f"Invalid job input format: {job_input}")


def extract_job_identifier(job_input: str) -> tuple[str, str]:
    """
    Extract job identifier and determine input type (remote/local).

    Args:
        job_input: Job URL, job ID, or local emv-* path

    Returns:
        Tuple of (job_identifier, input_type) where:
        - For remote: (job_id, "remote")
        - For local: (emv_path, "local")

    Raises:
        ProverAPIError: If job identifier cannot be extracted
    """
    # Check if it's a local path
    if (job_input.startswith("/") or job_input.startswith("./") or 
        job_input.startswith("../") or "emv-" in job_input):
        
        # Validate it's an emv-* folder path
        abs_path = os.path.abspath(job_input)
        if os.path.basename(abs_path).startswith("emv-") or any("emv-" in part for part in abs_path.split(os.sep)):
            # Find the emv-* part of the path
            path_parts = abs_path.split(os.sep)
            for i, part in enumerate(path_parts):
                if part.startswith("emv-"):
                    emv_path = os.sep.join(path_parts[:i+1])
                    return emv_path, "local"
        
        # If path-like but not emv-*, check if it exists and contains emv-*
        if os.path.exists(abs_path) and os.path.basename(abs_path).startswith("emv-"):
            return abs_path, "local"
            
        raise ProverAPIError(f"Local path must point to an emv-* folder: {job_input}")
    
    # Otherwise, it's a remote job (URL or job ID)
    return extract_job_id(job_input), "remote"


def extract_job_id_from_url(url: str) -> str:
    """
    Extract job ID from a prover URL.

    Args:
        url: Prover job URL

    Returns:
        Job ID string

    Raises:
        ProverAPIError: If job ID cannot be extracted from URL
    """
    parsed = urlparse(url)

    # Validate that this is a Certora domain
    if not parsed.netloc or "certora.com" not in parsed.netloc:
        raise ProverAPIError(f"URL must be from Certora domain, got: {parsed.netloc}")

    # Common patterns for prover URLs:
    # https://prover.certora.com/output/userid/jobid/...
    # https://prover.certora.com/job/jobid
    path_parts = parsed.path.strip("/").split("/")

    if "output" in path_parts:
        idx = path_parts.index("output")
        # Job ID is 2 positions after 'output' (skipping userid)
        if idx + 2 < len(path_parts):
            return path_parts[idx + 2]
        # Fallback: if only one part after output, use it as job ID
        # (for backwards compatibility)
        elif idx + 1 < len(path_parts):
            return path_parts[idx + 1]

    if "job" in path_parts:
        idx = path_parts.index("job")
        if idx + 1 < len(path_parts):
            return path_parts[idx + 1]

    # Try to extract from query parameters
    query_params = parse_qs(parsed.query)
    if "job_id" in query_params:
        return query_params["job_id"][0]

    raise ProverAPIError(f"Could not extract job ID from URL: {url}")
