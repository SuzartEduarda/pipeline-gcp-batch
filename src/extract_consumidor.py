import os
import re
import sys
import io
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

# ==============================================================================
# CONFIGURAÇÕES E CONSTANTES DA EXTRAÇÃO REAL
# ==============================================================================
DATA_MINIMA = datetime(2025, 1, 1)
INCREMENTAL = os.getenv("INCREMENTAL", "True").lower() == "true"
INCREMENTAL_DAYS = int(os.getenv("INCREMENTAL_DAYS", "3"))

# URLs de backup oficiais do Portal de Dados Abertos do Governo (Consumidor.gov.br)
URLS_DADOS_ABERTOS = [
    "https://dados.mj.gov.br/dataset/21034442-f831-4dd9-a5f1-325fb08e53d5/resource/a4087131-bb96-4a6c-9a4f-560647b0e0d0/download/dados-consumidor-gov-br-2025-01.csv",
    "https://dados.mj.gov.br/dataset/21034442-f831-4dd9-a5f1-325fb08e53d5/resource/dados-consumidor-gov-br-2024-12.csv",
    "https://dados.gov.br/dados/conjuntos-dados/consumidor-gov-br"
]


def get_incremental_cutoff_date(is_incremental: Optional[bool] = None, delta_days: Optional[int] = None) -> datetime:
    """Calcula a data limite para corte da janela de extração."""
    inc = is_incremental if is_incremental is not None else INCREMENTAL
    days = delta_days if delta_days is not None else INCREMENTAL_DAYS

    if not inc:
        logging.info("[Carga em Backfill] Flag INCREMENTAL=False. Extraindo dados a partir de DATA_MINIMA (01/01/2025)")
        return DATA_MINIMA

    calculated_cutoff = datetime.now() - timedelta(days=days)
    cutoff = max(DATA_MINIMA, calculated_cutoff)
    logging.info(f"[MODO INCREMENTAL] Janela de {days} dia(s) -> Data limite: {cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
    return cutoff


def sanitize_sensitive_data(text: str) -> str:
    """Higienização e Anonimização de dados sensíveis para conformidade com a LGPD."""
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b', '[CPF MASCARADO]', text)
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL MASCARADO]', text)
    text = re.sub(r'\b(?:\(?\d{2}\)?\s?)??(?:9\d{4}|\d{4})-?\d{4}\b', '[TELEFONE MASCARADO]', text)
    return text.strip()


