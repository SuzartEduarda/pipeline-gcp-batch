import os
import sys
import logging
import argparse
from dotenv import load_dotenv
from src.ingestion import extract_classroom_data
from storage.storage import save_raw_to_bronze



load_dotenv()

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
    )


# Configura os argumentos de linha de comando (CLI) para flexibilidade de orquestração
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Pipeline Lakehouse: Google Classroom API -> Camada Bronze (GCS/LOCAL)"
    )

    # Flags mutuamente exclusivas para controle de carga
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--incremental",
        action="store_true",
        default=None,
        help="Força a execução incremental usando a janela de dias definida"
    )
    group.add_argument(
        "--backfill",
        action="store_true",
        default=None,
        help="Força a carga completa/historica a partir da Data Minima"
    )
    #Janela incremental personalizada
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Quantidade de dias para janela de extração incremental"
    )
    # Nome do bucket customizado via CLI
    parser.add_argument(
        "--bucket",
        type=str,
        default=None,
        help="Nome do Bucket no GCS(sobrescreve a variavel GCP_BRONZE_BUCKET no .env)"
    )
    return parser.parse_args()

def run_pipeline():
    setup_logging()
    args = parse_arguments()
    logging.info("INICIANDO EXTRAÇÃO: GOOGLE CLASSROOM -> BRONZE")

    # Resolução dos parâmetros de carga
    is_incremental = None
    if args.backfill:
        is_incremental = False
    elif args.incremental:
        is_incremental = True
    delta_days = args.days

    #Resolução do Bucket do Storage
    bucket_setting = args.bucket or os.getenv("GCP_BRONZE_BUCKET") or os.getenv("GCS_BUCKET_NAME")
    is_local = os.getenv("LOCAL_ONLY", "False").lower() == "true"

    if not is_local and not bucket_setting:
        logging.error("ERRO CRITICO: Nome do Bucket não definido via CLI (--bucket) ou .env (GCP_BRONZE_BUCKET)")
        sys.exit(1)

    # Execução da Ingestão de Dados
    try:
        logging.info("[ETAPA: 1/2] Iniciando extração via API do Google Classroom")
        extracted_comment, has_errors = extract_classroom_data(
            is_incremental=is_incremental,
            delta_days=delta_days
        )
        if not extracted_comment:
            logging.warning("Nenhum comentario encontrado para a janela de tempo/filtros especificados. Finalizar sem Salvar")
            sys.exit(0)
        logging.info(f"Extração concluida. Total de {len(extracted_comment)} comentarios capturados")
    except Exception as e:
        logging.error(f"ERRO CRITICO na etapa ded extração: {str(e)}")
        sys.exit(1)

    # Gravação dos dados na Camada Bronze
    try:
        logging.info("[ETAPA: 2/2] Salvando comentarios na Camada Bronze em formato Parquet")
        save_raw_to_bronze(
            data=extracted_comment,
            bucket_setting=bucket_setting,
            category_folder="classroom_feedbacks"
        )
    except Exception as e:
        logging.error(f"ERRO CRITICO na etapa de persistencia na Bronze: {str(e)}")
        sys.exit(1)

    # Fechamento da Execução
    if has_errors:
        logging.warning("Pipeline concluido com ALERTAS (algumas turmas apresentam erros de extração)")
    else:
        logging.info("EXECUTADO COM SUCESSO ABSOLUTO")
    sys.exit(0)

    
if __name__ == '__main__':
    run_pipeline()