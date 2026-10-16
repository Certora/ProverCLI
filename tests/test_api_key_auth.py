# SPDX-FileCopyrightText: 2026 Certora Ltd.
#
# SPDX-License-Identifier: GPL-3.0-only

"""An organization API key authenticates without a browser login.

The API classifies an opaque credential on the ``Authorization`` header as an
organization API key and exchanges it for a short-lived token itself, so a
caller that holds a key needs neither the login flow nor a cookie.
"""

import pytest

from prover_output_utility.auth import ProverAuth, organization_api_key

KEY = "zk_test_value_that_is_opaque"


@pytest.fixture(autouse=True)
def clear_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for suffix in ("", "_PROD", "_STG", "_DEV"):
        monkeypatch.delenv(f"CERTORA_API_KEY{suffix}", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ENVIRONMENT", raising=False)


def test_no_key_configured_reads_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AISS_ENV", "stg")
    assert organization_api_key() is None
    assert ProverAuth().get_auth_headers() == {}


def test_env_scoped_key_becomes_a_bearer_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AISS_ENV", "stg")
    monkeypatch.setenv("CERTORA_API_KEY_STG", KEY)
    assert organization_api_key() == KEY
    assert ProverAuth().get_auth_headers() == {"Authorization": f"Bearer {KEY}"}


def test_the_env_scoped_key_wins_over_the_generic_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AISS_ENV", "stg")
    monkeypatch.setenv("CERTORA_API_KEY", "generic")
    monkeypatch.setenv("CERTORA_API_KEY_STG", KEY)
    assert organization_api_key() == KEY


def test_a_key_for_another_env_is_not_used(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AISS_ENV", "stg")
    monkeypatch.setenv("CERTORA_API_KEY_PROD", KEY)
    assert organization_api_key() is None


def test_a_blank_key_reads_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AISS_ENV", "stg")
    monkeypatch.setenv("CERTORA_API_KEY_STG", "   ")
    assert organization_api_key() is None


def test_a_key_replaces_the_login_rather_than_adding_to_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The login flow must not run when a key is present, including the browser
    flow a developer machine would otherwise open."""
    monkeypatch.setenv("AISS_ENV", "stg")
    monkeypatch.setenv("CERTORA_API_KEY_STG", KEY)

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("the login flow ran although a key was configured")

    monkeypatch.setattr("prover_output_utility.auth.login", fail_if_called)
    assert len(ProverAuth().get_auth_cookies()) == 0
