import os
import sys
import logging
import argparse
from dotenv import load_dotenv

from src.extract_consumidor import extract_consumidor_gov_data as extract_reclame_aqui_data
from storage.storage import save_raw_to_bronze

load_dotenv()


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Pipeline Lakehouse: Ingestão de Dados Abertos Reais -> Camada Bronze (GCS/LOCAL)"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--incremental",
        action="store_true",
        default=None,
        help="Força a execução incremental usando a janela de dias definida no .env"
    )
    group.add_argument(
        "--backfill",
        action="store_true",
        default=None,
        help="Força a carga completa/histórica a partir da Data Mínima (01/01/2025)"
    )
    
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Quantidade de dias para janela de extração incremental"
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=None,
        help="Nome do Bucket no GCS (sobrescreve a variável GCP_BRONZE_BUCKET no .env)"
    )
    return parser.parse_args()


def run_pipeline():
    setup_logging()
    args = parse_arguments()
    logging.info("==========================================================================")
    logging.info("INICIANDO EXTRAÇÃO: DADOS ABERTOS REAIS (Consumidor.gov) -> CAMADA BRONZE")
    logging.info("==========================================================================")

    is_incremental = None
    if args.backfill:
        is_incremental = False
    elif args.incremental:
        is_incremental = True
    delta_days = args.days

    bucket_setting = args.bucket or os.getenv("GCP_BRONZE_BUCKET") or os.getenv("GCS_BUCKET_NAME") or ""
    is_local = os.getenv("LOCAL_ONLY", "False").lower() == "true"

    if not is_local and not bucket_setting:
        logging.error("ERRO CRÍTICO: Nome do Bucket não definido via CLI (--bucket) ou .env (GCP_BRONZE_BUCKET)")
        sys.exit(1)

    # ETAPA 1: Obtém apenas dados reais
    try:
        logging.info("[ETAPA: 1/2] Lendo dados reais oficiais e aplicando mascaramento LGPD...")
        extracted_complaints, has_errors = extract_reclame_aqui_data(
            is_incremental=is_incremental,
            delta_days=delta_days
        )
        
        if not extracted_complaints:
            logging.error("ABORTANDO: Nenhum dado real foi capturado. Verifique o arquivo 'data_local/consumidor_gov.csv'.")
            sys.exit(1)
            
        logging.info(f"Extração concluída. Total de {len(extracted_complaints)} reclamações REAIS preparadas.")
    except Exception as e:
        logging.error(f"ERRO CRÍTICO na etapa de extração: {str(e)}")
        sys.exit(1)

    # ETAPA 2: Grava os dados reais em Parquet de 100 em 100 itens
    try:
        logging.info("[ETAPA: 2/2] Persistindo dados reais na Camada Bronze Parquet (Lotes de 100)")
        save_raw_to_bronze(
            data=extracted_complaints,
            bucket_setting=bucket_setting,
            category_folder="reclame_aqui_data",
            page_size=100
        )
    except Exception as e:
        logging.error(f"ERRO CRÍTICO na etapa de persistência na Bronze: {str(e)}")
        sys.exit(1)

    if has_errors:
        logging.warning("Pipeline concluído com alertas.")
    else:
        logging.info("EXECUTADO COM SUCESSO ABSOLUTO (APENAS DADOS REAIS)")
    sys.exit(0)


if __name__ == '__main__':
    run_pipeline()