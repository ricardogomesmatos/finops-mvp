variable "project_id" {
  type        = string
  description = "Projeto GCP onde o Scheduler é criado."
}

variable "region" {
  type        = string
  description = "Região do Cloud Scheduler."
}

variable "name" {
  type        = string
  description = "Nome do Cloud Scheduler job."
}

variable "description" {
  type        = string
  description = "Descrição do Cloud Scheduler job."
  default     = ""
}

variable "schedule" {
  type        = string
  description = "Expressão cron do agendamento."
}

variable "time_zone" {
  type        = string
  description = "Fuso horário do agendamento."
  default     = "America/Sao_Paulo"
}

variable "uri" {
  type        = string
  description = "URI HTTP alvo (ex: API :run do Cloud Run Job)."
}

variable "service_account_email" {
  type        = string
  description = "Service Account usada para autenticar a chamada via OIDC."
}

variable "audience" {
  type        = string
  description = "Audience do token OIDC."
}
