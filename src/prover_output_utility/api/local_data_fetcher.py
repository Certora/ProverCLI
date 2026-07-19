# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Local data fetcher for reading prover outputs from emv-* folders.
"""

import json
import os
import re
from glob import glob
from typing import Any, Dict, List, Optional

from ..exceptions import JobNotFoundError, ProverAPIError
from .base_data_fetcher import BaseDataFetcher


class LocalDataFetcher(BaseDataFetcher):
    """Handles data fetching from local emv-* folders."""

    def __init__(self):
        """Initialize the local data fetcher."""
        pass

    def fetch_raw_output(self, job_identifier: str) -> Dict[str, Any]:
        """
        Fetch raw output data from local files.

        For local runs, we construct job info from available metadata files.

        Args:
            job_identifier: Path to the emv-* folder

        Returns:
            Raw job data constructed from local files

        Raises:
            ProverAPIError: If local files cannot be read
        """
        emv_path = os.path.abspath(job_identifier)

        if not os.path.exists(emv_path):
            raise JobNotFoundError(f"Local prover output path not found: {job_identifier}")

        if not os.path.basename(emv_path).startswith("emv-"):
            raise ProverAPIError(f"Path must be an emv-* folder, got: {job_identifier}")

        try:
            metadata = {}

            # Extract job ID from folder name (emv-1-certora-19-Aug--13-09)
            folder_name = os.path.basename(emv_path)
            metadata["job_id"] = folder_name

            # Try to read CVT version if available
            cvt_version_path = os.path.join(emv_path, "inputs", "cvt_version.json")
            if os.path.exists(cvt_version_path):
                with open(cvt_version_path, "r") as f:
                    cvt_data = json.load(f)
                    metadata["prover_version"] = cvt_data.get("version", "unknown")

            # Try to read certora metadata
            certora_metadata_path = os.path.join(emv_path, "inputs", ".certora_metadata.json")
            if os.path.exists(certora_metadata_path):
                with open(certora_metadata_path, "r") as f:
                    certora_data = json.load(f)
                    metadata.update(certora_data)

            # Check if we have a valid structure
            reports_path = os.path.join(emv_path, "Reports")
            if not os.path.exists(reports_path):
                raise ProverAPIError(f"Invalid emv-* folder structure: missing Reports directory")

            # Set basic status based on folder existence
            metadata["status"] = "completed"  # Local runs are assumed completed
            metadata["source"] = "local"
            metadata["emv_path"] = emv_path

            return metadata

        except json.JSONDecodeError as e:
            raise ProverAPIError(f"Failed to parse JSON metadata in {emv_path}: {e}")
        except Exception as e:
            raise ProverAPIError(f"Failed to read local output from {emv_path}: {e}")

    def fetch_tree_view_data(
        self, job_identifier: str, path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch tree-view data from local files.

        Args:
            job_identifier: Path to the emv-* folder
            path: Optional path within tree-view (e.g., "treeViewStatus.json" or specific rule files)

        Returns:
            Tree-view data

        Raises:
            ProverAPIError: If local files cannot be read
        """
        emv_path = os.path.abspath(job_identifier)

        if not os.path.exists(emv_path):
            raise JobNotFoundError(f"Local prover output path not found: {job_identifier}")

        try:
            tree_view_dir = os.path.join(emv_path, "Reports", "treeView")

            if not os.path.exists(tree_view_dir):
                raise JobNotFoundError(f"TreeView directory not found: {tree_view_dir}")

            if path is None or path == "treeViewStatus.json":
                # Find the latest treeViewStatus_*.json file
                return self._get_latest_tree_view_status(tree_view_dir)
            else:
                # Look for specific file in treeView directory
                file_path = os.path.join(tree_view_dir, path)
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        return json.load(f)

                # If not found in treeView, might be a rule output file
                # Look for it by pattern matching
                matching_files = glob(os.path.join(tree_view_dir, f"*{path}*"))
                if matching_files:
                    with open(matching_files[0], "r") as f:
                        return json.load(f)

                raise JobNotFoundError(f"Tree-view file not found: {path}")

        except json.JSONDecodeError as e:
            raise ProverAPIError(f"Failed to parse JSON file {path}: {e}")
        except Exception as e:
            raise ProverAPIError(f"Failed to read tree-view data {path}: {e}")

    def _get_latest_tree_view_status(self, tree_view_dir: str) -> Dict[str, Any]:
        """
        Get the latest treeViewStatus_*.json file based on the highest number.

        Args:
            tree_view_dir: Path to the treeView directory

        Returns:
            Latest tree view status data
        """
        status_files = glob(os.path.join(tree_view_dir, "treeViewStatus_*.json"))

        if not status_files:
            raise JobNotFoundError("No treeViewStatus_*.json files found")

        # Extract numbers and find the highest
        latest_file = None
        highest_num = -1

        for status_file in status_files:
            filename = os.path.basename(status_file)
            match = re.search(r"treeViewStatus_(\d+)\.json", filename)
            if match:
                num = int(match.group(1))
                if num > highest_num:
                    highest_num = num
                    latest_file = status_file

        if latest_file is None:
            raise JobNotFoundError("No valid treeViewStatus_*.json files found")

        with open(latest_file, "r") as f:
            return json.load(f)

    def list_recent_jobs(
        self,
        created_after: str,
        limit: int = 100,
        all_users: bool = True,
    ) -> List[Dict[str, Any]]:
        """List recent jobs - not applicable for local fetcher."""
        raise ProverAPIError("list_recent_jobs is not supported for local prover outputs")

    def fetch_group_jobs(
        self, group_id: str, created_after: str, created_before: str
    ) -> List[Dict[str, Any]]:
        """Fetch group jobs - not applicable for local fetcher."""
        raise ProverAPIError("fetch_group_jobs is not supported for local prover outputs")

    def cancel_jobs(self, job_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel jobs - not applicable for local fetcher.

        Args:
            job_ids: Ignored

        Returns:
            Empty dict

        Raises:
            ProverAPIError: Always (not supported for local)
        """
        raise ProverAPIError("cancel_jobs is not supported for local prover outputs")

    def fetch_statsdata(self, job_identifier: str) -> Dict[str, Any]:
        """Fetch statsdata.json from local emv-* folder."""
        try:
            return json.loads(self.fetch_output_file(job_identifier, "statsdata.json"))
        except json.JSONDecodeError as e:
            raise ProverAPIError(f"Failed to parse statsdata.json: {e}")

    def fetch_outputs(self, job_identifier: str) -> bytes:
        """
        Fetch outputs archive for local job - not applicable for local files.

        Args:
            job_identifier: Path to the emv-* folder

        Returns:
            Raw tar.gz content as bytes

        Raises:
            ProverAPIError: Always (not supported for local)
        """
        raise ProverAPIError("fetch_outputs is not supported for local prover outputs - files are already local")

    def fetch_source_files_list(self, job_identifier: str) -> List[Dict[str, Any]]:
        """
        Fetch the source file tree from local emv-* folder.

        Raises:
            ProverAPIError: Always (not supported for local)
        """
        raise ProverAPIError("fetch_source_files_list is not supported for local prover outputs")

    def fetch_source_file_content(self, job_identifier: str, path: str) -> str:
        """
        Fetch source file content from local emv-* folder.

        Raises:
            ProverAPIError: Always (not supported for local)
        """
        raise ProverAPIError("fetch_source_file_content is not supported for local prover outputs")

    def fetch_output_file(self, job_identifier: str, rel_path: str) -> str:
        """Read a Reports/-relative output file from a local emv-* folder.

        Args:
            job_identifier: Path to the emv-* folder
            rel_path: Path of the file relative to the folder's Reports/ directory

        Returns:
            The file contents as text

        Raises:
            JobNotFoundError: If the folder or file is not found
            ProverAPIError: If the file cannot be read
        """
        emv_path = os.path.abspath(job_identifier)
        if not os.path.exists(emv_path):
            raise JobNotFoundError(f"Local prover output path not found: {job_identifier}")
        file_path = os.path.join(emv_path, "Reports", rel_path)
        if not os.path.exists(file_path):
            raise JobNotFoundError(f"Output file not found: {rel_path}")
        try:
            with open(file_path, "r") as f:
                return f.read()
        except OSError as e:
            raise ProverAPIError(f"Failed to read output file {rel_path}: {e}")

    def fetch_alert_report(self, job_identifier: str) -> List[Dict[str, Any]]:
        """
        Fetch alert report (alertReport.json) from local emv-* folder.

        Args:
            job_identifier: Path to the emv-* folder

        Returns:
            Alert report data as a list of alert objects

        Raises:
            JobNotFoundError: If alertReport.json is not found
            ProverAPIError: If local files cannot be read
        """
        emv_path = os.path.abspath(job_identifier)

        if not os.path.exists(emv_path):
            raise JobNotFoundError(f"Local prover output path not found: {job_identifier}")

        try:
            # Look for alertReport.json in Reports directory
            alert_report_path = os.path.join(emv_path, "Reports", "alertReport.json")

            if not os.path.exists(alert_report_path):
                # Return empty list if alertReport.json doesn't exist (common for jobs without alerts)
                return []

            with open(alert_report_path, "r") as f:
                return json.load(f)

        except json.JSONDecodeError as e:
            raise ProverAPIError(f"Failed to parse alertReport.json: {e}")
        except Exception as e:
            raise ProverAPIError(f"Failed to read alert report from {job_identifier}: {e}")
