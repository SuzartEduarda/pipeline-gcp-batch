import os.path
import logging
import re
from datetime import datetime
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

# Termos da região do Vale do São Francisco
KEYWORDS_VALE = ['petrolina', 'sao francisco', 'são francisco', 'vales', 'pe', 'ba']
INSTITUICOES_LOCAIS = ['univasf', 'facape', 'uneb', 'upe', 'if sertao', 'ifsertao', 'uninassau']
# Palavras que indicam o Ceará (para eliminar Juazeiro do Norte)
TERMOS_EXCLUSAO_CEARA = ['norte', 'ceará', 'ceara', 'ufca', 'leão sampaio', 'fap']



#Função auxiliar que recebe a string de data ISO da API (ex: "2024-05-20T14:10:00Z")
# e compara com a variável global DATA_MINIMA_EXTRACAO.
def is_data_valida(data_iso_str):
    if not data_iso_str:
        return False
    # Converte a string ISO do Google para objeto datetime do Python
    dt_obj = datetime.fromisoformat(data_iso_str.replace('Z', '+00:00')).replace(tzinfo=None)
    # Compara se a data do registro é MAIOR ou IGUAL à data mínima global
    return dt_obj >= DATA_MINIMA


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
    if os.path.exists('src/token.json'):
        creds = Credentials.from_authorized_user_file('src/token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'src/credentials.json', SCOPES
                )
            creds = flow.run_local_server(port=0)
        with open('src/token.json', 'w') as token:
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

def extract_course_comments(service, course_id, post_id):
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
        comments.extend(response.get('comments', []))
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    logging.info(f"Total de {len(comments)} comentarios extraidos com sucesso da tarefa {post_id}.")    
    return comments

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    service = authenticate_classroom()
    logging.info("Servico do google classroom authenticado com sucesso")


