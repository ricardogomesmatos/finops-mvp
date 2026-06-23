"""Testes unitários do BaseEnvConfigs."""

from __future__ import annotations

import pytest

from billing_common.config.base import BaseEnvConfigs


def test_validate_passes_when_all_expected_envs_present():
    configs = BaseEnvConfigs(
        expected_envs=["GCP_PROJECT", "GCP_SILVER_LABEL_TABLE"],
        environ={"GCP_PROJECT": "my-project", "GCP_SILVER_LABEL_TABLE": "dataset.table"},
    )

    assert configs.get("GCP_PROJECT") == "my-project"
    assert configs.get("GCP_SILVER_LABEL_TABLE") == "dataset.table"


def test_validate_exits_when_required_env_missing():
    with pytest.raises(SystemExit) as exc_info:
        BaseEnvConfigs(
            expected_envs=["GCP_PROJECT", "GCP_SILVER_LABEL_TABLE"],
            environ={"GCP_PROJECT": "my-project"},
        )

    assert exc_info.value.code == 1


def test_get_returns_default_when_key_absent():
    configs = BaseEnvConfigs(expected_envs=["GCP_PROJECT"], environ={"GCP_PROJECT": "my-project"})

    assert configs.get("NOT_SET", "fallback") == "fallback"


def test_empty_expected_envs_never_exits():
    configs = BaseEnvConfigs(expected_envs=[], environ={})

    assert configs.get("ANYTHING") is None


def test_defaults_to_os_environ_when_environ_not_injected(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "from-os-environ")

    configs = BaseEnvConfigs(expected_envs=["GCP_PROJECT"])

    assert configs.get("GCP_PROJECT") == "from-os-environ"
