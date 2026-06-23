"""Testes da camada Silver (`SilverLabelService`), reescritos do zero.

Não porta `gcp_labels/tests/test_silver_label_service.py` do legado — aquele
teste está desatualizado em relação ao código de produção real (ver
`expected_silver_queries.py` e o plano de migração para o detalhe das 4
divergências encontradas: API de `bypass_validation`, `net_cost` ausente,
`CONTAINS_SUBSTR` em vez de `REGEXP_CONTAINS`, e partição `-5/+10` em vez de
`-17/+10` dias). Os casos abaixo cobrem o mesmo comportamento de negócio do
legado, mas contra a API e o template reais.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from expected_silver_queries import (
    EXPECTED_CHECK_SILVER_DATA,
    EXPECTED_DELETE_SILVER_DATA,
    EXPECTED_INSERT_SILVER_DATA,
    EXPECTED_SELECT_RAW_LABEL_DATA,
    GCP_SILVER_LABEL_TABLE,
    INVOICE_MONTH,
    PARTITION_END,
    PARTITION_START,
)
from silver_pipeline.services.silver_label_service import SilverLabelService


def _row(custo_raw=0.0, credito_raw=0.0, custo_silver=0.0, credito_silver=0.0):
    """Constrói um stub de linha de resultado do BigQuery (dict-like .get())."""
    return {
        "custo_raw": custo_raw,
        "credito_raw": credito_raw,
        "custo_silver": custo_silver,
        "credito_silver": credito_silver,
    }


class TestGeneratePartitionLimitFromInvoiceMonth:
    def test_partition_for_april_2024(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)

        result = service.generate_partition_limit_from_invoice_month("2024-04-01")

        assert result == (PARTITION_START, PARTITION_END)

    def test_partition_handles_december_year_rollover(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)

        partition_start, partition_end = service.generate_partition_limit_from_invoice_month(
            "2024-12-01"
        )

        # primeiro dia do mês (2024-12-01) - 17 dias
        assert partition_start == "2024-11-14"
        # último dia do mês (2024-12-31) + 10 dias, atravessando o ano
        assert partition_end == "2025-01-10"

    def test_partition_handles_leap_february(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)

        partition_start, partition_end = service.generate_partition_limit_from_invoice_month(
            "2024-02-01"
        )

        assert partition_start == "2024-01-15"
        # 2024 é bissexto: último dia de fevereiro é 29, não 28.
        assert partition_end == "2024-03-10"


class TestGenerateSilverQuery:
    def test_renders_select_raw_label_data_with_current_template(
        self, silver_env, mock_bigquery_adapter
    ):
        service = SilverLabelService(bypass_validation=True)

        query = service.generate_silver_query(INVOICE_MONTH, (PARTITION_START, PARTITION_END))

        assert query == EXPECTED_SELECT_RAW_LABEL_DATA
        assert "net_cost" in query
        assert "REGEXP_CONTAINS" in query
        assert "CONTAINS_SUBSTR" not in query


class TestGetCheckData:
    def test_renders_check_query_and_returns_first_row(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)
        expected_row = _row(
            custo_silver=100.0, credito_silver=-10.0, custo_raw=100.0, credito_raw=-10.0
        )
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([expected_row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        result = service.get_check_data(INVOICE_MONTH, (PARTITION_START, PARTITION_END))

        assert result == expected_row
        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_CHECK_SILVER_DATA
        called_kwargs = mock_bigquery_adapter.exec_query.call_args.kwargs
        assert called_kwargs["labels"] == {
            "finops-workflow": "gcp",
            "finops-workflow-layer": "gcp-silver",
        }
        assert called_kwargs["month"] == INVOICE_MONTH

    def test_raises_when_result_is_empty(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 0
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        with pytest.raises(RuntimeError, match="Empty check cost data query result"):
            service.get_check_data(INVOICE_MONTH, (PARTITION_START, PARTITION_END))


class TestCheckCostData:
    def test_returns_none_when_delta_is_negligible(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)
        row = _row(custo_silver=100.0, credito_silver=0.0, custo_raw=100.0, credito_raw=0.0)

        result = service.check_cost_data(row, INVOICE_MONTH)

        assert result is None

    def test_returns_message_when_delta_is_between_threshold_and_limit(
        self, silver_env, mock_bigquery_adapter
    ):
        service = SilverLabelService(bypass_validation=True)
        row = _row(custo_silver=100.0, credito_silver=0.0, custo_raw=90.0, credito_raw=0.0)

        result = service.check_cost_data(row, INVOICE_MONTH)

        assert result is not None
        assert "diff: 10.0" in result
        assert INVOICE_MONTH in result

    def test_raises_when_delta_exceeds_limit(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)
        # COST_VALIDATION_LIMIT do fixture é 15000.
        row = _row(custo_silver=100_000.0, credito_silver=0.0, custo_raw=0.0, credito_raw=0.0)

        with pytest.raises(RuntimeError, match="diff: 100000.0"):
            service.check_cost_data(row, INVOICE_MONTH)


class TestCheckSilverData:
    def test_bypass_validation_true_skips_check(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)

        result = service.check_silver_data(INVOICE_MONTH, (PARTITION_START, PARTITION_END))

        assert result is None
        mock_bigquery_adapter.exec_query.assert_not_called()

    def test_bypass_validation_false_runs_check(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=False)
        row = _row(custo_silver=100.0, credito_silver=0.0, custo_raw=100.0, credito_raw=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        result = service.check_silver_data(INVOICE_MONTH, (PARTITION_START, PARTITION_END))

        assert result is None
        mock_bigquery_adapter.exec_query.assert_called_once()

    def test_raises_when_invoice_month_or_partition_limits_missing(
        self, silver_env, mock_bigquery_adapter
    ):
        service = SilverLabelService(bypass_validation=False)

        with pytest.raises(RuntimeError, match="Check cost data parameters can't be null"):
            service.check_silver_data("", (PARTITION_START, PARTITION_END))


class TestDeleteData:
    def test_renders_delete_query_with_current_template(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)

        service.delete_data(INVOICE_MONTH)

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_DELETE_SILVER_DATA
        assert GCP_SILVER_LABEL_TABLE in called_query


class TestInsertData:
    def test_renders_insert_query_with_current_template(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)

        service.insert_data(INVOICE_MONTH, (PARTITION_START, PARTITION_END))

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_INSERT_SILVER_DATA
        assert "net_cost" in called_query


class TestLoadSilverData:
    def test_happy_path_returns_success(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=True)

        result = service.load_silver_data(INVOICE_MONTH)

        assert result["status"] == "success"
        # delete + insert, sem check (bypass_validation=True)
        assert mock_bigquery_adapter.exec_query.call_count == 2

    def test_failure_returns_failed_status_with_details(self, silver_env, mock_bigquery_adapter):
        service = SilverLabelService(bypass_validation=False)
        mock_bigquery_adapter.exec_query.side_effect = RuntimeError("BQ query failed: boom")

        result = service.load_silver_data(INVOICE_MONTH)

        assert result["status"] == "failed"
        assert "boom" in result["details"]
