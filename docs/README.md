# Documentação — SkyTrax Analytics

## Índice

| Documento | Descrição |
|-----------|-----------|
| [architecture/architecture.md](architecture/architecture.md) | Visão arquitetural e fluxo de dados |
| [architecture/diagram.md](architecture/diagram.md) | Diagrama Mermaid (Frontend → API → DB → Analytics) |
| [architecture/project_inventory.md](architecture/project_inventory.md) | Inventário de pastas, módulos e APIs |
| [architecture/PROJECT_STRUCTURE.md](architecture/PROJECT_STRUCTURE.md) | Auditoria da árvore do projeto (órfãos, duplicatas) |
| [architecture/TARGET_STRUCTURE.md](architecture/TARGET_STRUCTURE.md) | Estrutura alvo proposta (sem mover arquivos) |
| [architecture/technical_debt.md](architecture/technical_debt.md) | Dívida técnica classificada (ALTO/MÉDIO/BAIXO) |
| [backend/README.md](backend/README.md) | API, workers, Scrapy, configuração |
| [frontend/README.md](frontend/README.md) | React workspaces, Vite, stack UI |
| [testing/README.md](testing/README.md) | Pytest, cobertura, smoke CI |
| [MATURITY_REPORT.md](MATURITY_REPORT.md) | Relatório de maturidade do projeto |
| [modules/modules.md](modules/modules.md) | Mapa dos workspaces e endpoints |
| [deployment/deployment.md](deployment/deployment.md) | Deploy Docker e variáveis |
| [roadmap/roadmap.md](roadmap/roadmap.md) | Roadmap por versão |
| [development.md](development.md) | Guia de desenvolvimento local |
| [FRONTEND_RUNTIME_SETUP.md](FRONTEND_RUNTIME_SETUP.md) | Setup do frontend |
| [database.md](database.md) | Modelo de dados |
| [etl_flow.md](etl_flow.md) | Fluxo ETL Scrapy → NLP |
| [observability.md](observability.md) | Métricas e logs |
| [production.md](production.md) | Hardening de produção |
| [screenshots/](screenshots/) | Capturas para o README |
| [ci_cd/](ci_cd/) | Auditoria e remediação do GitHub Actions |
| [release/PROJECT_HEALTH_REPORT.md](release/PROJECT_HEALTH_REPORT.md) | Saúde do projeto (CI, testes, Docker, débito) |
| [release/QUALITY_AUDIT.md](release/QUALITY_AUDIT.md) | Auditoria de qualidade pré-release |
| [release/README_AUDIT.md](release/README_AUDIT.md) | Auditoria do README |
| [release/FINAL_RELEASE_REPORT.md](release/FINAL_RELEASE_REPORT.md) | Relatório final de publicação GitHub |
| [security/DEPENDENCY_AUDIT.md](security/DEPENDENCY_AUDIT.md) | pip-audit — CVEs e severidade |
| [security/UPGRADE_PLAN.md](security/UPGRADE_PLAN.md) | Plano de upgrade de dependências |
| [security/SECURITY_RELEASE_REPORT.md](security/SECURITY_RELEASE_REPORT.md) | Relatório de estabilização security CI |
| [audits/](audits/) | Auditorias de domínio (Aviation, API, data flow) |

## Arquivos legados

- `ARCHITECTURE.md` — redireciona para `architecture/`
- `roadmap.md` — redireciona para `roadmap/roadmap.md`
