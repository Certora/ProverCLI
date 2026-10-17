# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""
Authentication handling for Certora Prover API.
"""

import os
from typing import Dict, Literal

import requests

from .exceptions import AuthenticationError

LoginEnv = Literal["prod", "stg", "dev"]
_VALID_AISS_ENVS: frozenset[str] = frozenset(("dev", "stg", "prod"))


def resolve_login_env() -> LoginEnv:
    """
    Resolve which Certora login environment to authenticate against.

    Precedence:
      1. If ``AISS_ENV`` is set, it must be one of ``{dev, stg, prod}`` and is used
         directly. Any other value raises ``AuthenticationError``.
      2. Otherwise, fall back to the legacy ``GITHUB_ENVIRONMENT`` mapping:
         ``staging`` -> ``stg``, ``development`` -> ``dev``, anything else -> ``prod``.

    Per the AISS deployment contract, only one of the two variables is set at a time.
    """
    aiss_env = os.environ.get("AISS_ENV")
    if aiss_env is not None:
        if aiss_env not in _VALID_AISS_ENVS:
            raise AuthenticationError(
                f"Invalid AISS_ENV={aiss_env!r}; expected one of {sorted(_VALID_AISS_ENVS)}"
            )
        return aiss_env  # type: ignore[return-value]

    github_env = os.environ.get("GITHUB_ENVIRONMENT", "")
    if github_env == "staging":
        return "stg"
    if github_env == "development":
        return "dev"
    return "prod"


# Login env -> certoraRun `--server` value. The canonical source of truth so
# every component (autosetup, AIComposer, PreAudit) picks the same backend for a
# given env instead of hand-rolling it. Note 'dev' -> 'vaas-dev', not 'dev'.
_SERVER_BY_LOGIN_ENV: Dict[LoginEnv, str] = {
    "prod": "production",
    "stg": "staging",
    "dev": "vaas-dev",
}

# Login env -> Prover web-UI base URL (what `--server` resolves to in
# certoraUtils.SupportedServers): the host that serves job output pages.
_PROVER_FRONTEND_BY_LOGIN_ENV: Dict[LoginEnv, str] = {
    "prod": "https://prover.certora.com",
    "stg": "https://vaas-stg.certora.com",
    "dev": "https://vaas-dev.certora.com",
}


def cloud_server_for_env() -> str:
    """The certoraRun ``--server`` value for the current login env
    (:func:`resolve_login_env`). Raises ``AuthenticationError`` on an invalid
    ``AISS_ENV`` (via ``resolve_login_env``)."""
    return _SERVER_BY_LOGIN_ENV[resolve_login_env()]


def prover_frontend_url() -> str:
    """Base URL of the Prover web UI for the current login env."""
    return _PROVER_FRONTEND_BY_LOGIN_ENV[resolve_login_env()]


try:
    from certora_login import SERVERS, delete_credentials, login
except ImportError:
    login = None
    delete_credentials = None
    SERVERS = None


# Environment variables holding an organization API key, in the order they are
# consulted. The env-scoped name comes first so a machine configured for one
# environment cannot be pointed at another by a stray generic value.
_API_KEY_ENV_VARS: Dict[LoginEnv, tuple[str, ...]] = {
    "prod": ("CERTORA_API_KEY_PROD", "CERTORA_API_KEY"),
    "stg": ("CERTORA_API_KEY_STG", "CERTORA_API_KEY"),
    "dev": ("CERTORA_API_KEY_DEV", "CERTORA_API_KEY"),
}


def organization_api_key() -> str | None:
    """The organization API key for the current login env, if one is set.

    This is the key issued on the organization's API page, not ``CERTORAKEY``.
    The API accepts it on the ``Authorization`` header and exchanges it for a
    short-lived token itself, so a caller that has one needs no browser login.
    """
    for name in _API_KEY_ENV_VARS[resolve_login_env()]:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


class ProverAuth:
    """
    Handles authentication with Certora Prover API using certora_login.
    """

    def __init__(self):
        """
        Initialize authentication.
        Uses certora_login for authentication, no CERTORAKEY needed.
        """
        self._retry_count = 0
        self._max_retries = 1

    def delete_stored_credentials(self) -> None:
        """
        Delete stored credentials when they are expired or invalid.

        Raises:
            AuthenticationError: If delete_credentials is not available
        """
        if delete_credentials is None:
            raise AuthenticationError(
                "certora_login package is not installed. "
                "Please install it with: pip install certora-login"
            )

        try:
            delete_credentials()
        except Exception as e:
            raise AuthenticationError(f"Failed to delete credentials: {e}")

    def get_auth_cookies(self, force_relogin: bool = False) -> requests.cookies.RequestsCookieJar:
        """
        Get authentication cookies for API requests.

        Args:
            force_relogin: If True, delete existing credentials and force a new login

        Returns:
            RequestsCookieJar with authentication cookies

        Raises:
            AuthenticationError: If certora_login is not available or fails
        """
        cookies = requests.cookies.RequestsCookieJar()

        # An organization API key authenticates on the header instead, so
        # there is nothing to log in for and no cookie to carry.
        if organization_api_key() is not None:
            return cookies

        # Skip authentication in CI environment - return empty cookies
        if os.getenv("CI"):
            return cookies

        # Use certora_login for authentication
        if login is None:
            raise AuthenticationError(
                "certora_login package is not installed. "
                "Please install it with: pip install certora-login"
            )

        if force_relogin:
            try:
                self.delete_stored_credentials()
            except Exception:
                pass

        try:
            _login_env = resolve_login_env()
            credentials = login(env=_login_env, force_file=True)

            # Set all credential cookies with proper domain
            for name, value in credentials.items():
                cookies.set(name, str(value), domain="certora.com")

            return cookies

        except Exception as e:
            raise AuthenticationError(f"Authentication failed: {e}")

    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests.

        An organization API key authenticates on the ``Authorization``
        header: the API classifies the credential by shape and exchanges an
        opaque key for a short-lived token on the caller's behalf, so no
        browser login and no cookie are involved. Without a key the cookies
        from certora_login carry the identity and there is no header to add.

        Returns:
            The bearer header for the organization API key, or an empty
            dictionary when authentication is via cookies.
        """
        key = organization_api_key()
        if key is None:
            return {}
        return {"Authorization": f"Bearer {key}"}
