# pipeline-gcp-batch
# Ingestão Multicloud, Mensageria Orientada a Eventos e Transformação Analytics
# Principal prioridade: criar uma arquitetura com o mínimo de gasto ou gasto Zero.

Pipeline de engenharia de dados focado em processamento em lote (Batch), infraestrutura declarativa e enriquecimento de dados via LLM Gemini para análise de satisfação do consumidor no Vale do São Francisco.

## 1. Fluxo de Arquitetura End-to-End

### Fluxo da Infraestrutura e Build (CI/CD)
VS Code (Código) >> Terraform (IaC / Provisionamento GCP) >> GitHub Actions (Autenticação / CI-CD) >> Docker (Containerização do Ambiente)

### Fluxo de Orquestração, Ingestão e Armazenamento (Bronze)
GitHub Actions (Cron Job)
   >> Script Python (Contêiner - src/create_data.py)
   >> Geração Sintética de Dados (Faker pt_BR - VSF)
   >> Chamada LLM (Google AI Studio / Gemini API)
   >> Mensageria (GCP Pub/Sub)
   >> Ingestão Raw Parquet Paginada (Google Cloud Storage - Camada Bronze)

### Fluxo de Transformação, Higienização e Analytics (Silver & Gold)
Google Cloud Storage (Bronze Parquet)
   >> Carga Relacional (BigQuery - Camada Silver)
   >> Orquestração SQL (GCP Dataform / Particionamento Incremental)
   >> Anonimização e Mascaramento LGPD (Regras de Negócio / Regex)
   >> Data Warehouse Otimizado (BigQuery - Camada Gold)

## 2. Visão Geral e Pivô Estratégico

O projeto atua no monitoramento analítico de reclamações de serviços essenciais e varejo regional no Vale do São Francisco (COMPESA, Neoenergia, BRK Ambiental, provedores de internet e redes de varejo)

Para garantir resiliência técnica, alta disponibilidade (SLA) e eliminar gargalos de rede (WAF, instabilidades de DNS e bloqueios de IP), o módulo de ingestão foi evoluído para um *Engine de Geração de Dados Sintéticos Estruturados* (src/create_data.py) utilizando a biblioteca Faker (pt_BR)

Essa abordagem garante:
* *Execução Autônoma e Resiliente:* Zero dependência de serviços externos ou raspagem vulnerável a quedas de conexão
* *Massa de Teste para LGPD:* Injeção proposital de CPFs, e-mails e telefones fictícios nos relatos para validação dos filtros de anonimização na Camada Silver
* *Contexto Semântico Rico para a LLM:* Narrativas estruturadas em português regional para classificação de sentimento, identificação da causa-raiz e resumos executivos via *Gemini 2.5 Flash*

## 3 Governança de Custos (Kill Switch)

Para evitar custos inesperados em projetos com limite de faturamento, a arquitetura utiliza um mecanismo automático de *Kill Switch* (Desligamento de Emergência)

Em vez de depender de alertas manuais por e-mail, o Google Cloud Billing monitora os custos em tempo real. Assim que o valor pré-estabelecido é atingido (ex: R$ 50,00), um evento assíncrono é disparado para desativar a conta de faturamento (Billing Account) ou pausar os recursos ativos, paralisando imediatamente qualquer nova cobrança.

text
Google Cloud Billing
   >> Budget Alert (Atinge o limite de custo definido)
   >> Cloud Pub/Sub (Dispara mensagem no tópico de notificação)
   >> Cloud Function (Executa o script que desvincula o Billing / desliga os serviços)
   >> Desligar Recursos (Parada imediata de processamento no BigQuery / Custo zerado)

## 4. Estrutura de Diretórios do Repositório

text
PIPELINE-GCP-BATCH-INGESTAO/
│
├── .github/workflows/
│   └── github-pipelines.yml   <-- Centraliza o Cron Job e a execução do contêiner
│
├── src/                       <-- Módulos de desenvolvimento Python
│   ├── __init__.py            <-- Inicializador do pacote Python
│   └── create_data.py         <-- Gerador sintético de reclamações com Faker VSF
│
├── storage/
│   └── storage.py             <-- Gravação paginada em Parquet (data/YYYYMMDD/...)
│
├── terraform/                 <-- Infraestrutura como Código (IaC)
│   ├── main.tf                <-- Declaração de Buckets, Pub/Sub e BigQuery
│   ├── providers.tf            <-- Provedor Google Cloud
│   └── variables.tf           <-- Variáveis globais
│
├── Dockerfile                 <-- Ambiente contêinerizado
├── main.py                    <-- Orquestrador principal da execução
├── README.md                  <-- Documentação arquitetural
└── requirements.txt           <-- Dependências (pandas, pyarrow, faker, etc.)
