import os
import sys
import logging
from dotenv import load_dotenv
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError

load_dotenv()

# instanciar o logger do proprio modulo
logger = logging.getLogger(__name__)

# função principal e tratamento de credenciais

def carregar_bronze_para_silver() -> None:
    logger.info("INICIANDO PROCESSO DE CARGA: Camada Bronze(GCS) -> Camada Silver(BigQuery)")
    
    # Pegando variaveis do .env
    project_id = os.getenv("GCP_PROJECT_ID")
    environment = os.getenv("ENVIRONMENT", "dev")
    bucket_name = os.getenv("GCP_BRONZE_BUCKET")
    
    if not project_id or not bucket_name:
        logger.error("ERRO CRITICO: Variaveis não informadas")
        sys.exit(1)
        
    # Definição do destino no BQ e origem no GCS
    dataset_id = f"silver_{environment}"
    table_id = "tb_reclame_aqui_raw"
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    
    # Instrução para o BQ ler arquivos dentro das subpastas separadas por /
    gcs_source_uri = f"gs://{bucket_name}/*.parquet"
    
    logger.info(f"Origem dos dados no GCS: {gcs_source_uri}")
    logger.info(f"Tabela de destino no BQ: {table_ref}")
    
    # Orquestra a comunicação entre os serviços de nuvem
    # inicializa o cliente Bigquery
    try:
        client = bigquery.Client(project=project_id)
    except Exception as e:
        logger.error(f"Falha ao connectar cliente BigQuery: {str(e)}")
        sys.exit(1)
        
    # Parâmetros  da Ingestão
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        autodetect=True
    )
    
    # Dispara o job de carga
    try:
        logger.info("Disparando JOB de Ingestão no BigQuery")
        load_job = client.load_table_from_uri(
            gcs_source_uri,
            table_ref,
            job_config=job_config
        )
        
        # Execução Sincrona: aguarda o fim do processamento do BQ
        load_job.result()
        logger.info(f"[CARGA CONCLUIDA COM SUCESSO] Tabelas atualizadas: {table_ref}")
    
    except GoogleAPIError as gcp_err:
        logger.error(f"[ERRO NA API DO GCP]: {str(gcp_err)}")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"[ERRO] inesperado durante a carga: {str(e)}")
        sys.exit(1)
        
        
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    carregar_bronze_para_silver()
