"""Serviço da camada Unificado — consolidação multicloud (GCP/Tsuru/DBaaS).

Migrado de `gcp_labels/services/gcp_unificado_label_service.py` (legado),
mantendo paridade funcional (mesmas assinaturas públicas, mesmo SQL, mesma
lógica de validação por provedor).

Achados de paridade preservados fielmente (não corrigidos nesta migração):

- **Sem `labels` de custo nas chamadas a `exec_query`**: diferente de todas as
  outras camadas do medalhão (Silver, Gold Pre-Foundation, Gold Foundation,
  Gold), o service legado nunca define `self.labels` nem passa `labels=` ao
  `exec_query`. Os jobs desta camada não recebem o label
  `finops-workflow-layer` usado para auditoria de custo por camada em
  `INFORMATION_SCHEMA.JOBS_BY_PROJECT`.
- **`diff_total` soma diferenças com sinal, não valores absolutos**: em
  `check_result_query`, divergências positivas e negativas entre provedores
  podem se cancelar matematicamente antes de comparar com
  `cost_validation_limit` — uma divergência real grande pode passar
  despercebida se compensada por outra divergência de sinal oposto em outro
  provedor/coluna. Mantido fiel ao comportamento legado; não é uma decisão de
  design desta migração.
- **Achado documentado em `CLAUDE.md` da raiz do repositório**: o orquestrador
  legado (`gcp_labels/main.py`), no branch `pre_dbaas_tsuru` (modo padrão de
  produção via `gcp-cost-with-labels`), **não chama** `load_gold_unificado_data`
  — apenas o branch `layer=None`/`layer="unificado"` o faz. Ou seja, esta
  camada pode não estar sendo atualizada pelo fluxo automático diário em
  produção. Confirmar com o usuário antes de decidir se a migração replica ou
  corrige esse comportamento (ver CLAUDE.md).
"""

from __future__ import annotations

from datetime import datetime

import jinja2

from billing_common.adapters.bigquery import BigQueryAdapter
from billing_common.logging.json_logger import build_logger
from unificado_pipeline.config.env_configs import UnificadoEnvConfigs
from unificado_pipeline.templates.gold_unificada_query import (
    CHECK_GOLD_UNIFICADO_DATA,
    DELETE_GOLD_UNIFICADO_DATA,
    INSERT_GOLD_UNIFICADO_DATA,
    SELECT_GOLD_UNIFICADO_DATA,
)

logger = build_logger(name="unificado_pipeline.unificado_service")

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

_INVOICE_MONTH_FORMAT = "%Y-%m-%d"

_CHECK_COLUMNS = [
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


class UnificadoService:
    """Camada Unificado do medalhão `gcp_labels`: consolidação multicloud e validação cruzada de paridade."""

    def __init__(self, bypass_validation: bool = False) -> None:
        self.error_msgs: list[str] = []
        self.env_configs = UnificadoEnvConfigs()
        self.bigquery_adapter = BigQueryAdapter(project_id=self.env_configs.get_project_id())
        self.gcp_gold_unificado_label_table = self.env_configs.get_gcp_gold_unificado_table()
        self.cost_validation_limit = self.env_configs.get_cost_validation_limit()
        self.bypass_validation = bypass_validation
        self.project_id = self.env_configs.get_project_id()

    def load_gold_unificado_data(self, invoice_month: str) -> dict[str, object]:
        try:
            datetime.strptime(invoice_month, _INVOICE_MONTH_FORMAT)
            self.check_result_query(invoice_month)
            self.delete_data(invoice_month)
            self.insert_data(invoice_month)
            return {"status": "success", "details": self.error_msgs}
        except Exception as e:
            logger.error(
                f"[gold-unificado] Failed for invoice_month={invoice_month}: {e}",
                exc_info=True,
            )
            return {"status": "failed", "details": str(e)}

    def delete_data(self, invoice_month: str) -> None:
        query_parameters = {
            "gcp_gold_unificado_label_table": self.gcp_gold_unificado_label_table,
            "invoice_month": invoice_month,
        }
        query = _jinja_env.from_string(DELETE_GOLD_UNIFICADO_DATA).render(query_parameters)
        logger.info(
            f"[gold-unificado] Deleting invoice_month={invoice_month} "
            f"from {self.gcp_gold_unificado_label_table}"
        )
        self.bigquery_adapter.exec_query(query, month=invoice_month)

    def insert_data(self, invoice_month: str) -> None:
        query_parameters = {
            "gcp_gold_unificado_label_table": self.gcp_gold_unificado_label_table,
            "invoice_month": invoice_month,
            "select_gold_unificado_query": self.select_gold_unificado_query(invoice_month),
        }
        query = _jinja_env.from_string(INSERT_GOLD_UNIFICADO_DATA).render(query_parameters)
        logger.info(
            f"[gold-unificado] Inserting invoice_month={invoice_month} "
            f"into {self.gcp_gold_unificado_label_table}"
        )
        self.bigquery_adapter.exec_query(query, month=invoice_month)

    def select_gold_unificado_query(self, invoice_month: str) -> str:
        query_parameters = {"invoice_month": invoice_month, "project_id": self.project_id}
        return _jinja_env.from_string(SELECT_GOLD_UNIFICADO_DATA).render(query_parameters)

    def check_gold_unificado_data(self, select_gold_unificado_query: str, invoice_month: str) -> str:
        query_parameters = {
            "select_gold_unificado_query": select_gold_unificado_query,
            "invoice_month": invoice_month,
            "project_id": self.project_id,
        }
        logger.info(f"[gold-unificado] Checking invoice_month={invoice_month}")
        return _jinja_env.from_string(CHECK_GOLD_UNIFICADO_DATA).render(query_parameters)

    def check_result_query(self, invoice_month: str) -> None:
        if self.bypass_validation:
            return

        select_gold_unificado_query = self.select_gold_unificado_query(invoice_month)
        result_check_gold_unificado_data = self.check_gold_unificado_data(
            select_gold_unificado_query, invoice_month
        )
        rows_iterator = list(
            self.bigquery_adapter.exec_query(result_check_gold_unificado_data, month=invoice_month)
        )

        dict_check_unificado: dict[str, dict[str, float]] = {}
        for row in rows_iterator:
            dict_check_unificado[row.get("provedor")] = {
                column: row.get(column) for column in _CHECK_COLUMNS
            }

        dict_column_diff = {"GCP": {}, "Tsuru": {}, "DBaas": {}}
        for cost_column in _CHECK_COLUMNS:
            dict_column_diff["GCP"][cost_column] = (
                dict_check_unificado["GCP"][cost_column]
                - dict_check_unificado["GCP_gold"][cost_column]
            )
            dict_column_diff["Tsuru"][cost_column] = (
                dict_check_unificado["Tsuru"][cost_column]
                - dict_check_unificado["Tsuru_gold"][cost_column]
            )
            dict_column_diff["DBaas"][cost_column] = (
                dict_check_unificado["DBaaS"][cost_column]
                - dict_check_unificado["Dbaas_gold"][cost_column]
            )

        diff_total = 0
        for provedor in dict_column_diff:
            for column_diff in dict_column_diff[provedor].values():
                diff_total += column_diff

        if diff_total > self.cost_validation_limit:
            text_error = (
                f"Os custos totais não estão batendo por: {diff_total}. "
                f"As colunas não estão batendo por: {dict_column_diff}"
            )
            raise RuntimeError(text_error)

        if diff_total > 0.01:
            text_error = (
                f"Os custos totais não estão batendo por: {diff_total}. "
                f"As colunas não estão batendo por: {dict_column_diff}"
            )
            self.error_msgs.append(text_error)
