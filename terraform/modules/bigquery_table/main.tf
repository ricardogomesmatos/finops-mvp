resource "google_bigquery_table" "this" {
  project     = var.project_id
  dataset_id  = var.dataset_id
  table_id    = var.table_id
  description = var.description

  time_partitioning {
    type  = var.time_partitioning_type
    field = var.time_partitioning_field
  }

  clustering          = var.clustering
  deletion_protection = var.deletion_protection
  schema              = var.schema
}
