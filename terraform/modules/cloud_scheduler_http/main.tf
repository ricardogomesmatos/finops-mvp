resource "google_cloud_scheduler_job" "this" {
  name        = var.name
  region      = var.region
  project     = var.project_id
  description = var.description
  schedule    = var.schedule
  time_zone   = var.time_zone

  http_target {
    uri         = var.uri
    http_method = "POST"

    oidc_token {
      service_account_email = var.service_account_email
      audience              = var.audience
    }
  }
}
