# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Main ProverOutputAPI class that provides the high-level interface.
"""

import io
import json
import logging
import os
import tarfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..auth import ProverAuth
from ..aws_auth import AWSAuth
from ..breadcrumb import BreadcrumbParser
from ..exceptions import JobNotFoundError, ProverAPIError
from ..job_report import JobAnalyzer, JobReport
from ..models import (
    BreadcrumbInfo,
    CallResolutionInfo,
    CalltraceInfo,
    CheckResult,
    JobInfo,
    JobStatus,
    ParsedAlert,
    SourceFileNode,
    TreeViewData,
    convert_job_status,
)
from ..parsers import OutputParser
from .aws_data_fetcher import AWSDataFetcher
from .cache import APICache
from .data_fetcher import DataFetcher, default_api_base_url
from .local_data_fetcher import LocalDataFetcher
from .tree_parser import TreeParser
from .url_utils import extract_job_id, extract_job_identifier


# Per-job locks for thread-safe fetch operations
_fetch_locks: dict[str, threading.Lock] = {}
_fetch_locks_lock = threading.Lock()


def _get_fetch_lock(job_identifier: str) -> threading.Lock:
    """Get or create a per-job lock for thread-safe fetching."""
    with _fetch_locks_lock:
        if job_identifier not in _fetch_locks:
            _fetch_locks[job_identifier] = threading.Lock()
        return _fetch_locks[job_identifier]


def _flatten_source_file_tree(nodes: List[SourceFileNode], prefix: str = "") -> List[tuple]:
    """Flatten a SourceFileNode tree into (relative_path, api_path) tuples."""
    result: List[tuple] = []
    for node in nodes:
        path = f"{prefix}{node.name}" if prefix else node.name
        if node.selectable and not node.name.startswith("."):
            result.append((path, node.output))
        if node.children:
            result.extend(_flatten_source_file_tree(node.children, f"{path}/"))
    return result


def _collect_treeview_output_files(tree_status: Dict[str, Any]) -> List[str]:
    """Recursively collect all output filenames from 'output' keys in a treeViewStatus dict."""
    output_files: List[str] = []

    def traverse(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "output" and isinstance(value, list):
                    output_files.extend(value)
                else:
                    traverse(value)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    traverse(tree_status)
    return list(set(output_files))


class ProverOutputAPI:
    """
    Main API class for fetching and parsing Certora Prover outputs.

    Authentication is handled automatically via certora_login when accessing remote APIs.
    No CERTORAKEY required.

    Usage:
        # Remote API (default) - uses certora_login for authentication
        api = ProverOutputAPI()
        violations = api.get_violated_rules("https://prover.certora.com/output/12345/...")
        violations = api.get_violated_rules("12345")

        # Local emv-* folders (no authentication needed)
        api = ProverOutputAPI(use_local=True)
        violations = api.get_violated_rules("/path/to/emv-1-certora-19-Aug--13-09")
        violations = api.get_violated_rules("./emv-1-certora-19-Aug--13-09")
    """

    def __init__(
        self,
        certora_key: Optional[str] = None,
        enable_cache: bool = True,
        use_local: bool = False,
        api_base_url: Optional[str] = None,
    ):
        """
        Initialize the ProverOutputAPI.

        Args:
            certora_key: Deprecated - authentication is handled automatically via certora_login
            enable_cache: Whether to enable persistent caching of API responses (default: True)
            use_local: Whether to use local emv-* folders instead of remote API (default: False)
            api_base_url: API base URL. When None (the default), resolve from the
                          Certora login env via :func:`resolve_login_env` —
                          dev → data-api-dev.certora.com, stg → data-api-stg.certora.com,
                          prod → data-api.certora.com. Pass an explicit URL (e.g.
                          ``DataFetcher.STAGING_API_BASE_URL``) to override.
        """
        self.logger = logging.getLogger(__name__)
        self.parser = OutputParser()
        self.breadcrumb_parser = BreadcrumbParser()
        self.tree_parser = TreeParser()
        self.use_local = use_local
        # Resolve at instance-construction time so the same process can serve
        # multiple envs by re-instantiating; bound-default would freeze on import.
        self.api_base_url = api_base_url if api_base_url is not None else default_api_base_url()

        # Initialize cache
        self.cache = APICache() if enable_cache else None

        # Initialize appropriate data fetcher
        if use_local:
            self.data_fetcher = LocalDataFetcher()
        elif os.getenv("CI") and self._is_aws_available():
            # In CI with AWS credentials, use AWS Lambda authentication
            self.logger.info("Using AWS Lambda authentication in CI")
            aws_auth = AWSAuth()
            aws_session = aws_auth.get_session()
            self.data_fetcher = AWSDataFetcher(aws_session)
            # No session needed for AWS auth
            self.session = None
        else:
            # Regular cookie-based authentication
            self.auth = ProverAuth()
            self._setup_session()

    def _setup_session(self, force_relogin: bool = False):
        """Setup session with authentication cookies."""
        self.session = requests.Session()
        # Set up authentication
        self.session.cookies = self.auth.get_auth_cookies(force_relogin=force_relogin)
        self.data_fetcher = DataFetcher(self.session, api_instance=self, api_base_url=self.api_base_url)

    def _is_aws_available(self) -> bool:
        """Check if AWS authentication is available."""
        try:
            aws_auth = AWSAuth()
            return aws_auth.is_available()
        except Exception:
            return False

    def _extract_job_identifier(self, job_input: str) -> str:
        """
        Extract job identifier based on the fetcher type.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            Job identifier (job_id for remote, emv_path for local)
        """
        if self.use_local:
            # For local, validate it's an emv-* path and return the path
            job_identifier, input_type = extract_job_identifier(job_input)
            if input_type != "local":
                raise ProverAPIError(
                    f"ProverOutputAPI configured for local use but got remote input: {job_input}"
                )
            return job_identifier
        else:
            # For remote, extract job ID from URL or use direct job ID
            return extract_job_id(job_input)


    def _set_default_contract(self, job_identifier: str) -> None:
        """Set the tree parser's default contract from the job's API response."""
        try:
            raw_output = self.data_fetcher.fetch_raw_output(job_identifier)
            self.tree_parser.default_contract = raw_output.get("contract")
        except Exception:
            pass  # best-effort

    def get_treeview_status(self, job_input: str) -> Dict[str, Any]:
        """
        Get tree view status data with caching for completed jobs.

        This is a public API method that retrieves the treeViewStatus.json file
        for a job. The data is cached for completed jobs to improve performance.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            Tree view status data as a dictionary

        Example:
            ```python
            api = ProverOutputAPI()
            tree_status = api.get_treeview_status("12345678")
            print(f"Tree status: {tree_status}")
            ```
        """
        job_identifier = self._extract_job_identifier(job_input)
        return self._get_tree_view_status(job_identifier)

    def _get_tree_view_status(self, job_identifier: str) -> Dict[str, Any]:
        """
        Get tree view status data with caching for completed jobs.

        Internal method - use get_treeview_status() for the public API.
        Only caches treeViewStatus.json if the job is not running.

        Args:
            job_identifier: Job ID or local emv-* path

        Returns:
            Tree view status data
        """
        # Check cache first (only for remote jobs)
        cache_key = "treeViewStatus.json"
        if self.cache and not self.use_local:
            cached_data = self.cache.get("tree_view_status", job_identifier, cache_key)
            if cached_data:
                self.logger.debug(f"Using cached treeViewStatus for job {job_identifier}")
                return cached_data

        # Fetch the data
        tree_data = self.data_fetcher.fetch_tree_view_data(
            job_identifier, path="treeViewStatus.json"
        )

        # Cache if job is not running (only for remote jobs)
        if self.cache and not self.use_local:
            # Check if job is running by looking for finish_time in the tree data
            # or by calling is_job_running
            try:
                # Get job info to check if it's running
                raw_output = self.data_fetcher.fetch_raw_output(job_identifier)
                is_running = raw_output.get("finish_time") is None

                if not is_running:
                    self.logger.debug(f"Caching treeViewStatus for completed job {job_identifier}")
                    self.cache.set("tree_view_status", tree_data, job_identifier, cache_key)
                else:
                    self.logger.debug(
                        f"Not caching treeViewStatus for running job {job_identifier}"
                    )
            except Exception as e:
                # If we can't determine job status, don't cache
                self.logger.debug(f"Could not determine job status for caching: {e}")

        return tree_data

    def fetch_output(self, job_input: str) -> Dict[str, Any]:
        """
        Fetch and parse prover output from either a job URL, job ID, or local emv-* path.

        This method is kept for backward compatibility.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            Parsed output data as a dictionary

        Raises:
            ProverAPIError: If API call fails
        """
        job_identifier = self._extract_job_identifier(job_input)
        self.logger.info(f"Fetching output for job: {job_identifier}")

        try:
            raw_output = self.data_fetcher.fetch_raw_output(job_identifier)
            parsed_output = self.parser.parse(raw_output)
            return parsed_output

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch output for job {job_identifier}: {e}")

    def get_violated_rules(self, job_input: str) -> List[CheckResult]:
        """
        Get all violated rules for a job with assert messages.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            List of ViolationInfo objects for violated rules
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            self._set_default_contract(job_identifier)
            tree_data = self._get_tree_view_status(job_identifier)
            violations = self.tree_parser.parse_violations(tree_data)
            return violations

        except Exception as e:
            raise ProverAPIError(f"Failed to get violated rules for job {job_identifier}: {e}")

    def get_all_checks(self, job_input: str, include_rule_not_vacuous: bool = False) -> List[CheckResult]:
        """
        Get all checks (both successful and failed) for a job.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            include_rule_not_vacuous: If True, include rule_not_vacuous nodes and their descendants.

        Returns:
            List of ViolationInfo objects for all checks
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            self._set_default_contract(job_identifier)
            tree_data = self._get_tree_view_status(job_identifier)
            all_checks = self.tree_parser.parse_all_checks(tree_data, include_rule_not_vacuous=include_rule_not_vacuous)
            return all_checks

        except Exception as e:
            raise ProverAPIError(f"Failed to get all checks for job {job_identifier}: {e}")

    def get_leaf_checks(self, job_input: str) -> List[CheckResult]:
        """
        Get only leaf checks (actual assertions without intermediate tree nodes) for a job.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            List of CheckResult objects for leaf checks only
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            self._set_default_contract(job_identifier)
            tree_data = self._get_tree_view_status(job_identifier)
            leaf_checks = self.tree_parser.parse_leaf_checks(tree_data)
            return leaf_checks

        except Exception as e:
            raise ProverAPIError(f"Failed to get leaf checks for job {job_identifier}: {e}")

    def fetch_treeview_output_by_filename(self, job_input: str, filename: str) -> Dict[str, Any]:
        """
        Fetch a specific tree view output file by filename.

        This is a public API method that retrieves individual output files from
        the tree-view data, such as rule outputs, calltraces, or other JSON files.
        The data is cached for completed jobs to improve performance.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            filename: Filename within tree-view (e.g., 'rule_output_58.json', 'dap_calltrace_56-certora-dap.json')

        Returns:
            Tree view output data as a dictionary

        Example:
            ```python
            api = ProverOutputAPI()

            # Fetch a rule output file
            rule_output = api.fetch_treeview_output_by_filename("12345678", "rule_output_58.json")
            print(f"Rule data: {rule_output}")

            # Fetch a calltrace/DAP file
            dap_data = api.fetch_treeview_output_by_filename("12345678", "dap_calltrace_56-certora-dap.json")
            print(f"DAP data: {dap_data}")
            ```
        """
        job_identifier = self._extract_job_identifier(job_input)
        return self._fetch_tree_view_data_with_cache(job_identifier, filename)

    def _fetch_tree_view_data_with_cache(self, job_identifier: str, path: str) -> Dict[str, Any]:
        """
        Fetch tree view data with caching support.

        Internal method - use fetch_treeview_output_by_filename() for the public API.
        Handles caching logic for tree view data fetches.
        Checks bulk cache first, then individual cache, then API.

        Args:
            job_identifier: Job ID or local emv-* path
            path: Path within tree-view (e.g., 'rule_output_58.json')

        Returns:
            Tree view data
        """
        # Check bulk cache first (disk-based)
        if not self.use_local:
            bulk_cache_dir = self._get_bulk_cache_dir(job_identifier)
            bulk_file_path = bulk_cache_dir / path
            if bulk_file_path.exists():
                try:
                    with open(bulk_file_path, 'r') as f:
                        data = json.load(f)
                    self.logger.debug(f"Using bulk cache for {path} in job {job_identifier}")
                    return data
                except Exception as e:
                    self.logger.warning(f"Failed to read bulk cache file {bulk_file_path}: {e}")

        # Check individual hash-based cache
        cache_key = f"tree_view:{path}"

        if self.cache and not self.use_local:
            cached_data = self.cache.get("tree_view_data", job_identifier, cache_key)
            if cached_data:
                self.logger.debug(f"Using cached tree view data for {path} in job {job_identifier}")
                return cached_data

        # Fetch from API if not cached
        data = self.data_fetcher.fetch_tree_view_data(job_identifier, path=path)

        # Cache for completed jobs (rule outputs and calltraces are immutable once job completes)
        if self.cache and not self.use_local and data:
            try:
                # Check if job is completed before caching
                raw_output = self.data_fetcher.fetch_raw_output(job_identifier)
                is_running = raw_output.get("finish_time") is None

                if not is_running:
                    self.logger.debug(
                        f"Caching tree view data for {path} in completed job {job_identifier}"
                    )
                    self.cache.set("tree_view_data", data, job_identifier, cache_key)
            except Exception:
                # If we can't determine job status, cache anyway for rule outputs
                # (they're immutable and won't change)
                if path.startswith("rule_output") or path.endswith(".json"):
                    self.logger.debug(f"Caching tree view data for {path}")
                    self.cache.set("tree_view_data", data, job_identifier, cache_key)

        return data

    def get_calltrace(self, job_input: str, output_file: str) -> CalltraceInfo:
        """
        Get calltrace data for a specific rule using its output file path.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            output_file: Output file path from the violation's output field

        Returns:
            CalltraceInfo object with wrapped calltrace data
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            calltrace_data = self._fetch_tree_view_data_with_cache(job_identifier, output_file)
            return CalltraceInfo(
                job_id=job_identifier,
                output_file=output_file,
                trace_data=calltrace_data,
            )

        except Exception as e:
            raise ProverAPIError(
                f"Failed to get calltrace for output file {output_file} in job {job_identifier}: {e}"
            )

    def get_calltrace_for_violation(self, job_input: str, violation: CheckResult) -> CalltraceInfo:
        """
        Get calltrace data for a specific violation using its output files.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            violation: ViolationInfo object

        Returns:
            CalltraceInfo object, or raises error if no output files
        """
        if not violation.output_files:
            raise ProverAPIError("No output files available for this violation")

        # Use the first output file (there might be multiple)
        output_file = violation.output_files[0]
        calltrace = self.get_calltrace(job_input, output_file)
        calltrace.rule_name = violation.rule_name
        return calltrace

    def get_breadcrumbs(self, job_input: str, dap_file: str) -> BreadcrumbInfo:
        """
        Get breadcrumb trace summary from a DAP file with caching.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            dap_file: DAP file path (e.g., 'dap_calltrace_56-certora-dap.json')

        Returns:
            BreadcrumbInfo object with execution trace
        """
        job_identifier = self._extract_job_identifier(job_input)

        # Check cache first
        if self.cache:
            cached_data = self.cache.get("get_breadcrumbs", job_identifier, dap_file)
            if cached_data:
                self.logger.debug(
                    f"Using cached breadcrumbs for {dap_file} in job {job_identifier}"
                )
                return BreadcrumbInfo.from_dict(cached_data, dap_file=dap_file)

        try:
            dap_data = self.data_fetcher.fetch_tree_view_data(job_identifier, path=dap_file)
            breadcrumbs_data = self.breadcrumb_parser.parse_dap_file(dap_data)

            # Cache the result
            if self.cache:
                self.cache.set("get_breadcrumbs", breadcrumbs_data, job_identifier, dap_file)

            return BreadcrumbInfo.from_dict(breadcrumbs_data, dap_file=dap_file)

        except Exception as e:
            raise ProverAPIError(
                f"Failed to get breadcrumbs from DAP file {dap_file} in job {job_identifier}: {e}"
            )

    def get_breadcrumbs_for_violation(
        self, job_input: str, violation: CheckResult
    ) -> BreadcrumbInfo:
        """
        Get breadcrumb trace summary for a specific violation using its debug trace file.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            violation: ViolationInfo object

        Returns:
            BreadcrumbInfo object with execution trace
        """
        if not violation.debug_trace_file:
            raise ProverAPIError("No debug trace file available for this violation")

        return self.get_breadcrumbs(job_input, violation.debug_trace_file)

    def get_call_resolutions(self, job_input: str) -> List[CallResolutionInfo]:
        """
        Get call resolution information from the globalCallResolution field.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            List of CallResolutionInfo objects
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            tree_data = self._get_tree_view_status(job_identifier)
            call_resolutions = self.tree_parser.parse_call_resolutions(tree_data)
            return call_resolutions

        except Exception as e:
            raise ProverAPIError(f"Failed to get unresolved calls for job {job_identifier}: {e}")

    def get_tree_view_data(self, job_input: str) -> TreeViewData:
        """
        Get wrapped tree-view data for a job.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            TreeViewData object
        """
        job_identifier = self._extract_job_identifier(job_input)
        raw_data = self._get_tree_view_status(job_identifier)
        return TreeViewData.from_dict(raw_data, job_identifier)

    def get_job_status(self, job_input: str) -> JobStatus:
        """
        Get the status of a job without fetching full output.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            JobStatus enum value
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            raw_output = self.data_fetcher.fetch_raw_output(job_identifier)
            status_str = raw_output.get("job_status", "unknown")
            return convert_job_status(status_str)
        except Exception as e:
            raise ProverAPIError(f"Failed to get status for job {job_identifier}: {e}")

    def get_job_info(self, job_input: str) -> JobInfo:
        """
        Get comprehensive job information.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            JobInfo object with job details
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            raw_output = self.data_fetcher.fetch_raw_output(job_identifier)
            status_str = raw_output.get("job_status", "unknown")
            return JobInfo(
                job_id=job_identifier,
                status=convert_job_status(status_str),
                start_time=raw_output.get("start_time"),
                finish_time=raw_output.get("finish_time"),
                user_id=raw_output.get("user_id"),
                project=raw_output.get("project"),
                contract=raw_output.get("contract"),
                raw_data=raw_output,
            )
        except Exception as e:
            raise ProverAPIError(f"Failed to get job info for {job_identifier}: {e}")

    def is_job_running(self, job_input: str) -> bool:
        """
        Check if a job is still running by checking if finish_time is null.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            True if job is still running, False if completed
        """
        job_info = self.get_job_info(job_input)
        return job_info.is_running

    def list_recent_jobs(
        self,
        days_back: int = 7,
        limit: int = 100,
        all_users: bool = True,
    ) -> List[JobInfo]:
        """
        List recent jobs from the data API.

        Args:
            days_back: How many days back to look (default: 7).
            limit: Max jobs to return (default: 100, the API caps page size at 100).
            all_users: Include all users' jobs (default: True). False = my jobs only.

        Returns:
            List of JobInfo objects.

        Raises:
            ProverAPIError: If configured for local use or the API call fails.
        """
        if self.use_local:
            raise ProverAPIError(
                "list_recent_jobs is not supported when using local prover outputs"
            )

        created_after = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat()
        raw_jobs = self.data_fetcher.list_recent_jobs(
            created_after=created_after,
            limit=limit,
            all_users=all_users,
        )
        return [JobInfo.from_dict(job_data) for job_data in raw_jobs]

    def cancel_jobs(self, job_inputs: List[str]) -> Dict[str, Any]:
        """
        Cancel multiple jobs by their URLs or IDs.

        Args:
            job_inputs: List of job URLs or job IDs to cancel

        Returns:
            API response data with cancellation results

        Raises:
            ProverAPIError: If cancellation fails or configured for local use
        """
        if self.use_local:
            raise ProverAPIError("cancel_jobs is not supported when using local prover outputs")

        # Extract job IDs from URLs or use IDs directly
        job_ids = []
        for job_input in job_inputs:
            try:
                job_id = extract_job_id(job_input)
                job_ids.append(job_id)
            except Exception as e:
                self.logger.warning(f"Failed to extract job ID from {job_input}: {e}")
                # Skip invalid inputs rather than failing completely
                continue

        if not job_ids:
            raise ProverAPIError("No valid job IDs found to cancel")

        self.logger.info(f"Cancelling {len(job_ids)} jobs: {job_ids}")
        return self.data_fetcher.cancel_jobs(job_ids)

    def cancel_job(self, job_input: str) -> Dict[str, Any]:
        """
        Cancel a single job by its URL or ID.

        Args:
            job_input: Job URL or job ID to cancel

        Returns:
            API response data with cancellation results

        Raises:
            ProverAPIError: If cancellation fails or configured for local use
        """
        return self.cancel_jobs([job_input])

    def get_statsdata(self, job_input: str) -> Dict[str, Any]:
        """
        Get statsdata.json for a job.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            Stats data from statsdata.json

        Raises:
            ProverAPIError: If fetching fails
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            return self.data_fetcher.fetch_statsdata(job_identifier)
        except Exception as e:
            raise ProverAPIError(f"Failed to get statsdata for job {job_identifier}: {e}")

    def get_console_logs(self, job_input: str) -> str:
        """
        Get console logs for a job. This contains the full console output 
        including error messages like filtering errors.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            Console logs as a string

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found or logs are not available
            ProverAPIError: If API call fails or configured for local use
        """
        if self.use_local:
            raise ProverAPIError("get_console_logs is not supported when using local prover outputs")

        job_identifier = self._extract_job_identifier(job_input)

        try:
            return self.data_fetcher.fetch_console_logs(job_identifier)
        except Exception as e:
            raise ProverAPIError(f"Failed to get console logs for job {job_identifier}: {e}")

    def get_alert_report(self, job_input: str) -> List[Dict[str, Any]]:
        """
        Get raw alert report for a job. This contains prover alerts and messages.

        For typed alert objects, use get_alerts() instead.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            Alert report data as a list of raw alert dictionaries

        Raises:
            JobNotFoundError: If job is not found or alert report is not available
            ProverAPIError: If API call fails
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            return self.data_fetcher.fetch_alert_report(job_identifier)
        except Exception as e:
            raise ProverAPIError(f"Failed to get alert report for job {job_identifier}: {e}")

    def get_alerts(self, job_input: str) -> List[ParsedAlert]:
        """
        Get parsed alerts for a job with typed alert information.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            List of ParsedAlert objects with typed alert information

        Raises:
            JobNotFoundError: If job is not found or alert report is not available
            ProverAPIError: If API call fails
        """
        raw_alerts = self.get_alert_report(job_input)
        return [ParsedAlert.from_dict(alert) for alert in raw_alerts]

    def get_job_report(self, job_input: str) -> JobReport:
        """Analyze a job and return a structured report of its results.

        Covers call resolution, rule results, and alerts.
        """
        return JobAnalyzer(self).analyze(job_input)

    def who_am_i(self) -> Dict[str, Any]:
        """
        Get information about the currently authenticated user.

        Returns:
            User information including email, user ID, and other details

        Raises:
            AuthenticationError: If authentication fails
            ProverAPIError: If API call fails or configured for local use
        """
        if self.use_local:
            raise ProverAPIError("who_am_i is not supported when using local prover outputs")

        try:
            return self.data_fetcher.who_am_i()
        except Exception as e:
            raise ProverAPIError(f"Failed to get user information: {e}")

    def parse_tree_view_path(self, tree_view_path: str) -> List[str]:
        """
        Parse a treeViewPath field to extract the rule hierarchy.

        The treeViewPath is split by '-' to create a list representing
        the hierarchical structure of the rule.

        Args:
            tree_view_path: The treeViewPath string from rule_output files

        Returns:
            List of hierarchy levels extracted from the path

        Example:
            Input: "sanity-previewUnwindExercise(bytes32,uint256)-Satisfy_sanity_check_failed_(sanity_spec_11_5)-sanity check failed"
            Output: ["sanity", "previewUnwindExercise(bytes32,uint256)", "Satisfy_sanity_check_failed_(sanity_spec_11_5)", "sanity check failed"]
        """
        if not tree_view_path:
            return []

        # Split by '-' to get hierarchy levels
        hierarchy = tree_view_path.split("-")

        # Clean up any extra whitespace
        hierarchy = [level.strip() for level in hierarchy if level.strip()]

        return hierarchy

    def get_rule_hierarchy(self, job_input: str, output_file: str) -> List[str]:
        """
        Get the rule hierarchy from a rule output file's treeViewPath.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            output_file: Output file path (e.g., 'rule_output_58.json')

        Returns:
            List of hierarchy levels extracted from the treeViewPath

        Example:
            Returns ["sanity", "previewUnwindExercise(bytes32,uint256)",
                     "Satisfy_sanity_check_failed_(sanity_spec_11_5)", "sanity check failed"]
        """
        job_identifier = self._extract_job_identifier(job_input)

        try:
            # Use the cached fetch method
            rule_data = self._fetch_tree_view_data_with_cache(job_identifier, output_file)

            # Extract and parse the treeViewPath
            if isinstance(rule_data, dict) and "treeViewPath" in rule_data:
                return self.parse_tree_view_path(rule_data["treeViewPath"])

            return []

        except Exception as e:
            raise ProverAPIError(
                f"Failed to get rule hierarchy for {output_file} in job {job_identifier}: {e}"
            )

    # Backward compatibility methods that return raw dicts
    def _get_violated_rules_dict(self, job_input: str) -> List[Dict[str, Any]]:
        """Get violated rules as raw dictionaries (backward compatibility)."""
        violations = self.get_violated_rules(job_input)
        return [v.to_dict() for v in violations]

    def _get_all_checks_dict(self, job_input: str) -> List[Dict[str, Any]]:
        """Get all checks as raw dictionaries (backward compatibility)."""
        checks = self.get_all_checks(job_input)
        return [c.to_dict() for c in checks]

    def _get_leaf_checks_dict(self, job_input: str) -> List[Dict[str, Any]]:
        """Get leaf checks as raw dictionaries (backward compatibility)."""
        leaf_checks = self.get_leaf_checks(job_input)
        return [c.to_dict() for c in leaf_checks]

    # Compatibility methods for tests that use internal parsing methods
    def _parse_tree_view_for_all_checks(self, tree_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse tree-view data for all checks (backward compatibility for tests)."""
        # Create parser if not exists (for tests that bypass __init__)
        if not hasattr(self, "tree_parser"):
            from .tree_parser import TreeParser

            self.tree_parser = TreeParser()
        checks = self.tree_parser.parse_all_checks(tree_data)
        return [c.to_dict() for c in checks]

    def _parse_tree_view_for_violations(self, tree_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse tree-view data for VIOLATED_ASSERT nodes (backward compatibility for tests).

        Note: This returns only VIOLATED_ASSERT nodes, not all nodes with VIOLATED status.
        For all violated nodes, use parse_violations() directly.
        """
        # Create parser if not exists (for tests that bypass __init__)
        if not hasattr(self, "tree_parser"):
            from .tree_parser import TreeParser

            self.tree_parser = TreeParser()
        violations = self.tree_parser.parse_violated_asserts(tree_data)
        return [v.to_dict() for v in violations]

    def get_source_files(self, job_input: str) -> List[SourceFileNode]:
        """
        Get the source file tree for a job.

        Args:
            job_input: Job URL, job ID, or local emv-* path

        Returns:
            List of SourceFileNode objects representing the file tree

        Raises:
            ProverAPIError: If API call fails
        """
        job_identifier = self._extract_job_identifier(job_input)
        self.logger.info(f"Fetching source files for job: {job_identifier}")
        raw_data = self.data_fetcher.fetch_source_files_list(job_identifier)
        return SourceFileNode.from_list(raw_data)

    def get_source_file_content(self, job_input: str, path: str) -> str:
        """
        Get the content of a specific source file for a job.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            path: Path to the source file (e.g. ".certora_sources/src/Contract.sol")

        Returns:
            Raw file content as a string

        Raises:
            ProverAPIError: If API call fails
        """
        job_identifier = self._extract_job_identifier(job_input)
        self.logger.info(f"Fetching source file {path} for job: {job_identifier}")
        return self.data_fetcher.fetch_source_file_content(job_identifier, path)

    def fetch_custom_endpoint(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Fetch data from an arbitrary user-provided endpoint.

        Args:
            endpoint: The full URL endpoint to fetch from
            params: Optional query parameters (for GET/DELETE) or request body (for POST/PUT)
            method: HTTP method (GET, POST, PUT, DELETE)

        Returns:
            API response data

        Raises:
            ProverAPIError: If configured for local use or if API call fails
            AuthenticationError: If authentication fails
        """
        if self.use_local:
            raise ProverAPIError(
                "fetch_custom_endpoint is not supported when using local prover outputs"
            )

        try:
            return self.data_fetcher.fetch_custom_endpoint(endpoint, params, method)
        except Exception as e:
            raise ProverAPIError(f"Failed to fetch from custom endpoint {endpoint}: {e}")

    def download_job_outputs(self, job_input: str) -> Dict[str, Any]:
        """
        Download and extract all output files for a job using bulk tar.gz download.
        
        This method downloads the entire job output archive and extracts individual
        JSON files to disk cache. Subsequent calls to get_rule_hierarchy, get_calltrace, 
        etc. will read from local disk instead of making individual API calls.
        
        Args:
            job_input: Job URL, job ID, or local emv-* path
        
        Returns:
            Dictionary with download statistics:
            {
                'files_extracted': 123,
                'download_size_mb': 30.4,
                'download_time_s': 4.22,
                'extraction_time_s': 1.15,
                'cache_dir': '/path/to/cache'
            }
        
        Raises:
            ProverAPIError: If configured for local use or if download fails
        """
        if self.use_local:
            raise ProverAPIError(
                "download_job_outputs is not supported when using local prover outputs"
            )
        
        job_identifier = self._extract_job_identifier(job_input)
        
        # Check if already downloaded
        cache_dir = self._get_bulk_cache_dir(job_identifier)
        if cache_dir.exists():
            existing_files = list(cache_dir.glob("*.json"))
            if existing_files:
                self.logger.info(f"Job outputs already cached for {job_identifier} ({len(existing_files)} files)")
                return {
                    'files_extracted': len(existing_files),
                    'download_size_mb': 0,
                    'download_time_s': 0,
                    'extraction_time_s': 0,
                    'cache_hit': True,
                    'cache_dir': str(cache_dir)
                }
        
        self.logger.info(f"Downloading bulk outputs for job {job_identifier}")
        
        try:
            import time
            
            # Download tar.gz using data_fetcher
            start_download = time.time()
            tar_content = self.data_fetcher.fetch_outputs(job_identifier)
            download_time = time.time() - start_download
            download_size_mb = len(tar_content) / (1024 * 1024)
            
            # Create cache directory
            cache_dir = self._get_bulk_cache_dir(job_identifier)
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract tar.gz directly to disk
            start_extraction = time.time()
            files_extracted = 0
            
            with tarfile.open(fileobj=io.BytesIO(tar_content), mode='r:gz') as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith('.json'):
                        try:
                            # Extract file content
                            file_obj = tar.extractfile(member)
                            if file_obj:
                                content = file_obj.read().decode('utf-8')
                                # Validate JSON
                                json_data = json.loads(content)
                                
                                # Save to disk with just filename
                                filename = os.path.basename(member.name)
                                file_path = cache_dir / filename
                                
                                with open(file_path, 'w') as f:
                                    json.dump(json_data, f, indent=2, default=str)
                                
                                files_extracted += 1
                                
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            self.logger.warning(f"Skipping invalid file {member.name}: {e}")
                            continue
            
            extraction_time = time.time() - start_extraction
            
            self.logger.info(
                f"Downloaded {files_extracted} files for job {job_identifier} "
                f"({download_size_mb:.1f}MB in {download_time:.2f}s + {extraction_time:.2f}s extraction)"
            )
            
            return {
                'files_extracted': files_extracted,
                'download_size_mb': download_size_mb,
                'download_time_s': download_time,
                'extraction_time_s': extraction_time,
                'cache_hit': False,
                'cache_dir': str(cache_dir)
            }
            
        except Exception as e:
            raise ProverAPIError(f"Failed to download job outputs for {job_identifier}: {e}")

    def _fetch_outputs_cached(self, job_identifier: str) -> bytes:
        """Fetch the job outputs tar with disk-level caching.

        Caches the raw tar bytes in bulk_cache/job_{id}/outputs.tar.gz so subsequent
        calls for the same job skip the network fetch.
        """
        cache_dir = self._get_bulk_cache_dir(job_identifier)
        tar_path = cache_dir / "outputs.tar.gz"
        if tar_path.exists():
            return tar_path.read_bytes()
        tar_content = self.data_fetcher.fetch_outputs(job_identifier)
        cache_dir.mkdir(parents=True, exist_ok=True)
        tar_path.write_bytes(tar_content)
        return tar_content

    def extract_unsat_core_files(self, job_input: str, dest_dir: Path) -> List[Path]:
        """Extract UnsatCoreTAC*.txt files into dest_dir.

        Uses unsat_core_map.json to fetch only the referenced files; falls back to the
        full output tar when the map is absent. No filtering is applied — the caller is
        responsible for any filtering.

        Returns list of extracted file paths.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        core_map = self.unsat_core_map(job_input)
        if core_map:
            filenames = sorted({f for files in core_map.values() for f in files})
            extracted: List[Path] = []
            for name in filenames:
                file_dest = dest_dir / Path(name).name
                file_dest.write_text(self.fetch_output_file(job_input, name), encoding="utf-8")
                extracted.append(file_dest)
            return extracted
        return self._extract_unsat_core_files_from_tar(job_input, dest_dir)

    def _extract_unsat_core_files_from_tar(self, job_input: str, dest_dir: Path) -> List[Path]:
        job_identifier = self._extract_job_identifier(job_input)
        dest_dir.mkdir(parents=True, exist_ok=True)
        tar_content = self._fetch_outputs_cached(job_identifier)
        extracted: List[Path] = []
        with tarfile.open(fileobj=io.BytesIO(tar_content), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                parts = Path(member.name).parts
                name = parts[-1]
                if "Reports" in parts and name.startswith("UnsatCoreTAC") and name.endswith(".txt"):
                    file_dest = dest_dir / name
                    file_obj = tar.extractfile(member)
                    if file_obj:
                        file_dest.write_bytes(file_obj.read())
                        extracted.append(file_dest)
        return extracted

    def fetch_output_file(self, job_input: str, rel_path: str) -> str:
        """Fetch the raw text of a Reports/-relative output file (e.g. 'unsat_core_map.json')."""
        job_identifier = self._extract_job_identifier(job_input)
        return self.data_fetcher.fetch_output_file(job_identifier, rel_path)

    def unsat_core_map(self, job_input: str) -> Dict[str, List[str]]:
        """The job's `{ ruleId -> [UnsatCoreTAC .txt filenames] }` map, or {} if the job has none."""
        try:
            content = self.fetch_output_file(job_input, "unsat_core_map.json")
        except JobNotFoundError:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ProverAPIError(f"Failed to parse unsat_core_map.json for {job_input}: {e}")

    def unsat_core_filenames(self, job_input: str, rule_id: str) -> List[str]:
        """UnsatCoreTAC .txt filenames for a rule (by its treeView ruleId); [] if none."""
        return self.unsat_core_map(job_input).get(rule_id, [])

    def read_unsat_cores(self, job_input: str, rule_id: str) -> List[str]:
        """Contents of a rule's UnsatCoreTAC .txt dumps (by its treeView ruleId)."""
        return [self.fetch_output_file(job_input, name) for name in self.unsat_core_filenames(job_input, rule_id)]

    def extract_certora_sources(self, job_input: str, dest_dir: Path) -> None:
        """Extract the .certora_sources tree from the job output tar into dest_dir.

        The tree structure rooted at .certora_sources is preserved under dest_dir.
        """
        job_identifier = self._extract_job_identifier(job_input)
        tar_content = self._fetch_outputs_cached(job_identifier)
        with tarfile.open(fileobj=io.BytesIO(tar_content), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                parts = Path(member.name).parts
                if ".certora_sources" in parts:
                    src_idx = parts.index(".certora_sources")
                    rel = Path(*parts[src_idx:])
                    file_dest = dest_dir / rel
                    file_dest.parent.mkdir(parents=True, exist_ok=True)
                    file_obj = tar.extractfile(member)
                    if file_obj:
                        file_dest.write_bytes(file_obj.read())

    # ---------------------------------------------------------------------------
    # High-level fetch methods (no tarball download)
    # ---------------------------------------------------------------------------

    def fetch_job_sources(self, job_input: str, dest_dir: Path, max_workers: int = 8) -> Path:
        """Download all source files for a job into dest_dir/inputs/.certora_sources/.

        Uses the source-files API to fetch individual files in parallel, avoiding
        the need to download the full job output tarball.

        Files are only downloaded once — if the marker file .source_fetch_complete
        exists, the download is skipped.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            dest_dir: Base directory for the report layout
            max_workers: Number of parallel download threads (default: 8)

        Returns:
            dest_dir (unchanged, for chaining)
        """
        job_identifier = self._extract_job_identifier(job_input)
        sources_dir = dest_dir / "inputs" / ".certora_sources"
        marker = sources_dir / ".source_fetch_complete"

        # Per-job lock prevents concurrent threads from writing the same files
        with _get_fetch_lock(f"sources_{job_identifier}"):
            if marker.exists():
                self.logger.info(f"Source files already fetched for {dest_dir}")
                return dest_dir

            sources_dir.mkdir(parents=True, exist_ok=True)

            file_tree = self.get_source_files(job_input)
            all_files = _flatten_source_file_tree(file_tree)

            certora_prefix = ".certora_sources/"
            source_files = [
                (api_path[len(certora_prefix):], api_path)
                for _, api_path in all_files
                if api_path.startswith(certora_prefix)
            ]

            if not source_files:
                self.logger.warning(f"No source files found for job {job_identifier}")
                marker.touch()
                return dest_dir

            def _fetch_one(item: tuple) -> None:
                rel_path, api_path = item
                content = self.get_source_file_content(job_input, api_path)
                file_path = sources_dir / rel_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                list(pool.map(_fetch_one, source_files))

            marker.touch()
            self.logger.info(f"Fetched {len(source_files)} source files to {sources_dir}")
            return dest_dir

    def fetch_job_treeview(self, job_input: str, dest_dir: Path, max_workers: int = 8) -> Path:
        """Download treeview status and all output files into dest_dir/Reports/treeView/.

        Uses the tree-view API to fetch the treeViewStatus and individual output files
        in parallel, avoiding the need to download the full job output tarball.

        Files are only downloaded once — if treeViewStatus_0.json exists, the download
        is skipped.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            dest_dir: Base directory for the report layout
            max_workers: Number of parallel download threads (default: 8)

        Returns:
            dest_dir (unchanged, for chaining)
        """
        job_identifier = self._extract_job_identifier(job_input)
        treeview_dir = dest_dir / "Reports" / "treeView"
        status_file = treeview_dir / "treeViewStatus_0.json"

        # Per-job lock prevents concurrent threads from writing the same files
        with _get_fetch_lock(f"treeview_{job_identifier}"):
            if status_file.exists():
                self.logger.info(f"Treeview data already fetched for {dest_dir}")
                return dest_dir

            treeview_dir.mkdir(parents=True, exist_ok=True)

            tree_status = self.get_treeview_status(job_input)

            output_files = _collect_treeview_output_files(tree_status)

            def _fetch_one(filename: str) -> Optional[str]:
                try:
                    file_data = self.fetch_treeview_output_by_filename(job_input, filename)
                    output_path = treeview_dir / filename
                    with open(output_path, "w") as f:
                        json.dump(file_data, f, indent=2)
                    return None
                except Exception as e:
                    return f"Warning: Failed to fetch {filename}: {e}"

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                for error in pool.map(_fetch_one, output_files):
                    if error:
                        self.logger.warning(error)

            # Write status file last — acts as the completion marker
            with open(status_file, "w") as f:
                json.dump(tree_status, f, indent=2)

            self.logger.info(f"Fetched treeview + {len(output_files)} output files to {treeview_dir}")
            return dest_dir

    def fetch_sources_and_treeview_files(self, job_input: str, dest_dir: Path, max_workers: int = 8) -> Path:
        """Download source files and treeview data into a report directory layout.

        Combines fetch_job_sources() and fetch_job_treeview() into a single call.
        The resulting directory layout matches what tarball extraction produces::

            dest_dir/
              inputs/.certora_sources/   <- contract source files
              Reports/treeView/          <- treeview status + output JSONs

        This is a drop-in replacement for downloading and extracting the full job
        output tarball when only source files and treeview data are needed.

        Args:
            job_input: Job URL, job ID, or local emv-* path
            dest_dir: Base directory for the report layout
            max_workers: Number of parallel download threads (default: 8)

        Returns:
            dest_dir (for use as the ``folder`` argument to AIComposer analysis)
        """
        self.fetch_job_sources(job_input, dest_dir, max_workers=max_workers)
        self.fetch_job_treeview(job_input, dest_dir, max_workers=max_workers)
        return dest_dir

    def _get_bulk_cache_dir(self, job_identifier: str) -> Path:
        """Get the bulk cache directory for a specific job."""
        if self.cache:
            base_dir = self.cache.cache_dir.parent / "bulk_cache"
        else:
            # Fallback if no regular cache enabled
            base_dir = Path.cwd() / ".certora_internal" / "bulk_cache"
        
        return base_dir / f"job_{job_identifier}"
