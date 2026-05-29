# Inventário CI/CD — SkyTrax Analytics

## Workflows GitHub Actions

| Arquivo | Nome | Status |
|---------|------|--------|
| `.github/workflows/ci.yml` | CI | Único workflow ativo (reescrito) |

Não existem outros workflows em `.github/workflows/` além de `ci.yml`.

## Gatilhos

| Evento | Branches / condição |
|--------|---------------------|
| `push` | `main`, `master` |
| `pull_request` | Todas as branches |
| `workflow_dispatch` | Manual |

## Jobs (após hardening)

```text
┌─────────┐
│  lint   │  ruff check, ruff format, import smoke, scrapy list
└────┬────┘
     ├──────────────┬──────────────┐
     ▼              ▼              ▼
┌─────────┐  ┌───────────┐  ┌─────────┐
│  test   │  │ security  │  │ docker  │
│ alembic │  │ pip-audit │  │ build   │
│ pytest  │  │ (soft)    │  │ compose │
└─────────┘  └───────────┘  └─────────┘

┌───────────┐
│ frontend  │  npm ci + build (paralelo)
└───────────┘
```

### Job `lint` (bloqueante)

| Step | Comando | Objetivo |
|------|---------|----------|
| Setup Python | 3.11 + cache pip | Ambiente |
| Install | `requirements-dev.txt` | Deps app + tooling |
| Ruff check | `ruff check .` | Lint estático |
| Ruff format | `ruff format --check .` | Estilo consistente |
| Import smoke | `from api.main import app` | Valida imports |
| Scrapy smoke | `scrapy list \| grep airlinequality` | Spiders registrados |

### Job `test` (bloqueante, `needs: lint`)

| Serviço | Imagem |
|---------|--------|
| PostgreSQL | `pgvector/pgvector:pg16` |
| Redis | `redis:7-alpine` |

| Step | Comando |
|------|---------|
| Migrations | `alembic upgrade head` + `alembic check` |
| Pytest | `pytest --cov` (ignora `test_metadata_extractor` — requer extensão dedicada) |

**Variáveis de ambiente CI:**

- `DATABASE_URL=postgresql+psycopg://skytrax:skytrax@localhost:5432/skytrax`
- `NLP_ENABLE_EMBEDDINGS=false`
- `SCHEMA_VALIDATE_ON_STARTUP=false`

### Job `security` (não bloqueante)

- `pip-audit -r requirements.txt`
- `continue-on-error: true`

### Job `frontend` (bloqueante)

- `npm ci` + `npm run build` em `frontend/`

### Job `docker` (bloqueante, `needs: lint`)

- `docker compose config`
- Build `app`, `worker` (sem Playwright)
- Build `frontend` produção

## Workflow anterior (causa das falhas)

O workflow legado tinha **2 jobs** (`test`, `docker`) em um único job `test`:

1. `ruff check .` — **falhava** com dezenas de erros (F401, E402, F841)
2. `alembic upgrade head` — raramente alcançado
3. `pytest --cov` — **falhava** por `fail_under = 70%` no `pyproject.toml`
4. Sem `ruff format --check` (mas formato inconsistente)
5. Sem job frontend isolado
6. Sem import smoke dedicado
7. `python app.py` **não existe** — entrypoint é `main.py` / `uvicorn main:app`

## Artefatos relacionados

| Arquivo | Função |
|---------|--------|
| `requirements.txt` | Runtime Python |
| `requirements-dev.txt` | CI: pytest, ruff, pip-audit |
| `pyproject.toml` | Ruff, pytest paths, coverage |
| `pytest.ini` | `pythonpath = .` |
| `alembic.ini` | Migrations |
| `Makefile` | `make test` via Docker (serviço `api` — nome desatualizado vs `app`) |

## Concorrência

`concurrency: ci-${{ github.workflow }}-${{ github.ref }}` com `cancel-in-progress: true` evita filas de CI #18–#42 empilhadas no mesmo branch.
