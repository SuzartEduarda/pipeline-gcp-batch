#
#

variable "project_id" {
  type    = string
  default = "projeto-dados-pessoal"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "environment" {
  description = "Ambiente de execução (ex: dev, hml, prod)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Localização geografica para buckets e datasets"
  type        = string
  default     = "US"
}