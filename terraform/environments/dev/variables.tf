variable "project_id" {
  type        = string
  description = "Projeto GCP de dev (homologação)."
  default     = "gglobo-billinghomolog-hdg-prd"
}

variable "region" {
  type        = string
  description = "Região dos recursos."
  default     = "us-east1"
}

variable "billing_raw_dataset_id" {
  type        = string
  description = "Dataset billing_raw existente (não gerenciado por este módulo)."
  default     = "billing_raw"
}

variable "service_account_email" {
  type        = string
  description = "Service Account existente reaproveitada pelos pipelines de billing em dev."
  default     = "sa-gcp-billing-hmg@gglobo-billinghomolog-hdg-prd.iam.gserviceaccount.com"
}
