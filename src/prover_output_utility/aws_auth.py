# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
AWS authentication handling for CI environments.
"""

import os
from typing import Optional

import boto3
from botocore.exceptions import NoCredentialsError

from .exceptions import AuthenticationError


class AWSAuth:
    """
    Handles AWS authentication for CI environments.
    Uses either existing AWS credentials or assumes a role if AWS_ROLE_ARN is provided.
    """

    def __init__(self):
        """Initialize AWS authentication."""
        self.role_arn = os.getenv("AWS_ROLE_ARN")
        self.session = None

    def get_session(self) -> boto3.Session:
        """
        Get an authenticated boto3 session.

        If AWS_ROLE_ARN is set, assumes that role.
        Otherwise, uses default AWS credentials chain.

        Returns:
            boto3.Session configured with appropriate credentials

        Raises:
            AuthenticationError: If AWS authentication fails
        """
        if self.session:
            return self.session

        try:
            if self.role_arn:
                # Assume role if AWS_ROLE_ARN is provided
                self.session = self._assume_role_session()
            else:
                # Use default AWS credentials chain
                self.session = boto3.Session()
                # Verify credentials are available
                credentials = self.session.get_credentials()
                if not credentials:
                    raise NoCredentialsError

            return self.session

        except NoCredentialsError:
            raise AuthenticationError(
                "No AWS credentials found. Please configure AWS credentials or set AWS_ROLE_ARN."
            )
        except Exception as e:
            raise AuthenticationError(f"AWS authentication failed: {e}")

    def _assume_role_session(self) -> boto3.Session:
        """
        Create a boto3 session by assuming the specified IAM role.

        Returns:
            boto3.Session with assumed role credentials

        Raises:
            AuthenticationError: If role assumption fails
        """
        try:
            # Create STS client with default credentials
            sts_client = boto3.client("sts")

            # Generate a session name
            import uuid

            session_name = f"certora-ci-{uuid.uuid4().hex[:8]}"

            # Assume the role
            response = sts_client.assume_role(
                RoleArn=self.role_arn, RoleSessionName=session_name, DurationSeconds=3600  # 1 hour
            )

            # Extract credentials from response
            credentials = response["Credentials"]

            # Create new session with assumed role credentials
            return boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
            )

        except Exception as e:
            raise AuthenticationError(f"Failed to assume role {self.role_arn}: {e}")

    def is_available(self) -> bool:
        """
        Check if AWS authentication is available in the current environment.

        Returns:
            True if AWS credentials are available or AWS_ROLE_ARN is set
        """
        # Check if we're in CI and have AWS configuration
        if not os.getenv("CI"):
            return False

        # Check for AWS_ROLE_ARN
        if self.role_arn:
            return True

        # Check for standard AWS credentials
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            return credentials is not None
        except Exception:
            return False
