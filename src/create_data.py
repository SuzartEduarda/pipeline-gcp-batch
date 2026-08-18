import os
import random
import shutil
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from faker import Faker

# Biblioteca faker
fake = Faker('pt_BR')

# Configurações de data e variavel incremental
DATA_MINIMA_SRT = os.getenv("DATA_MINIMA", "2025-01-01")
DATA_MINIMA = datetime.strptime(DATA_MINIMA_SRT, "%Y-%m-%d")
# Cargas incremental=aappend, backfill = (Truncate/Reload)
INCREMENTAL = os.getenv("INCREMENTAL", "True").lower() == "true"
INCREMENTAL_DAYS = int(os.getenv("INCREMENTAL_DAYS", "3"))
# VOLUMETRIA DE DADOS DINAMICA
VOLUMETRIA_INCREMENTAL = int(os.getenv("VOLUMETRIA_INCREMENTAL", "1000"))
VOLUMETRIA_BACKFILL = int(os.getenv("VOLUMETRIA_BACKFILL", "2500"))
#Timestamp de id unico fixo 
EXECUTION_STAMP = datetime.now().strftime("%Y%m%d%H%M")

# Função para calcular a data limite de corte de reclamações
def obter_corte_data(is_incremental: Optional[bool] = None, delta_days: Optional[int] = None) -> datetime:
    inc = is_incremental if is_incremental is not None else INCREMENTAL
    days = delta_days if delta_days is not None else INCREMENTAL_DAYS

    if not inc:
        logging.info(f"[MODO BACKFILL / TRUNCATE] Gerando dados fake historicos a partir de ({DATA_MINIMA.strftime('%Y-%m-%d')})")
        return DATA_MINIMA

    calculo_decorte = datetime.now() - timedelta(days=days)
    corte = max(DATA_MINIMA, calculo_decorte)
    logging.info(f"[MODO INCREMENTAL / APPEND] Janela de {days} dia(s) -> Data Limite de corte: {corte.strftime('%Y-%m-%d %H:%M:%S')}")
    return corte

# Simula abertura de conexão com portal
def simular_conexao() -> bool:
    logging.info("Simulando Conexão com fonte de dados publica")
    logging.info("Status 200 ok. Sucesso")
    return True

# Simula o encerramento da conexão
def simula_desconexao() -> None:
    logging.info("Simula encerramento de conexão e liberação de recursos")
    logging.info("Conexão finalizada, com Sucesso")


