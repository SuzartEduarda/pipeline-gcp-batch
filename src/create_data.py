import os
import re
import glob
import random
import shutil
import logging
import pandas as pd
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
VOLUMETRIA_INCREMENTAL = int(os.getenv("VOLUMETRIA_INCREMENTAL", "100"))
VOLUMETRIA_BACKFILL = int(os.getenv("VOLUMETRIA_BACKFILL", "500"))
#Timestamp de id unico fixo 
EXECUTION_STAMP = datetime.now().strftime("%Y%m%d%H%M%S")

# Varre a pasta local do dia ou consulta os IDs existentes para encontrar o maior sequencial já gerado 
# para o nome do arquivo e retornar o proximo numero
def check_sequencial(diretorio_dia: str, prefixo_data: str) -> int:
    if not os.path.exists(diretorio_dia):
        return 1

    maior_seq = 0
    arquivos_parquet = glob.glob(os.path.join(diretorio_dia, "*.parquet"))

    for arq in arquivos_parquet:
        try:
            df_temp = pd.read_parquet(arq, columns=["id_reclamacao"])
            for id_val in df_temp["id_reclamacao"].dropna():
                match = re.search(r'-(\d{5})$', str(id_val))
                if match:
                    seq = int(match.group(1))
                    if seq > maior_seq:
                        maior_seq = seq
        except Exception:
            continue
    return maior_seq + 1

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

def gerar_texto_dinamico(tipo: str, empresa: str, cidade: str, uf: str, causa: str, bairro: str, cpf:str, tel: str, email: str) -> str:
    saudacoes = {
        "CRITICO": [
            "É UM ABSURDO O QUE ESTÁ ACONTECENDO!",
            "Inaceitável o descaso com os moradores.",
            "Venho através deste canal registrar minha total indignação.",
            "Não agumento mais essa situação recorrente!",
            "Urgente! Preciso de providências imediatas."
        ],
        "MODERADO": [
            "Gostaria de abrir um chamado sobre um problema recorrente.",
            "Preciso de auxílio da empresa para resolver uma pendência.",
            "Prezados, venho informar uma irregularidade no meu serviço.",
            "Solicito verificação da equipe responsável.",
            "Escrevo para relatar uma falha na prestação do serviço."
        ],
        "ELOGIO": [
            "Gostaria de registrar meu elogio ao atendimento!",
            "Parabéns pelo excelente trabalho prestado.",
            "Venho manifestar minha satisfação com a equipe.",
            "Muito satisfeito com a rapidez na solução!",
            "Quero agradecer pelo suporte prestado hoje."
        ],
        "DUVIDA": [
            "Olá, gostaria de tirar uma dúvida sobre minha conta/contrato.",
            "Preciso de informações sobre os serviços na minha região.",
            "Por gentileza, poderiam me esclarecer um procedimento?",
            "Gostaria de entender melhor a cobrança deste mês.",
            "Como faço para solicitar alterações no meu cadastro?"
        ]
    }
    
    contextos_locais =[
        f"Moro no bairro {bairro} em {cidade}-{uf}",
        f"Sou morador aqui perto do centro de {cidade}",
        f"Tenho um estabelecimento comercial no bairro {bairro}",
        f"Resido na região de {cidade}-{uf}, próximo ao bairro {bairro}",
        f"A situação ocorre na minha residência localizada no {bairro}"
    ]
    
    impactos = {
        "CRITICO": [
            "Estou com idosos e crianças em casa passando por dificuldades.",
            "Isso prejudicou totalmente meu trabalho em home office hoje.",
            "Já tive prejuízos financeiros por conta dessa falha grave.",
            "A comunidade inteira está sendo afetada e sem suporte.",
            "Tentei contato pelo SAC diversas vezes e desligaram na minha cara."
        ],
        "MODERADO": [
            "Isso tem gerado transtornos no meu dia a dia.",
            "Aguardando há dias por uma resposta formal.",
            "O valor cobrado não condiz com o serviço contratado.",
            "Já abri protocolos anteriores mas o problema retorna.",
            "Espero que não precise acionar os órgãos de defesa do consumidor."
        ],
        "ELOGIO": [
            "O técnico foi super atencioso e resolveu tudo em poucos minutos.",
            "Serviço de altíssima qualidade, superou minhas expectativas.",
            "A equipe de rua foi muito prestativa e educada.",
            "Atendimento nota 10 do início ao fim.",
            "Continuem com esse ótimo padrão de atendimento!"
        ],
        "DUVIDA": [
            "Não encontrei essa informação clara no aplicativo nem no site.",
            "Aguardando orientação para proceder da maneira correta.",
            "Preciso organizar meu planejamento financeiro e necessito do detalhamento.",
            "Se puderem me enviar por e-mail, agradeço.",
            "Aguardo um retorno simples para sanar esta questão."
        ]
    }
    
    encerramentos = [
        f"Meus dados para localização do contrato: CPF {cpf}, Celular {tel} e e-mail {email}.",
        f"Podem entrar em contato pelo e-mail {email} ou telefone {tel}. Titular CPF: {cpf}.",
        f"Registrado por titular do CPF {cpf}. Contato rápido via WhatsApp {tel}.",
        f"Favor responder para {email}. Telefone de recado: {tel}.",
        f"Aguardo retorno urgente no número {tel} ou e-mail {email}. CPF do titular: {cpf}."
    ]
    
    s = random.choice(saudacoes[tipo])
    c = random.choice(contextos_locais)
    i = random.choice(impactos[tipo])
    e = random.choice(encerramentos)
    paragrafo_faker = fake.paragraph(nb_sentences=random.randint(1, 3))
    
    estruturas = [
        f"{s} {c}. Relato: {causa}. {i} {e} {paragrafo_faker}",
        f"{c}. {s} O problema é: {causa}. {paragrafo_faker} {i} {e}",
        f"{s} {i} Sobre a {empresa}: {causa}. {c}. {e} ({paragrafo_faker})"
    ]
    
    return random.choice(estruturas)
 
