"""Fixtures compartilhadas pelos testes do pipeline oci_recommendations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

PROJECT_ID = "test-project"
OCI_RECOMMENDATIONS_TABLE = "test-project.billing_raw.tb_oci_optimizer_recommendations_snapshot"
OCI_TENANCY_ID = "ocid1.tenancy.oc1..aaaaaaaatenancyexample"
OCI_CREDENTIALS_SECRET_ID = "oci-optimizer-credentials"


@pytest.fixture
def oci_env(monkeypatch):
    """Configura as 4 variáveis de ambiente exigidas por OciRecommendationsEnvConfigs."""
    monkeypatch.setenv("GCP_PROJECT", PROJECT_ID)
    monkeypatch.setenv("OCI_RECOMMENDATIONS_TABLE", OCI_RECOMMENDATIONS_TABLE)
    monkeypatch.setenv("OCI_TENANCY_ID", OCI_TENANCY_ID)
    monkeypatch.setenv("OCI_CREDENTIALS_SECRET_ID", OCI_CREDENTIALS_SECRET_ID)


@pytest.fixture
def mock_bigquery_adapter():
    """Substitui o BigQueryAdapter real por um mock, sem chamadas ao BigQuery."""
    with patch(
        "oci_recommendations_pipeline.services.oci_recommendations_service.BigQueryAdapter"
    ) as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def mock_get_secret_json():
    """Substitui get_secret_json por um mock retornando credenciais OCI válidas."""
    with patch(
        "oci_recommendations_pipeline.services.oci_recommendations_service.get_secret_json"
    ) as mock_fn:
        mock_fn.return_value = {
            "user": "ocid1.user.oc1..aaaaaaaauserexample",
            "fingerprint": "20:3b:97:13:55:1c:5b:0d:d3:37:d8:50:4e:c5:3a:34",
            "tenancy": OCI_TENANCY_ID,
            "region": "sa-saopaulo-1",
            "key_content": "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----",
        }
        yield mock_fn
