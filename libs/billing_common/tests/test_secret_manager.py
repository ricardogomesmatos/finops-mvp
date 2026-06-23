"""Testes unitários de get_secret_json — sem chamadas reais ao Secret Manager."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from billing_common.secrets.secret_manager import get_secret_json


@pytest.fixture
def mock_secretmanager_client():
    with patch(
        "billing_common.secrets.secret_manager.secretmanager.SecretManagerServiceClient"
    ) as mock_cls:
        yield mock_cls.return_value


def test_get_secret_json_parses_payload(mock_secretmanager_client):
    payload = {"user": "abc", "key_content": "pem"}
    response = MagicMock()
    response.payload.data = json.dumps(payload).encode("utf-8")
    mock_secretmanager_client.access_secret_version.return_value = response

    result = get_secret_json(project_id="my-project", secret_id="api-credentials")

    assert result == payload
    called_kwargs = mock_secretmanager_client.access_secret_version.call_args.kwargs
    assert called_kwargs["name"] == "projects/my-project/secrets/api-credentials/versions/latest"


def test_get_secret_json_uses_explicit_version(mock_secretmanager_client):
    response = MagicMock()
    response.payload.data = b"{}"
    mock_secretmanager_client.access_secret_version.return_value = response

    get_secret_json(project_id="my-project", secret_id="api-credentials", version="3")

    called_kwargs = mock_secretmanager_client.access_secret_version.call_args.kwargs
    assert called_kwargs["name"] == "projects/my-project/secrets/api-credentials/versions/3"


def test_get_secret_json_wraps_exceptions_in_runtime_error(mock_secretmanager_client):
    mock_secretmanager_client.access_secret_version.side_effect = ValueError("boom")

    with pytest.raises(RuntimeError, match="Failed to access secret"):
        get_secret_json(project_id="my-project", secret_id="api-credentials")
