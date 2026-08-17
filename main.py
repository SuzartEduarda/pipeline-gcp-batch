import os
import sys
import logging
import argparse
from dotenv import load_dotenv

from src.create_data import extract_reclame_aqui_data
from storage.storage import save_raw_to_bronze

load_dotenv()

# Configurar logs de execução
def configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

# Função para ler parametros via linha ded comando
def obter_argumentos():
    parser = argparse.ArgumentParser(
        description="Pipeline Lakehouse: Geração de Dados Abertos Reais -> Camada Bronze (GCS/LOCAL)"
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
        help="Quantidade de dias para janela de Geração incremental"
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=None,
        help="Nome do Bucket no GCS (sobrescreve a variável GCP_BRONZE_BUCKET no .env)"
    )
    return parser.parse_args()

# Função principal para orquestra a geração e salvamento dos dados
def executar_pipeline() -> None:
    configurar_logs()
    args = obter_argumentos()
    logging.info("INICIANDO pipeline: DADOS GERADOS (via Faker) -> CAMADA BRONZE")

    #Resolução parametros de carga
    is_incremental = None
    if args.backfill:
        is_incremental = False
    elif args.incremental:
        is_incremental = True
    delta_days = args.days

    # Resolução de Variavel do Bucket
    bucket_setting = args.bucket or os.getenv("GCP_BRONZE_BUCKET") or os.getenv("GCS_BUCKET_NAME") or ""
    is_local = os.getenv("LOCAL_ONLY", "False").lower() == "true"

    if not is_local and not bucket_setting:
        logging.error("ERRO CRÍTICO: Nome do Bucket não definido")
        sys.exit(1)

    # ETAPA 1: Geração de dados
    try:
        logging.info("[ETAPA: 1/2] Gerando dados via Faker")
        reclamacoes_extraidas, has_errors = extract_reclame_aqui_data(
            is_incremental=is_incremental,
            delta_days=delta_days
        )
        
        if not reclamacoes_extraidas:
            logging.warning("Nenhuma reclamação gerada. finalizar sem salvar")
            sys.exit(0)
            
        logging.info(f"Geração concluída. Total de {len(reclamacoes_extraidas)} reclamações preparadas.")
    except Exception as e:
        logging.error(f"ERRO CRÍTICO na etapa de Geração de dados: {str(e)}")
        sys.exit(1)

    # ETAPA 2: Grava os dados em Parquet de 100 em 100 itens
    try:
        logging.info("[ETAPA: 2/2] Persistindo reclamações na Camada Bronze Parquet (em Lotes)")
        save_raw_to_bronze(
            data=reclamacoes_extraidas,
            bucket_setting=bucket_setting,
            category_folder="reclame_aqui_data",
            page_size=100
        )
    except Exception as e:
        logging.error(f"ERRO CRÍTICO na etapa de persistência na Bronze: {str(e)}")
        sys.exit(1)

    if has_errors:
        logging.warning("Pipeline concluído com alertas durante geração de dados.")
    else:
        logging.info("EXECUTADO COM SUCESSO ABSOLUTO")
    sys.exit(0)


if __name__ == '__main__':
    executar_pipeline()