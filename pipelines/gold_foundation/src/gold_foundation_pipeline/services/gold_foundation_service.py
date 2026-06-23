"""Serviço da camada Gold Foundation — rateio Foundation sobre a Gold Pre-Foundation.

Migrado de `gcp_labels/services/gold_label_foundation_service.py` (legado),
mantendo paridade funcional (mesmas assinaturas públicas, mesmo SQL).

Achado de código órfão (preservado fielmente, não corrigido nesta migração):
o construtor legado aceita `bypass_validation`, mas nunca o armazena nem o
usa — esta camada não tem validação de custo (diferente de Gold
Pre-Foundation e Gold). O orquestrador legado (`gcp_labels/main.py`) também
nunca passa esse argumento ao instanciar o serviço. Mantido aqui apenas para
não alterar a assinatura pública do construtor.
"""

from __future__ import annotations

from datetime import datetime

import jinja2

from billing_common.adapters.bigquery import BigQueryAdapter
from billing_common.logging.json_logger import build_logger
from gold_foundation_pipeline.config.env_configs import GoldFoundationEnvConfigs
from gold_foundation_pipeline.templates.gold_foundation_query import (
    DELETE_GOLD_FOUNDATION_DATA,
    INSERT_GOLD_FOUNDATION_DASHBOARD_DATA,
    INSERT_GOLD_FOUNDATION_DATA,
)

logger = build_logger(name="gold_foundation_pipeline.gold_foundation_service")

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

_INVOICE_MONTH_FORMAT = "%Y-%m-%d"


class GoldFoundationService:
    """Camada Gold Foundation do medalhão `gcp_labels`: rateio sobre projetos Foundation."""

    def __init__(self, bypass_validation: bool = False) -> None:
        self.error_msgs = ""
        self.env_configs = GoldFoundationEnvConfigs()
        self.bigquery_adapter = BigQueryAdapter(project_id=self.env_configs.get_project_id())
        self.gcp_gold_label_pre_foundation_table = (
            self.env_configs.get_gcp_gold_pre_foundation_table()
        )
        self.gcp_gold_label_foundation_table = self.env_configs.get_gcp_gold_foundation_table()
        self.gcp_gold_label_foundation_dashboard_table = (
            self.env_configs.get_gcp_gold_foundation_dashboard_table()
        )
        self.labels = {"finops-workflow": "gcp", "finops-workflow-layer": "gcp-gold"}
        self.project_id = self.env_configs.get_project_id()

    def load_gold_foundation_data(self, invoice_month: str) -> dict[str, str]:
        try:
            datetime.strptime(invoice_month, _INVOICE_MONTH_FORMAT)

            logger.info(
                f"[gold-foundation] Deleting invoice_month={invoice_month} "
                f"from {self.gcp_gold_label_foundation_table}"
            )
            query_parameters = {
                "target_table": self.gcp_gold_label_foundation_table,
                "invoice_month": invoice_month,
                "project_id": self.project_id,
            }
            self.delete_data(invoice_month, query_parameters)

            logger.info(
                f"[gold-foundation] Inserting invoice_month={invoice_month} "
                f"into {self.gcp_gold_label_foundation_table}"
            )
            query_parameters = {
                "invoice_month": invoice_month,
                "gcp_gold_label_foundation_table": self.gcp_gold_label_foundation_table,
                "project_id": self.project_id,
                "gold_pre_foundation_table": self.gcp_gold_label_pre_foundation_table,
            }
            self.insert_data(invoice_month, query_parameters, layer="gold")

            logger.info(
                f"[gold-foundation] Deleting invoice_month={invoice_month} "
                f"from {self.gcp_gold_label_foundation_dashboard_table}"
            )
            query_parameters = {
                "target_table": self.gcp_gold_label_foundation_dashboard_table,
                "invoice_month": invoice_month,
                "project_id": self.project_id,
            }
            self.delete_data(invoice_month, query_parameters)

            logger.info(
                f"[gold-foundation] Inserting invoice_month={invoice_month} "
                f"into {self.gcp_gold_label_foundation_dashboard_table}"
            )
            query_parameters = {
                "invoice_month": invoice_month,
                "gcp_gold_label_foundation_dashboard_table": (
                    self.gcp_gold_label_foundation_dashboard_table
                ),
                "project_id": self.project_id,
            }
            self.insert_data(invoice_month, query_parameters, layer="dashboard")

            return {"status": "success", "details": self.error_msgs}
        except Exception as e:
            logger.error(
                f"[gold-foundation] Failed for invoice_month={invoice_month}: {e}",
                exc_info=True,
            )
            return {"status": "failed", "details": str(e)}

    def delete_data(self, invoice_month: str, query_parameters: dict[str, str]) -> None:
        query = _jinja_env.from_string(DELETE_GOLD_FOUNDATION_DATA).render(query_parameters)
        self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)

    def insert_data(self, invoice_month: str, query_parameters: dict[str, str], layer: str) -> None:
        if layer == "gold":
            query = _jinja_env.from_string(INSERT_GOLD_FOUNDATION_DATA).render(query_parameters)
            self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)
            return None
        query = _jinja_env.from_string(INSERT_GOLD_FOUNDATION_DASHBOARD_DATA).render(
            query_parameters
        )
        self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)
