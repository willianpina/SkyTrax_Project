# Inventário do Projeto — SkyTrax Analytics

> Auditoria gerada para publicação no GitHub. Última revisão: maio/2026.

## Resumo executivo

O **SkyTrax Analytics** é uma plataforma de inteligência analítica para avaliação de companhias aéreas. A stack atual **não utiliza Flask, Jinja2, Bootstrap nem Chart.js** — o backend é **FastAPI** e o frontend é **React 18 + Vite + ECharts**.

| Camada | Tecnologia principal |
|--------|---------------------|
| API | FastAPI, Pydantic, SQLAlchemy |
| Banco | PostgreSQL (+ pgvector, PostGIS opcional) |
| Filas | Redis, RQ |
| Coleta | Scrapy (+ scrapy-playwright opcional) |
| NLP | spaCy, scikit-learn, sentence-transformers (opcional) |
| Frontend | React 18, Vite, i18next, ECharts, MapLibre |
| Infra | Docker Compose, Prometheus, Grafana |

---

## Árvore de diretórios (nível 1–2)

```text
SkyTrax_Project/
├── api/                 # Aplicação REST FastAPI
├── app/                 # Config, middleware, observabilidade, governança de startup
├── analytics/           # Motores analíticos (reputação, forecast, anomalias, semântica…)
├── aviation/            # Domínio aeronáutico (master data, cobertura, validação)
├── database/            # Modelos ORM, migrations Alembic, schema health
├── nlp/                 # Pipeline NLP (sentimento, tópicos, entidades)
├── scraper/             # Spiders Scrapy e pipelines de persistência
├── pipelines/           # Pipelines Scrapy legados (testes de fingerprint)
├── worker/              # Jobs RQ, scheduler, orquestração operacional
├── frontend/            # Dashboard React (workspaces modulares)
├── tests/               # Pytest (unit, integration, api)
├── scripts/             # Bootstrap, seed, repair, smoke tests
├── docs/                # Documentação técnica e de arquitetura
├── ops/                 # Prometheus, Grafana, alertas
├── exports/             # Artefatos locais de crawl (gitignored)
└── secrets/             # Segredos locais (gitignored)
```

---

## Backend — API (`api/`)

| Arquivo / pasta | Função | Dependências principais |
|-----------------|--------|-------------------------|
| `main.py` | App FastAPI, lifespan, middleware, CORS | `api.routes`, `app.*`, `database.session` |
| `routes.py` | Agregador de routers sob `/api` | Routers em `api/routers/` |
| `router_registry.py` | Validação de rotas de health operacional | FastAPI route introspection |
| `schemas.py` | Contratos Pydantic da API | — |
| `startup_health.py` | Boot checks de import graph e pipeline | Worker orchestration |
| `pipeline_health_service.py` | Serialização de saúde do pipeline | Redis, analytics |
| `operations_dispatch.py` | Dispatch de operações assíncronas | RQ, worker |

### Routers (`api/routers/`)

| Router | Prefixo / escopo | Responsabilidade |
|--------|------------------|------------------|
| `reviews.py` | `/api` | Reviews, airlines, topics |
| `analytics_router.py` | `/api` | Analytics executivo, rankings, sentiment |
| `intelligence.py` | `/api` | Reputação, benchmarking, insights, snapshots |
| `forecasting.py` | `/api` | Previsões e refresh |
| `anomalies.py` | `/api` | Detecção de anomalias e alertas |
| `search.py` | `/api` | Busca semântica, clusters, RAG |
| `aviation.py` | `/api/aviation` | Metadados, hubs, hub-intelligence, alianças |
| `operations.py` | `/api/operations` | Sync, pipeline, reconciliação |
| `ops_health.py` | `/api/operations/health` | Schema, native, integrity, pipeline |
| `admin.py` | `/api` | Scheduler, data quality |

**Nota:** Não existem blueprints Flask nem templates Jinja2 no repositório.

---

## Application core (`app/`)

| Módulo | Responsabilidade |
|--------|------------------|
| `config.py` | Settings via variáveis de ambiente |
| `middleware.py` | Rate limit, timeout, security headers, request context |
| `logging_config.py` | Logging estruturado JSON |
| `observability.py` | Métricas Prometheus, instrumentação SQLAlchemy |
| `startup_governance.py` | Validação de schema no boot |
| `health_snapshot.py` | Snapshot de integridade em memória/Redis |
| `runtime_state.py` | Estado runtime da API |
| `response_contract.py` | Contrato de resposta padronizado |
| `payload_serialization.py` | Serialização segura de payloads |

