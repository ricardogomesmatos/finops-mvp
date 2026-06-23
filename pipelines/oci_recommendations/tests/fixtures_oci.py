"""Objetos reais do SDK `oci` usados como fixtures de teste.

Usa as classes de modelo do próprio SDK (`oci.optimizer.models.RecommendationSummary`,
`oci.optimizer.models.ResourceCount`) em vez de dicts crus, para validar que
`oci.util.to_dict()` funciona contra a estrutura real do SDK.
"""

from __future__ import annotations

from datetime import UTC, datetime

from oci.optimizer.models import RecommendationSummary, ResourceCount

RECOMMENDATION_ID = "ocid1.optimizerrecommendation.oc1..aaaaaaaarecexample"


def build_recommendation_summary(**overrides) -> RecommendationSummary:
    defaults = {
        "id": RECOMMENDATION_ID,
        "compartment_id": "ocid1.tenancy.oc1..aaaaaaaatenancyexample",
        "category_id": "ocid1.optimizercategory.oc1..aaaaaaaacatexample",
        "name": "Rightsize underutilized compute instances",
        "description": "Resize idle compute instances to reduce cost.",
        "importance": RecommendationSummary.IMPORTANCE_HIGH,
        "resource_counts": [
            ResourceCount(status=ResourceCount.STATUS_PENDING, count=3),
            ResourceCount(status=ResourceCount.STATUS_IMPLEMENTED, count=2),
        ],
        "lifecycle_state": RecommendationSummary.LIFECYCLE_STATE_ACTIVE,
        "estimated_cost_saving": 123.45,
        "status": RecommendationSummary.STATUS_PENDING,
        "time_status_begin": datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
        "time_status_end": None,
        "time_created": datetime(2026, 5, 1, 8, 30, 0, tzinfo=UTC),
        "time_updated": datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
        "extended_metadata": {"key": "value"},
    }
    defaults.update(overrides)
    return RecommendationSummary(**defaults)
