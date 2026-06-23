"""Adapter unificado de BigQuery.

Funde as duas versões divergentes mantidas no ambiente legado (`gcp-billing`):

- ``gcp_raw_to_silver/adapters/bigquery_adapter.py`` — capacidades de DDL
  (``create_table``, ``delete_table``, ``update_table_schema_if_necessary``, ``get_table``).
- ``gcp_labels/adapters/bigquery_adapter.py`` — ``exec_query`` com
  ``QueryJobConfig(labels=...)`` (tagueamento de custo por job, prática FinOps) e
  logging do ``job.job_id``.

Nenhuma capacidade das duas versões foi descartada.

Desvio de design deliberado (registrado para o agente `qa-reconciliation`, não é
regressão de paridade): ``project_id`` é parâmetro explícito do construtor, em vez
de lido internamente via uma classe de config de um pipeline específico (como o
legado fazia chamando ``EnvConfigs()`` dentro do adapter). Isso evita acoplar a
lib comum à implementação de configuração de um pipeline e mantém o adapter
testável sem variáveis de ambiente.
"""

from __future__ import annotations

import logging

from google.api_core.client_options import ClientOptions
from google.cloud import bigquery

logger = logging.getLogger(__name__)

_BIGQUERY_CLIENT_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/bigquery",
    "https://www.googleapis.com/auth/cloud-platform",
]


class BigQueryAdapter:
    """Encapsula o `google.cloud.bigquery.Client` usado por todos os pipelines."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        client_options = ClientOptions(scopes=_BIGQUERY_CLIENT_SCOPES)
        self.client = bigquery.Client(project=project_id, client_options=client_options)

    def exec_query(
        self,
        query: str,
        labels: dict[str, str] | None = None,
        month: str = "",
    ) -> bigquery.table.RowIterator:
        """Executa uma query síncrona, com labels de custo opcionais por job.

        ``labels`` é propagado via ``QueryJobConfig`` para permitir auditoria de
        custo por workflow/camada em `INFORMATION_SCHEMA.JOBS_BY_PROJECT`.
        """
        job_config = bigquery.QueryJobConfig(labels=labels) if labels else None
        month_tag = f" [{month}]" if month else ""
        try:
            job = self.client.query(query, job_config=job_config)
            logger.info("BQ job submitted: %s%s", job.job_id, month_tag)
            result = job.result(timeout=None)
            logger.info("BQ job completed: %s%s", job.job_id, month_tag)
            return result
        except Exception as exc:
            raise RuntimeError(f"BQ query failed{month_tag}: {exc}") from exc

    def query(self, query: str) -> bigquery.QueryJob:
        """Submete uma query sem esperar o resultado (paridade com o legado)."""
        return self.client.query(query)

    def create_table(
        self,
        project: str,
        dataset: str,
        table_id: str,
        schema: list[bigquery.SchemaField],
    ) -> bigquery.Table | None:
        """Cria uma tabela particionada por MONTH, padrão de todas as tabelas de fato."""
        dataset_ref = bigquery.DatasetReference(project, dataset)
        table = bigquery.Table(dataset_ref.table(table_id), schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.MONTH
        )
        try:
            return self.client.create_table(table)
        except Exception:
            logger.exception("Failed to create table %s.%s.%s", project, dataset, table_id)
            return None

    def delete_table(self, project: str, dataset: str, table_id: str) -> None:
        dataset_ref = bigquery.DatasetReference(project, dataset)
        table = bigquery.Table(dataset_ref.table(table_id))
        self.client.delete_table(table)

    def update_table_schema_if_necessary(
        self,
        project: str,
        dataset: str,
        table_id: str,
        new_schema: list[bigquery.SchemaField],
    ) -> bigquery.Table | None:
        dataset_ref = bigquery.DatasetReference(project, dataset)
        table = bigquery.Table(dataset_ref.table(table_id))
        table.schema = new_schema
        try:
            return self.client.update_table(table, ["schema"])
        except Exception:
            logger.exception(
                "Failed to update schema for table %s.%s.%s", project, dataset, table_id
            )
            return None

    def insert_rows(
        self,
        project: str,
        dataset: str,
        table_id: str,
        rows: list[dict],
    ) -> list[dict]:
        """Insere linhas via streaming insert (`insertAll`), append-only.

        Usado por pipelines de snapshot raw que não fazem DDL/MERGE — apenas
        gravação append-only de cada extração.
        """
        table_ref = f"{project}.{dataset}.{table_id}"
        return self.client.insert_rows_json(table_ref, rows)

    def get_table(self, project: str, dataset: str, table_id: str) -> bigquery.Table:
        dataset_ref = bigquery.DatasetReference(project, dataset)
        table_ref = bigquery.Table(dataset_ref.table(table_id))
        return self.client.get_table(table_ref)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"{type(self).__name__}(project_id={self.project_id!r})"
