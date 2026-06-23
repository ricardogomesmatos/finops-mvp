"""Testes da camada Gold Foundation (`GoldFoundationService`).

Escritos do zero contra o comportamento real de
`gold_label_foundation_service.py` (legado) + o template SQL real, no mesmo
espírito de `pipelines/gold_pre_foundation/tests/`.
"""

from __future__ import annotations

from expected_gold_foundation_queries import (
    EXPECTED_DELETE_GOLD_FOUNDATION_DASHBOARD_DATA,
    EXPECTED_DELETE_GOLD_FOUNDATION_DATA,
    EXPECTED_INSERT_GOLD_FOUNDATION_DASHBOARD_DATA,
    EXPECTED_INSERT_GOLD_FOUNDATION_DATA,
    GCP_GOLD_FOUNDATION_DASHBOARD_TABLE,
    GCP_GOLD_FOUNDATION_TABLE,
    GCP_GOLD_PRE_FOUNDATION_TABLE,
    INVOICE_MONTH,
    PROJECT_ID,
)
from gold_foundation_pipeline.services.gold_foundation_service import GoldFoundationService


class TestDeleteData:
    def test_renders_delete_query_for_foundation_table(
        self, gold_foundation_env, mock_bigquery_adapter
    ):
        service = GoldFoundationService()

        service.delete_data(
            INVOICE_MONTH,
            {
                "target_table": GCP_GOLD_FOUNDATION_TABLE,
                "invoice_month": INVOICE_MONTH,
                "project_id": PROJECT_ID,
            },
        )

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_DELETE_GOLD_FOUNDATION_DATA
        called_kwargs = mock_bigquery_adapter.exec_query.call_args.kwargs
        assert called_kwargs["labels"] == {
            "finops-workflow": "gcp",
            "finops-workflow-layer": "gcp-gold",
        }
        assert called_kwargs["month"] == INVOICE_MONTH


class TestInsertData:
    def test_layer_gold_renders_insert_into_foundation_table(
        self, gold_foundation_env, mock_bigquery_adapter
    ):
        service = GoldFoundationService()

        service.insert_data(
            INVOICE_MONTH,
            {
                "invoice_month": INVOICE_MONTH,
                "gcp_gold_label_foundation_table": GCP_GOLD_FOUNDATION_TABLE,
                "project_id": PROJECT_ID,
                "gold_pre_foundation_table": GCP_GOLD_PRE_FOUNDATION_TABLE,
            },
            layer="gold",
        )

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_INSERT_GOLD_FOUNDATION_DATA

    def test_layer_dashboard_renders_insert_into_dashboard_table(
        self, gold_foundation_env, mock_bigquery_adapter
    ):
        service = GoldFoundationService()

        service.insert_data(
            INVOICE_MONTH,
            {
                "invoice_month": INVOICE_MONTH,
                "gcp_gold_label_foundation_dashboard_table": GCP_GOLD_FOUNDATION_DASHBOARD_TABLE,
                "project_id": PROJECT_ID,
            },
            layer="dashboard",
        )

        called_query = mock_bigquery_adapter.exec_query.call_args.args[0]
        assert called_query == EXPECTED_INSERT_GOLD_FOUNDATION_DASHBOARD_DATA


class TestLoadGoldFoundationData:
    def test_happy_path_runs_delete_and_insert_for_both_tables(
        self, gold_foundation_env, mock_bigquery_adapter
    ):
        service = GoldFoundationService()

        result = service.load_gold_foundation_data(INVOICE_MONTH)

        assert result == {"status": "success", "details": ""}
        assert mock_bigquery_adapter.exec_query.call_count == 4
        calls = mock_bigquery_adapter.exec_query.call_args_list
        assert calls[0].args[0] == EXPECTED_DELETE_GOLD_FOUNDATION_DATA
        assert calls[1].args[0] == EXPECTED_INSERT_GOLD_FOUNDATION_DATA
        assert calls[2].args[0] == EXPECTED_DELETE_GOLD_FOUNDATION_DASHBOARD_DATA
        assert calls[3].args[0] == EXPECTED_INSERT_GOLD_FOUNDATION_DASHBOARD_DATA

    def test_bypass_validation_argument_has_no_effect(
        self, gold_foundation_env, mock_bigquery_adapter
    ):
        """Achado de paridade: `bypass_validation` é aceito mas não usado (camada não valida custo)."""
        service = GoldFoundationService(bypass_validation=True)

        result = service.load_gold_foundation_data(INVOICE_MONTH)

        assert result["status"] == "success"
        assert mock_bigquery_adapter.exec_query.call_count == 4

    def test_failure_returns_failed_status_with_details(
        self, gold_foundation_env, mock_bigquery_adapter
    ):
        service = GoldFoundationService()
        mock_bigquery_adapter.exec_query.side_effect = RuntimeError("BQ query failed: boom")

        result = service.load_gold_foundation_data(INVOICE_MONTH)

        assert result["status"] == "failed"
        assert "boom" in result["details"]

    def test_invalid_invoice_month_format_returns_failed(
        self, gold_foundation_env, mock_bigquery_adapter
    ):
        service = GoldFoundationService()

        result = service.load_gold_foundation_data("not-a-date")

        assert result["status"] == "failed"
        mock_bigquery_adapter.exec_query.assert_not_called()