---

## Analytics (`analytics/`)

| Módulo | Domínio |
|--------|---------|
| `intelligence/reputation.py` | Airline Reputation Score (ARS) |
| `intelligence/benchmarking.py` | Benchmarking entre pares |
| `intelligence/topic_trends.py` | Evolução temporal de tópicos |
| `forecasting/service.py` | EWMA, médias móveis, horizonte configurável |
| `forecasting/safe_service.py` | Isolamento / fallback de forecasting |
| `anomaly/detector.py` | Detecção estatística de anomalias |
| `semantic/search.py` | Busca por similaridade (pgvector) |
| `hub_intelligence.py` | KPIs, rankings e rede de hubs |
| `fusion_intelligence.py` | Sinais fusion para feed executivo |
| `friction_matrix.py` | Matriz de fricção reputacional |
| `knowledge_graph.py` | Grafo de conhecimento operacional |
| `pipeline_integrity.py` | Integridade do pipeline de dados |
| `kpi_governance.py` | Governança de KPIs |
| `metadata_extractor.py` | Extração de metadados aeronáuticos |
| `geospatial_intelligence.py` | Camadas geoespaciais |
| `operational_intelligence.py` | Inteligência operacional transversal |
| `quality/monitor.py` | Monitoramento de qualidade de dados |
| `explainability/` | Insights executivos, copilot, snapshots |

**Duplicatas legadas (raiz vs pacote):** `explainable.py`, `insights_engine.py`, `copilot.py` na raiz de `analytics/` coexistem com `explainability/` — ver [technical_debt.md](./technical_debt.md).

---

## Aviation domain (`aviation/`)

| Pasta | Função |
|-------|--------|
| `master_data/` | Sync e normalização de fontes aeronáuticas |
| `coverage/` | Engine de cobertura de metadados |
| `validation/` | Validação de identidade e schema |
| `enrichment/` | Pipeline de enriquecimento |
| `graph/` | Contexto de grafo aeronáutico |
| `aviation_identity_governance.py` | Governança de identificadores |

---

## Database (`database/`)

| Pasta | Função |
|-------|--------|
| `models/core.py` | Reviews, airlines base |
| `models/aviation.py` | AirportMetadata, AirlineMetadata, Alliance |
| `models/intelligence.py` | Insights, snapshots, forecasts |
| `models/analytics.py` | Métricas analíticas |
| `models/geo.py` | Camadas geoespaciais |
| `models/graph.py` | Knowledge graph |
| `models/operations.py` | Pipeline runs, operações |
| `migrations/versions/` | 13 migrações Alembic (0001–0013) |
| `schema_health.py` | Diagnóstico de schema |
| `runtime_schema.py` | Schema em runtime |

---

## Scraper & pipelines

| Local | Função |
|-------|--------|
| `scraper/spiders/` | `airlinequality`, `airport_metadata`, `airline_metadata`, `discovery` |
| `scraper/pipelines/` | Validação, dedup, persistência aviation |
| `pipelines/` | Cópia/legado usado por testes (`fingerprinting`, `scrapy_pipeline`) |

---

## Worker (`worker/`)

| Módulo | Função |
|--------|--------|
| `jobs.py` | Enriquecimento NLP, snapshots, refresh |
| `scheduler.py` | Agendamento com locks |
| `runner.py` | Entrypoint RQ |
| `orchestration/` | Watchdog, refresh pipeline, reconciliação |
| `subprocess_governor.py` | Limite de subprocessos |
| `forecasting_isolation.py` | Isolamento de jobs de forecast |

---

## Frontend (`frontend/src/`)

### Workspaces (páginas)

| Workspace | Rota | Hook / dados |
|-----------|------|--------------|
| Executive | `/executive` | `AnalyticsProvider` |
| Reputation | `/reputation` | Shared analytics |
| Forecasting | `/forecasting` | `useForecasting` |
| Benchmarking | `/benchmarking` | `useBenchmarking` |
| Anomalies | `/anomalies` | `useAnomalies` |
| Semantic | `/semantic` | Shared + API semântica |
| Aviation | `/aviation` | `useAviation` |
| Hubs | `/hubs` | `useAviation` (hub-intelligence) |
| Alliances | `/alliances` | `useAllianceIntel` |
| Coverage | `/coverage` | `useCoverage` |
| Geospatial | `/geospatial` | `useGeospatial` |
| Investigations | `/investigations` | Shared analytics |

