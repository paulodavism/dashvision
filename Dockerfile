# Dockerfile para dashVision
FROM python:3.13-slim

# Instala dependências do sistema (Chrome, etc)
RUN apt-get update && \
    apt-get install -y wget gnupg2 curl unzip && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . /app

# Instala dependências Python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Expõe a porta padrão do Streamlit
EXPOSE 8080

# Comando para rodar o Streamlit
CMD ["sh", "-c", "streamlit run src/main.py --server.port=${PORT:-8080} --server.address=0.0.0.0"]
