variable "project_id" {
  type        = string
  description = "Projeto GCP onde o Job é criado."
}

variable "region" {
  type        = string
  description = "Região do Cloud Run Job."
}

variable "name" {
  type        = string
  description = "Nome do Cloud Run Job."
}

variable "image" {
  type        = string
  description = "Imagem do container (Artifact Registry)."
}

variable "service_account_email" {
  type        = string
  description = "Service Account usada pela execução do Job."
}

variable "env_vars" {
  type        = map(string)
  description = "Variáveis de ambiente do container, nome -> valor."
  default     = {}
}

variable "cpu" {
  type        = string
  description = "Limite de CPU do container (formato Cloud Run, ex: \"1\")."
  default     = "1"
}

variable "memory" {
  type        = string
  description = "Limite de memória do container (formato Cloud Run, ex: \"512Mi\")."
  default     = "512Mi"
}

variable "timeout" {
  type        = string
  description = "Timeout por task (formato Terraform de duração, ex: \"600s\")."
  default     = "600s"
}

variable "max_retries" {
  type        = number
  description = "Número de tentativas adicionais em caso de falha da task."
  default     = 1
}