### Design system

| Pasta | Função |
|-------|--------|
| `design-system/tokens/` | Cores, spacing, tipografia, motion |
| `design-system/components/` | KPIStatCard, OperationalCard, TimelinePanel… |
| `design-system/patterns/` | Grid executivo, pipeline, timeline |
| `components/forecasting/OperationalModuleCard.jsx` | Card padrão dos workspaces refatorados |

### Navegação

- **Fonte única:** `frontend/src/config/navigation.js` + `i18n/*/nav.json`
- Ícones Lucide, grupos: Inteligência / Aviação / Espacial

### Assets

- **Não há** pasta `static/` nem `templates/` no backend.
- CSS principal: `frontend/src/styles.css` (~250KB, inclui legado `.ali-*`, `.hub-*` antigos).
- Tema geoespacial: `workspaces/geospatial/geospatial.css`.

---

## Testes (`tests/`)

| Categoria | Exemplos |
|-----------|----------|
| API / health | `test_health_routes.py`, `test_api_contract.py` |
| Pipeline | `test_pipeline_integrity.py`, `test_pipeline_watchdog.py` |
| Aviation | `test_aviation_schema.py`, `test_aviation_identity_governance.py` |
| Forecast / anomaly | `test_forecasting_isolation.py`, `test_forecast_anomaly.py` |
| Frontend libs | `kpiGovernance.test.js`, `integrityReconciliation.test.js` |

---

## Documentação existente

| Arquivo | Status |
|---------|--------|
| `docs/ARCHITECTURE.md` | Legado — referencia `ExecutiveDashboard` obsoleto |
| `docs/development.md` | Guia de desenvolvimento |
| `docs/FRONTEND_RUNTIME_SETUP.md` | Setup do frontend |
| `docs/production.md` | Hardening de produção |
| `docs/roadmap.md` | Roadmap antigo na raiz de `docs/` |

---

## Arquivos candidatos a obsolescência

| Item | Motivo |
|------|--------|
| `frontend/src/components/ExecutiveDashboard.jsx` | Não importado pelo router; substituído por `workspaces/executive/` |
| `analytics/explainable.py`, `insights_engine.py`, `copilot.py` | Duplicam `explainability/` |
| `pipelines/` (raiz) | Paralelo a `scraper/pipelines/`; só testes |
| CSS `.ali-*` em `styles.css` | Workspace Alianças migrou para classes `.alliance-*` |
| `pipeline_lineage_report.json` (raiz) | Artefato gerado; não versionar |
| `docs/ARCHITECTURE.md` | Desatualizado vs workspaces modulares |

---

## Dependências entre camadas

```text
Scrapy → PostgreSQL → NLP Worker → Analytics Engines → FastAPI → React Workspaces
                ↓
         Alembic migrations
                ↓
         Redis (cache, RQ, health snapshots)
```

---

## Convenção de nomenclatura (módulos UI)

Verificação em `i18n/pt/nav.json` e namespaces por workspace:

| Módulo | Menu (PT) | Título de página | Status |
|--------|-----------|------------------|--------|
| Executive | Executivo | Executivo | OK |
| Forecasting | Previsão | Previsão | OK |
| Benchmarking | Benchmarking | Benchmarking | OK |
| Anomalies | Anomalias | Inteligência de anomalias | Título página ≠ menu |
| Semantic | Análise Semântica | Análise Semântica | OK |
| Aviation | Aviação | Aviação | OK |
| Hubs | Hubs | Hubs (+ subtítulo estendido no workspace) | Subtitle nav ≠ pageSubtitle |
| Alliances | Alianças | Alianças | OK |
| Coverage | Cobertura | Cobertura | OK |
| Investigations | Investigações | Investigação Operacional | Título página ≠ menu |

Recomendação: alinhar `anomalies.pageTitle` e `investigations.pageTitle` aos labels de menu, ou documentar intencionalidade (título longo na página, label curto na sidebar).
