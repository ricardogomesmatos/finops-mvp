"""Testes da camada Unificado (`UnificadoService`).

Não há baseline de teste legado utilizável para esta camada (`gcp_labels/tests/`
só cobre Silver e Gold). Escritos do zero contra o comportamento real de
`gcp_unificado_label_service.py` (legado) + o template SQL real.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from expected_unificado_queries import (
    EXPECTED_CHECK_GOLD_UNIFICADO_DATA,
    EXPECTED_DELETE_GOLD_UNIFICADO_DATA,
    EXPECTED_INSERT_GOLD_UNIFICADO_DATA,
    GCP_GOLD_UNIFICADO_TABLE,
    INVOICE_MONTH,
)
from unificado_pipeline.services.unificado_service import UnificadoService

_COLUMNS = [
    "custo",
    "custo_foundation",
    "custo_suporte",
    "creditos",
    "credito_cud",
    "credito_suporte",
    "credito_foundation",
    "cud_foundation",
    "ajuste",
]

_PROVIDERS = ["GCP", "GCP_gold", "Tsuru", "Tsuru_gold", "DBaaS", "Dbaas_gold"]


def _check_rows(overrides: dict[str, dict[str, float]] | None = None) -> list[dict]:
    """Constrói as 6 linhas (GCP/GCP_gold/Tsuru/Tsuru_gold/DBaaS/Dbaas_gold) de CHECK_GOLD_UNIFICADO_DATA.

    Por padrão todas as colunas são 0 (nenhuma divergência); `overrides`
    permite sobrescrever colunas específicas por provedor.
    """
    overrides = overrides or {}
    rows = []
    for provedor in _PROVIDERS:
        row = {"provedor": provedor}
        row.update(dict.fromkeys(_COLUMNS, 0.0))
        row.update(overrides.get(provedor, {}))
        rows.append(row)
    return rows


class TestDeleteData:
    def test_renders_delete_query_without_labels(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=True)

        service.delete_data(INVOICE_MONTH)

        called_args = mock_bigquery_adapter.exec_query.call_args
        assert called_args.args[0] == EXPECTED_DELETE_GOLD_UNIFICADO_DATA
        assert GCP_GOLD_UNIFICADO_TABLE in called_args.args[0]
        # Achado de paridade: esta camada nunca passa `labels=` ao exec_query.
        assert "labels" not in called_args.kwargs
        assert called_args.kwargs["month"] == INVOICE_MONTH


class TestInsertData:
    def test_renders_insert_query_with_current_template(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=True)

        service.insert_data(INVOICE_MONTH)

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_INSERT_GOLD_UNIFICADO_DATA


class TestCheckResultQuery:
    def test_bypass_validation_skips_check_entirely(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=True)

        service.check_result_query(INVOICE_MONTH)

        mock_bigquery_adapter.exec_query.assert_not_called()

    def test_no_divergence_does_not_append_error(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=False)
        mock_row_iterator = MagicMock()
        mock_row_iterator.__iter__.return_value = iter(_check_rows())
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        service.check_result_query(INVOICE_MONTH)

        assert service.error_msgs == []
        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_CHECK_GOLD_UNIFICADO_DATA

    def test_diff_above_threshold_appends_error_without_raising(
        self, unificado_env, mock_bigquery_adapter
    ):
        service = UnificadoService(bypass_validation=False)
        rows = _check_rows(overrides={"GCP": {"custo": 5.0}})
        mock_row_iterator = MagicMock()
        mock_row_iterator.__iter__.return_value = iter(rows)
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        service.check_result_query(INVOICE_MONTH)

        assert len(service.error_msgs) == 1
        assert "5.0" in service.error_msgs[0]

    def test_diff_exceeding_limit_raises_runtime_error(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=False)
        rows = _check_rows(overrides={"GCP": {"custo": 100_000.0}})
        mock_row_iterator = MagicMock()
        mock_row_iterator.__iter__.return_value = iter(rows)
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        with pytest.raises(RuntimeError, match="100000.0"):
            service.check_result_query(INVOICE_MONTH)

    def test_opposite_sign_diffs_across_providers_cancel_out(
        self, unificado_env, mock_bigquery_adapter
    ):
        """Achado de paridade do legado: `diff_total` soma diferenças com sinal.

        Uma divergência real de +100000 no GCP e -100000 no Tsuru (mesma
        coluna) resulta em `diff_total == 0`, mascarando duas divergências
        graves por coluna/provedor. Comportamento do legado, preservado
        fielmente — não é uma correção desta migração.
        """
        service = UnificadoService(bypass_validation=False)
        rows = _check_rows(
            overrides={"GCP": {"custo": 100_000.0}, "Tsuru": {"custo": -100_000.0}}
        )
        mock_row_iterator = MagicMock()
        mock_row_iterator.__iter__.return_value = iter(rows)
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        service.check_result_query(INVOICE_MONTH)

        assert service.error_msgs == []


class TestLoadGoldUnificadoData:
    def test_happy_path_runs_check_delete_and_insert(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=False)
        mock_row_iterator = MagicMock()
        mock_row_iterator.__iter__.return_value = iter(_check_rows())
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        result = service.load_gold_unificado_data(INVOICE_MONTH)

        assert result == {"status": "success", "details": []}
        assert mock_bigquery_adapter.exec_query.call_count == 3

    def test_bypass_validation_skips_check_step(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=True)

        result = service.load_gold_unificado_data(INVOICE_MONTH)

        assert result["status"] == "success"
        # apenas delete + insert (sem check)
        assert mock_bigquery_adapter.exec_query.call_count == 2

    def test_failure_returns_failed_status_with_details(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=True)
        mock_bigquery_adapter.exec_query.side_effect = RuntimeError("BQ query failed: boom")

        result = service.load_gold_unificado_data(INVOICE_MONTH)

        assert result["status"] == "failed"
        assert "boom" in result["details"]

    def test_invalid_invoice_month_format_returns_failed(self, unificado_env, mock_bigquery_adapter):
        service = UnificadoService(bypass_validation=True)

        result = service.load_gold_unificado_data("not-a-date")

        assert result["status"] == "failed"
        mock_bigquery_adapter.exec_query.assert_not_called()
