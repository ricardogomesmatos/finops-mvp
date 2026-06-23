"""Testes unitários do cliente OCI Optimizer — sem chamadas reais à OCI."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import oci
import pytest
from oci_recommendations_pipeline.clients.oci_client import (
    build_oci_config,
    build_optimizer_client,
    list_all_recommendations,
)

_VALID_SECRET_PAYLOAD = {
    "user": "ocid1.user.oc1..aaaaaaaauserexample",
    "fingerprint": "20:3b:97:13:55:1c:5b:0d:d3:37:d8:50:4e:c5:3a:34",
    "tenancy": "ocid1.tenancy.oc1..aaaaaaaatenancyexample",
    "region": "sa-saopaulo-1",
    "key_content": "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----",
}


def test_build_oci_config_returns_dict_with_required_keys():
    config = build_oci_config(_VALID_SECRET_PAYLOAD)

    assert config == _VALID_SECRET_PAYLOAD


@pytest.mark.parametrize("missing_key", ["user", "fingerprint", "tenancy", "region", "key_content"])
def test_build_oci_config_raises_value_error_when_key_missing(missing_key):
    payload = {k: v for k, v in _VALID_SECRET_PAYLOAD.items() if k != missing_key}

    with pytest.raises(ValueError, match=missing_key):
        build_oci_config(payload)


@patch("oci_recommendations_pipeline.clients.oci_client.oci.optimizer.OptimizerClient")
def test_build_optimizer_client_passes_config(mock_client_cls):
    build_optimizer_client(_VALID_SECRET_PAYLOAD)

    mock_client_cls.assert_called_once_with(_VALID_SECRET_PAYLOAD)


@patch("oci_recommendations_pipeline.clients.oci_client.oci.pagination.list_call_get_all_results")
def test_list_all_recommendations_calls_with_tenancy_in_subtree(mock_list_call):
    mock_optimizer_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = ["rec-1", "rec-2"]
    mock_list_call.return_value = mock_response

    result = list_all_recommendations(mock_optimizer_client, "ocid1.tenancy.oc1..aaaa")

    assert result == ["rec-1", "rec-2"]
    mock_list_call.assert_called_once_with(
        mock_optimizer_client.list_recommendations,
        compartment_id="ocid1.tenancy.oc1..aaaa",
        compartment_id_in_subtree=True,
    )


@patch("oci_recommendations_pipeline.clients.oci_client.oci.pagination.list_call_get_all_results")
def test_list_all_recommendations_propagates_service_error(mock_list_call):
    mock_list_call.side_effect = oci.exceptions.ServiceError(
        status=429, code="TooManyRequests", headers={}, message="rate limited"
    )

    with pytest.raises(oci.exceptions.ServiceError):
        list_all_recommendations(MagicMock(), "ocid1.tenancy.oc1..aaaa")
