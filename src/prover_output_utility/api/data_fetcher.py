# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Low-level data fetching utilities for the Prover API.
"""
import functools
import json
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

import requests

from ..auth import LoginEnv, resolve_login_env
from ..exceptions import AuthenticationError, JobNotFoundError, ProverAPIError
from .base_data_fetcher import BaseDataFetcher

T = TypeVar("T")


# Per-environment data-api hosts. Kept in sync with the Certora login envs
# `resolve_login_env()` understands: AISS_ENV / GITHUB_ENVIRONMENT.
_API_BASE_URL_BY_ENV: Dict[LoginEnv, str] = {
    "prod": "https://data-api.certora.com",
    "stg": "https://data-api-stg.certora.com",
    "dev": "https://data-api-dev.certora.com",
}


def default_api_base_url() -> str:
    """Return the data-api base URL for the current Certora login env.

    Resolution mirrors :func:`prover_output_utility.auth.resolve_login_env` —
    ``AISS_ENV`` takes precedence; otherwise ``GITHUB_ENVIRONMENT`` maps to
    stg/dev; otherwise prod. Callers that need a specific host should pass
    ``api_base_url=`` to the constructor explicitly.

    Public so callers (e.g. job-listing tooling) can resolve the env-aware
    data-api host without re-deriving the env→host mapping or constructing a
    (auth-triggering) ``ProverOutputAPI``.
    """
    return _API_BASE_URL_BY_ENV[resolve_login_env()]


# Per-environment Prover web-UI hosts (what `--server` resolves to in
# certoraUtils.SupportedServers). Distinct from the data-api hosts above:
# prod is prover.certora.com, not data-api.certora.com.
_PROVER_BASE_URL_BY_ENV: Dict[LoginEnv, str] = {
    "prod": "https://prover.certora.com",
    "stg": "https://vaas-stg.certora.com",
    "dev": "https://vaas-dev.certora.com",
}


def _default_prover_base_url() -> str:
    """Return the Prover web-UI base URL for the current Certora login env.

    Same env resolution as :func:`default_api_base_url`, but for the
    user-facing Prover host used in shareable links (e.g. group-summary URLs).
    """
    return _PROVER_BASE_URL_BY_ENV[resolve_login_env()]


def handle_token_expiration(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to handle token expiration and retry with re-authentication."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs) -> T:
        try:
            return func(self, *args, **kwargs)
        except AuthenticationError as e:
            # Check if this is a token expiration error (401 response)
            if "401" in str(e) or "Authentication failed" in str(e):
                # Only retry once
                if not getattr(self, "_retry_auth", False):
                    self._retry_auth = True
                    try:
                        # Get the API instance and force re-login
                        if hasattr(self, "_api_instance"):
                            self._api_instance._setup_session(force_relogin=True)
                            # Update our session reference
                            self.session = self._api_instance.session
                        # Retry the original request
                        result = func(self, *args, **kwargs)
                        self._retry_auth = False
                        return result
                    finally:
                        self._retry_auth = False
            raise

    return wrapper


class DataFetcher(BaseDataFetcher):
    """Handles low-level data fetching from Certora API endpoints."""

    # API URLs by environment. Kept as class attributes for back-compat with
    # callers that referenced them directly; the canonical lookup is
    # ``_API_BASE_URL_BY_ENV`` at module level.
    PRODUCTION_API_BASE_URL = _API_BASE_URL_BY_ENV["prod"]
    STAGING_API_BASE_URL = _API_BASE_URL_BY_ENV["stg"]
    DEV_API_BASE_URL = _API_BASE_URL_BY_ENV["dev"]

    def __init__(
        self,
        session: requests.Session,
        api_instance=None,
        api_base_url: Optional[str] = None,
    ):
        """
        Initialize the data fetcher.

        Args:
            session: Configured requests session with authentication
            api_instance: Reference to the ProverOutputAPI instance for re-auth
            api_base_url: API base URL. When None (the default), resolve from
                          the Certora login env (``AISS_ENV`` / ``GITHUB_ENVIRONMENT``,
                          via :func:`resolve_login_env`) — dev → data-api-dev,
                          stg → data-api-stg, prod → data-api. Pass an explicit
                          URL to override.
        """
        self.session = session
        # Resolve inside the body so callers picking up `AISS_ENV` at runtime get
        # the right host; the previous `= PRODUCTION_API_BASE_URL` default was
        # bound at class-definition time and could not be retargeted.
        self.api_base_url = api_base_url if api_base_url is not None else default_api_base_url()
        self._api_instance = api_instance
        self._retry_auth = False

    @classmethod
    def get_api_base_url_for_prover_url(cls, prover_url: str) -> str:
        """
        Get the appropriate API base URL for a prover output URL.

        Dev jobs (vaas-dev.certora.com) use data-api-dev.certora.com,
        staging jobs (vaas-stg.certora.com) use data-api-stg.certora.com,
        production jobs use data-api.certora.com.

        Args:
            prover_url: Full prover URL (e.g., "https://vaas-stg.certora.com/output/...")

        Returns:
            Appropriate API base URL for API calls
        """
        if "vaas-dev.certora.com" in prover_url:
            return cls.DEV_API_BASE_URL
        if "vaas-stg.certora.com" in prover_url:
            return cls.STAGING_API_BASE_URL
        return cls.PRODUCTION_API_BASE_URL

    def _execute_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """
        Execute HTTP request with method dispatch.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: Full URL endpoint
            params: Query parameters (for GET/DELETE)
            json_data: JSON body data (for POST/PUT)

        Returns:
            requests.Response object

        Raises:
            ProverAPIError: If HTTP method is unsupported
        """
        if method.upper() == "GET":
            return self.session.get(endpoint, params=params)
        elif method.upper() == "POST":
            return self.session.post(endpoint, json=json_data)
        elif method.upper() == "PUT":
            return self.session.put(endpoint, json=json_data)
        elif method.upper() == "DELETE":
            return self.session.delete(endpoint, params=params)
        else:
            raise ProverAPIError(f"Unsupported HTTP method: {method}")

    @handle_token_expiration
    def fetch_raw_output(self, job_identifier: str) -> Dict[str, Any]:
        """
        Fetch raw output data from the prover API.

        Args:
            job_identifier: Job ID to fetch

        Returns:
            Raw API response data

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs/{job_identifier}"

        try:
            response = self.session.get(endpoint)

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Job {job_identifier} not found")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch job data for {job_identifier}: {e}")

    @handle_token_expiration
    def fetch_tree_view_data(
        self, job_identifier: str, path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch tree-view data for a job.

        Args:
            job_identifier: Job ID to fetch
            path: Optional path within the tree-view

        Returns:
            Tree-view data

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs/{job_identifier}/tree-view"

        params = {}
        if path:
            params["path"] = path

        try:
            response = self.session.get(endpoint, params=params)

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Tree-view data not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch tree-view data for {job_identifier}: {e}")

    def fetch_statsdata(self, job_identifier: str) -> Dict[str, Any]:
        """Fetch statsdata.json for a job."""
        return cast(Dict[str, Any], json.loads(self.fetch_output_file(job_identifier, "statsdata.json")))

    @handle_token_expiration
    def fetch_output_file(self, job_identifier: str, rel_path: str) -> str:
        """Fetch the raw text of a Reports/-relative output file (e.g. unsat_core_map.json)."""
        endpoint = f"{self.api_base_url}/v1/domain/jobs/{job_identifier}/f/{rel_path}"

        try:
            response = self.session.get(endpoint)

            if response.status_code == 200:
                return response.text
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Output file not found for job {job_identifier}: {rel_path}")
            else:
                response.raise_for_status()
                return response.text

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch output file {rel_path} for {job_identifier}: {e}")

    def fetch_outputs(self, job_identifier: str) -> bytes:
        """
        Fetch outputs archive (tar.gz) for a job.

        Args:
            job_identifier: Job ID to fetch

        Returns:
            Raw tar.gz content as bytes

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs/{job_identifier}/f/outputs"

        try:
            response = self.session.get(endpoint)

            if response.status_code == 200:
                return response.content
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Outputs not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return response.content

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch outputs for {job_identifier}: {e}")

    @handle_token_expiration
    def list_recent_jobs(
        self,
        created_after: str,
        limit: int = 100,
        all_users: bool = True,
    ) -> List[Dict[str, Any]]:
        """List recent jobs from the data API.

        See BaseDataFetcher.list_recent_jobs for parameter docs.
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs"

        try:
            response = self._execute_request("GET", endpoint, params={
                "currentPage": 1,
                # API caps page size at 100 per response, so don't request more
                "pageSize": min(limit, 100),
                "sortOrder": "desc",
                "allUsers": "true" if all_users else "false",
                "createdAfter": created_after,
                "deleted": "false",
            })

            if response.status_code == 200:
                return cast(List[Dict[str, Any]], response.json().get("items", []))
            else:
                raise ProverAPIError(
                    f"Failed to list recent jobs (status {response.status_code}): "
                    f"{response.text[:200]}"
                )

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to list recent jobs: {e}")

    @handle_token_expiration
    def fetch_group_jobs(
        self, group_id: str, created_after: str, created_before: str
    ) -> List[Dict[str, Any]]:
        """Fetch all jobs in a group from the data API."""
        endpoint = f"{self.api_base_url}/v1/domain/jobs"

        try:
            response = self._execute_request("GET", endpoint, params={
                "groupIds": group_id,
                "pageSize": 200,
                "createdAfter": created_after,
                "createdBefore": created_before,
                "allUsers": "true",
            })

            if response.status_code == 200:
                return cast(List[Dict[str, Any]], response.json().get("items", []))
            else:
                raise ProverAPIError(
                    f"Failed to fetch group jobs (status {response.status_code}): "
                    f"{response.text[:200]}"
                )

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch group jobs: {e}")

    @handle_token_expiration
    def cancel_jobs(self, job_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel multiple jobs by their IDs.

        Args:
            job_ids: List of job IDs to cancel

        Returns:
            API response data

        Raises:
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs/cancel"
        payload = {"ids": job_ids}

        try:
            response = self.session.post(endpoint, json=payload)

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError("Cancel endpoint not found")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to cancel jobs {job_ids}: {e}")

    @handle_token_expiration
    def fetch_console_logs(self, job_identifier: str) -> str:
        """
        Fetch console logs for a job.

        Args:
            job_identifier: Job ID to fetch logs for

        Returns:
            Console logs as a string

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs/{job_identifier}/logs"

        try:
            response = self.session.get(endpoint)

            if response.status_code == 200:
                return response.text
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Console logs not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return response.text

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch console logs for {job_identifier}: {e}")

    @handle_token_expiration
    def who_am_i(self) -> Dict[str, Any]:
        """
        Get information about the currently authenticated user.

        Returns:
            User information including email and user ID

        Raises:
            AuthenticationError: If authentication fails
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/who-am-i"

        try:
            response = self.session.get(endpoint)

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check credentials")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to get user information: {e}")

    @handle_token_expiration
    def fetch_custom_endpoint(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, method: str = "GET"
    ) -> Dict[str, Any]:
        """
        Fetch data from an arbitrary user-provided endpoint.

        Args:
            endpoint: The full URL endpoint to fetch from
            params: Optional query parameters or request body
            method: HTTP method (GET, POST, etc.)

        Returns:
            API response data

        Raises:
            AuthenticationError: If authentication fails
            ProverAPIError: If API call fails
        """
        try:
            # Use helper method for HTTP method dispatch
            if method.upper() in ("GET", "DELETE"):
                response = self._execute_request(method, endpoint, params=params)
            elif method.upper() in ("POST", "PUT"):
                response = self._execute_request(method, endpoint, json_data=params)
            else:
                raise ProverAPIError(f"Unsupported HTTP method: {method}")

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check credentials")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch from custom endpoint {endpoint}: {e}")

    @handle_token_expiration
    def fetch_source_files_list(self, job_identifier: str) -> List[Dict[str, Any]]:
        """
        Fetch the source file tree for a job.

        Calls the source-files endpoint with path="" which redirects to S3
        and returns the full file tree as JSON.

        Args:
            job_identifier: Job ID to fetch

        Returns:
            List of source file tree nodes

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs/{job_identifier}/source-files"

        try:
            response = self.session.get(endpoint, params={"path": ""})

            if response.status_code == 200:
                return cast(List[Dict[str, Any]], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Source files not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return cast(List[Dict[str, Any]], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch source files for {job_identifier}: {e}")

    @handle_token_expiration
    def fetch_source_file_content(self, job_identifier: str, path: str) -> str:
        """
        Fetch the content of a specific source file for a job.

        Calls the source-files endpoint with the given path which redirects
        to S3 and returns the raw file content.

        Args:
            job_identifier: Job ID to fetch
            path: Path to the source file (e.g. ".certora_sources/src/Contract.sol")

        Returns:
            Raw file content as a string

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs/{job_identifier}/source-files"

        try:
            response = self.session.get(endpoint, params={"path": path})

            if response.status_code == 200:
                return response.text
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Source file not found for job {job_identifier}: {path}")
            else:
                response.raise_for_status()
                return response.text

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch source file for {job_identifier}: {e}")

    @handle_token_expiration
    def fetch_alert_report(self, job_identifier: str) -> List[Dict[str, Any]]:
        """
        Fetch alert report (alertReport.json) for a job.

        Args:
            job_identifier: Job ID to fetch

        Returns:
            Alert report data as a list of alert objects

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.api_base_url}/v1/domain/jobs/{job_identifier}/f/alertReport.json"

        try:
            response = self.session.get(endpoint)

            if response.status_code == 200:
                return cast(List[Dict[str, Any]], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check CERTORAKEY")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Alert report not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return cast(List[Dict[str, Any]], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch alert report for {job_identifier}: {e}")