# Função geradora de dados mockados dinamicamente, via Lib Faker
def criar_dados(total_registros: int = 1000, data_inicio_janela: Optional[datetime] = None) -> List[Dict]:
    logging.info(f"Iniciando Geração de Dados Dinamica, via biblioteca Faker({total_registros} Registros)")

    # Garantia de datas restritas a janela ativa sem descartar dados
    inicio_sorteio = data_inicio_janela if data_inicio_janela else DATA_MINIMA
    fim_sorteio = datetime.now()
    intervalo_segundos = int(max(1, (fim_sorteio - inicio_sorteio).total_seconds()))

    # Mapeamento/Filtro Regional de Empresas e Cidades do vale do são francisco
    empresas_vsf = [
        {"nome": "COMPESA", "uf": "PE", "cidade": "Petrolina", "categoria": "Saneamento / Água"},
        {"nome": "Neoenergia Pernambuco", "uf": "PE", "cidade": "Petrolina", "categoria": "Energia Elétrica"},
        {"nome": "BRK Ambiental Juazeiro", "uf": "BA", "cidade": "Juazeiro", "categoria": "Saneamento / Água"},
        {"nome": "Neoenergia Coelba", "uf": "BA", "cidade": "Juazeiro", "categoria": "Energia Elétrica"},
        {"nome": "Giga+ Fibra", "uf": "PE", "cidade": "Petrolina", "categoria": "Banda Larga / Internet"},
        {"nome": "Mob Telecom", "uf": "BA", "cidade": "Juazeiro", "categoria": "Banda Larga / Internet"},
        {"nome": "River Shopping Petrolina", "uf": "PE", "cidade": "Petrolina", "categoria": "Varejo / Shopping"},
        {"nome": "Casas Bahia", "uf": "PE", "cidade": "Petrolina", "categoria": "Varejo / E-commerce"},
        {"nome": "Magazine Luiza", "uf": "BA", "cidade": "Juazeiro", "categoria": "Varejo / E-commerce"},
        {"nome": "Lojas Americanas", "uf": "PE", "cidade": "Petrolina", "categoria": "Varejo / E-commerce"}
    ]

    # Tipos de problemas para contextualização
    problemas_tipos =[
        "Falta de abastecimento de água e torneiras secas",
        "Queda e oscilação constante de energia elétrica",
        "Esgoto a céu aberto e vazamento na via pública",
        "Lentidão extrema e queda no sinal de internet de fibra",
        "Atraso no prazo de entrega do pedido comprado online",
        "Cobrança de taxa indevida não autorizada no boleto mensal"
    ]

    canais = ["Consumidor.gov.br (Simulado)", "Reclame Aqui (Simulado)", "Portal Web Direct"]
    status = ["não resolvida", "Em Análise", "Resolvido", "PENDENTE", "Aguardando Resposta"]
    prioridades = ["ALTA", "MEDIA", "BAIXA"]

    registros = []

    for idx in range(1, total_registros + 1):
        emp = random.choice(empresas_vsf)
        problemas_base = random.choice(problemas_tipos)

        # Injeção dinamica de dados reais/ruido pela biblioteca-lib Faker
        cpf_ruido = fake.cpf()
        telefone_ruido = fake.cellphone_number()
        email_ruido = fake.free_email()
        bairro_ruido = fake.bairro()

        # Construção da narrativa dinâmica usando o Faker
        titulo_dinamico = f"{problemas_base.upper()} No Bairro {bairro_ruido.upper()}"

        descricao_dinamica = (
            f"Relato do consumidor em {emp['cidade']}-{emp['uf']}: {problemas_base} no bairro {bairro_ruido}. "
            f"O serviço da empresa {emp['nome']} apresentou falha grave. "
            f"Dados para contato direto: CPF {cpf_ruido}, telefone {telefone_ruido} e e-mail {email_ruido}. "
            f"{fake.paragraph(nb_sentences=3)}"
        )

        replica_dinamica = (
            f"Prezado cliente, informamos que a equipe tecnica da {emp['nome']} foi acionada para o bairro {bairro_ruido}"
            f"{fake.sentence()}"
        )
        
        tentativa_dinamica =f"{random.randint(1,6)} chamados abertos no SAC sem resolução"

        # Injeção de ruidos de formatação
        cidade_com_ruido = emp["cidade"].lower() if idx % 2 == 0 else emp["cidade"]
        uf_com_ruido = emp["uf"].lower() if idx % 3 == 0 else emp["uf"]
        status_com_ruido = random.choice(status)

        # Sorteio preciso para filtro
        segundos_aleatorios = random.randint(0, intervalo_segundos)
        dt_postagem = inicio_sorteio + timedelta(seconds=segundos_aleatorios)

        #Id unico = timestamp de execução + indice sequencial
        id_unico = f"CG-MOCK-{EXECUTION_STAMP}-{idx:05d}"

        registro = {
            "id_reclamacao": id_unico,
            "canal_origem": random.choice(canais),
            "empresa_alvo": emp["nome"],
            "categoria_servico": emp["categoria"],
            "titulo": titulo_dinamico,
            "descricao_texto": descricao_dinamica,
            "replica_empresa_texto": replica_dinamica,
            "cidade": cidade_com_ruido,
            "uf": uf_com_ruido,
            "data_postagem": dt_postagem.strftime("%Y-%m-%d %H:%M:%S"),
            "status_resolucao": status_com_ruido,
            "nota_consumidor": random.choice([1, 2, 3, 4, 5, None]),
            "tempo_resposta_dias": random.choice([1, 2, 3, 5, 10, None]),
            "houve_reconsideracao": random.choice([True, False]),
            "score_prioridade_simulado": random.choice(prioridades),
            "tentativas_contato_previas": tentativa_dinamica,
            "data_ingestao": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        registros.append(registro)

    return registros

# Função realiza o reset/limpesa da pasta local quando o modo backfill/Truncate for acionado
def executar_truncamento_local() -> None:
    path_local = os.path.join("data")
    if os.path.exists(path_local):
        logging.info("[TRUNCATE / BACKFILL] Limpando pasta de dados 'data/' e recriando do zero")
        try:
            shutil.rmtree(path_local)
            os.makedirs(path_local, exist_ok=True)
            logging.info("[TRUNCATE / BACKFILL] pasta 'data/' reiniciada com Sucesso")
        except Exception as e:
            logging.warning(f"Alerta ao executar truncate local: {str(e)}")

#Função orquestradora principal para gerar e filtrar as reclamações
def dados_reclamacao(is_incremental: Optional[bool] = None, delta_days: Optional[int] = None) -> Tuple[List[Dict], bool]:
    inc = is_incremental if is_incremental is not None else INCREMENTAL
    corte_dedata = obter_corte_data(is_incremental, delta_days)

    #Se for backfill (inc == False), executa o Truncate(Reset)
    if not inc:
        executar_truncamento_local()
        volumetria = VOLUMETRIA_BACKFILL
    else:
        volumetria = VOLUMETRIA_INCREMENTAL

    simular_conexao()

    #Gerar registros já alinhados com a janela temporal definida
    reclamacoes_geradas = criar_dados(
        total_registros=volumetria,

        data_inicio_janela=corte_dedata
    )

    has_error = False

    try:
        logging.info(f"Geração dinamica de dados via Faker Concluida. Total de {len(reclamacoes_geradas)} reclamações ok")
    except Exception as e:
        logging.error(f"Erro durante o processamento de dados sinteticos com Faker: {str(e)}")
        has_error = True
    finally:
        #Simula o encerramento da conexão
        simula_desconexao()
    return reclamacoes_geradas, has_error

# compatibilidade para permitir chamadas pelo main
extract_reclame_aqui_data = dados_reclamacao
extract_consumidor_gov_data = dados_reclamacao

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
    logging.info("Executando módulo com (Lib Faker) em modo isolado")
    dados, erro = dados_reclamacao(is_incremental=False)
    logging.info(f"[TESTE CONCLUIDO] Total de registros gerados: {len(dados)} | Houveram erros: {erro}")