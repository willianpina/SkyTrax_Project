# Módulos da Plataforma — SkyTrax Analytics

Mapa funcional dos workspaces e APIs associadas.

## Inteligência

### Executive (`/executive`)

- **Objetivo:** Visão estratégica consolidada para liderança.
- **UI:** `workspaces/executive/ExecutiveWorkspace.jsx`
- **Dados:** `/api/analytics`, `/api/insights`, reputação, alertas.
- **Capacidades:** KPIs ARS, timeline, feed de insights, matriz comparativa.

### Reputation (`/reputation`)

- **Objetivo:** Monitoramento de reputação por companhia.
- **UI:** `workspaces/reputation/`
- **Dados:** `/api/reputation`, `/api/reputation/{slug}`

### Forecasting (`/forecasting`)

- **Objetivo:** Projeção de tendências e risco futuro.
- **UI:** `workspaces/forecasting/` — ExecutiveSummary, PredictionsTable, TemporalHeatmap, TopMovers.
- **API:** `/api/forecasting`, `/api/forecasting/{slug}`, `POST /refresh`.

### Benchmarking (`/benchmarking`)

- **Objetivo:** Comparação entre pares e ranking operacional.
- **UI:** `BenchmarkKpiStrip`, `BenchmarkRuntimeTable`, `BenchmarkAnalyticsRow`.
- **API:** `/api/benchmarking`

### Anomalies (`/anomalies`)

- **Objetivo:** Detecção de riscos e incidentes reputacionais.
- **UI:** `workspaces/anomalies/` — KPI strip, incident runtime, timeline, assessment.
- **API:** `/api/anomalies`, `/api/anomalies/alerts`

### Semantic Analysis (`/semantic`)

- **Objetivo:** Clusterização temática, entidades e narrativas.
- **UI:** `SemanticOverviewStrip`, `SemanticTopicsPanel`, `SemanticEntityRuntime`, `SemanticFrictionModule`.
- **API:** `/api/semantic-search`, `/api/semantic-clusters`, `/api/rag/context`

## Rede de aviação

### Aviation (`/aviation`)

- **Objetivo:** Registro global de companhias, aeroportos e metadados.
- **API:** `/api/aviation/*`
- **UI:** Registry, módulos premium e regional.

### Hubs (`/hubs`)

- **Objetivo:** Inteligência de infraestrutura aeroportuária.
- **API:** `/api/aviation/hub-intelligence/*` (dashboard, rankings, risk, alliances, incidents, concentration)
- **UI:** Overview, painel operacional, matriz de risco, timeline, rede global, concentração, insights.

### Alliances (`/alliances`)

- **Objetivo:** Ecossistemas Star Alliance, SkyTeam, Oneworld.
- **API:** `/api/aviation/alliances`, `/api/fusion/signals`
- **UI:** Panorama, comparativo, heatmap de rede, feed analítico.

### Coverage (`/coverage`)

- **Objetivo:** Completude de metadados e prontidão do grafo.
- **API:** `/api/aviation/coverage` (via `useCoverage`)
- **UI:** `CoverageWorkspace.jsx`

## Espacial e investigação

### Geospatial (`/geospatial`)

- **Objetivo:** Mapa operacional, hubs, rotas, eventos.
- **Stack:** MapLibre, Deck.gl, `useGeospatial`
- **UI:** `GeospatialWorkspace.jsx`, `GeoHud.jsx`

### Investigations (`/investigations`)

- **Objetivo:** Correlação de sinais e análise aprofundada.
- **UI:** Filtros, grid de incidentes, insights, forecast charts, módulo semântico.
- **Dados:** Shared analytics (anomalies, insights, clusters)

## Componentes transversais

| Componente | Uso |
|------------|-----|
| `OperationalModuleCard` | Card padrão 20px radius, 24px padding |
| `WorkspaceShell` | Header de página com título i18n |
| `FrictionMatrix` | Matriz de fricção (semântica / benchmarking) |
| `PipelineIntegrityStrip` | Saúde do pipeline operacional |
| `AnalyticsProvider` | Contexto global de dados analíticos |

## i18n

Namespaces: `nav`, `dashboard`, `command`, `benchmarking`, `anomalies`, `semantic`, `aviation`, `hubs`, `alliances`, `coverage`, `investigations`, `charts`, `alerts`, `common`.

Configuração: `frontend/src/i18n/index.ts`.
