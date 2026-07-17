import os
from dotenv import load_dotenv
import requests
from google.cloud import bigquery
from google.cloud import storage

# Testando se o ambiente lê o arquivo .env
load_dotenv()

print("🎉 Tudo importado com sucesso e pronto para rodar!")