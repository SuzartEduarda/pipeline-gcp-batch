import os
import io
import re
import sys
import logging
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError

# trava de execução timestamp e data fixada no momento do início da execução
EXECUTION_DATE = datetime.now()
EXECUTION_TIMESTAMP = EXECUTION_DATE.strftime("%Y%m%d_%H%M%S")
EXECUTION_DATE_FOLDER = EXECUTION_DATE.strftime("%Y%m%d")


# Função para extrair nome do bucket e o prefixo do caminho do .env
def extrair_bucket_prefixo(raw_bucket_setting: str):
    if not raw_bucket_setting:
        return "", ""
    if "/" in raw_bucket_setting:
        bucket_name, base_prefix = raw_bucket_setting.split("/", 1)
        if base_prefix and not base_prefix.endswith("/"):
            base_prefix += "/"
        return bucket_name, base_prefix
    return raw_bucket_setting, ""

#Calcula a próxima partição local no disco para evitar sobrescrever dados.
def obter_proxima_particao_local(diretorio: str) -> int:
    if not os.path.exists(diretorio):
        return 1
    pattern = re.compile(rf".*_\d{{6}}_part_(\d{{5}})\.parquet$")
    maior = 0
    for arq in os.listdir(diretorio):
        match = pattern.match(arq)
        if match:
            num = int(match.group(1))
            if num > maior:
                maior = num
    return maior + 1

#Calcula a próxima partição dentro da pasta no GCS para evitar sobrescrever dados.
def obter_proxima_particao_gcs(bucket, prefixo_busca: str) -> int:
    blobs = bucket.list_blobs(prefix=prefixo_busca)
    pattern = re.compile(rf".*_\d{{6}}_part_(\d{{5}})\.parquet$")
    maior = 0
    for blob in blobs:
        match = pattern.match(blob.name)
        if match:
            num = int(match.group(1))
            if num > maior:
                maior = num
    return maior + 1


# Converter e salvar dados na camada Bronze em arquivos Parquet
def salvar_dados_bronze(data, bucket_setting: str, category_folder: str = "reclame_aqui_data", page_size: int = 100, is_incremental: bool = True) -> None:
    if not data:
        logging.warning("Nenhum dado fornecido para salvar no Storage.")
        return

    # Leitura de configurações do ambiente
    is_local_only = os.getenv("LOCAL_ONLY", "False").lower() == "true"
    gcp_project_id = os.getenv("GCP_PROJECT_ID", None)

    # Tratamento do Bucket e Prefixo
    bucket_name, env_base_prefix = extrair_bucket_prefixo(bucket_setting)

    # Pasta única com a data da execução
    # Estruturação dos caminhos de saída (local/GCP)
    if is_local_only:
        output_dir = os.path.join("data", EXECUTION_DATE_FOLDER)
        logging.info(f"[Salvo Localmente] Destino definido em: {output_dir}")
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            logging.error(f"Falha Crítica para criar diretório local '{output_dir}': {str(e)}")
            sys.exit(1)
    else:
        gcs_full_prefix = f"{env_base_prefix}{EXECUTION_DATE_FOLDER}"
        logging.info(f"[Salvo em Nuvem] Destino definido em: gs://{bucket_name}/{gcs_full_prefix}/")

    # Conversão dos dados e cálculo de paginação
    try:
        df = pd.json_normalize(data)
        
        # Casting explicito de tipos para evitar divergencia de schema entre lotes
        df['nota_consumidor'] = pd.to_numeric(df['nota_consumidor'], errors='coerce').fillna(0).astype('int64')
        df['tempo_resposta_dias'] = pd.to_numeric(df['tempo_resposta_dias'], errors='coerce').fillna(0).astype('int64')
        df['data_postagem'] = pd.to_datetime(df['data_postagem']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df['data_ingestao'] = pd.to_datetime(df['data_ingestao']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        total_records = len(df)
        total_parts = (total_records + page_size - 1) // page_size
        logging.info(f"Processando {total_records} registros em {total_parts} arquivo(s) Parquet.")
        
    except Exception as e:
        logging.error(f"ERRO ao converter registros para DataFrame: {str(e)}")
        sys.exit(1)

    # Conexão com Google Cloud Storage se estiver em Nuvem
    bucket = None
    if not is_local_only:
        if not bucket_name:
            logging.error("Nome do Bucket não configurado.")
            sys.exit(1)
        try:
            client = storage.Client(project=gcp_project_id) if gcp_project_id else storage.Client()
            bucket = client.bucket(bucket_name)
        except Exception as e:
            logging.error(f"ERRO ao conectar com GCS - Google Cloud Storage: {str(e)}")
            sys.exit(1)
            
        # Backfill no GCP / Truncate
        if not is_incremental:
            try:
                logging.info(f"[BACKFILL / TRUNCATE EM NUVEM] Limpeza de dados existentes no Bucket: {gcs_full_prefix}")
                blobs = bucket.list_blobs(prefix=gcs_full_prefix)
                count_deleted = 0
                for blob in blobs:
                    if blob.name.endswith(".parquet"):
                        blob.delete()
                        count_deleted += 1
                logging.info(f"[Backfill TRUNCATE NUVEM ]: Sucesso: {count_deleted} arquivo(s) antigo(s) apagado(s) do GCS")
            except Exception as e:
                logging.error(f"ERRO ao conectar ou limpar o GCS - Google Cloud Storage: {str(e)}")
                sys.exit(1)

    # Obter sequência incremental da partição
    if is_incremental:
        if is_local_only:
            particao_atual = obter_proxima_particao_local(output_dir)
        else:
            particao_atual = obter_proxima_particao_gcs(bucket, gcs_full_prefix)
    else:
        particao_atual = 1

    # Gravação e envio dos lotes em Parquet paginado
    for i in range(total_parts):
        start_idx = i * page_size
        end_idx = start_idx + page_size
        df_chunk = df.iloc[start_idx:end_idx]

        filename = f"{EXECUTION_TIMESTAMP}_part_{particao_atual:05d}.parquet"        
        # Rota de destino final Local/Nuvem
        if is_local_only:
            local_filepath = os.path.join(output_dir, filename)
            try:
                df_chunk.to_parquet(local_filepath, index=False, engine='pyarrow')
                logging.info(f"[Salvamento local] arquivo salvo em: {local_filepath}")
            except Exception as e:
                logging.error(f"ERRO ao gerar Parquet local '{local_filepath}': {str(e)}")
                sys.exit(1)

        else:
            # ROTA NUVEM: Escrita direto na memória RAM e upload
            gcs_blob_path = f"{gcs_full_prefix}/{filename}"
            try:
                parquet_buffer = io.BytesIO()
                df_chunk.to_parquet(parquet_buffer, index=False, engine='pyarrow')
                parquet_buffer.seek(0)

                blob = bucket.blob(gcs_blob_path)
                blob.upload_from_file(parquet_buffer, content_type='application/octet-stream')
                logging.info(f"[Upload Nuvem] upload concluido: gs://{bucket_name}/{gcs_blob_path}")
            except GoogleAPIError as gcp_err:
                logging.error(f"ERRO na API do GCP durante upload: {str(gcp_err)}")
                sys.exit(1)
            except Exception as e:
                logging.error(f"ERRO ao gerar/enviar Parquet: {str(e)}")
                sys.exit(1)

        particao_atual += 1

    logging.info("Processo Concluido com Sucesso Absoluto")


# Compatibilidade com chamado main.py
save_raw_to_bronze = salvar_dados_bronze