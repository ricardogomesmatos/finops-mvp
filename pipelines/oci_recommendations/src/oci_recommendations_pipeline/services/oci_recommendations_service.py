"""Serviço de extração das recomendações OCI Optimizer para billing_raw.

Camada estritamente raw/landing: lista as recomendações da tenancy, serializa
cada uma (campos estruturados + payload bruto) e grava como snapshot
append-only. Sem transformação, dedup ou upsert — fases seguintes ficam para
outro card.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import oci.util

from billing_common.adapters.bigquery import BigQueryAdapter
from billing_common.logging.json_logger import build_logger
from billing_common.secrets.secret_manager import get_secret_json
from oci_recommendations_pipeline.clients.oci_client import (
    build_optimizer_client,
    list_all_recommendations,
)
from oci_recommendations_pipeline.config.env_configs import OciRecommendationsEnvConfigs

logger = build_logger(name="oci_recommendations_pipeline.oci_recommendations_service")


class OciRecommendationsService:
    """Extrai as recomendações OCI Optimizer da tenancy e grava em BigQuery."""

    def __init__(self) -> None:
        self.env_configs = OciRecommendationsEnvConfigs()
        self.bigquery_adapter = BigQueryAdapter(project_id=self.env_configs.get_project_id())

    def extract_and_load(self) -> dict[str, str]:
        try:
            secret_payload = get_secret_json(
                project_id=self.env_configs.get_project_id(),
                secret_id=self.env_configs.get_oci_credentials_secret_id(),
            )
            optimizer_client = build_optimizer_client(secret_payload)
            tenancy_id = self.env_configs.get_oci_tenancy_id()

            recommendations = list_all_recommendations(optimizer_client, tenancy_id)
            logger.info(f"[oci] list_recommendations returned {len(recommendations)} item(s)")

            if not recommendations:
                return {"status": "success", "details": "0 recommendations"}

            rows = self._build_rows(recommendations, tenancy_id)
            table_ref = self.env_configs.get_oci_recommendations_table()
            project, dataset, table_id = table_ref.split(".")

            errors = self.bigquery_adapter.insert_rows(project, dataset, table_id, rows)
            if errors:
                raise RuntimeError(f"BQ insert returned errors: {errors}")

            message = f"{len(rows)} recommendation(s) inserted into {table_ref}"
            logger.info(f"[oci] {message}")
            return {"status": "success", "details": message}
        except Exception as e:
            logger.error(f"[oci] Failed: {e}", exc_info=True)
            return {"status": "failed", "details": str(e)}

    def _build_rows(self, recommendations: list, tenancy_id: str) -> list[dict]:
        extracted_at = datetime.now(UTC).isoformat()
        return [self._build_row(rec, tenancy_id, extracted_at) for rec in recommendations]

    @staticmethod
    def _build_row(rec, tenancy_id: str, extracted_at: str) -> dict:
        # oci.util.to_dict já converte datetime -> string ISO 8601 e listas de
        # sub-modelos (ex.: resource_counts) -> listas de dicts, recursivamente.
        raw = oci.util.to_dict(rec)
        return {
            "extracted_at": extracted_at,
            "recommendation_id": raw.get("id"),
            "compartment_id": raw.get("compartment_id"),
            "tenancy_id": tenancy_id,
            "category_id": raw.get("category_id"),
            "name": raw.get("name"),
            "description": raw.get("description"),
            "status": raw.get("status"),
            "importance": raw.get("importance"),
            "lifecycle_state": raw.get("lifecycle_state"),
            "estimated_cost_saving": raw.get("estimated_cost_saving"),
            "resource_count": OciRecommendationsService._sum_resource_counts(
                raw.get("resource_counts")
            ),
            "time_created": raw.get("time_created"),
            "time_updated": raw.get("time_updated"),
            "time_status_begin": raw.get("time_status_begin"),
            "time_status_end": raw.get("time_status_end"),
            "extended_metadata": json.dumps(raw.get("extended_metadata") or {}, default=str),
            "raw_payload": json.dumps(raw, default=str),
        }

    @staticmethod
    def _sum_resource_counts(resource_counts: list[dict] | None) -> int | None:
        if not resource_counts:
            return None
        return sum(rc.get("count", 0) for rc in resource_counts)
