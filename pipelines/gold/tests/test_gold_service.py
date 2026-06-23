"""Testes da camada Gold (`GoldService`).

A baseline legada (`gcp_labels/tests/test_gold_label_service.py`) testa um SQL
desatualizado (ver docstring de `expected_gold_queries.py`) — os testes deste
diretório são escritos do zero contra o comportamento real do service +
template SQL atuais, no mesmo espírito de
`pipelines/gold_pre_foundation/tests/`.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from expected_gold_queries import (
    EXPECTED_CHECK_GOLD_DATA,
    EXPECTED_DELETE_GOLD_DATA,
    EXPECTED_GENERATE_CUSTOM_COLUMNS,
    EXPECTED_GENERATE_NULL_COLUMNS,
    EXPECTED_INSERT_GOLD_DATA,
    EXPECTED_LOOKER_MERGE_QUERY,
    EXPECTED_SELECT_GOLD_DATA,
    GCP_GOLD_TABLE,
    INVOICE_MONTH,
)
from gold_pipeline.services.gold_service import GoldService


def _row(custo_gold=0.0, creditos_gold=0.0, custo_silver=0.0, creditos_silver=0.0):
    return {
        "custo_gold": custo_gold,
        "creditos_gold": creditos_gold,
        "custo_silver": custo_silver,
        "creditos_silver": creditos_silver,
    }


class TestGenerateCustomColumns:
    def test_generates_record_extraction_columns(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)

        result = service.generate_custom_columns("z.custo_unitario", ["squad", "produto"])

        assert result == EXPECTED_GENERATE_CUSTOM_COLUMNS


class TestGenerateNullColumns:
    def test_generates_ifnull_fallback_columns(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)

        result = service.generate_null_columns(["squad", "produto"])

        assert result == EXPECTED_GENERATE_NULL_COLUMNS


class TestSelectGoldData:
    def test_renders_select_with_current_template(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)

        query = service.select_gold_data(INVOICE_MONTH)

        assert query == EXPECTED_SELECT_GOLD_DATA


class TestDeleteData:
    def test_renders_delete_query_with_current_template(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)

        service.delete_data(INVOICE_MONTH)

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_DELETE_GOLD_DATA
        assert GCP_GOLD_TABLE in called_query


class TestInsertData:
    def test_inserts_and_merges_looker_lancamentos(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)

        service.insert_data(INVOICE_MONTH)

        calls = mock_bigquery_adapter.exec_query.call_args_list
        assert len(calls) == 2
        assert calls[0].args[0] == EXPECTED_INSERT_GOLD_DATA
        assert calls[1].args[0] == EXPECTED_LOOKER_MERGE_QUERY


class TestCheckGoldData:
    def test_no_message_when_delta_is_negligible(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)
        row = _row(custo_gold=100.0, creditos_gold=0.0, custo_silver=100.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        service.check_gold_data(INVOICE_MONTH)

        assert service.error_msgs == ""
        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_CHECK_GOLD_DATA

    def test_raises_when_delta_exceeds_limit(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)
        row = _row(custo_gold=100_000.0, creditos_gold=0.0, custo_silver=0.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        with pytest.raises(RuntimeError, match="diff: 100000.0"):
            service.check_gold_data(INVOICE_MONTH)

    def test_raises_when_result_is_empty(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 0
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        with pytest.raises(RuntimeError, match="Empty check cost data query result"):
            service.check_gold_data(INVOICE_MONTH)


class TestLoadGoldData:
    def test_happy_path_returns_success(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)

        result = service.load_gold_data(INVOICE_MONTH)

        assert result["status"] == "success"
        # delete + insert + looker merge + backup, sem check (bypass_validation=True)
        assert mock_bigquery_adapter.exec_query.call_count == 4

    def test_bypass_validation_false_runs_check(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=False)
        row = _row(custo_gold=100.0, creditos_gold=0.0, custo_silver=100.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        result = service.load_gold_data(INVOICE_MONTH)

        assert result["status"] == "success"
        # check + delete + insert + looker merge + backup
        assert mock_bigquery_adapter.exec_query.call_count == 5

    def test_failure_returns_failed_status_with_details(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)
        mock_bigquery_adapter.exec_query.side_effect = RuntimeError("BQ query failed: boom")

        result = service.load_gold_data(INVOICE_MONTH)

        assert result["status"] == "failed"
        assert "boom" in result["details"]

    def test_invalid_invoice_month_format_returns_failed(self, gold_env, mock_bigquery_adapter):
        service = GoldService(bypass_validation=True)

        result = service.load_gold_data("not-a-date")

        assert result["status"] == "failed"
        mock_bigquery_adapter.exec_query.assert_not_called()
