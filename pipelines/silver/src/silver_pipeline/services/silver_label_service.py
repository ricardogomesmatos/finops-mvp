"""Serviço da camada Silver — aplica labels de negócio sobre o billing raw do GCP.

Migrado de `gcp_labels/services/silver_label_service.py` (legado), mantendo
paridade funcional (mesmas assinaturas públicas, mesmo comportamento de
validação de custo, mesma fórmula de partição). Diferenças deliberadas:

- Importa ``BigQueryAdapter``, ``build_logger`` e ``DateUtil`` de
  ``billing_common`` em vez de manter cópias locais em ``utils/``.
- ``BigQueryAdapter`` agora recebe ``project_id`` explicitamente no construtor
  (em vez de resolver sozinho via ``EnvConfigs()`` interno).
- ``generate_partition_limit_from_invoice_month`` usa
  ``DateUtil.get_last_day_of_this_month`` em vez de reimplementar a mesma conta
  inline. ``DateUtil.get_last_day_of_this_month`` recebe e retorna ``date``
  (não ``datetime``); o ponto de entrada do método (``datetime.strptime``)
  continua produzindo um ``datetime``, então a chamada converte explicitamente
  para ``date`` antes de delegar, e ambos os limites de partição são formatados
  a partir de objetos ``date``/``datetime`` com ``strftime`` — sem perda de
  precisão, já que a granularidade usada em toda a função é de dia.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import jinja2

from billing_common.adapters.bigquery import BigQueryAdapter
from billing_common.dates.date_util import DateUtil
from billing_common.logging.json_logger import build_logger
from silver_pipeline.config.env_configs import SilverEnvConfigs
from silver_pipeline.templates.silver_query import (
    CHECK_SILVER_DATA,
    DELETE_SILVER_DATA,
    INSERT_SILVER_DATA,
    SELECT_RAW_LABEL_DATA,
)

logger = build_logger(name="silver_pipeline.silver_label_service")

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

_PARTITION_DAYS_BEFORE = 17
_PARTITION_DAYS_AFTER = 10


class SilverLabelService:
    """Camada Silver do medalhão `gcp_labels`: aplica labels e valida paridade de custo."""

    def __init__(self, bypass_validation: bool = False) -> None:
        self.env_configs = SilverEnvConfigs()
        self.bypass_validation = bypass_validation
        self.bigquery_adapter = BigQueryAdapter(project_id=self.env_configs.get_project_id())
        self.labels = {"finops-workflow": "gcp", "finops-workflow-layer": "gcp-silver"}

    def load_silver_data(self, invoice_month: str) -> dict[str, str]:
        try:
            partition_limits = self.generate_partition_limit_from_invoice_month(invoice_month)
            message = self.check_silver_data(invoice_month, partition_limits)
            self.delete_data(invoice_month)
            self.insert_data(invoice_month, partition_limits)
            return {"status": "success", "details": message}
        except Exception as e:
            logger.error(f"[silver] Failed for invoice_month={invoice_month}: {e}", exc_info=True)
            return {"status": "failed", "details": str(e)}

    def check_silver_data(
        self, invoice_month: str, partition_limits: tuple[str, str]
    ) -> str | None:
        if not self.bypass_validation:
            if invoice_month and partition_limits:
                result_row = self.get_check_data(invoice_month, partition_limits)
                return self.check_cost_data(result_row, invoice_month)
            else:
                raise RuntimeError("Check cost data parameters can't be null")
        return None

    def get_check_data(
        self, invoice_month: str, partition_limits: tuple[str, str]
    ) -> dict[str, int]:
        query_parameters = {
            "select_silver_data": self.generate_silver_query(invoice_month, partition_limits),
            "invoice_month": invoice_month,
            "partition_start": partition_limits[0],
            "partition_end": partition_limits[1],
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(CHECK_SILVER_DATA).render(query_parameters)
        logger.info(f"[silver] Checking invoice_month={invoice_month}")
        row_iterator = self.bigquery_adapter.exec_query(
            query, labels=self.labels, month=invoice_month
        )
        if not row_iterator.total_rows:
            raise RuntimeError("Empty check cost data query result")
        return next(iter(row_iterator))

    def generate_silver_query(self, invoice_month: str, partition_limits: tuple[str, str]) -> str:
        query_parameters = {
            "invoice_month": invoice_month,
            "partition_start": partition_limits[0],
            "partition_end": partition_limits[1],
            "project_id": self.env_configs.get_project_id(),
        }
        return _jinja_env.from_string(SELECT_RAW_LABEL_DATA).render(query_parameters)

    def check_cost_data(self, query_result_row, invoice_month: str) -> str | None:
        custo_silver = query_result_row.get("custo_silver")
        credito_silver = query_result_row.get("credito_silver")
        custo_raw = query_result_row.get("custo_raw")
        credito_raw = query_result_row.get("credito_raw")
        total_silver = custo_silver + credito_silver
        total_raw = custo_raw + credito_raw
        cost_delta = abs(total_silver - total_raw)
        limit = self.env_configs.get_cost_validation_limit()
        logger.info(
            f"[silver] Check result | "
            f"custo_silver={custo_silver:.4f} credito_silver={credito_silver:.4f} total_silver={total_silver:.4f} | "
            f"custo_raw={custo_raw:.4f} credito_raw={credito_raw:.4f} total_raw={total_raw:.4f} | "
            f"delta={cost_delta:.4f} limit={limit}"
        )

        message = (
            f"invoice_month: {invoice_month}, diff: {cost_delta}, "
            f"total_silver: {total_silver}, total_raw: {total_raw}"
        )
        if cost_delta > limit:
            raise RuntimeError(message)
        if cost_delta >= 0.01:
            return message
        return None

    def delete_data(self, invoice_month: str) -> None:
        query_parameters = {
            "gcp_silver_label_table": self.env_configs.get_gcp_silver_label_table(),
            "invoice_month": invoice_month,
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(DELETE_SILVER_DATA).render(query_parameters)
        logger.info(
            f"[silver] Deleting invoice_month={invoice_month} "
            f"from {self.env_configs.get_gcp_silver_label_table()}"
        )
        self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)

    def insert_data(self, invoice_month: str, partition_limits: tuple[str, str]) -> None:
        query_parameters = {
            "select_silver_data": self.generate_silver_query(invoice_month, partition_limits),
            "gcp_silver_label_table": self.env_configs.get_gcp_silver_label_table(),
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(INSERT_SILVER_DATA).render(query_parameters)
        logger.info(
            f"[silver] Inserting invoice_month={invoice_month} "
            f"into {self.env_configs.get_gcp_silver_label_table()}"
        )
        self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)

    def generate_partition_limit_from_invoice_month(self, invoice_month: str) -> tuple[str, str]:
        datetime_first_day_of_month = datetime.strptime(invoice_month, "%Y-%m-%d").replace(day=1)
        last_day_of_month = DateUtil.get_last_day_of_this_month(datetime_first_day_of_month.date())
        partition_start = (
            datetime_first_day_of_month - timedelta(days=_PARTITION_DAYS_BEFORE)
        ).strftime("%Y-%m-%d")
        partition_end = (last_day_of_month + timedelta(days=_PARTITION_DAYS_AFTER)).strftime(
            "%Y-%m-%d"
        )
        return partition_start, partition_end