# Função geradora de dados mockados dinamicamente, via Lib Faker
def criar_dados(total_registros: int = 100, data_inicio_janela: Optional[datetime] = None, is_incremental: bool = True) -> List[Dict]:
    logging.info(f"Iniciando Geração de Dados ({total_registros} Registros) | Modo Incremental: {is_incremental}")

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
    
    #definir o diretorio do dia atual
    data_hoje = datetime.now().strftime("%Y%m%d")
    pasta_dia = os.path.join("data", data_hoje)
                
    if is_incremental:
        seq_inicial = check_sequencial(pasta_dia, data_hoje)
    else:
        seq_inicial = 1              
    # gerar o imestamp da execução com segundos
    stamp_execucao = datetime.now().strftime("%Y%m%d%H%M%S")

    for idx in range(1, total_registros + 1):
        cat_nome = random.choice(list(DADOS_CATEGORIZADOS.keys()))
        setor = DADOS_CATEGORIZADOS[cat_nome]
        emp = random.choice(setor["empresas"])
        
        # Regra 35% das reclamaações são criticas
        sorteio = random.random()

        if sorteio < 0.35:
            tipo_relato = "CRITICO"
            problema = random.choice(setor["criticos"])
            prioridade_canal = random.choice(["BAIXA", "MEDIA"]) if random.random() < 0.4 else "ALTA"
            tempo_resposta = random.choice([5, 7, 10, 14])
            nota_consumidor = random.choice([1, 2])
            status_final = random.choice(["nao resolvida", "Em analise", "PENDENTE"])
            tentativas_num = random.randint(3, 7)
        elif sorteio < 0.75:
            tipo_relato = "MODERADO"
            problema = random.choice(setor["moderados"])
            prioridade_canal = random.choice(["BAIXA", "MEDIA"])
            tempo_resposta = random.choice([1, 2, 3, 4])
            nota_consumidor = random.choice([3, 4])
            status_final = random.choice(["Resolvido", "Em Analise"])
            tentativas_num = random.randint(1, 2)
        elif sorteio < 0.90:
            tipo_relato = "DUVIDA"
            problema = "Solicitacao de informacoes e esclarecimentos sobre fatura e contrato"
            prioridade_canal = "BAIXA"
            tempo_resposta = random.choice([1, 2])
            nota_consumidor = 4
            status_final = "Resolvido"
            tentativas_num = 1
        else:
            tipo_relato = "ELOGIO"
            problema = "Elogio e agradecimento pela agilidade no atendimento prestado"
            prioridade_canal = "BAIXA"
            tempo_resposta = 1
            nota_consumidor = 5
            status_final = "Resolvido"
            tentativas_num = 1

        is_critico = (tipo_relato == "CRITICO")
            
        cpf_ruido =fake.cpf()
        tel_ruido = fake.cellphone_number()
        email_ruido = fake.free_email()
        bairro_ruido = fake.bairro()
        
        descricao_dinamica = gerar_texto_dinamico(
            tipo=tipo_relato,    # ex: "CRITICO", "MODERADO", "ELOGIO" ou "DUVIDA"
            empresa=emp['nome'],
            cidade=emp['cidade'],
            uf=emp['uf'],
            causa=problema,          # ou a variável referente ao problema/motivo sorteado
            bairro=bairro_ruido,
            cpf=cpf_ruido,
            tel=tel_ruido,
            email=email_ruido
        )
        
        replica_dinamica = (
            f"A {emp['nome']} informa que recebeu o protocolo referente a '{problema}' no bairro {bairro_ruido}. "
            f"Status do atendimento: {status_final}. {fake.sentence()}"
        )
        
        cidade_com_ruido = emp["cidade"].lower() if idx % 2 == 0 else emp["cidade"].upper()
        uf_com_ruido = emp["uf"].lower() if idx % 3 == 0 else emp["uf"]
        
        segundos_aleatorios = random.randint(0, max(0, intervalo_segundos))
        dt_postagem = inicio_sorteio + timedelta(seconds=segundos_aleatorios)
        
        agora = datetime.now()
        timestamp_preciso = agora.strftime("%Y%m%d%H%M%S") + f"{agora.microsecond:06d}"
        id_seq_atual = seq_inicial + (idx - 1)
        id_unico = f"CG-MOCK-{timestamp_preciso}-{id_seq_atual:05d}"
            
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
    volumetria_backfill = int(os.getenv("VOLUMETRIA_BACKFILL", "500"))
    volumetria_incremental = int(os.getenv("VOLUMETRIA_INCREMENTAL", "100"))

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
        data_inicio_janela=corte_dedata,
        is_incremental=inc
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