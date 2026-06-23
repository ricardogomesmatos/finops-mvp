"""Fixtures compartilhadas pelos testes da camada Gold Foundation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from expected_gold_foundation_queries import (
    GCP_GOLD_FOUNDATION_DASHBOARD_TABLE,
    GCP_GOLD_FOUNDATION_TABLE,
    GCP_GOLD_PRE_FOUNDATION_TABLE,
    PROJECT_ID,
)


@pytest.fixture
def gold_foundation_env(monkeypatch):
    """Configura as 4 variáveis de ambiente exigidas por GoldFoundationEnvConfigs."""
    monkeypatch.setenv("GCP_PROJECT", PROJECT_ID)
    monkeypatch.setenv("GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE", GCP_GOLD_PRE_FOUNDATION_TABLE)
    monkeypatch.setenv("GCP_GOLD_LABEL_FOUNDATION_TABLE", GCP_GOLD_FOUNDATION_TABLE)
    monkeypatch.setenv(
        "GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE", GCP_GOLD_FOUNDATION_DASHBOARD_TABLE
    )


@pytest.fixture
def mock_bigquery_adapter():
    """Substitui o BigQueryAdapter real por um mock, sem chamadas ao BigQuery."""
    with patch(
        "gold_foundation_pipeline.services.gold_foundation_service.BigQueryAdapter"
    ) as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance
