"""Serviço da camada Gold Pre-Foundation — pré-rateio sobre a Silver com labels do GCP.

Migrado de `gcp_labels/services/gold_label_pre_foundation_service.py` (legado),
mantendo paridade funcional (mesmas assinaturas públicas, mesmo comportamento
de validação de custo, mesmo SQL). Diferenças deliberadas em relação ao
legado:

- Importa ``BigQueryAdapter`` e ``build_logger`` de ``billing_common`` em vez
  de manter cópias locais em ``utils/``/``adapters/`` (mesmo padrão da camada
  Silver).
- ``BigQueryAdapter`` agora recebe ``project_id`` explicitamente no construtor
  (em vez de resolver sozinho via ``EnvConfigs()`` interno, como o legado
  fazia chamando ``BigQueryAdapter()`` sem argumentos).
- Esta camada não usa ``DateUtil``/cálculo de partição (diferente da Silver):
  ela lê diretamente da tabela ``gcp_billing_silver_label``, já particionada
  por ``invoice_month``, sem janela de ``PARTITION_TIME`` própria. A validação
  de formato de data (``datetime.strptime(invoice_month, "%Y-%m-%d")``) é
  preservada dentro do mesmo ``try`` de ``load_gold_pre_foundation_data``,
  replicando o comportamento exato do legado (uma data malformada produz
  ``status="failed"`` em vez de propagar a exceção).
- ``check_gold_data`` mantém a assinatura ``-> None`` e o efeito colateral em
  ``self.error_msgs`` do legado (em vez de retornar a mensagem, como a Silver
  faz em ``check_cost_data``). Optou-se por preservar o contrato original aqui
  porque ``error_msgs`` já é lido em ``load_gold_pre_foundation_data`` no
  mesmo objeto ``self`` — mudar para retorno explícito não traria ganho de
  clareza nesta camada e aumentaria o diff de paridade sem necessidade.

Achado de código órfão (documentado em detalhe em
``templates/gold_pre_foundation_query.py``): ``CUSTO_UNITARIO_FIELDS`` e os
parâmetros Jinja que ``generate_custom_columns``/``generate_null_columns``
produzem são montados e passados ao ``render()`` exatamente como no legado,
mas não têm efeito hoje porque os placeholders correspondentes não existem
mais no corpo das queries. Replicado fielmente — não corrigido nesta entrega.
"""

from __future__ import annotations

from datetime import datetime

import jinja2

from billing_common.adapters.bigquery import BigQueryAdapter
from billing_common.logging.json_logger import build_logger
from gold_pre_foundation_pipeline.config.env_configs import GoldPreFoundationEnvConfigs
from gold_pre_foundation_pipeline.templates.gold_pre_foundation_query import (
    CHECK_GOLD_PRE_FOUNDATION_DATA,
    DELETE_GOLD_PRE_FOUNDATION_DATA,
    INSERT_GOLD_PRE_FOUNDATION_DATA,
    SELECT_GOLD_PRE_FOUNDATION_DATA,
)

logger = build_logger(name="gold_pre_foundation_pipeline.gold_pre_foundation_service")

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

_INVOICE_MONTH_FORMAT = "%Y-%m-%d"


