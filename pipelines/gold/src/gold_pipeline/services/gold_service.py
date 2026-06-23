"""Serviço da camada Gold — rateio final por projeto/AR com labels do GCP.

Migrado de `gcp_labels/services/gold_label_service.py` (legado), mantendo
paridade funcional (mesmas assinaturas públicas, mesmo SQL, mesma validação
de custo).

Achados de código órfão (preservados fielmente, não corrigidos):
- `generate_custom_columns`/`generate_null_columns` existem no service legado
  mas não são chamados em `load_gold_data` — mantidos aqui pela mesma razão
  documentada em `gold_pre_foundation_pipeline`.
- `backup_rateio_bq_valiant` roda incondicionalmente ao final de
  `load_gold_data`, escrevendo numa tabela hardcoded de projeto fixo
  (`gglobo-billing-hdg-prd`), mesmo quando a camada roda em homologação.
"""

from __future__ import annotations

from datetime import datetime

import jinja2

from billing_common.adapters.bigquery import BigQueryAdapter
from billing_common.logging.json_logger import build_logger
from gold_pipeline.config.env_configs import GoldEnvConfigs
from gold_pipeline.templates.gold_query import (
    BACKUP_PESOS_RATEIO_BQ_FORA_DA_ORG,
    CHECK_GOLD_DATA,
    DELETE_GOLD_DATA,
    INSERT_GOLD_DATA,
    SELECT_GOLD_DATA,
)
from gold_pipeline.templates.lancamentos_looker_merge_query import LOOKER_MERGE_QUERY

logger = build_logger(name="gold_pipeline.gold_service")

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

_INVOICE_MONTH_FORMAT = "%Y-%m-%d"


