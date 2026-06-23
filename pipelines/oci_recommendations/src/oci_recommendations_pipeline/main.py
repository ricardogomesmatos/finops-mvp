"""Entry point do Cloud Run Job de extração de recomendações OCI Optimizer."""

from __future__ import annotations

import sys

from billing_common.logging.json_logger import build_logger
from oci_recommendations_pipeline.services.oci_recommendations_service import (
    OciRecommendationsService,
)

logger = build_logger(name="oci_recommendations_pipeline.main")


def run() -> dict[str, str]:
    logger.info("[oci] Starting OCI Optimizer recommendations extraction")
    service = OciRecommendationsService()
    result = service.extract_and_load()
    logger.info(f"[oci] Finished with status={result['status']}")
    return result


if __name__ == "__main__":
    outcome = run()
    if outcome["status"] != "success":
        sys.exit(1)