class GoldPreFoundationService:
    """Camada Gold Pre-Foundation do medalhão `gcp_labels`: pré-rateio e validação de paridade de custo."""

    def __init__(self, bypass_validation: bool = False) -> None:
        self.error_msgs = ""
        self.env_configs = GoldPreFoundationEnvConfigs()
        self.bigquery_adapter = BigQueryAdapter(project_id=self.env_configs.get_project_id())
        self.bq_table_custo_unitario_fields = self.env_configs.get_bq_table_custo_unitario_fields()
        self.cost_validation_limit = self.env_configs.get_cost_validation_limit()
        self.gcp_gold_label_pre_foundation_table = (
            self.env_configs.get_gcp_gold_pre_foundation_table()
        )
        self.gcp_silver_label_table = self.env_configs.get_gcp_silver_label_table()
        self.gcp_marketplace_services_table = self.env_configs.get_gcp_marketplace_services_table()
        self.bypass_validation = bypass_validation
        self.labels = {
            "finops-workflow": "gcp",
            "finops-workflow-layer": "gcp-gold-pre-foundation",
        }

    def load_gold_pre_foundation_data(self, invoice_month: str) -> dict[str, str]:
        try:
            datetime.strptime(invoice_month, _INVOICE_MONTH_FORMAT)
            if not self.bypass_validation:
                self.check_gold_data(invoice_month)
            self.delete_data(invoice_month)
            self.insert_data(invoice_month)
            return {"status": "success", "details": self.error_msgs}
        except Exception as e:
            logger.error(
                f"[gold-pre-foundation] Failed for invoice_month={invoice_month}: {e}",
                exc_info=True,
            )
            return {"status": "failed", "details": str(e)}

    def check_gold_data(self, invoice_month: str) -> None:
        query_parameters = {
            "invoice_month": invoice_month,
            "gcp_billing_silver": self.gcp_silver_label_table,
            "select_gold_pre_foundation_data": self.select_gold_pre_foundation_data(invoice_month),
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(CHECK_GOLD_PRE_FOUNDATION_DATA).render(query_parameters)
        logger.info(f"[gold-pre-foundation] Checking invoice_month={invoice_month}")
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
            f"[gold-pre-foundation] Check result | "
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

    def select_gold_pre_foundation_data(self, invoice_month: str) -> str:
        query_parameters = {
            "invoice_month": invoice_month,
            "gcp_billing_silver": self.gcp_silver_label_table,
            "gcp_marketplace_services_table": self.gcp_marketplace_services_table,
            "custo_unitario_column_names": ", ".join(self.bq_table_custo_unitario_fields),
            "generate_null_columns": self.generate_null_columns(self.bq_table_custo_unitario_fields),
            "project_id": self.env_configs.get_project_id(),
        }
        return _jinja_env.from_string(SELECT_GOLD_PRE_FOUNDATION_DATA).render(query_parameters)

    def delete_data(self, invoice_month: str) -> None:
        query_parameters = {
            "gcp_label_gold_pre_foundation_table": self.gcp_gold_label_pre_foundation_table,
            "invoice_month": invoice_month,
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(DELETE_GOLD_PRE_FOUNDATION_DATA).render(query_parameters)
        logger.info(
            f"[gold-pre-foundation] Deleting invoice_month={invoice_month} "
            f"from {self.gcp_gold_label_pre_foundation_table}"
        )
        self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)

    def insert_data(self, invoice_month: str) -> None:
        query_parameters = {
            "invoice_month": invoice_month,
            "custo_unitario_column_names": self.generate_custom_columns(
                "z.custo_unitario", self.bq_table_custo_unitario_fields
            ),
            "select_gold_pre_foundation_data": self.select_gold_pre_foundation_data(invoice_month),
            "final_table": self.gcp_gold_label_pre_foundation_table,
            "project_id": self.env_configs.get_project_id(),
        }
        query = _jinja_env.from_string(INSERT_GOLD_PRE_FOUNDATION_DATA).render(query_parameters)
        logger.info(
            f"[gold-pre-foundation] Inserting invoice_month={invoice_month} "
            f"into {self.gcp_gold_label_pre_foundation_table}"
        )
        self.bigquery_adapter.exec_query(query, labels=self.labels, month=invoice_month)

    def generate_custom_columns(self, record_column_name: str, custom_fields: list[str]) -> str:
        """Extrai colunas nomeadas de um RECORD repetido (`key`/`value`).

        Achado de código órfão: o resultado deste método é passado ao
        parâmetro `custo_unitario_column_names` de `insert_data`, mas esse
        placeholder não existe no corpo de `INSERT_GOLD_PRE_FOUNDATION_DATA`
        hoje (confirmado por leitura do template). Mantido fiel ao legado.
        """
        custom_columns = ""
        for column_name in custom_fields:
            custom_columns += (
                f"(SELECT value FROM {record_column_name} WHERE key = '{column_name.strip()}') "
                f"as {column_name.strip()}, "
            )
        return custom_columns.rstrip()

    def generate_null_columns(self, custom_fields: list[str]) -> str:
        """Gera fallback `IFNULL(...)` nomeado para cada campo de `CUSTO_UNITARIO_FIELDS`.

        Mesmo achado de código órfão de `generate_custom_columns`: o
        placeholder `{{generate_null_columns}}` não existe no corpo de
        `SELECT_GOLD_PRE_FOUNDATION_DATA` hoje. Mantido fiel ao legado.
        """
        null_columns = ""
        for column_name in custom_fields:
            null_columns += (
                f"IFNULL({column_name.strip()}, '{column_name.strip()}-nao-identificado') "
                f"AS {column_name.strip()}, "
            )
        return null_columns.rstrip()
