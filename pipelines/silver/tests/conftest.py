"""Fixtures compartilhadas pelos testes da camada Silver."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from expected_silver_queries import (
    GCP_SILVER_LABEL_TABLE,
    PROJECT_ID,
)


@pytest.fixture
def silver_env(monkeypatch):
    """Configura as 3 variáveis de ambiente exigidas por SilverEnvConfigs."""
    monkeypatch.setenv("GCP_PROJECT", PROJECT_ID)
    monkeypatch.setenv("GCP_SILVER_LABEL_TABLE", GCP_SILVER_LABEL_TABLE)
    monkeypatch.setenv("COST_VALIDATION_LIMIT", "15000")


@pytest.fixture
def mock_bigquery_adapter():
    """Substitui o BigQueryAdapter real por um mock, sem chamadas ao BigQuery."""
    with patch("silver_pipeline.services.silver_label_service.BigQueryAdapter") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance
