# pipeline-gcp-batch
# Ingestão Multicloud, Mensageria Orientada a Eventos e Transformação Analytics

Pipeline de engenharia de dados focado em processamento em lote (Batch), 
infraestrutura declarativa e enriquecimento de dados via LLM:

Fluxo da Infraestrutura e Build (CI/CD):

VS Code (Código) >> Terraform (IaC / Provisionamento GCP) >> 
GitHub Actions (Autenticação / CI-CD) >> Docker (Containerização do Ambiente)

Fluxo de Orquestração, Ingestão e Armazenamento (Bronze):

GitHub Actions (Cron Job) 
   >> Script Python (Contêiner) 
   >> Extração REST (Google Classroom API / REST APIs) 
   >> Chamada LLM (Google AI Studio / Gemini API) 
   >> Mensageria (GCP Pub/Sub) 
   >> Ingestão Raw (Google Cloud Storage - Camada Bronze)

Fluxo de Transformação, Higienização e Analytics (Silver & Gold):

Google Cloud Storage (Bronze) 
   >> Carga Relacional (BigQuery - Camada Silver) 
   >> Orquestração SQL (GCP Dataform / Particionamento Incremental) 
   >> Anonimização LGPD (Regras de Negócio) 
   >> Data Warehouse Otimizado (BigQuery - Camada Gold)



Para futuros projetos (com limitação de gasto) incluir na arquitetura:
Cloud Function + Pub/Sub com máquinas virtuais ligadas direto
Com a finalidade de pausar os serviços caso o projeto chegue a um limite de custo 
pre estabelecido.