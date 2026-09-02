#Esse bloco serve para dizer ao Terraform quais ferramentas e 
# versões ele precisa baixar da internet para conseguir conversar com a nuvem do Google.

terraform {
  required_version = ">= 1.5.0" #controle de versão do terraform
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0" #controle de versão do provider do google
    }
  }
}

provider "google" {
  credentials = file("../_SA/gcp-credentials.json") #acesso ao arquivo de credenciais 
  project     = var.project_id                      #leitura dinamica de variaveis
  region      = var.region
}

#O Bucket da Camada Bronze
#Este bloco instrui o Terraform a criar um espaço de armazenamento de objetos 
#(como arquivos Parquet ou JSON) no Google Cloud.
# essa é a Caamada Bronze e a fonte direta dos dados
resource "google_storage_bucket" "bronze_bucket" {
  name                        = "${var.project_id}-${var.environment}-bronze-storage"
  location                    = var.location
  force_destroy               = true #desbloqueio da chave de segurança
  uniform_bucket_level_access = true #nivel de acesso do iam

  labels = {
    environment = var.environment
    layer       = "bronze"
    managed_by  = "terraform"
  }
}
 
# O bloco a baixo vai declarar os datasets
# Camada  silver
resource "google_bigquery_dataset" "silver_dataset" {
  dataset_id                 = "silver_${var.environment}"
  description                = "Camada Silver: Dados Higienizados, deduplicados e anonimizados"
  location                   = var.location
  delete_contents_on_destroy = true

  labels = {
    environment = var.environment
    layer       = "silver"
    managed_by  = "terraform"
  }
}

# Camada gold / Analytics
resource "google_bigquery_dataset" "gold_dataset" {
  dataset_id                 = "gold_${var.environment}"
  description                = "Camada Gold: Dados agregados e otimizados para camada ded llm e Analytics"
  location                   = var.location
  delete_contents_on_destroy = true

  labels = {
    environment = var.environment
    layer       = "gold"
    managed_by  = "terraform"
  }
}

# Topico PUB/SUB para kill switch de faturamento
resource "google_pubsub_topic" "kill_switch_topic" {
  name = "${var.project_id}-${var.environment}-killswitch_topic"

  labels = {
    environment = var.environment
    purpose     = "cost-governance"
    managed_by  = "terraform"
  }
}

# Conexão externa do Bigquery para comunicação com o Vertex AI
resource "google_bigquery_connection" "gemini_conection"{
  connection_id = "gemini_vertex_connection"
  project       = var.project_id
  location      = var.location
  description   = "Conexão remota BQ para invocar o modelo Gemini na Vertex AI"

  cloud_resource {}
}

# Permissão IAM: Concede a Service account a role de vertex ai user
resource "google_project_iam_member" "bq_connection_vertex_user"{
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_bigquery_connection.gemini_conection.cloud_resource[0].service_account_id}"
}