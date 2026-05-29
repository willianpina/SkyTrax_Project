# Arquitetura — SkyTrax Analytics

## Visão de alto nível

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Scrapy    │────▶│  PostgreSQL  │────▶│  NLP Worker │
│   Spiders   │     │  + pgvector  │     │  (RQ/Redis) │
└─────────────┘     └──────┬───────┘     └──────┬──────┘
                           │                     │
                           ▼                     ▼
                    ┌──────────────────────────────────┐
                    │     Analytics Engines            │
                    │ reputation · forecast · anomaly  │
                    │ semantic · hub · fusion · graph  │
                    └──────────────┬───────────────────┘
                                   │
                            ┌──────▼──────┐
                            │   FastAPI   │
                            │  REST /api  │
                            └──────┬──────┘
                                   │
                            ┌──────▼──────┐
                            │  React SPA  │
                            │  Workspaces │
                            └─────────────┘
```

## Princípios

1. **Scrapy-first** — A coleta primária é via spiders; a API não faz scraping síncrono em requests de usuário.
2. **Analytics desacoplados** — Motores em `analytics/` são invocados por workers ou endpoints de refresh, não embutidos nos routers.
3. **Contrato operacional** — Health de schema, pipeline e integridade expostos em `/api/operations/health/*`.
4. **UI por workspace** — Cada módulo analítico tem workspace React dedicado com design system unificado (`OperationalModuleCard`, grid 12 colunas, gap 24px).

## Backend

### FastAPI (`api/`)

- Entry: `api/main.py`
- Routers agregados em `api/routes.py` com prefixo `/api`
- Lifespan executa governança de schema, watchdog de pipeline e validação de rotas

### Persistência (`database/`)

- SQLAlchemy 2.x ORM
- Alembic para migrations versionadas
- Modelos segmentados: `core`, `aviation`, `intelligence`, `analytics`, `geo`, `graph`, `operations`

### Processamento assíncrono (`worker/`)

- Redis + RQ para filas
- Jobs: enriquecimento NLP, geração de snapshots, refresh de forecasts/anomalias
- `orchestration/` — watchdog, reconciliação, lifecycle de operações

## Analytics

| Domínio | Pacote | Saída típica |
|---------|--------|--------------|
| Reputação | `intelligence/reputation` | ARS, componentes |
| Benchmarking | `intelligence/benchmarking` | Radar, complaint density |
| Forecasting | `forecasting/` | Séries projetadas por airline |
| Anomalias | `anomaly/detector` | Eventos com severidade |
| Semântica | `semantic/search` | Clusters, embeddings |
| Hubs | `hub_intelligence` | Dashboard, rankings, rede |
| Qualidade | `quality/` | Scans, lineage |

## Frontend

### Stack

- React 18 + React Router 6
- Vite 5 (build e dev server)
- i18next (PT / EN)
- ECharts via `LazyEChart` e `ChartPanel`
- MapLibre + Deck.gl (geoespacial)

### Padrão de workspace

```text
WorkspaceShell (title, subtitle)
  └── forecasting-grid
        └── fg-cell fg-span-*
              └── OperationalModuleCard
                    ├── op-status-pill
                    ├── KPI strip / table / chart
                    └── empty state elegante
```

Fonte de navegação: `config/navigation.js` + `i18n/*/nav.json`.

## Observabilidade

- Logs JSON estruturados (`app/logging_config.py`)
- `GET /metrics` — Prometheus
- Grafana dashboard em `ops/grafana/`
- Tracing opcional (`app/tracing.py`)

## Segurança

- CORS configurável
- Rate limiting por IP
- Trusted hosts em produção
- Secrets via env ou `*_FILE` (Docker secrets)

## Referências

- [Inventário completo](./project_inventory.md)
- [Dívida técnica](./technical_debt.md)
- [Deployment](../deployment/deployment.md)
- [Módulos](../modules/modules.md)
