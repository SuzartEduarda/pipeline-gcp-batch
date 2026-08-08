# pipeline-gcp-batch
# Ingestão Multicloud, Mensageria Orientada a Eventos e Transformação Analytics
# Principal prioridade: criar uma arquitetura com o mínimo de gasto ou gasto Zero.

Pipeline de engenharia de dados focado em processamento em lote (Batch), 
infraestrutura declarativa e enriquecimento de dados via LLM:

Fluxo da Infraestrutura e Build (CI/CD):

VS Code (Código) >> Terraform (IaC / Provisionamento GCP) >> 
GitHub Actions (Autenticação / CI-CD) >> Docker (Containerização do Ambiente)

Fluxo de Orquestração, Ingestão e Armazenamento (Bronze):

GitHub Actions (Cron Job) 
   >> Script Python (Contêiner) 
   >> Extração de Dados (Web Scraping Reclame Aqui / Dados Abertos Consumidor.gov) 
   >> Chamada LLM (Google AI Studio / Gemini API) 
   >> Mensageria (GCP Pub/Sub) 
   >> Ingestão Raw (Google Cloud Storage - Camada Bronze)

Fluxo de Transformação, Higienização e Analytics (Silver & Gold):

Google Cloud Storage (Bronze) 
   >> Carga Relacional (BigQuery - Camada Silver) 
   >> Orquestração SQL (GCP Dataform / Particionamento Incremental) 
   >> Anonimização LGPD (Regras de Negócio) 
   >> Data Warehouse Otimizado (BigQuery - Camada Gold)

---------------------------------------------------------
FinOps e Governança de Custos (Kill Switch)

Para evitar custos inesperados em projetos com limite de faturamento (budget cap), a arquitetura utiliza um mecanismo automático de "Kill Switch" (Botão de Emergência).
Em vez de depender de alertas manuais por e-mail, o Google Cloud Billing monitora os custos em tempo real. Assim que o valor pré-estabelecido é atingido (ex: R$ 5,00), um evento assíncrono é disparado para desativar a conta de faturamento (Billing Account) ou pausar os recursos ativos, paralisando imediatamente qualquer nova cobrança.

Google Cloud Billing
   >> Budget Alert (Atinge o limite de custo definido)
   >> Cloud Pub/Sub (Dispara mensagem no tópico de notificação)
   >> Cloud Function (Executa o script que desvincula o Billing / desliga os serviços)
   >> Desligar Recursos (Parada imediata de processamento no BigQuery / Custo zerado)
