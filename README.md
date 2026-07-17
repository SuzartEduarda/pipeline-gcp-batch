# pipeline-gcp-batch-ingestao

Pipeline de engenharia de dados focado em micro-batching e automação serverless:

Fluxo da Infraestrutura e Build (CI/CD):

VS Code (Código) >> GitHub Actions (Workflows) >> Docker (Build) >> Artifact Registry (GCP)

Fluxo de Orquestração e Processamento dos Dados:

Cloud Scheduler / GitHub Workflows >> Gatilho >> Cloud Run Jobs (GCP) >> Ingestão via API do GitHub >> BigQuery (Data Warehouse)