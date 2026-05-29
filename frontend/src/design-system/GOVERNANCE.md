# SkyTrax Design Governance (SODS v1)

## Scope

SODS padroniza toda a linguagem visual operacional do SkyTrax com foco em command-center UX.

## Official Foundations

- **Tokens**: `tokens/*.css`
- **Themes**: `themes/skytrax-dark.css`, `themes/skytrax-light.css`
- **Patterns**: `patterns/*.css`
- **Reusable Components**: `components/*.jsx`
- **Operational Layouts**: `layouts/*.jsx`
- **Runtime Hook**: `hooks/useOperationalTheme.js`

## Visual Guidelines

- Use `--ops-*` tokens, nunca cores hardcoded em componentes novos.
- Labels pequenas podem ser uppercase; textos longos devem usar case normal.
- Métricas sempre com `font-variant-numeric: tabular-nums`.
- Estados operacionais devem usar `StatusBadge`.
- Painéis executivos devem herdar `OperationalCard` ou `IntelligencePanel`.
- Timeline operacional deve usar `TimelinePanel`/`timeline.css`.

## Migration Strategy

1. **Baseline**
   - Operational Sync já validado e atua como referência.
2. **Structural Layer**
   - Migrar modais e headers para `OperationalHeader`.
   - Trocar badges antigos por `StatusBadge`.
3. **Data Readability**
   - Migrar KPIs para `KPIStatCard` e `IntegrityPanel`.
   - Migrar tabelas para `ExecutiveTable`.
4. **Workspace Consolidation**
   - Forecast, Reputation, Semantic e Executive Insights.
5. **Platform Consolidation**
   - GEOINT, OSINT, Alert Center, navegação e side panels.

## Rollout Checklist

- [ ] Tokens `--ops-*` adotados no módulo
- [ ] Sem cor hardcoded no JSX
- [ ] Header no padrão `OperationalHeader`
- [ ] Status em `StatusBadge`
- [ ] KPIs em grid adaptativo (`IntegrityPanel`/`KPIStatCard`)
- [ ] Tabela no padrão `ExecutiveTable`
- [ ] Timeline no padrão `TimelinePanel`
- [ ] Focus-visible acessível
- [ ] Compatível com `prefers-reduced-motion`
- [ ] Testado em dark/light e breakpoints
- [ ] Telemetria de governança aplicada:
  - `[DESIGN_SYSTEM] SODS.v1`
  - `[THEME_RUNTIME] theme:<light|dark>`
  - `[LAYOUT_GOVERNANCE] operational-layout`

## Expansion Plan

- **v1.1**: tooltips operacionais e side panels padronizados
- **v1.2**: tokens semânticos por domínio (forecast, reputation, anomalies)
- **v1.3**: kits de skeleton/loading por tipo de painel
- **v2.0**: sistema de variáveis de densidade por persona (analyst/executive)
