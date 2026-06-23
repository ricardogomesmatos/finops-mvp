variable "project_id" {
  type        = string
  description = "Projeto GCP onde a tabela é criada."
}

variable "dataset_id" {
  type        = string
  description = "Dataset (já existente) onde a tabela é criada."
}

variable "table_id" {
  type        = string
  description = "ID da tabela."
}

variable "description" {
  type        = string
  description = "Descrição da tabela."
  default     = ""
}

variable "schema" {
  type        = string
  description = "Schema da tabela como JSON (jsonencode de uma lista de campos)."
}

variable "time_partitioning_type" {
  type        = string
  description = "Tipo de particionamento por tempo (DAY, MONTH, ...)."
  default     = "DAY"
}

variable "time_partitioning_field" {
  type        = string
  description = "Campo TIMESTAMP/DATE usado para particionamento."
}

variable "clustering" {
  type        = list(string)
  description = "Campos de clustering, em ordem de prioridade."
  default     = []
}

variable "deletion_protection" {
  type        = bool
  description = "Se true, impede deleção acidental da tabela via Terraform."
  default     = true
}
