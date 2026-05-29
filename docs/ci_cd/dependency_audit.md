# Auditoria de Dependências — SkyTrax Analytics

## Arquivos de dependências

| Arquivo | Uso |
|---------|-----|
| `requirements.txt` | Runtime produção e CI |
| `requirements-dev.txt` | Tooling CI (`pytest`, `ruff`, `pip-audit`) |
| `frontend/package.json` | SPA React |

## requirements.txt (runtime)

| Pacote | Versão pin | Uso |
|--------|------------|-----|
| fastapi | 0.109.0 | API REST |
| uvicorn[standard] | 0.25.0 | ASGI server |
| SQLAlchemy | 2.0.25 | ORM |
| alembic | 1.13.1 | Migrations |
| psycopg[binary] | 3.1.17 | PostgreSQL driver (**binary** necessário no CI) |
| pgvector | 0.2.4 | Embeddings / busca semântica |
| Scrapy | 2.11.0 | Crawlers |
| scrapy-playwright | 0.0.34 | Páginas dinâmicas |
| redis, rq, APScheduler | — | Filas e scheduler |
| spacy, scikit-learn | — | NLP |
| torch, sentence-transformers | CPU index | Embeddings opcionais |
| pandas, numpy | — | Analytics |
| httpx | 0.27.0 | Cliente HTTP / TestClient |
| gunicorn | 21.2.0 | Produção |

### Transitivas importantes (não pinadas explicitamente)

| Pacote | Origem | Notas |
|--------|--------|-------|
| pydantic | fastapi | OK |
| starlette | fastapi | OK |
| pytest | **não** em requirements.txt | Instalado via `requirements-dev.txt` no CI ✅ |

## requirements-dev.txt (CI)

```
pytest, pytest-cov, httpx, ruff, pip-audit
+ -r requirements.txt
```

## Imports vs dependências

### Presentes e corretos

- `fastapi`, `sqlalchemy`, `alembic`, `scrapy`, `redis`, `rq` — usados extensivamente.

### Pesadas mas intencionais

| Pacote | Motivo | CI mitigation |
|--------|--------|---------------|
| torch | sentence-transformers | `NLP_ENABLE_EMBEDDINGS=false` |
| sentence-transformers | Semântica | desligado no CI |
| scrapy-playwright | Crawl dinâmico | `INSTALL_PLAYWRIGHT=false` no Docker CI |

### Possivelmente subutilizadas (BAIXO)

| Pacote | Observação |
|--------|------------|
| trafilatura | Extração de texto — uso pontual em scraper |
| APScheduler | Scheduler worker — válido se worker ativo |

### Não listadas (OK via transitivas)

- `pydantic`, `click`, `twisted` (Scrapy), `greenlet` (SQLAlchemy)

## Frontend (package.json)

Principais: `react`, `react-router-dom`, `echarts`, `maplibre-gl`, `deck.gl`, `i18next`, `vite`.

CI valida com `npm ci && npm run build`.

## Riscos de versão

| Risco | Severidade | Mitigação |
|-------|------------|-----------|
| torch CPU index URL | MÉDIO | Pin mantido; cache pip no Actions |
| fastapi 0.109 + pydantic v2 | BAIXO | Stack estável |
| psycopg sem binary local | ALTO dev | CI usa `psycopg[binary]` ✅ |

## pip-audit

Job `security` executa `pip-audit -r requirements.txt` com `continue-on-error: true` até triagem de CVEs.

## Recomendações

1. Manter `requirements-dev.txt` separado do runtime.
2. Adicionar pre-commit: `ruff check` + `ruff format --check`.
3. Reintroduzir `fail_under` gradualmente (50 → 60 → 70) quando cobertura estabilizar.
4. Considerar `requirements-ci.txt` minimal sem torch para job lint-only (otimização futura).
