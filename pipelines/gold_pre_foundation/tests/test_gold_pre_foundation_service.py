"""Testes da camada Gold Pre-Foundation (`GoldPreFoundationService`).

Não há baseline de teste legado utilizável para esta camada específica — ver
docstring de `expected_gold_pre_foundation_queries.py` para o detalhe da
investigação. Estes testes foram escritos do zero contra o comportamento
real de `gold_label_pre_foundation_service.py` (legado) + o template SQL
real, no mesmo espírito de `pipelines/silver/tests/`.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from expected_gold_pre_foundation_queries import (
    EXPECTED_CHECK_GOLD_PRE_FOUNDATION_DATA,
    EXPECTED_DELETE_GOLD_PRE_FOUNDATION_DATA,
    EXPECTED_GENERATE_CUSTOM_COLUMNS,
    EXPECTED_GENERATE_NULL_COLUMNS,
    EXPECTED_INSERT_GOLD_PRE_FOUNDATION_DATA,
    EXPECTED_SELECT_GOLD_PRE_FOUNDATION_DATA,
    GCP_GOLD_PRE_FOUNDATION_TABLE,
    INVOICE_MONTH,
)
from gold_pre_foundation_pipeline.services.gold_pre_foundation_service import (
    GoldPreFoundationService,
)


def _row(custo_gold=0.0, creditos_gold=0.0, custo_silver=0.0, creditos_silver=0.0):
    """Constrói um stub de linha de resultado do BigQuery (dict-like .get())."""
    return {
        "custo_gold": custo_gold,
        "creditos_gold": creditos_gold,
        "custo_silver": custo_silver,
        "creditos_silver": creditos_silver,
    }


class TestGenerateCustomColumns:
    def test_generates_record_extraction_columns(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        result = service.generate_custom_columns("z.custo_unitario", ["squad", "produto"])

        assert result == EXPECTED_GENERATE_CUSTOM_COLUMNS

    def test_strips_whitespace_around_field_names(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        result = service.generate_custom_columns("z.custo_unitario", [" squad ", " produto"])

        assert result == EXPECTED_GENERATE_CUSTOM_COLUMNS

    def test_empty_fields_returns_empty_string(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        assert service.generate_custom_columns("z.custo_unitario", []) == ""


class TestGenerateNullColumns:
    def test_generates_ifnull_fallback_columns(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        result = service.generate_null_columns(["squad", "produto"])

        assert result == EXPECTED_GENERATE_NULL_COLUMNS

    def test_strips_whitespace_around_field_names(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        result = service.generate_null_columns([" squad ", " produto"])

        assert result == EXPECTED_GENERATE_NULL_COLUMNS

    def test_empty_fields_returns_empty_string(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        assert service.generate_null_columns([]) == ""


class TestSelectGoldPreFoundationData:
    def test_renders_select_with_current_template(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        query = service.select_gold_pre_foundation_data(INVOICE_MONTH)

        assert query == EXPECTED_SELECT_GOLD_PRE_FOUNDATION_DATA


class TestDeleteData:
    def test_renders_delete_query_with_current_template(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        service.delete_data(INVOICE_MONTH)

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_DELETE_GOLD_PRE_FOUNDATION_DATA
        assert GCP_GOLD_PRE_FOUNDATION_TABLE in called_query
        called_kwargs = mock_bigquery_adapter.exec_query.call_args.kwargs
        assert called_kwargs["labels"] == {
            "finops-workflow": "gcp",
            "finops-workflow-layer": "gcp-gold-pre-foundation",
        }
        assert called_kwargs["month"] == INVOICE_MONTH


class TestInsertData:
    def test_renders_insert_query_with_current_template(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        service.insert_data(INVOICE_MONTH)

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_INSERT_GOLD_PRE_FOUNDATION_DATA


class TestCheckGoldData:
    def test_no_message_when_delta_is_negligible(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)
        row = _row(custo_gold=100.0, creditos_gold=0.0, custo_silver=100.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        service.check_gold_data(INVOICE_MONTH)

        assert service.error_msgs == ""
        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_CHECK_GOLD_PRE_FOUNDATION_DATA

    def test_sets_error_msgs_when_delta_is_between_threshold_and_limit(
        self, gold_pre_foundation_env, mock_bigquery_adapter
    ):
        service = GoldPreFoundationService(bypass_validation=True)
        row = _row(custo_gold=100.0, creditos_gold=0.0, custo_silver=90.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        service.check_gold_data(INVOICE_MONTH)

        assert "diff: 10.0" in service.error_msgs
        assert INVOICE_MONTH in service.error_msgs

    def test_delta_below_threshold_does_not_set_error_msgs(
        self, gold_pre_foundation_env, mock_bigquery_adapter
    ):
        """Legado usa `> 0.01` (estrito), diferente da Silver que usa `>= 0.01`.

        Usa delta = 0.005 (exatamente representável em float dentro da
        tolerância do teste) em vez de tentar acertar `0.01` exato, já que
        `100.0 - 99.99` produz `0.010000000000005116` por imprecisão de
        ponto flutuante — o que tornaria o teste frágil e dependente de
        arredondamento, não do comportamento real de negócio (`> 0.01`).
        """
        service = GoldPreFoundationService(bypass_validation=True)
        row = _row(custo_gold=100.0, creditos_gold=0.0, custo_silver=99.995, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        service.check_gold_data(INVOICE_MONTH)

        assert service.error_msgs == ""

    def test_delta_exactly_at_limit_sets_error_msgs_but_does_not_raise(
        self, gold_pre_foundation_env, mock_bigquery_adapter
    ):
        """Fronteira exata: comparação é `> limit` (estrita), não `>= limit`.

        COST_VALIDATION_LIMIT do fixture é 15000. Um delta exatamente igual
        ao limite não deve disparar RuntimeError — só dispara quando o delta
        excede o limite. Usa valores inteiros (sem imprecisão de float) para
        que a fronteira seja exercitada de fato, não mascarada por
        arredondamento.
        """
        service = GoldPreFoundationService(bypass_validation=True)
        row = _row(custo_gold=15100.0, creditos_gold=0.0, custo_silver=100.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        service.check_gold_data(INVOICE_MONTH)

        assert "diff: 15000.0" in service.error_msgs

    def test_raises_when_delta_exceeds_limit(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)
        # COST_VALIDATION_LIMIT do fixture é 15000.
        row = _row(custo_gold=100_000.0, creditos_gold=0.0, custo_silver=0.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        with pytest.raises(RuntimeError, match="diff: 100000.0"):
            service.check_gold_data(INVOICE_MONTH)

    def test_raises_when_result_is_empty(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 0
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        with pytest.raises(RuntimeError, match="Empty check cost data query result"):
            service.check_gold_data(INVOICE_MONTH)


class TestLoadGoldPreFoundationData:
    def test_happy_path_returns_success(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)

        result = service.load_gold_pre_foundation_data(INVOICE_MONTH)

        assert result["status"] == "success"
        # delete + insert, sem check (bypass_validation=True)
        assert mock_bigquery_adapter.exec_query.call_count == 2

    def test_bypass_validation_false_runs_check(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=False)
        row = _row(custo_gold=100.0, creditos_gold=0.0, custo_silver=100.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        result = service.load_gold_pre_foundation_data(INVOICE_MONTH)

        assert result["status"] == "success"
        # check + delete + insert
        assert mock_bigquery_adapter.exec_query.call_count == 3

    def test_failure_returns_failed_status_with_details(self, gold_pre_foundation_env, mock_bigquery_adapter):
        service = GoldPreFoundationService(bypass_validation=True)
        mock_bigquery_adapter.exec_query.side_effect = RuntimeError("BQ query failed: boom")

        result = service.load_gold_pre_foundation_data(INVOICE_MONTH)

        assert result["status"] == "failed"
        assert "boom" in result["details"]

    def test_invalid_invoice_month_format_returns_failed(self, gold_pre_foundation_env, mock_bigquery_adapter):
        """Legado faz `datetime.strptime` dentro do mesmo `try` que captura tudo:
        uma data malformada produz status=failed, não uma exceção propagada."""
        service = GoldPreFoundationService(bypass_validation=True)

        result = service.load_gold_pre_foundation_data("not-a-date")

        assert result["status"] == "failed"
        mock_bigquery_adapter.exec_query.assert_not_called()

    def test_check_exceeding_limit_propagates_as_failed_status(
        self, gold_pre_foundation_env, mock_bigquery_adapter
    ):
        service = GoldPreFoundationService(bypass_validation=False)
        row = _row(custo_gold=100_000.0, creditos_gold=0.0, custo_silver=0.0, creditos_silver=0.0)
        mock_row_iterator = MagicMock()
        mock_row_iterator.total_rows = 1
        mock_row_iterator.__iter__.return_value = iter([row])
        mock_bigquery_adapter.exec_query.return_value = mock_row_iterator

        result = service.load_gold_pre_foundation_data(INVOICE_MONTH)

        assert result["status"] == "failed"
        assert "diff: 100000.0" in result["details"]
