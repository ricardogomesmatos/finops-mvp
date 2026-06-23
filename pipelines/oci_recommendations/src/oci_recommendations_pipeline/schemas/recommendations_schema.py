"""Schema BigQuery da tabela de snapshot de recomendações OCI Optimizer.

Tabela append-only (`billing_raw.tb_oci_optimizer_recommendations_snapshot`),
particionada por `extracted_at` (DAY). Campos estruturados cobrem o que
`oci.optimizer.models.RecommendationSummary` expõe; `raw_payload` guarda o
objeto serializado por completo — rede de segurança para evolução de schema
da API OCI sem exigir migration, já que esta camada é landing raw (sem
transformação, conforme o card).
"""

from __future__ import annotations

from google.cloud import bigquery

OCI_RECOMMENDATIONS_SNAPSHOT_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField(
        "extracted_at", "TIMESTAMP", mode="REQUIRED",
        description="Timestamp UTC da execução do job. Campo de partição (DAY).",
    ),
    bigquery.SchemaField("recommendation_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("compartment_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField(
        "tenancy_id", "STRING", mode="NULLABLE",
        description="OCID da tenancy usada como escopo da extração (compartment_id raiz).",
    ),
    bigquery.SchemaField("category_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
    bigquery.SchemaField(
        "status", "STRING", mode="NULLABLE",
        description="PENDING, DISMISSED, POSTPONED ou IMPLEMENTED.",
    ),
    bigquery.SchemaField(
        "importance", "STRING", mode="NULLABLE",
        description="CRITICAL, HIGH, MODERATE, LOW ou MINOR.",
    ),
    bigquery.SchemaField(
        "lifecycle_state", "STRING", mode="NULLABLE",
        description="ACTIVE, FAILED, INACTIVE, ATTACHING, DETACHING, DELETING, DELETED, UPDATING ou CREATING.",
    ),
    bigquery.SchemaField("estimated_cost_saving", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField(
        "resource_count", "INT64", mode="NULLABLE",
        description="Soma de resource_counts[].count do summary.",
    ),
    bigquery.SchemaField("time_created", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("time_updated", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("time_status_begin", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("time_status_end", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("extended_metadata", "JSON", mode="NULLABLE"),
    bigquery.SchemaField(
        "raw_payload", "JSON", mode="REQUIRED",
        description="oci.util.to_dict(rec) serializado por completo.",
    ),
]
