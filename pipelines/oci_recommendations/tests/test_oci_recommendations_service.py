"""Testes unitários de OciRecommendationsService — sem chamadas reais à OCI/BQ."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fixtures_oci import RECOMMENDATION_ID, build_recommendation_summary
from oci_recommendations_pipeline.services.oci_recommendations_service import (
    OciRecommendationsService,
)


@pytest.fixture
def mock_optimizer_pipeline(mock_get_secret_json):
    """Mocka build_optimizer_client e list_all_recommendations no módulo do service."""
    with (
        patch(
            "oci_recommendations_pipeline.services.oci_recommendations_service.build_optimizer_client"
        ) as mock_build_client,
        patch(
            "oci_recommendations_pipeline.services.oci_recommendations_service.list_all_recommendations"
        ) as mock_list_recs,
    ):
        yield mock_build_client, mock_list_recs


def test_extract_and_load_happy_path_inserts_rows(
    oci_env, mock_bigquery_adapter, mock_optimizer_pipeline
):
    _, mock_list_recs = mock_optimizer_pipeline
    mock_list_recs.return_value = [build_recommendation_summary()]
    mock_bigquery_adapter.insert_rows.return_value = []

    service = OciRecommendationsService()
    result = service.extract_and_load()

    assert result["status"] == "success"
    mock_bigquery_adapter.insert_rows.assert_called_once()
    project, dataset, table_id, rows = mock_bigquery_adapter.insert_rows.call_args[0]
    assert (project, dataset, table_id) == (
        "test-project",
        "billing_raw",
        "tb_oci_optimizer_recommendations_snapshot",
    )
    assert len(rows) == 1
    assert rows[0]["recommendation_id"] == RECOMMENDATION_ID


def test_extract_and_load_empty_list_does_not_call_insert_rows(
    oci_env, mock_bigquery_adapter, mock_optimizer_pipeline
):
    _, mock_list_recs = mock_optimizer_pipeline
    mock_list_recs.return_value = []

    service = OciRecommendationsService()
    result = service.extract_and_load()

    assert result == {"status": "success", "details": "0 recommendations"}
    mock_bigquery_adapter.insert_rows.assert_not_called()


def test_extract_and_load_fails_when_secret_lookup_raises(
    oci_env, mock_bigquery_adapter, mock_get_secret_json
):
    mock_get_secret_json.side_effect = RuntimeError("secret not found")

    service = OciRecommendationsService()
    result = service.extract_and_load()

    assert result["status"] == "failed"
    assert "secret not found" in result["details"]
    mock_bigquery_adapter.insert_rows.assert_not_called()


def test_extract_and_load_fails_when_oci_list_call_raises(
    oci_env, mock_bigquery_adapter, mock_optimizer_pipeline
):
    _, mock_list_recs = mock_optimizer_pipeline
    mock_list_recs.side_effect = RuntimeError("OCI API unavailable")

    service = OciRecommendationsService()
    result = service.extract_and_load()

    assert result["status"] == "failed"
    assert "OCI API unavailable" in result["details"]


def test_extract_and_load_fails_when_bq_insert_returns_errors(
    oci_env, mock_bigquery_adapter, mock_optimizer_pipeline
):
    _, mock_list_recs = mock_optimizer_pipeline
    mock_list_recs.return_value = [build_recommendation_summary()]
    mock_bigquery_adapter.insert_rows.return_value = [{"reason": "invalid"}]

    service = OciRecommendationsService()
    result = service.extract_and_load()

    assert result["status"] == "failed"
    assert "invalid" in result["details"]


def test_build_row_serializes_raw_payload_as_valid_json(oci_env, mock_bigquery_adapter):
    rec = build_recommendation_summary()
    service = OciRecommendationsService()

    row = service._build_row(rec, tenancy_id="ocid1.tenancy.oc1..aaaa", extracted_at="2026-06-23T00:00:00+00:00")

    parsed = json.loads(row["raw_payload"])
    assert parsed["id"] == RECOMMENDATION_ID
    assert isinstance(row["time_created"], str)
    assert row["resource_count"] == 5


def test_build_row_extended_metadata_defaults_to_empty_object(oci_env, mock_bigquery_adapter):
    rec = build_recommendation_summary(extended_metadata=None)
    service = OciRecommendationsService()

    row = service._build_row(rec, tenancy_id="ocid1.tenancy.oc1..aaaa", extracted_at="2026-06-23T00:00:00+00:00")

    assert json.loads(row["extended_metadata"]) == {}


@pytest.mark.parametrize(
    ("resource_counts", "expected"),
    [
        (None, None),
        ([], None),
        ([{"status": "PENDING", "count": 3}, {"status": "IMPLEMENTED", "count": 2}], 5),
    ],
)
def test_sum_resource_counts(resource_counts, expected):
    assert OciRecommendationsService._sum_resource_counts(resource_counts) == expected
