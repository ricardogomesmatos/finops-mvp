"""Testes unitários do BigQueryAdapter — sem chamadas reais ao BigQuery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google.cloud import bigquery

from billing_common.adapters.bigquery import BigQueryAdapter


@pytest.fixture
def mock_bq_client():
    with patch("billing_common.adapters.bigquery.bigquery.Client") as mock_client_cls:
        yield mock_client_cls.return_value


def test_constructor_stores_project_id_and_builds_client(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")

    assert adapter.project_id == "my-project"
    assert adapter.client is mock_bq_client


def test_exec_query_returns_row_iterator_and_applies_labels(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")
    mock_job = MagicMock()
    mock_job.job_id = "job-123"
    mock_row_iterator = MagicMock()
    mock_job.result.return_value = mock_row_iterator
    mock_bq_client.query.return_value = mock_job

    result = adapter.exec_query("SELECT 1", labels={"team": "finops"}, month="2024-04-01")

    assert result is mock_row_iterator
    called_query, called_kwargs = mock_bq_client.query.call_args
    assert called_query[0] == "SELECT 1"
    job_config = called_kwargs["job_config"]
    assert job_config.labels == {"team": "finops"}


def test_exec_query_without_labels_does_not_set_job_config(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")
    mock_job = MagicMock()
    mock_job.job_id = "job-456"
    mock_bq_client.query.return_value = mock_job

    adapter.exec_query("SELECT 1")

    _, called_kwargs = mock_bq_client.query.call_args
    assert called_kwargs["job_config"] is None


def test_exec_query_wraps_exceptions_in_runtime_error(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")
    mock_bq_client.query.side_effect = ValueError("boom")

    with pytest.raises(RuntimeError, match="BQ query failed"):
        adapter.exec_query("SELECT 1", month="2024-04-01")


def test_query_delegates_to_client_without_waiting_result(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")
    mock_bq_client.query.return_value = "query-job"

    result = adapter.query("SELECT 1")

    assert result == "query-job"
    mock_bq_client.query.assert_called_once_with("SELECT 1")


def test_create_table_sets_month_partitioning(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")
    schema = [bigquery.SchemaField("col", "STRING")]
    mock_bq_client.create_table.return_value = "created-table"

    result = adapter.create_table("my-project", "billing_silver", "tb_test", schema)

    assert result == "created-table"
    created_table_arg = mock_bq_client.create_table.call_args[0][0]
    assert created_table_arg.time_partitioning.type_ == bigquery.TimePartitioningType.MONTH


def test_create_table_returns_none_on_failure(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")
    mock_bq_client.create_table.side_effect = RuntimeError("already exists")

    result = adapter.create_table("my-project", "billing_silver", "tb_test", [])

    assert result is None


def test_delete_table_calls_client_delete(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")

    adapter.delete_table("my-project", "billing_silver", "tb_test")

    mock_bq_client.delete_table.assert_called_once()


def test_update_table_schema_if_necessary_returns_none_on_failure(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")
    mock_bq_client.update_table.side_effect = RuntimeError("schema incompatible")

    result = adapter.update_table_schema_if_necessary("my-project", "billing_silver", "tb_test", [])

    assert result is None


def test_get_table_delegates_to_client(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")
    mock_bq_client.get_table.return_value = "table-obj"

    result = adapter.get_table("my-project", "billing_silver", "tb_test")

    assert result == "table-obj"


def test_repr_includes_project_id(mock_bq_client):
    adapter = BigQueryAdapter(project_id="my-project")

    assert "my-project" in repr(adapter)
