import os
import sys
import time
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv
from google.cloud import bigquery
from google.api_core.exceptions import NotFound
from pydantic import BaseModel, Field
from typing import Literal

# Carregar variáveis de ambiente
load_dotenv()

# Configuração de Logs
logger = logging.getLogger(__name__)

# Modelos Pydantic para saída estruturada em lotes
class ItemAnalise(BaseModel):
    id_reclamacao: str = Field(description="ID exato da reclamacao")
    sentimento: Literal["POSITIVO", "NEUTRO", "NEGATIVO"] = Field(
        description="Classificacao de sentimento do relato"
    )
    causa_raiz: str = Field(
        description="Resumo da causa-raiz do problema em ate 5 palavras"
    )
    urgencia: Literal["ALTA", "MEDIA", "BAIXA"] = Field(
        description="Nivel de urgencia da reclamacao"
    )
    justificativa_urgencia: str = Field(
        description="Frase explicativa sobre a urgencia em ate 15 palavras"
    )
    acao_recomendada: str = Field(
        description="Acao pratica sugerida para resolucao em ate 10 palavras"
    )

class LoteAnalise(BaseModel):
    analises: List[ItemAnalise]


def obter_cliente_bigquery(project_id: str) -> bigquery.Client:
    """Inicializa e retorna o cliente do BigQuery."""
    try:
        return bigquery.Client(project=project_id)
    except Exception as e:
        logger.error(f"Falha ao conectar cliente BigQuery: {str(e)}")
        sys.exit(1)


def obter_cliente_gemini():
    """
    Inicializa o cliente Google GenAI utilizando a GEMINI_API_KEY do Google AI Studio.
    Custo Zero via Free Tier.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error(
            "ERRO CRÍTICO: Variável GEMINI_API_KEY não encontrada no arquivo .env!\n"
            "Adicione sua chave gratuita ao .env: GEMINI_API_KEY=sua_chave"
        )
        sys.exit(1)
    
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"Falha ao inicializar cliente Google GenAI: {str(e)}")
        sys.exit(1)


def garantir_tabela_gold(client: bigquery.Client, table_ref: str) -> None:
    """
    Garante que a tabela tb_enriquecimento_llm exista no BigQuery.
    """
    try:
        client.get_table(table_ref)
        logger.info(f"Tabela de destino confirmada: {table_ref}")
    except NotFound:
        logger.info(f"Tabela {table_ref} não encontrada. Criando com schema...")
        schema = [
            bigquery.SchemaField("id_reclamacao", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("empresa_alvo", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("categoria_servico", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("cidade", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("uf", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("data_postagem", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("sentimento", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("causa_raiz", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("urgencia", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("justificativa_urgencia", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("acao_recomendada", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("data_processamento_gold", "TIMESTAMP", mode="NULLABLE"),
        ]
        table = bigquery.Table(table_ref, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="data_postagem"
        )
        table.clustering_fields = ["empresa_alvo", "sentimento"]
        client.create_table(table)
        logger.info(f"Tabela {table_ref} criada com sucesso no BigQuery.")


def buscar_reclamacoes_pendentes(
    client: bigquery.Client,
    project_id: str,
    environment: str,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Busca registros da camada Silver (tb_reclame_aqui_clean) que ainda não foram enriquecidos na Gold.
    """
    silver_table = f"`{project_id}.silver_{environment}.tb_reclame_aqui_clean`"
    gold_table = f"`{project_id}.gold_{environment}.tb_enriquecimento_llm`"

    try:
        client.get_table(f"{project_id}.gold_{environment}.tb_enriquecimento_llm")
        where_clause = f"WHERE s.id_reclamacao NOT IN (SELECT id_reclamacao FROM {gold_table})"
    except NotFound:
        where_clause = ""

    limit_clause = f"LIMIT {limit}" if limit else ""

    query = f"""
        SELECT
            s.id_reclamacao,
            s.empresa_alvo,
            s.categoria_servico,
            s.cidade,
            s.uf,
            s.data_postagem,
            s.descricao_texto
        FROM {silver_table} s
        {where_clause}
        ORDER BY s.data_postagem DESC
        {limit_clause}
    """

    logger.info("Buscando registros pendentes de enriquecimento na Silver...")
    query_job = client.query(query)
    results = [dict(row) for row in query_job.result()]
    logger.info(f"Total de registros pendentes encontrados para enriquecer: {len(results)}")
    return results


def analisar_lote_com_gemini(
    genai_client,
    model_name: str,
    itens: List[Dict[str, Any]]
) -> Dict[str, ItemAnalise]:
    """
    Chama o Gemini para analisar uma lista de reclamações em uma única requisição.
    """
    from google.genai import types

    lista_prompt = []
    for item in itens:
        lista_prompt.append({
            "id_reclamacao": str(item["id_reclamacao"]),
            "empresa_alvo": str(item.get("empresa_alvo", "")),
            "texto": str(item.get("descricao_texto", ""))
        })

    prompt = f"""
Voce eh um analista especialista em satisfacao do consumidor no Vale do Sao Francisco.
Analise cada uma das reclamacoes abaixo e retorne a analise estruturada com o id_reclamacao correspondente:

{json.dumps(lista_prompt, ensure_ascii=False, indent=2)}
"""

    try:
        response = genai_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LoteAnalise,
                temperature=0.1,
            )
        )
        dados = json.loads(response.text)
        lote = LoteAnalise(**dados)
        return {item.id_reclamacao: item for item in lote.analises}

    except Exception as e:
        logger.warning(f"Erro na chamada em lote do Gemini: {str(e)}")
        return {}


