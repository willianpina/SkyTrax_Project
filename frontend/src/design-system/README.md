# SkyTrax Operational Design System (SODS)

SODS e a linguagem oficial da interface do SkyTrax para ambientes de inteligencia operacional.

## Governance Tags

- `[DESIGN_SYSTEM]`: SODS.v1
- `[THEME_RUNTIME]`: runtime da tema ativa
- `[LAYOUT_GOVERNANCE]`: padrao de layout aplicado

## Principles

1. Hierarquia operacional executiva
2. Contraste alto e leitura imediata
3. Densidade elegante
4. Estados consistentes
5. Componentes reutilizaveis

## Rollout Strategy

1. `Operational Sync` (baseline validado)
2. `Command Dashboard` + `Timeline`
3. `Forecast Center` + `Reputation`
4. `Semantic Fusion`, `Airline Intelligence`, `Executive Insights`
5. `GEOINT`, `OSINT`, `Alert Center`

## Usage Example

```jsx
import { OperationalHeader, StatusBadge, IntegrityPanel } from "../design-system";

<OperationalHeader
  title="Plataforma Analitica Operacional"
  subtitle="Orquestracao de inteligencia e correlacao"
  badges={<StatusBadge label="SAFE MODE" variant="safe-mode" compact />}
  status={<StatusBadge label="SINCRONIZADO" variant="success" pulse />}
/>
```

## Accessibility

- WCAG AA contrast targets
- focus-visible ring por token
- suporte a `prefers-reduced-motion`
- tabela e timeline com roles semanticos
