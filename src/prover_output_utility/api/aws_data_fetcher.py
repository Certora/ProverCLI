# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
AWS Lambda-based data fetcher for CI environments.
Uses AWS SigV4 authentication to access Certora API through Lambda.
"""

import json
import os
from typing import Any, Dict, List, Optional, cast

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from ..exceptions import AuthenticationError, JobNotFoundError, ProverAPIError
from .base_data_fetcher import BaseDataFetcher


class AWSDataFetcher(BaseDataFetcher):
    """Handles data fetching from Certora API via AWS Lambda with SigV4 authentication."""

    #: Environment variable holding the Lambda function URL (no default is baked in).
    LAMBDA_URL_ENV_VAR = "CERTORA_LAMBDA_URL"

    def __init__(
        self, aws_session: Optional[boto3.Session] = None, base_url: Optional[str] = None
    ):
        """
        Initialize the AWS data fetcher.

        Args:
            aws_session: Optional boto3 session. If not provided, creates default session.
            base_url: Lambda function URL. If not provided, read from the
                ``CERTORA_LAMBDA_URL`` environment variable.

        Raises:
            ProverAPIError: If no base URL is provided or configured.
        """
        self.session = aws_session or boto3.Session()
        resolved = base_url or os.environ.get(self.LAMBDA_URL_ENV_VAR)
        if not resolved:
            raise ProverAPIError(
                f"AWS Lambda endpoint not configured. Set the {self.LAMBDA_URL_ENV_VAR} "
                "environment variable to the Lambda function URL, or pass base_url=."
            )
        self.base_url = resolved.rstrip("/")
        self.region = "us-west-2"
        self.service = "lambda"

    def _make_signed_request(
        self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None
    ) -> requests.Response:
        """
        Make a signed request to the AWS Lambda endpoint with redirect handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Full URL endpoint
            data: Optional JSON data for POST requests
            params: Optional query parameters

        Returns:
            requests Response object

        Raises:
            ProverAPIError: If request fails
        """
        # Create AWS request for signing
        aws_request = AWSRequest(method=method, url=endpoint, data=data, params=params)

        # Sign the request with SigV4
        credentials = self.session.get_credentials()
        if not credentials:
            raise AuthenticationError("No AWS credentials available. Check AWS configuration.")

        SigV4Auth(credentials, self.service, self.region).add_auth(aws_request)

        # Make the initial request with signed headers, but don't follow redirects
        try:
            response = requests.request(
                method=method,
                url=endpoint,
                headers=dict(aws_request.headers),
                json=data,
                params=params,
                timeout=30,
                allow_redirects=False,  # Handle redirects manually
            )

            # Handle redirects manually
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get("Location")
                if redirect_url:
                    # Check if redirecting to *.certora.com domain
                    from urllib.parse import urlparse

                    parsed_url = urlparse(redirect_url)

                    if parsed_url.hostname and not parsed_url.hostname.endswith(".certora.com"):
                        # For non certora.com domains, follow without AWS headers
                        response = requests.request(
                            method="GET" if response.status_code == 303 else method,
                            url=redirect_url,
                            json=data,
                            params=params,
                            timeout=30,
                            allow_redirects=True,  # Allow further redirects
                        )
                    else:
                        # For certora.com domains, make request with AWS headers
                        response = requests.request(
                            method="GET" if response.status_code == 303 else method,
                            url=redirect_url,
                            headers=dict(aws_request.headers),
                            json=data,
                            params=params,
                            timeout=30,
                            allow_redirects=True,
                        )

            return response
        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Request failed: {e}")

    def fetch_raw_output(self, job_identifier: str) -> Dict[str, Any]:
        """
        Fetch raw output data from the prover API via Lambda.

        Args:
            job_identifier: Job ID to fetch

        Returns:
            Raw API response data

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.base_url}/v1/domain/jobs/{job_identifier}"

        try:
            response = self._make_signed_request("GET", endpoint)

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Job {job_identifier} not found")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch job data for {job_identifier}: {e}")

    def fetch_tree_view_data(
        self, job_identifier: str, path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch tree-view data for a job via Lambda.

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
        endpoint = f"{self.base_url}/v1/domain/jobs/{job_identifier}/tree-view"

        params = {}
        if path:
            params["path"] = path

        try:
            response = self._make_signed_request("GET", endpoint, params=params)

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Tree-view data not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch tree-view data for {job_identifier}: {e}")

    def fetch_statsdata(self, job_identifier: str) -> Dict[str, Any]:
        """Fetch statsdata.json for a job via Lambda."""
        return cast(Dict[str, Any], json.loads(self.fetch_output_file(job_identifier, "statsdata.json")))

    def fetch_output_file(self, job_identifier: str, rel_path: str) -> str:
        """Fetch the raw text of a Reports/-relative output file (e.g. unsat_core_map.json)."""
        endpoint = f"{self.base_url}/v1/domain/jobs/{job_identifier}/f/{rel_path}"

        try:
            response = self._make_signed_request("GET", endpoint)

            if response.status_code == 200:
                return response.text
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Output file not found for job {job_identifier}: {rel_path}")
            else:
                response.raise_for_status()
                return response.text

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch output file {rel_path} for {job_identifier}: {e}")

    def fetch_outputs(self, job_identifier: str) -> bytes:
        """
        Fetch outputs archive (tar.gz) for a job via Lambda.

        Args:
            job_identifier: Job ID to fetch

        Returns:
            Raw tar.gz content as bytes

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.base_url}/v1/domain/jobs/{job_identifier}/f/outputs"

        try:
            response = self._make_signed_request("GET", endpoint)

            if response.status_code == 200:
                return response.content
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Outputs not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return response.content

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch outputs for {job_identifier}: {e}")

    def list_recent_jobs(
        self,
        created_after: str,
        limit: int = 100,
        all_users: bool = True,
    ) -> List[Dict[str, Any]]:
        """List recent jobs via Lambda.

        See BaseDataFetcher.list_recent_jobs for parameter docs.
        """
        endpoint = f"{self.base_url}/v1/domain/jobs"

        try:
            response = self._make_signed_request("GET", endpoint, params={
                "currentPage": 1,
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

    def fetch_group_jobs(
        self, group_id: str, created_after: str, created_before: str
    ) -> List[Dict[str, Any]]:
        """Fetch all jobs in a group via Lambda."""
        endpoint = f"{self.base_url}/v1/domain/jobs"

        try:
            response = self._make_signed_request("GET", endpoint, params={
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

    def cancel_jobs(self, job_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel multiple jobs by their IDs via Lambda.

        Args:
            job_ids: List of job IDs to cancel

        Returns:
            API response data

        Raises:
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.base_url}/v1/domain/jobs/cancel"
        payload = {"ids": job_ids}

        try:
            response = self._make_signed_request("POST", endpoint, data=payload)

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            elif response.status_code == 404:
                raise JobNotFoundError("Cancel endpoint not found")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to cancel jobs {job_ids}: {e}")

    def who_am_i(self) -> Dict[str, Any]:
        """
        Get information about the currently authenticated user via Lambda.

        Returns:
            User information including email and user ID

        Raises:
            AuthenticationError: If authentication fails
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.base_url}/who-am-i"

        try:
            response = self._make_signed_request("GET", endpoint)

            if response.status_code == 200:
                return cast(Dict[str, Any], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            else:
                response.raise_for_status()
                return cast(Dict[str, Any], response.json())

        except requests.exceptions.RequestException as e:
            if "401" in str(e):
                raise AuthenticationError("Authentication failed - check AWS credentials")
            raise ProverAPIError(f"Failed to get user information: {e}")

    def fetch_source_files_list(self, job_identifier: str) -> List[Dict[str, Any]]:
        """
        Fetch the source file tree for a job via Lambda.

        Args:
            job_identifier: Job ID to fetch

        Returns:
            List of source file tree nodes

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.base_url}/v1/domain/jobs/{job_identifier}/source-files"

        try:
            response = self._make_signed_request("GET", endpoint, params={"path": ""})

            if response.status_code == 200:
                return cast(List[Dict[str, Any]], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Source files not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return cast(List[Dict[str, Any]], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch source files for {job_identifier}: {e}")

    def fetch_source_file_content(self, job_identifier: str, path: str) -> str:
        """
        Fetch the content of a specific source file for a job via Lambda.

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
        endpoint = f"{self.base_url}/v1/domain/jobs/{job_identifier}/source-files"

        try:
            response = self._make_signed_request("GET", endpoint, params={"path": path})

            if response.status_code == 200:
                return response.text
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Source file not found for job {job_identifier}: {path}")
            else:
                response.raise_for_status()
                return response.text

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch source file for {job_identifier}: {e}")

    def fetch_alert_report(self, job_identifier: str) -> List[Dict[str, Any]]:
        """
        Fetch alert report (alertReport.json) for a job via Lambda.

        Args:
            job_identifier: Job ID to fetch

        Returns:
            Alert report data as a list of alert objects

        Raises:
            AuthenticationError: If authentication fails
            JobNotFoundError: If job is not found
            ProverAPIError: If API call fails
        """
        endpoint = f"{self.base_url}/v1/domain/jobs/{job_identifier}/f/alertReport.json"

        try:
            response = self._make_signed_request("GET", endpoint)

            if response.status_code == 200:
                return cast(List[Dict[str, Any]], response.json())
            elif response.status_code == 401:
                raise AuthenticationError("Authentication failed - check AWS credentials")
            elif response.status_code == 404:
                raise JobNotFoundError(f"Alert report not found for job {job_identifier}")
            else:
                response.raise_for_status()
                return cast(List[Dict[str, Any]], response.json())

        except requests.exceptions.RequestException as e:
            raise ProverAPIError(f"Failed to fetch alert report for {job_identifier}: {e}")
