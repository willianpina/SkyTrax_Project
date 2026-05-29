# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Documentação de auditoria: `docs/architecture/project_inventory.md`, `technical_debt.md`
- Estrutura `docs/{architecture,modules,deployment,roadmap,screenshots}/`
- Workspaces modulares refatorados: Alliances, Hubs, Aviation, Investigations, Semantic
- Design system operacional (`OperationalModuleCard`, grid 24px, cards 20px radius)
- Hub intelligence API (`/api/aviation/hub-intelligence/*`)
- Health operacional (`/api/operations/health/*`)

### Changed

- README reescrito para publicação GitHub (stack FastAPI + React)
- i18n PT/EN com `navLabel` centralizado em `navigation.js`

### Deprecated

- `frontend/src/components/ExecutiveDashboard.jsx` (substituído por `workspaces/executive/`)
- Rotas `/ops/health/*` (usar `/api/operations/health/*`)

## [0.2.0] - 2026-05

### Added

- FastAPI application com routers modulares
- React 18 dashboard com lazy-loaded workspaces
- Forecasting, anomalies e benchmarking endpoints
- Scrapy spiders com pipelines de persistência
- Docker Compose dev + prod
- Prometheus / Grafana observability
- Alembic migrations 0001–0013

### Security

- Rate limiting, request size limits, security headers middleware

## [0.1.0] - 2024

### Added

- Initial Scrapy collector e schema PostgreSQL
- NLP pipeline básico (sentimento, tópicos)
- Reputation scoring inicial

[Unreleased]: https://github.com/willianpina/SkyTrax_Project/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/willianpina/SkyTrax_Project/releases/tag/v0.2.0
[0.1.0]: https://github.com/willianpina/SkyTrax_Project/releases/tag/v0.1.0
