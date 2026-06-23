# Cria apenas o "container" do secret — a versão com o valor sensível nunca é
# gerenciada pelo Terraform (nunca commitada), é populada manualmente fora
# deste módulo, ex.: `gcloud secrets versions add <secret_id> --data-file=...`.
resource "google_secret_manager_secret" "this" {
  project   = var.project_id
  secret_id = var.secret_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "accessor" {
  for_each  = toset(var.accessor_service_account_emails)
  project   = var.project_id
  secret_id = google_secret_manager_secret.this.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}
