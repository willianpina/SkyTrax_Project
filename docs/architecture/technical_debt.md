# Dívida Técnica — SkyTrax Analytics

Classificação: **ALTO** · **MÉDIO** · **BAIXO**

---

## ALTO

### 1. Componente frontend órfão — `ExecutiveDashboard.jsx`

| Item | Detalhe |
|------|---------|
| Arquivo | `frontend/src/components/ExecutiveDashboard.jsx` |
| Problema | Não é importado por `router.jsx`; duplica lógica de `workspaces/executive/ExecutiveWorkspace.jsx` |
| Risco | Manutenção dupla, confusão para contribuidores |
| Ação | Remover ou marcar `@deprecated` e redirecionar imports |

### 2. Módulos analytics duplicados na raiz

| Arquivos | Duplicata de |
|----------|--------------|
| `analytics/explainable.py` | `analytics/explainability/explainable.py` |
| `analytics/insights_engine.py` | `analytics/explainability/insights_engine.py` |
| `analytics/copilot.py` | `analytics/explainability/copilot.py` |

| Problema | Imports ambíguos; refatorações podem alterar o módulo errado |
| Ação | Consolidar em `explainability/` e reexportar via `__init__.py` se necessário |

### 3. CSS monolítico com classes legadas

| Item | Detalhe |
|------|---------|
| Arquivo | `frontend/src/styles.css` (~10k+ linhas) |
| Problema | Blocos `.ali-*` (Alianças antigo) coexistem com `.alliance-*` (novo design system) |
| Risco | Bundle CSS inflado, conflitos visuais |
| Ação | Remover bloco `GLOBAL ALLIANCE INTELLIGENCE` após confirmar zero referências |

### 4. Documentação desalinhada com a stack real

| Item | Detalhe |
|------|---------|
| Prompts / docs antigos | Referências a Flask, Jinja2, Bootstrap, Chart.js |
| Realidade | FastAPI, React, Vite, ECharts |
| Ação | README e `docs/architecture/` atualizados (esta auditoria) |

### 5. Artefatos versionáveis na raiz

| Arquivo | Problema |
|---------|----------|
| `pipeline_lineage_report.json` | Relatório gerado; deve estar no `.gitignore` |

---

## MÉDIO

### 6. Pipelines Scrapy duplicados

| Local A | Local B |
|---------|---------|
| `pipelines/` (raiz) | `scraper/pipelines/` |

Usado por testes em `tests/test_fingerprinting.py` e `test_scrapy_hardening.py`. Produção usa `scraper/pipelines/`.

**Ação:** Unificar em `scraper/pipelines/` e ajustar imports dos testes.

### 7. Inconsistência de nomenclatura UI (PT)

| Módulo | Menu | Título da página |
|--------|------|------------------|
| Anomalies | Anomalias | Inteligência de anomalias |
| Investigations | Investigações | Investigação Operacional |
| Hubs | Hubs (subtitle curto no nav) | Subtítulo longo só no workspace |

**Ação:** Padronizar via `nav.json` + `pageTitle` por namespace ou aceitar padrão “label curto / título longo” documentado.

### 8. Design system paralelo ao app

| Pasta | Uso |
|-------|-----|
| `frontend/src/design-system/` | Componentes e tokens |
| `frontend/src/components/` | Componentes de produção |

Parte do design-system (`CommandLayout`, `ExecutiveWorkspace` em layouts/) não é usada pelos workspaces atuais que preferem `WorkspaceShell` + `OperationalModuleCard`.

**Ação:** Documentar em `design-system/GOVERNANCE.md` quais primitivos são canônicos.

### 9. Rotas de health legadas

| Rotas | Status |
|-------|--------|
| `/api/operations/health/*` | Canônicas |
| `/ops/health/*` | Deprecated (warning em `router_registry.py`) |

**Ação:** Remover aliases deprecated após período de transição.

### 10. `docs/ARCHITECTURE.md` legado

Conteúdo pré-refatoração dos workspaces. Substituir links para `docs/architecture/architecture.md`.

---

## BAIXO

### 11. Hooks com sobreposição de fetch

| Hooks | Endpoints sobrepostos |
|-------|----------------------|
| `useAviation` | `/aviation/hub-intelligence/alliances` |
| `useAllianceIntel` | Mesmo endpoint de alianças |

**Ação:** Cache compartilhado via React Query ou provider (futuro).

### 12. Testes frontend limitados

Apenas `*.test.js` em `lib/`; workspaces sem testes de componente.

**Ação:** Adicionar Vitest + Testing Library para KPI strips críticos.

### 13. Exports locais de crawl

Pasta `exports/` já está no `.gitignore`; garantir que CI não dependa dela.

### 14. Subtítulos de módulo desatualizados em `nav.json`

Ex.: Hubs — `modules.hubs.subtitle` ainda diz “Conectividade de hubs…” enquanto `hubs.pageSubtitle` no workspace foi atualizado.

**Ação:** Sincronizar `nav.json` com namespaces `hubs`, `alliances`, `aviation`.

### 15. Chunks frontend grandes

Build alerta: `echarts` e `maplibre-gl` > 500KB.

**Ação:** Já há lazy routes; considerar dynamic import adicional no geoespacial.

---

## Matriz resumida

| ID | Item | Prioridade | Esforço |
|----|------|------------|---------|
| 1 | ExecutiveDashboard órfão | ALTO | Baixo |
| 2 | Analytics explainability duplicado | ALTO | Médio |
| 3 | CSS legado `.ali-*` | ALTO | Médio |
| 4 | Docs stack incorreta | ALTO | Baixo |
| 5 | pipeline_lineage_report.json | ALTO | Baixo |
| 6 | pipelines/ raiz | MÉDIO | Médio |
| 7 | Nomenclatura i18n | MÉDIO | Baixo |
| 8 | Design system vs app | MÉDIO | Médio |
| 9 | Health routes deprecated | MÉDIO | Baixo |
| 10 | ARCHITECTURE.md legado | MÉDIO | Baixo |
| 11–15 | Itens BAIXO | BAIXO | Variável |

---

## Imports não utilizados (amostragem)

Verificação manual recomendada com:

```bash
cd frontend && npx eslint src --rule 'no-unused-vars: error' 2>/dev/null || true
ruff check . --select F401
```

Componentes com baixa probabilidade de uso em runtime:

- `ExecutiveDashboard.jsx` (confirmado órfão)
- Possíveis exports não usados em `design-system/index.js`

---

## Rotas não utilizadas (frontend)

Todas as rotas em `router.jsx` estão ativas. Não há rotas órfãs no React Router.

Rotas API: todas montadas via `api/routes.py`; forecasting e anomalies montados adicionalmente em `main.py` — validar com:

```bash
curl -s http://localhost:8000/openapi.json | jq '.paths | keys'
```

---

## Plano de saneamento sugerido (pré-release)

1. Atualizar README e docs (feito nesta auditoria).
2. Adicionar `pipeline_lineage_report.json` ao `.gitignore`.
3. Remover `ExecutiveDashboard.jsx` ou convertê-lo em re-export deprecated.
4. Purga CSS `.ali-*` após grep zero.
5. Alinhar subtítulos `nav.json` ↔ workspaces.
6. Consolidar `analytics/explainability`.
