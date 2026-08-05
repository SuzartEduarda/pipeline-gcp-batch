import os
import logging
from dotenv import load_dotenv
from src.ingestion import authenticate_classroom,list_courses,list_course_work,extract_course_comments
from storage.storage import save_raw_to_bronze



load_dotenv()
logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

# função principal do pipeline, 
# serve para orquestrar a execução das funções de autenticação, 
# extração e armazenamento dos comentários do Google Classroom.

def run_pipeline():
    logging.info("Execução do pipeline em andamento")
    bucket_name = os.getenv("GCP_BRONZE_BUCKET")

    if not bucket_name:
        logging.error("variavel de Bucket ausente")
        return

    service = authenticate_classroom()
    
    # Busca todas as turmas ativas na API
    courses = list_courses(service)
    logging.info(f"Encontradas {len(courses)} turmas para processar")

    # Varre cada turma
    for course in courses:
        course_id = course['id']
        course_name = course.get('name', 'Sem Nome')
        logging.info(f"Processando turma: {course_name} (ID: {course_id})")

        # Busca todas as tarefas daquela turma
        posts = list_course_work(service, course_id)

        # Varre cada tarefa da turma
        for post in posts:
            post_id = post['id']
            # Extrai os comentários da tarefa atual
            comments = extract_course_comments(service, course_id, post_id)

            # Particionamento na Camada Bronze por curso e post
            if comments:
                destination_blob = f"raw/classroom/course_id={course_id}/post_id={post_id}.json"
                save_raw_to_bronze(comments, bucket_name, destination_blob)
            
    logging.info("Pipeline Concluido com sucesso")

if __name__ == '__main__':
    run_pipeline()