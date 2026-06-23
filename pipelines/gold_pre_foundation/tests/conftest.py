"""Fixtures compartilhadas pelos testes da camada Gold Pre-Foundation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from expected_gold_pre_foundation_queries import (
    CUSTO_UNITARIO_FIELDS,
    GCP_GOLD_PRE_FOUNDATION_TABLE,
    GCP_MARKETPLACE_SERVICES_TABLE,
    GCP_SILVER_LABEL_TABLE,
    PROJECT_ID,
)


@pytest.fixture
def gold_pre_foundation_env(monkeypatch):
    """Configura as 6 variáveis de ambiente exigidas por GoldPreFoundationEnvConfigs."""
    monkeypatch.setenv("GCP_PROJECT", PROJECT_ID)
    monkeypatch.setenv("GCP_SILVER_LABEL_TABLE", GCP_SILVER_LABEL_TABLE)
    monkeypatch.setenv("GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE", GCP_GOLD_PRE_FOUNDATION_TABLE)
    monkeypatch.setenv("CUSTO_UNITARIO_FIELDS", ", ".join(CUSTO_UNITARIO_FIELDS))
    monkeypatch.setenv("GCP_MARKETPLACE_SERVICES_TABLE", GCP_MARKETPLACE_SERVICES_TABLE)
    monkeypatch.setenv("COST_VALIDATION_LIMIT", "15000")


@pytest.fixture
def mock_bigquery_adapter():
    """Substitui o BigQueryAdapter real por um mock, sem chamadas ao BigQuery."""
    with patch(
        "gold_pre_foundation_pipeline.services.gold_pre_foundation_service.BigQueryAdapter"
    ) as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance
