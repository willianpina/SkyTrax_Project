# Auditoria Docker — SkyTrax Analytics

## Arquivos

| Arquivo | Propósito |
|---------|-----------|
| `Dockerfile` | Imagem Python 3.11-slim backend |
| `frontend/Dockerfile` | Build Nginx SPA |
| `docker-compose.yml` | Desenvolvimento (bind mounts, Vite) |
| `docker-compose.prod.yml` | Produção (Gunicorn, secrets) |
| `scripts/docker_entrypoint.sh` | Entrypoint dev app/worker |

## Dockerfile (backend)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
ARG INSTALL_PLAYWRIGHT=true
RUN playwright install ...  # condicional
COPY . .
USER skytrax
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Validações

| Item | Status | Notas |
|------|--------|-------|
| `COPY requirements.txt` | ✅ | Antes do código — cache layer |
| `COPY . .` | ✅ | Contexto raiz do repo |
| Entrypoint `main:app` | ✅ | Alinhado com `main.py` |
| Playwright opcional | ✅ | CI usa `INSTALL_PLAYWRIGHT=false` |
| Non-root user | ✅ | `skytrax` uid 1000 |

### Riscos

| Risco | Severidade |
|-------|------------|
| Build longo (torch) | MÉDIO — esperado |
| `build-essential` em slim | OK para compilar wheels |

## docker-compose.yml (dev)

| Serviço | Comando | Health |
|---------|---------|--------|
| app | `scripts/docker_entrypoint.sh` + uvicorn | `/health` |
| worker | entrypoint + `worker.runner` | Redis ping |
| scheduler | `worker.scheduler` | — |
| postgres | pgvector:pg16 | pg_isready |
| redis | 7-alpine | — |
| frontend | Vite dev | — |

**Nota:** Makefile referencia serviço `api` mas compose define `app` — inconsistência documentada.

## docker-compose.prod.yml

| Item | Status |
|------|--------|
| Gunicorn + UvicornWorker | ✅ |
| `DATABASE_URL_FILE` secret | ✅ |
| Health `/api/health` | ✅ (path API) |
| Frontend Nginx build | ✅ |

CI executa:

```bash
docker compose config
docker compose -f docker-compose.prod.yml config
docker compose build --build-arg INSTALL_PLAYWRIGHT=false app worker
docker compose -f docker-compose.prod.yml build frontend
```

## Simulação local

```bash
docker compose config          # valida YAML
docker compose build app       # requer Docker daemon
```

Falhas comuns:

| Erro | Causa |
|------|-------|
| Build timeout | torch download |
| Playwright deps | usar `INSTALL_PLAYWRIGHT=false` |
| Missing .env | CI copia `.env.example` |

## .dockerignore

Verificar se `exports/`, `.venv`, `frontend/node_modules` estão excluídos (recomendado — não auditado linha a linha nesta passagem).

## Alinhamento com CI

Job `docker` separado do `test` evita que falha de build de imagem mascare falha de pytest, e vice-versa.
