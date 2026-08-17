# 1. Usa uma imagem oficial do Python focada em desempenho
FROM python:3.11-slim

# 2. Define a pasta de trabalho dentro do contêiner
WORKDIR /app

# 3. Copia o arquivo de dependências primeiro (otimiza o cache do Docker)
COPY requirements.txt .

# 4. Instala as dependências de forma limpa
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o restante do código do seu projeto para o contêiner
COPY . .

# 6. Comando para rodar seu script principal de streaming
CMD ["python", "main.py"]