# 1. Usa uma imagem oficial do Python focada em desempenho
FROM python:3.11-slim

# Cria usuário sem privilégios (non-root)
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

# 2. Define a pasta de trabalho dentro do contêiner
WORKDIR /app

# 3. Copia o arquivo de dependências primeiro (otimiza o cache do Docker)
COPY requirements.txt .

# 4. Instala as dependências de forma limpa
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o restante do código do seu projeto para o contêiner
COPY . .

# Garante a posse dos arquivos pelo usuário sem privilégios
RUN chown -R appuser:appuser /app

# 6. Alterna para o usuário seguro non-root
USER appuser

# 7. Comando para rodar seu script principal
CMD ["python", "main.py"]