class GoldService:
    """Camada Gold do medalhão `gcp_labels`: rateio final por projeto/AR e validação de paridade de custo."""

    def __init__(self, bypass_validation: bool = False) -> None:
        self.error_msgs = ""
        self.env_configs = GoldEnvConfigs()
        self.bigquery_adapter = BigQueryAdapter(project_id=self.env_configs.get_project_id())
        self.bq_table_custo_unitario_fields = self.env_configs.get_bq_table_custo_unitario_fields()
        self.cost_validation_limit = self.env_configs.get_cost_validation_limit()
        self.gcp_gold_label_foundation_dashboard_table = (
            self.env_configs.get_gcp_gold_foundation_dashboard_table()
        )
        self.gcp_gold_label_table = self.env_configs.get_gcp_gold_table()
        self.gcp_gold_label_pre_foundation_table = (
            self.env_configs.get_gcp_gold_pre_foundation_table()
        )
        self.gcp_marketplace_services_table = self.env_configs.get_gcp_marketplace_services_table()
        self.bypass_validation = bypass_validation
        self.labels = {"finops-workflow": "gcp", "finops-workflow-layer": "gcp-gold"}

    def load_gold_data(self, invoice_month: str) -> dict[str, str]:
        try:
            datetime.strptime(invoice_month, _INVOICE_MONTH_FORMAT)
            if not self.bypass_validation:
                self.check_gold_data(invoice_month)
            self.delete_data(invoice_month)
            self.insert_data(invoice_month)
            self.backup_rateio_bq_valiant()
            return {"status": "success", "details": self.error_msgs}
        except Exception as e:
            logger.error(f"[gold] Failed for invoice_month={invoice_month}: {e}", exc_info=True)
            return {"status": "failed", "details": str(e)}

    def check_gold_data(self, invoice_month: str) -> None:
        query_parameters = {
            "invoice_month": invoice_month,
            "gold_pre_foundation": self.gcp_gold_label_pre_foundation_table,
            "select_gold_data": self.select_gold_data(invoice_month),
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(CHECK_GOLD_DATA).render(query_parameters)
        logger.info(f"[gold] Checking invoice_month={invoice_month}")
        rows_iterator = self.bigquery_adapter.exec_query(
            query, labels=self.labels, month=invoice_month
        )

        if not rows_iterator.total_rows:
            raise RuntimeError("Empty check cost data query result")
        result = next(iter(rows_iterator))

        custo_gold = result.get("custo_gold")
        creditos_gold = result.get("creditos_gold")
        custo_silver = result.get("custo_silver")
        creditos_silver = result.get("creditos_silver")
        total_gold = custo_gold + creditos_gold
        total_silver = custo_silver + creditos_silver
        cost_delta = abs(total_gold - total_silver)
        logger.info(
            f"[gold] Check result | "
            f"custo_gold={custo_gold:.4f} creditos_gold={creditos_gold:.4f} total_gold={total_gold:.4f} | "
            f"custo_silver={custo_silver:.4f} creditos_silver={creditos_silver:.4f} total_silver={total_silver:.4f} | "
            f"delta={cost_delta:.4f} limit={self.cost_validation_limit}"
        )

        text_error = (
            f"invoice_month: {invoice_month}, diff: {cost_delta}, "
            f"total_gold: {total_gold}, total_silver: {total_silver}"
        )
        if cost_delta > self.cost_validation_limit:
            raise RuntimeError(text_error)
        if cost_delta > 0.01:
            self.error_msgs = text_error

    def select_gold_data(self, invoice_month: str) -> str:
        query_parameters = {
            "invoice_month": invoice_month,
            "gold_pre_foundation": self.gcp_gold_label_pre_foundation_table,
            "gcp_marketplace_services_table": self.gcp_marketplace_services_table,
            "project_id": self.env_configs.get_project_id(),
            "gcp_billing_foundation_labels_dashboard": (
                self.gcp_gold_label_foundation_dashboard_table
            ),
        }
        return _jinja_env.from_string(SELECT_GOLD_DATA).render(query_parameters)

    def delete_data(self, invoice_month: str) -> None:
        query_parameters = {
            "gcp_label_gold_table": self.gcp_gold_label_table,
            "invoice_month": invoice_month,
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(DELETE_GOLD_DATA).render(query_parameters)
        logger.info(f"[gold] Deleting invoice_month={invoice_month} from {self.gcp_gold_label_table}")
        self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)

    def insert_data(self, invoice_month: str) -> None:
        query_parameters = {
            "invoice_month": invoice_month,
            "select_gold_data": self.select_gold_data(invoice_month),
            "final_table": self.gcp_gold_label_table,
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(INSERT_GOLD_DATA).render(query_parameters)
        logger.info(f"[gold] Inserting invoice_month={invoice_month} into {self.gcp_gold_label_table}")
        self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)
        logger.info(f"[gold] Merging Looker lancamentos data for invoice_month={invoice_month}")
        query_merge_looker_data = _jinja_env.from_string(LOOKER_MERGE_QUERY).render(
            query_parameters
        )
        self.bigquery_adapter.exec_query(
            query_merge_looker_data, labels=self.labels, month=invoice_month
        )

    def generate_custom_columns(self, record_column_name: str, custom_fields: list[str]) -> str:
        """Achado de código órfão: não é chamado em `load_gold_data`. Mantido fiel ao legado."""
        custom_columns = ""
        for column_name in custom_fields:
            custom_columns += (
                f"(SELECT value FROM {record_column_name} WHERE key = '{column_name.strip()}') "
                f"as {column_name.strip()}, "
            )
        return custom_columns.rstrip()

    def generate_null_columns(self, custom_fields: list[str]) -> str:
        """Achado de código órfão: não é chamado em `load_gold_data`. Mantido fiel ao legado."""
        null_columns = ""
        for column_name in custom_fields:
            null_columns += (
                f"IFNULL({column_name.strip()}, '{column_name.strip()}-nao-identificado') "
                f"AS {column_name.strip()}, "
            )
        return null_columns.rstrip()

    def backup_rateio_bq_valiant(self) -> None:
        self.bigquery_adapter.exec_query(BACKUP_PESOS_RATEIO_BQ_FORA_DA_ORG, labels=self.labels)
