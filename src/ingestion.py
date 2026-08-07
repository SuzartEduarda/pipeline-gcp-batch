import re
import os
import sys
import logging
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/classroom.courses.readonly',
    'https://www.googleapis.com/auth/classroom.coursework.students.readonly',
    'https://www.googleapis.com/auth/classroom.announcements.readonly'
]

DATA_MINIMA = datetime(2024, 1, 1)

# Variáveis padrão para controle do comportamento Incremental
INCREMENTAL = os.getenv("INCREMENTAL", "True").lower() == "true"
INCREMENTAL_DAYS = int(os.getenv("INCREMENTAL_DAYS", "3"))

# Termos da região do Vale do São Francisco
KEYWORDS_VALE = ['petrolina', 'sao francisco', 'são francisco', 'vales', 'pe', 'ba']
INSTITUICOES_LOCAIS = ['univasf', 'facape', 'uneb', 'upe', 'if sertao', 'ifsertao', 'uninassau']
# Palavras que indicam o Ceará (para eliminar Juazeiro do Norte)
TERMOS_EXCLUSAO_CEARA = ['norte', 'ceará', 'ceara', 'ufca', 'leão sampaio', 'fap']


# Calcula e retorna a data limite para corte dos dados considerando .env ou argumentos CLI
def get_incremental_cutoff_date(is_incremental=None, delta_days=None) -> datetime:
    inc = is_incremental if is_incremental is not None else INCREMENTAL
    days = delta_days if delta_days is not None else INCREMENTAL_DAYS

    if not inc:
        logging.info("[Carga em Backfill] Flag INCREMENTAL=False. Extraindo dados a partir de DATA_MINIMA")
        return DATA_MINIMA

    calculated_cutoff = datetime.now() - timedelta(days=days)
    cutoff = max(DATA_MINIMA, calculated_cutoff)
    logging.info(
        f"[MODO INCREMENTAL] Flag INCREMENTAL=True. janela de {days} dia(s) -> "
        f"Data limite de corte: {cutoff.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return cutoff

#Função auxiliar que recebe a string de data ISO da API (ex: "2024-05-20T14:10:00Z")
# e compara com a variável global DATA_MINIMA_EXTRACAO.
def is_data_valida(data_iso_str, cutoff_date=None):
    if not data_iso_str:
        return False
    if cutoff_date is None:
        cutoff_date = DATA_MINIMA

    try:
        # Converte a string ISO do Google para objeto datetime do Python
        dt_obj = datetime.fromisoformat(data_iso_str.replace('Z', '+00:00')).replace(tzinfo=None)
        # Compara se a data do registro é MAIOR ou IGUAL à data mínima global
        return dt_obj >= cutoff_date
    except Exception as e:
        logging.warning(f"ERRO ao converter data ISO'{data_iso_str}': {e}")
        return False


# Valida se a turma pertence a uma instituição de ensino da região 
# de Petrolina/Juazeiro (Vale do São Francisco), eliminando Juazeiro do Norte (CE).
def is_target_course(course):
    if not is_data_valida(course.get('creationTime')):
        return False
    
    # Concatena nome, seção e descrição em um único texto para busca (em minúsculas)
    raw_text = f"{course.get('name', '')} {course.get('section', '')} {course.get('descriptionHeading', '')}"
    text_lower = raw_text.lower()

    # TRAVA DE EXCLUSÃO: Se mencionar o Ceará ou Juazeiro do Norte, descarta imediatamente
    if any(excl in text_lower for excl in TERMOS_EXCLUSAO_CEARA):
        return False

    # Checa a sigla 'CE' isolada no texto original usando expressão regular (\b indica borda de palavra)
    if re.search(r'\bCE\b', raw_text):
        return False

    #VALIDAÇÃO POR SIGLA INSTITUCIONAL
    if any(inst in text_lower for inst in INSTITUICOES_LOCAIS):
        return True

    # Valida se possui pelo menos uma palavra da região E uma palavra ligada a faculdades
    tem_petrolina = 'petrolina' in text_lower
    tem_juazeiro_ba = 'juazeiro' in text_lower and any(v in text_lower for v in KEYWORDS_VALE)
    tem_palavras_faculdade = any(f in text_lower for f in ['faculdade', 'universidade', 'campus', 'curso'])

    # Retorna True se atingir os critérios
    return (tem_petrolina or tem_juazeiro_ba) and tem_palavras_faculdade

#função responsável por autenticar e gerar o token de acesso
def authenticate_classroom():
    creds = None
    token_path = 'src/token.json' if os.path.exists('src/token.json') else 'token.json'
    credentials_path = 'src/credentials.json' if os.path.exists('src/credentials.json') else 'credentials.json'
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                logging.error(f"ERRO CRITICO: Arquivo de credenciais'{credentials_path}' não encontrado")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return build('classroom', "v1", credentials=creds)

def list_courses(service):
    courses = []
    page_token = None
    while True:
        response = service.courses().list(
            pageSize=100,
            pageToken=page_token,
            courseStates=['ACTIVE']
        ).execute()
        raw_courses = response.get('courses', [])

        # Filtra apenas as turmas relevantes antes de adicionar à lista final
        for course in raw_courses:
            if is_target_course(course):
                courses.append(course)
            else:
                logging.info(f"turma invalida pelo filtro: {course.get('name')}")
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    return courses

def list_course_work(service, course_id):
    posts = []
    page_token = None
    while True:
        response = service.courses().courseWork().list(
            courseId=course_id,
            pageSize=100,
            pageToken=page_token
        ).execute()
        posts.extend(response.get('courseWork', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    return posts

# Esta é a função responsável por fazer a chamada à API do Google Classroom 
# para buscar os comentários das tarefas, aplicando a resposta parcial (fields) e a 
# paginação com pageSize e pageToken.

def extract_course_comments(service, course_id, post_id, cutoff_date=None):
    comments = []
    page_token = None
    fields_query = 'nextPageToken,comments(id,content,creationTime,author(emailAddress,name/fullName))'
    while True:
        response = service.courses().courseWork().comments().list(
            courseId=course_id,
            courseWorkId=post_id,
            pageSize=100,
            pageToken=page_token,
            fields=fields_query
        ).execute()
        raw_comments = response.get('comments', [])
        for comment in raw_comments:
            if is_data_valida(comment.get('creationTime'), cutoff_date):
                comment['courseId'] = course_id
                comment['courseWorkId'] = post_id
                comments.append(comment)
        
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    logging.info(f"Total de {len(comments)} comentarios extraidos com sucesso da tarefa {post_id}.")    
    return comments

#Extrai todos os dados do Google Classroom e os retorna para o orquestrador main.py
def extract_classroom_data(is_incremental=None, delta_days=None):
    cutoff_date = get_incremental_cutoff_date(is_incremental, delta_days)

    service = authenticate_classroom()
    logging.info("Servico do google classroom, autenticado com Sucesso.")

    courses = list_courses(service)
    if not courses:
        logging.warning("Nenhuma turma ativa encontrada pelos filtros")
        return [], False

    all_extract_comments = []
    has_errors = False

    for course in courses:
        course_id = course.get('id')
        course_name = course.get('name')
        logging.info(f"Processando turma: {course_name} (ID: {course_id})")
        
        try:
            coursework_list = list_course_work(service, course_id)
            for work in coursework_list:
                work_id = work.get('id')
                comments = extract_course_comments(service, course_id, work_id, cutoff_date)
                all_extract_comments.extend(comments)
        except Exception as e:
            logging.error(f"ERRO ao processar a turma {course_name} (ID: {course_id}): {str(e)}")
            has_errors = True
            continue
    return all_extract_comments, has_errors

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Executando modulo de extração  em modo de TESTE LOCAL")
    data, error = extract_classroom_data()
    logging.info(f"Teste concluido. {len(data)} comentarios extraidos. Houve error: {error}")


