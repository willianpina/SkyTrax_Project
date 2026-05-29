# Roadmap — SkyTrax Analytics

## v1 — Executive Intelligence ✅

- [x] Dashboard Executivo com KPIs e insights
- [x] Reputation scoring (ARS)
- [x] Coleta Scrapy + persistência PostgreSQL
- [x] API FastAPI + React SPA
- [x] i18n PT / EN

## v2 — Forecasting & Anomalies ✅

- [x] Módulo de Previsão (EWMA, heatmap temporal)
- [x] Detecção de anomalias e feed de incidentes
- [x] Benchmarking competitivo
- [x] Workers RQ e scheduler

## v3 — Semantic Intelligence ✅

- [x] Busca semântica (pgvector)
- [x] Clusterização e entidades
- [x] Workspace de Análise Semântica refatorado
- [x] Friction matrix integrada

## v4 — Network Intelligence 🚧

- [x] Aviation registry
- [x] Hubs intelligence (rankings, risco, concentração)
- [x] Alliances panorama e comparativo
- [x] Coverage engine
- [x] Geospatial workspace (MapLibre)
- [ ] Grafo de conhecimento visual interativo
- [ ] Unificação de cache entre `useAviation` e `useAllianceIntel`

## v5 — Enterprise Operations (planejado)

- [ ] Autenticação e RBAC multi-tenant
- [ ] Export PDF/CSV de relatórios executivos
- [ ] Alertas webhook (Slack / Teams)
- [ ] Testes E2E (Playwright) no CI
- [ ] Purga de dívida técnica (CSS legado, módulos duplicados)

## v6 — AI Copilot (exploratório)

- [ ] RAG contextual por airline com citações
- [ ] Explicações automáticas de anomalias (LLM)
- [ ] Assistente em linguagem natural sobre o corpus

---

Para histórico de releases, ver [CHANGELOG.md](../../CHANGELOG.md) na raiz do repositório.
