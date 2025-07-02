# Documentação de Arquitetura e DevOps — dashVision

## 1. Ambiente Local (Windows + VS Code)
- Desenvolvimento do app Streamlit com scraping Selenium e integração PostgreSQL.
- Uso de variáveis de ambiente em `.env` (não versionado).
- Testes locais do container Docker para garantir portabilidade.

## 2. Versionamento e GitHub
- Código-fonte versionado no GitHub.
- Arquivos sensíveis e grandes (ex: `.env`, `.csv`) adicionados ao `.gitignore`.
- Remoção de arquivos sensíveis já versionados do repositório.

## 3. Docker
- Criação de `Dockerfile` para rodar Streamlit, Selenium e Chrome headless.
- Uso de `webdriver-manager` para gerenciar o ChromeDriver.
- Criação de `.dockerignore` para evitar envio de arquivos desnecessários ao build.
- Testes locais do container com variáveis de ambiente via `--env-file`.

## 4. Google Cloud Run
- Build e push da imagem Docker para o Google Container Registry .
- Deploy do container no Cloud Run, configurando variáveis de ambiente via painel.
- Ajuste da porta para 8080 (padrão Cloud Run) e uso da variável `PORT`.
- Monitoramento de logs e troubleshooting de erros (porta, memória, variáveis).

- OBS PD: Basta atualizar os fontes no repositório do GitHub, subindo o arquivo dockerfile. O GCP está integrado com o repo do Github e o sincronismo é automático (CI/CD).
"No seu contexto, CI/CD significa que ao atualizar o código no GitHub, o Google Cloud automaticamente faz o build da imagem Docker e faz o deploy no Cloud Run, sem necessidade de ações manuais."

## 5. Integração e Atualização
- Fluxo de atualização: ambiente local → GitHub → build Docker → push → deploy Cloud Run.
- Deploy automático via GitHub Actions (opcional).
- Logs e troubleshooting pelo painel do Cloud Run.

---

## Comandos Essenciais Utilizados

### Git e GitHub
```sh
# Inicializar repositório e conectar ao GitHub
git init
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git

# Adicionar arquivos e commit
git add .
git commit -m "Mensagem do commit"

# Subir alterações
git push origin main

# Adicionar arquivos ao .gitignore
echo ".env" >> .gitignore
echo "*.csv" >> .gitignore

# Remover arquivo já versionado do Git
git rm --cached .env
git rm --cached meli_sales_data.csv
git commit -m "Remove arquivos sensíveis do versionamento"
git push origin main
```

### Docker (Windows PowerShell)
```sh
# Build da imagem Docker
docker build -t dashvision:latest .

# Rodar container localmente com variáveis de ambiente
docker run --env-file .env -p 8501:8080 dashvision:latest

# Login no Docker Hub
docker login

# Push da imagem para o Docker Hub
docker push seu-usuario/seu-app:latest
```

### Google Cloud (gcloud CLI)
```sh
# Autenticar na Google Cloud
gcloud auth login

# Configurar projeto
gcloud config set project SEU_PROJECT_ID

# Build e push da imagem para o Google Container Registry
gcloud builds submit --tag gcr.io/SEU_PROJECT_ID/seu-app:latest

# Deploy no Cloud Run
gcloud run deploy seu-app \
  --image gcr.io/SEU_PROJECT_ID/seu-app:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --set-env-vars VAR1=valor1,VAR2=valor2

# (Opcional) Atualizar variáveis de ambiente em massa via painel Cloud Run
```

### Outros
- Monitoramento de logs: pelo painel do Cloud Run.
- Ajuste de memória: via painel ou flag `--memory` no deploy.

### Troubleshooting Docker: Porta já em uso
```sh
# Listar containers ativos
docker ps

# Encontrar containers que usam uma porta específica (exemplo: 8080)
docker ps --filter "publish=8080"

# Parar um container pelo ID
docker stop <container_id>

# Remover um container parado pelo ID
docker rm <container_id>
```

---

Se precisar de detalhes de algum comando ou etapa, consulte este arquivo ou solicite complementação.
