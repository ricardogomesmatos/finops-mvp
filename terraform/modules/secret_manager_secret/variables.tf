variable "project_id" {
  type        = string
  description = "Projeto GCP onde o secret é criado."
}

variable "secret_id" {
  type        = string
  description = "Nome do secret no Secret Manager."
}

variable "accessor_service_account_emails" {
  type        = list(string)
  description = "Service Accounts com permissão secretAccessor sobre este secret (escopo mínimo, não a nível de projeto)."
  default     = []
}