def executar_enriquecimento(
    tamanho_lote: int = 15,
    delay_entre_lotes: float = 4.5,
    limit: Optional[int] = None,
    is_incremental: Optional[bool] = None
) -> int:
    """
    Orquestra o enriquecimento em lotes para alta performance e Custo Zero via Google AI Studio.
    Respeita dinamicamente as variáveis de volumetria do .env.
    """
    load_dotenv(override=True)
    project_id = os.getenv("GCP_PROJECT_ID")
    environment = os.getenv("ENVIRONMENT", "dev")
    model_name = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

    # Resolução de volumetria e modo de carga a partir do .env se não informado
    if is_incremental is None:
        inc = os.getenv("INCREMENTAL", "True").lower() == "true"
    else:
        inc = is_incremental

    if limit is None:
        if inc:
            limite_env = int(os.getenv("VOLUMETRIA_INCREMENTAL", "100"))
        else:
            limite_env = int(os.getenv("VOLUMETRIA_BACKFILL", "500"))
        limit = limite_env

    if not project_id:
        logger.error("ERRO: GCP_PROJECT_ID não definido no .env")
        sys.exit(1)

    bq_client = obter_cliente_bigquery(project_id)
    genai_client = obter_cliente_gemini()

    gold_table_ref = f"{project_id}.gold_{environment}.tb_enriquecimento_llm"
    garantir_tabela_gold(bq_client, gold_table_ref)

    pendentes = buscar_reclamacoes_pendentes(bq_client, project_id, environment, limit=limit)
    if not pendentes:
        logger.info("Tabela tb_enriquecimento_llm já está 100% atualizada! Nada a fazer.")
        return 0

    total_pendentes = len(pendentes)
    logger.info(f"Iniciando enriquecimento de {total_pendentes} registros via Gemini ({model_name}) | Limite configurado: {limit}...")
    
    total_processados = 0
    now_utc = datetime.now(timezone.utc).isoformat()

    # Dividir em lotes
    for i in range(0, total_pendentes, tamanho_lote):
        lote_itens = pendentes[i : i + tamanho_lote]
        num_lote = (i // tamanho_lote) + 1
        total_lotes = (total_pendentes + tamanho_lote - 1) // tamanho_lote

        logger.info(f"[Lote {num_lote}/{total_lotes}] Processando {len(lote_itens)} reclamações...")

        analises_map = analisar_lote_com_gemini(genai_client, model_name, lote_itens)

        registros_gold = []
        for row in lote_itens:
            id_rec = str(row["id_reclamacao"])
            analise = analises_map.get(id_rec)

            data_postagem_val = row["data_postagem"]
            if isinstance(data_postagem_val, datetime):
                data_postagem_str = data_postagem_val.isoformat()
            else:
                data_postagem_str = str(data_postagem_val) if data_postagem_val else None

            reg = {
                "id_reclamacao": id_rec,
                "empresa_alvo": row.get("empresa_alvo"),
                "categoria_servico": row.get("categoria_servico"),
                "cidade": row.get("cidade"),
                "uf": row.get("uf"),
                "data_postagem": data_postagem_str,
                "sentimento": analise.sentimento if analise else "NEUTRO",
                "causa_raiz": analise.causa_raiz if analise else "Falha de servico",
                "urgencia": analise.urgencia if analise else "MEDIA",
                "justificativa_urgencia": analise.justificativa_urgencia if analise else "Analise padrao",
                "acao_recomendada": analise.acao_recomendada if analise else "Atendimento prioritario",
                "data_processamento_gold": now_utc,
            }
            registros_gold.append(reg)

        # Inserir no BigQuery
        erros = bq_client.insert_rows_json(gold_table_ref, registros_gold)
        if erros:
            logger.error(f"Erros na inserção BigQuery (Lote {num_lote}): {erros}")
        else:
            total_processados += len(registros_gold)
            logger.info(f"-> [Lote {num_lote}/{total_lotes}] {len(registros_gold)} registros salvos em tb_enriquecimento_llm! (Progresso: {total_processados}/{total_pendentes})")

        # Intervalo para respeitar a cota gratuita da API
        if i + tamanho_lote < total_pendentes:
            time.sleep(delay_entre_lotes)

    logger.info(f"CONCLUÍDO COM SUCESSO: {total_processados} novos registros enriquecidos na Gold!")
    return total_processados


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enriquecimento Semântico via Gemini (Google AI Studio Free Tier)")
    parser.add_argument("--limit", type=int, default=None, help="Limite máximo de registros para enriquecer (sobrescreve .env)")
    parser.add_argument("--batch-size", type=int, default=15, help="Tamanho de cada lote enviado à LLM")
    parser.add_argument("--delay", type=float, default=4.5, help="Tempo de espera entre lotes em segundos")
    parser.add_argument("--backfill", action="store_true", help="Usa volumetria de backfill do .env")
    parser.add_argument("--incremental", action="store_true", help="Usa volumetria incremental do .env")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    inc = True if args.incremental else (False if args.backfill else None)
    executar_enriquecimento(
        tamanho_lote=args.batch_size,
        delay_entre_lotes=args.delay,
        limit=args.limit,
        is_incremental=inc
    )
