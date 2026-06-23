variable "project_id" {
  type        = string
  description = "Projeto GCP de produção."
  default     = "gglobo-billing-hdg-prd"
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
  description = "Service Account existente reaproveitada pelos pipelines de billing em prod."
  default     = "sa-gcp-billing-prd@gglobo-billing-hdg-prd.iam.gserviceaccount.com"
}
