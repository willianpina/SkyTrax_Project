# Deployment — SkyTrax Analytics

## Pré-requisitos

- Docker 24+ e Docker Compose v2
- 8 GB RAM recomendados (NLP com embeddings exige mais)
- Portas: 8000 (API), 5173 (dev UI), 5432, 6379, 9090, 3000

## Desenvolvimento (recomendado)

```bash
cp .env.example .env
docker compose up --build
```

Em outro terminal:

```bash
docker compose exec app alembic upgrade head
docker compose exec app python scripts/seed_airlines.py
docker compose exec app scrapy crawl airlinequality_reviews -a max_pages=3
```

Frontend em modo dev (se não usar o serviço compose do Vite):

```bash
cd frontend && npm install && npm run dev
```

## Produção

```bash
cp .env.example .env
# Editar segredos (POSTGRES_PASSWORD, DATABASE_URL, etc.)

docker compose -f docker-compose.prod.yml up --build -d
```

Características do compose de produção:

- Gunicorn/Uvicorn workers para API
- Build estático do frontend servido via Nginx
- Redis AOF habilitado
- Healthchecks em todos os serviços
- Playwright opcional no build (`INSTALL_PLAYWRIGHT=false` para builds rápidos)

## Variáveis críticas

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | Connection string PostgreSQL |
| `REDIS_URL` | Redis para RQ e cache |
| `NLP_ENABLE_EMBEDDINGS` | `true` para sentence-transformers |
| `SCHEDULER_ENABLED` | Jobs agendados no worker |
| `SCHEMA_VALIDATE_ON_STARTUP` | Validação de schema no boot da API |
| `CORS_ORIGINS` | Origens permitidas para o SPA |

Lista completa: `app/config.py`.

## Migrations

```bash
docker compose exec app alembic upgrade head
docker compose exec app alembic current
```

## Health checks

| Endpoint | Uso |
|----------|-----|
| `GET /health` | Liveness geral |
| `GET /api/operations/health/schema` | Schema vs models |
| `GET /api/operations/health/pipeline` | Estado do pipeline |
| `GET /api/operations/health/integrity` | Reconciliação de dados |

## Monitoramento

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (dashboard SkyTrax Enterprise)
- API metrics: `http://localhost:8000/metrics`

## Mac Apple Silicon

- Stack NLP CPU-only por padrão
- `NLP_ENABLE_EMBEDDINGS=false` acelera boot do worker
- Ver `docs/development.md` para detalhes de Torch CPU wheels

## Troubleshooting

| Sintoma | Ação |
|---------|------|
| API não sobe | Verificar logs `docker compose logs app` e migrations |
| Frontend 404 em rotas | Configurar fallback SPA no Nginx (`try_files`) |
| Worker idle | Verificar `REDIS_URL` e filas RQ |
| Playwright timeout | Rebuild com `INSTALL_PLAYWRIGHT=true` ou desabilitar playwright no crawl |

Ver também: [docs/production.md](../production.md), [docs/observability.md](../observability.md).
