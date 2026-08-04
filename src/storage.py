import json
import logging
from google.cloud import storage

# Declara a função que salvará o payload no Bucket Bronze. Ela recebe três argumentos: 
# data (os dados extraídos), bucket_name (o nome do bucket no GCP) e destination_blob_name 
# (o caminho/nome do arquivo de destino na nuvem).
def save_raw_to_bronze(data, bucket_name, destination_blob_name):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    json_data = json.dumps(data, ensure_ascii=False, indent=2)
    blob.upload_from_string(json_data, content_type='application/json')
    logging.info(f"Dados brutos salvos com sucesso no Bronze: gs://{bucket_name}/{destination_blob_name}")
