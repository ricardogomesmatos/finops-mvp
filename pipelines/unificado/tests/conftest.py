"""Fixtures compartilhadas pelos testes da camada Unificado."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from expected_unificado_queries import GCP_GOLD_UNIFICADO_TABLE, PROJECT_ID


@pytest.fixture
def unificado_env(monkeypatch):
    """Configura as 3 variáveis de ambiente exigidas por UnificadoEnvConfigs."""
    monkeypatch.setenv("GCP_PROJECT", PROJECT_ID)
    monkeypatch.setenv("GCP_GOLD_UNIFICADO_LABEL_TABLE", GCP_GOLD_UNIFICADO_TABLE)
    monkeypatch.setenv("COST_VALIDATION_LIMIT", "15000")


@pytest.fixture
def mock_bigquery_adapter():
    """Substitui o BigQueryAdapter real por um mock, sem chamadas ao BigQuery."""
    with patch("unificado_pipeline.services.unificado_service.BigQueryAdapter") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value = instance
        yield instance
