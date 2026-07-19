# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Abstract base class for data fetchers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseDataFetcher(ABC):
    """Abstract base class for fetching prover data from different sources."""

    @abstractmethod
    def fetch_raw_output(self, job_identifier: str) -> Dict[str, Any]:
        """
        Fetch raw output data.

        Args:
            job_identifier: Job identifier (job ID for remote, emv path for local)

        Returns:
            Raw job data

        Raises:
            ProverAPIError: If fetch fails
        """
        pass

    @abstractmethod
    def fetch_tree_view_data(self, job_identifier: str, path: str = "treeViewStatus.json") -> Dict[str, Any]:
        """
        Fetch tree-view data.

        Args:
            job_identifier: Job identifier (job ID for remote, emv path for local)
            path: Optional path within the tree-view

        Returns:
            Tree-view data

        Raises:
            ProverAPIError: If fetch fails
        """
        pass

    @abstractmethod
    def list_recent_jobs(
        self,
        created_after: str,
        limit: int = 100,
        all_users: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        List recent jobs from the data API.

        The data API's /v1/domain/jobs endpoint requires createdAfter to be set
        explicitly so this is required.

        Args:
            created_after: ISO datetime string for range start (lower bound on createdAt)
            limit: Maximum number of jobs to return (the API caps page size at 100)
            all_users: If True, include jobs from all users; if False, only the authenticated user's

        Returns:
            List of raw job dicts as returned by the API

        Raises:
            ProverAPIError: If fetch fails
        """
        pass

    @abstractmethod
    def fetch_outputs(self, job_identifier: str) -> bytes:
        """
        Fetch outputs archive (tar.gz) for a job.

        Args:
            job_identifier: Job identifier (job ID for remote, emv path for local)

        Returns:
            Raw tar.gz content as bytes

        Raises:
            ProverAPIError: If fetch fails
        """
        pass

    @abstractmethod
    def cancel_jobs(self, job_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel multiple jobs.

        Args:
            job_ids: List of job IDs to cancel

        Returns:
            API response data

        Raises:
            ProverAPIError: If cancellation fails
        """
        pass

    @abstractmethod
    def fetch_group_jobs(
        self, group_id: str, created_after: str, created_before: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch all jobs in a group.

        The data API requires createdAfter/createdBefore params for the groupIds filter to work.

        Args:
            group_id: Group UUID
            created_after: ISO datetime string for range start
            created_before: ISO datetime string for range end

        Returns:
            List of job dicts

        Raises:
            ProverAPIError: If fetch fails
        """
        pass

    @abstractmethod
    def fetch_source_files_list(self, job_identifier: str) -> List[Dict[str, Any]]:
        """
        Fetch the source file tree for a job.

        Args:
            job_identifier: Job identifier (job ID for remote, emv path for local)

        Returns:
            List of source file tree nodes

        Raises:
            ProverAPIError: If fetch fails
        """
        pass

    @abstractmethod
    def fetch_source_file_content(self, job_identifier: str, path: str) -> str:
        """
        Fetch the content of a specific source file for a job.

        Args:
            job_identifier: Job identifier (job ID for remote, emv path for local)
            path: Path to the source file (e.g. ".certora_sources/src/Contract.sol")

        Returns:
            Raw file content as a string

        Raises:
            ProverAPIError: If fetch fails
        """
        pass

    @abstractmethod
    def fetch_output_file(self, job_identifier: str, rel_path: str) -> str:
        """
        Fetch the raw text of a file under the job's Reports/ output dir.

        Args:
            job_identifier: Job identifier (job ID for remote, emv path for local)
            rel_path: Reports/-relative filename (e.g. "unsat_core_map.json", "UnsatCoreTAC-....txt")

        Returns:
            Raw file content as a string

        Raises:
            AuthenticationError: If authentication fails (remote fetchers)
            JobNotFoundError: If the file is not found
            ProverAPIError: If fetch fails
        """
        pass

    @abstractmethod
    def fetch_alert_report(self, job_identifier: str) -> List[Dict[str, Any]]:
        """
        Fetch alert report (alertReport.json) for a job.

        Args:
            job_identifier: Job identifier (job ID for remote, emv path for local)

        Returns:
            Alert report data as a list of alert objects

        Raises:
            ProverAPIError: If fetch fails
        """
        pass