def load_real_dataset() -> Optional[pd.DataFrame]:
    """
    Carrega a base oficial de Dados Abertos:
    1. Verifica primeiro se existe o arquivo CSV na pasta local 'data_local/consumidor_gov.csv'.
    2. Se não existir localmente, percorre a lista de URLs governamentais com tratamento SSL/Timeout.
    """
    local_path = os.path.join("data_local", "consumidor_gov.csv")

    # 1. Tenta carregar a base do cache local caso ela já esteja salva no disco
    if os.path.exists(local_path):
        logging.info(f"Carregando base real oficial do cache local: {local_path}")
        try:
            return pd.read_csv(local_path, sep=";", encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            return pd.read_csv(local_path, sep=";", encoding="latin1", low_memory=False)

    # 2. Tenta download ao vivo navegando pelas URLs de backup públicas do governo
    logging.info("Base local não encontrada em 'data_local/'. Baixando diretamente do Portal de Dados Abertos...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for url in URLS_DADOS_ABERTOS:
        try:
            logging.info(f"Tentando requisição na fonte pública: {url}")
            response = requests.get(url, headers=headers, timeout=20, verify=False)
            if response.status_code == 200 and len(response.content) > 100000:
                os.makedirs("data_local", exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(response.content)
                logging.info(f"Download concluído e gravado com sucesso em: {local_path}")
                
                content = response.content.decode('utf-8', errors='ignore')
                return pd.read_csv(io.StringIO(content), sep=";", low_memory=False)
        except Exception as e:
            logging.warning(f"Não foi possível obter dados da URL '{url}': {str(e)}")

    return None


def extract_consumidor_gov_data(is_incremental: Optional[bool] = None, delta_days: Optional[int] = None) -> Tuple[List[Dict], bool]:
    """
    Processa e estrutura as reclamações da base oficial do Consumidor.gov.br.
    Aplica filtros para Pernambuco e Bahia (Vale do São Francisco) e mascaramento LGPD.
    """
    cutoff_date = get_incremental_cutoff_date(is_incremental, delta_days)
    complaints = []
    has_errors = False

    df = load_real_dataset()

    if df is None or df.empty:
        logging.error("ERRO CRÍTICO: Não foi possível obter a base oficial do Consumidor.gov.br.")
        return [], True

    try:
        logging.info(f"Base oficial carregada com {len(df)} registros. Aplicando tratamento e regras de negócio...")

        # Mapeamento flexível de colunas do padrão de Dados Abertos do Governo
        col_data = 'Data Abertura' if 'Data Abertura' in df.columns else 'Data'
        col_empresa = 'Nome Fantasia' if 'Nome Fantasia' in df.columns else 'Empresa'
        col_cidade = 'Cidade' if 'Cidade' in df.columns else 'Município'
        col_uf = 'UF'
        col_assunto = 'Assunto' if 'Assunto' in df.columns else 'Grupo Problema'
        col_relato = 'Relato' if 'Relato' in df.columns else 'Descrição'
        col_status = 'Situação' if 'Situação' in df.columns else 'Avaliação Reclamação'

        # Parseamento das datas
        df['Data_Parsed'] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce')

        # 1. Filtro Temporal
        df_filtered = df[df['Data_Parsed'] >= cutoff_date].copy()

        # 2. Filtro Regional (Foco: Pernambuco e Bahia / Vale do São Francisco)
        df_filtered['UF_Clean'] = df_filtered[col_uf].astype(str).str.upper()
        df_filtered = df_filtered[df_filtered['UF_Clean'].isin(['PE', 'BA'])]

        logging.info(f"Total de {len(df_filtered)} registros reais filtrados para PE/BA pós-{cutoff_date.strftime('%Y-%m-%d')}.")

        # 3. Estruturação do Dicionário de Ingestão
        for idx, row in df_filtered.iterrows():
            relato_bruto = str(row.get(col_relato, ""))
            if relato_bruto.lower() in ["nan", "null", "none", ""]:
                relato_bruto = str(row.get(col_assunto, "Reclamação Consumidor.gov"))

            record = {
                "id_reclamacao": f"CG-REAL-{idx}",
                "empresa_alvo": str(row.get(col_empresa, "NÃO INFORMADO")),
                "titulo": sanitize_sensitive_data(str(row.get(col_assunto, "Reclamação de Consumo"))),
                "descricao_texto": sanitize_sensitive_data(relato_bruto),
                "cidade": str(row.get(col_cidade, "")),
                "uf": str(row.get(col_uf, "")),
                "data_postagem": row['Data_Parsed'].strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(row['Data_Parsed']) else "",
                "status_resolucao": str(row.get(col_status, "NÃO DEFINIDO")),
                "url_fonte": "https://www.consumidor.gov.br",
                "data_ingestao": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            complaints.append(record)

    except Exception as e:
        logging.error(f"Erro no processamento da base de dados reais: {str(e)}")
        has_errors = True

    logging.info(f"EXTRAÇÃO REAL CONCLUÍDA. Total de {len(complaints)} reclamações preparadas.")
    return complaints, has_errors


# Alias para integração perfeita com main.py
extract_reclame_aqui_data = extract_consumidor_gov_data


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
    data, error = extract_consumidor_gov_data(is_incremental=False)
    print(f"Total de registros reais extraídos: {len(data)}")