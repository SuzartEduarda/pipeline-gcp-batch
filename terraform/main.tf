#Esse bloco serve para dizer ao Terraform quais ferramentas e 
# versões ele precisa baixar da internet para conseguir conversar com a nuvem do Google.

terraform{
    required_version = ">= 1.5.0" #controle de versão do terraform
    required_providers{
        google = {
            source = "hashicorp/google"
            version = "~> 5.0" #controle de versão do provider do google
        }
    }
}

provider "google" {
    credentials = file("../_SA/gcp-credentials.json") #acesso ao arquivo de credenciais 
    project = var.project_id #leitura dinamica de variaveis
    region = var.region
}

#O Bucket da Camada Bronze
#Este bloco instrui o Terraform a criar um espaço de armazenamento de objetos 
#(como arquivos Parquet ou JSON) no Google Cloud.

resource "google_storage_bucket" "bronze_bucket"{
    name = "${var.project_id}-bronze-storage"
    location = "US"
    force_destroy = true #deesbloqueio da chave de segurança
    uniform_bucket_level_access = true #nivel de acesso do iam
}