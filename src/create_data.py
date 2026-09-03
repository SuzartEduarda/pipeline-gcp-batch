import os
import random
import shutil
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv
from faker import Faker

load_dotenv()

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
    logging.info(f"Iniciando Geração de Dados ({total_registros} Registros)")

    # Garantia de datas restritas a janela ativa sem descartar dados
    inicio_sorteio = data_inicio_janela if data_inicio_janela else DATA_MINIMA
    fim_sorteio = datetime.now()
    intervalo_segundos = int(max(1, (fim_sorteio - inicio_sorteio).total_seconds()))
 
    # Estrutura com divisão de gravidade para metricas de observabilidade e priorização de atendimento
    DADOS_CATEGORIZADOS = {
        "Saneamento / Água": {
            "empresas": [
                {"nome": "COMPESA", "uf": "PE", "cidade": "Petrolina"},
                {"nome": "BRK Ambiental Juazeiro", "uf": "BA", "cidade": "Juazeiro"}
            ],
            "criticos": [
                "Esgoto correndo a ceu aberto na porta de casa ha 5 dias",
                "Sem pingo de agua na torneira ha quase uma semana no bairro"
            ],
            "moderados": [
                "Conta de agua veio com valor o dobro da media habitual",
                "Pressao da agua muito fraca para encher a caixa d'agua"
            ]
        },
        "Energia Elétrica": {
            "empresas": [
                {"nome": "Neoenergia Pernambuco", "uf": "PE", "cidade": "Petrolina"},
                {"nome": "Neoenergia Coelba", "uf": "BA", "cidade": "Juazeiro"}
            ],
            "criticos": [
                "Oscilacao forte de energia queimou minha geladeira e televisao",
                "Fio de alta tensao partido no meio da rua oferecendo risco"
            ],
            "moderados": [
                "Demora para religar a energia apos pagamento de conta atrasada",
                "Cobranca indevida de taxa de iluminacao publica na fatura"
            ]
        },
        "Banda Larga / Internet": {
            "empresas": [
                {"nome": "Giga+ Fibra", "uf": "PE", "cidade": "Petrolina"},
                {"nome": "Mob Telecom", "uf": "BA", "cidade": "Juazeiro"}
            ],
            "criticos": [
                "Cabo de fibra rompeu e estou sem internet para trabalhar ha 3 dias",
                "Sinal caindo a cada 5 minutos impossibilitando uso basico"
            ],
            "moderados": [
                "Velocidade entregue esta abaixo do contratado no plano de 300 Mega",
                "Dificuldade para alterar a senha do Wi-Fi pelo aplicativo"
            ]
        }
    }
    
    canais = ["Consumidor.gov.br (Simulado)", "Reclame Aqui (Simulado)", "Portal Web Direct"]    
    registros = []

    for idx in range(1, total_registros + 1):
        cat_nome = random.choice(list(DADOS_CATEGORIZADOS.keys()))
        setor = DADOS_CATEGORIZADOS[cat_nome]
        emp = random.choice(setor["empresas"])
        
        # Regra 35% das reclamaações são criticas
        is_critico = random.random() < 0.35

        if is_critico:
            problema = random.choice(setor["criticos"])
            # Simula FALHA DA TRIAGEM ORIGINAL 
            prioridade_canal = random.choice(["BAIXA", "MEDIA"]) if random.random() < 0.4 else "ALTA"
            tempo_resposta = random.choice([5, 7, 10, 14])
            nota_consumidor = random.choice([1, 2])
            status_final = random.choice(["nao resolvida", "Em analise", "PENDENTE"])
            tentativas_num = random.randint(3, 7)
        else:
            problema = random.choice(setor["moderados"])
            prioridade_canal = random.choice(["BAIXA", "MEDIA"])
            tempo_resposta = random.choice([1, 2, 3, 4])
            nota_consumidor = random.choice([3, 4, 5])
            status_final = random.choice(["Resolvido", "Em Analise"])
            tentativas_num = random.randint(1, 2)
            
        cpf_ruido =fake.cpf()
        tel_ruido = fake.cellphone_number()
        email_ruido = fake.free_email()
        bairro_ruido = fake.bairro()
        
        descricao_dinamica = (
            f"Relato do consumidor residente no bairro {bairro_ruido}, em {emp['cidade']}-{emp['uf']}. "
            f"Problema enfrentado: {problema}. "
            f"Ja tentei contato com a {emp['nome']} por {tentativas_num} vezes sem sucesso. "
            f"Contatos do titular: CPF {cpf_ruido}, celular {tel_ruido} e e-mail {email_ruido}. "
            f"{fake.paragraph(nb_sentences=2)}"
        )
        
        replica_dinamica = (
            f"A {emp['nome']} informa que recebeu o protocolo referente a '{problema}' no bairro {bairro_ruido}. "
            f"Status do atendimento: {status_final}. {fake.sentence()}"
        )
        
        cidade_com_ruido = emp["cidade"].lower() if idx % 2 == 0 else emp["cidade"].upper()
        uf_com_ruido = emp["uf"].lower() if idx % 3 == 0 else emp["uf"]
        
        segundos_aleatorios = random.randint(0, intervalo_segundos)
        dt_postagem = inicio_sorteio + timedelta(seconds=segundos_aleatorios)
        
        id_unico = f"CG-MOCK-{EXECUTION_STAMP}-{idx:05d}"
            
        registro = {
            "id_reclamacao": id_unico,
            "canal_origem": random.choice(canais),
            "empresa_alvo": emp["nome"],
            "categoria_servico": cat_nome,
            "titulo": f"{problema.upper()} - BAIRRO {bairro_ruido.upper()}",
            "descricao_texto": descricao_dinamica,
            "replica_empresa_texto": replica_dinamica,
            "cidade": cidade_com_ruido,
            "uf": uf_com_ruido,
            "data_postagem": dt_postagem.strftime("%Y-%m-%d %H:%M:%S"),
            "status_resolucao":status_final,
            "nota_consumidor": nota_consumidor,
            "tempo_resposta_dias": tempo_resposta,
            "houve_reconsideracao": True if (is_critico and random.random() < 0.5) else False,
            "score_prioridade_simulado": prioridade_canal,
            "tentativas_contato_previas": f"{tentativas_num} chamados abertos",
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
    if is_incremental is not None:
        inc = is_incremental
    else:
        inc = os.getenv("INCREMENTAL", "True").lower() == "true"
    corte_dedata = obter_corte_data(is_incremental=inc, delta_days=delta_days)

    # leitura dinamica de variaveis
    volumetria_backfill = int(os.getenv("VOLUMETRIA_BACKFILL", "2500"))
    volumetria_incremental = int(os.getenv("VOLUMETRIA_INCREMENTAL", "1000"))

    #Se for backfill (inc == False), executa o Truncate(Reset)
    if not inc:
        executar_truncamento_local()
        volumetria = volumetria_backfill
    else:
        volumetria = volumetria_incremental

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