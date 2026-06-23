# Extração das recomendações OCI Optimizer para BigQuery — Cloud Run Job
# diário acionado por Cloud Scheduler. Ver pipelines/oci_recommendations/.

module "oci_recommendations_secret" {
  source     = "../../modules/secret_manager_secret"
  project_id = var.project_id
  secret_id  = var.oci_credentials_secret_id

  # Apenas a SA reaproveitada precisa ler este secret — escopo mínimo, não a
  # nível de projeto. O valor do secret (JSON com user/fingerprint/tenancy/
  # region/key_content) é populado manualmente fora do Terraform.
  accessor_service_account_emails = [var.service_account_email]
}

module "oci_recommendations_table" {
  source      = "../../modules/bigquery_table"
  project_id  = var.project_id
  dataset_id  = var.billing_raw_dataset_id
  table_id    = "tb_oci_optimizer_recommendations_snapshot"
  description = "Snapshot append-only das recomendações OCI Optimizer/Cloud Advisor, particionado por data de extração. Camada raw — sem transformação."

  time_partitioning_type  = "DAY"
  time_partitioning_field = "extracted_at"
  clustering              = ["status", "importance"]
  deletion_protection     = true

  schema = jsonencode([
    { name = "extracted_at", type = "TIMESTAMP", mode = "REQUIRED", description = "Timestamp UTC da execução do job. Campo de partição (DAY)." },
    { name = "recommendation_id", type = "STRING", mode = "REQUIRED" },
    { name = "compartment_id", type = "STRING", mode = "NULLABLE" },
    { name = "tenancy_id", type = "STRING", mode = "NULLABLE", description = "OCID da tenancy usada como escopo da extração." },
    { name = "category_id", type = "STRING", mode = "NULLABLE" },
    { name = "name", type = "STRING", mode = "NULLABLE" },
    { name = "description", type = "STRING", mode = "NULLABLE" },
    { name = "status", type = "STRING", mode = "NULLABLE", description = "PENDING, DISMISSED, POSTPONED ou IMPLEMENTED." },
    { name = "importance", type = "STRING", mode = "NULLABLE", description = "CRITICAL, HIGH, MODERATE, LOW ou MINOR." },
    { name = "lifecycle_state", type = "STRING", mode = "NULLABLE" },
    { name = "estimated_cost_saving", type = "FLOAT64", mode = "NULLABLE" },
    { name = "resource_count", type = "INT64", mode = "NULLABLE", description = "Soma de resource_counts[].count do summary." },
    { name = "time_created", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "time_updated", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "time_status_begin", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "time_status_end", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "extended_metadata", type = "JSON", mode = "NULLABLE" },
    { name = "raw_payload", type = "JSON", mode = "REQUIRED", description = "oci.util.to_dict(rec) serializado por completo." },
  ])
}

module "oci_recommendations_runner" {
  source                = "../../modules/cloud_run_job"
  project_id            = var.project_id
  region                = var.region
  name                  = "oci-recommendations-runner"
  image                 = "${var.region}-docker.pkg.dev/${var.project_id}/billing/oci-recommendations-runner:latest"
  service_account_email = var.service_account_email
  timeout               = "600s"
  max_retries           = 1
  cpu                   = "1"
  memory                = "512Mi"

  env_vars = {
    GCP_PROJECT               = var.project_id
    OCI_RECOMMENDATIONS_TABLE = "${var.project_id}.${var.billing_raw_dataset_id}.${module.oci_recommendations_table.table_id}"
    OCI_TENANCY_ID            = var.oci_tenancy_id
    OCI_CREDENTIALS_SECRET_ID = module.oci_recommendations_secret.secret_id
  }
}

module "oci_recommendations_scheduler" {
  source                = "../../modules/cloud_scheduler_http"
  project_id            = var.project_id
  region                = var.region
  name                  = "oci-recommendations-runner-daily"
  description           = "Dispara diariamente a extração das recomendações OCI Optimizer para o BigQuery"
  schedule              = "0 7 * * *"
  time_zone             = "America/Sao_Paulo"
  uri                   = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${module.oci_recommendations_runner.name}:run"
  service_account_email = var.service_account_email
  audience              = "https://${var.region}-run.googleapis.com/"
}
