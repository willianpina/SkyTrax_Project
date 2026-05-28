# SkyTrax Analytics

Plataforma de **Inteligência Analítica** para avaliação de companhias aéreas — reputação, previsão, anomalias, semântica e rede de aviação em um único centro de comando operacional.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Visão geral

O **SkyTrax Analytics** transforma avaliações de passageiros, metadados aeronáuticos e sinais operacionais em **inteligência acionável** para equipes de experiência do cliente, operações e estratégia.

### Problema

Companhias aéreas geram volume massivo de feedback disperso (reviews, reclamações, incidentes). Sem consolidação analítica, equipes reagem tarde a crises reputacionais e perdem visibilidade sobre hubs, alianças e concentração operacional.

### Benefícios

- **Visão 360°** — Do executivo ao hub aeroportuário, em workspaces dedicados.
- **Detecção proativa** — Anomalias e forecasting antes que métricas públicas degradem.
- **Semântica aplicada** — Tópicos, entidades e narrativas extraídas do corpus de reviews.
- **Rede de aviação** — Companhias, alianças, hubs, cobertura e mapa geoespacial.
- **Operação confiável** — Health de pipeline, schema e integridade expostos via API.

---

## Principais capacidades

### Executive Intelligence

- Visão estratégica consolidada
- Indicadores reputacionais (ARS)
- Feed de insights e timeline de atividade
- Monitoramento operacional em tempo quase real

### Forecasting

- Projeção de reputação e tendência temporal
- Heatmap temporal e ranking de movimentos
- Risco futuro por companhia

### Benchmarking

- Comparação entre companhias
- Ranking operacional com score e risco
- Radar multidimensional e densidade de reclamações

### Anomaly Detection

- Identificação automática de desvios estatísticos
- Alertas reputacionais com severidade
- Runtime de incidentes e linha do tempo

### Semantic Intelligence

- Clusterização temática de narrativas
- Extração de entidades
- Busca semântica (pgvector) e contexto RAG

### Aviation Network

| Módulo | Foco |
|--------|------|
| **Aviation** | Registro global de companhias |
| **Hubs** | Infraestrutura aeroportuária e concentração |
| **Alliances** | Star Alliance, SkyTeam, Oneworld |
| **Coverage** | Completude de metadados e grafo |

### Investigations

- Correlação de sinais entre anomalias, insights e semântica
- Análise aprofundada por companhia
- Integração com charts de forecasting

### Geospatial

- Mapa operacional com hubs, rotas e eventos
- Camadas Deck.gl sobre basemap aviation

---

## Arquitetura

| Camada | Tecnologia |
|--------|------------|
| **API** | FastAPI, Pydantic, SQLAlchemy, Alembic |
| **Banco** | PostgreSQL (+ pgvector, PostGIS opcional) |
| **Filas** | Redis, RQ |
| **Coleta** | Scrapy (+ Playwright opcional) |
| **NLP** | spaCy, scikit-learn, sentence-transformers (opcional) |
| **Frontend** | React 18, Vite, ECharts, i18next, Tailwind |
| **Observabilidade** | Prometheus, Grafana, logs JSON |

```text
Scrapy → PostgreSQL → NLP Worker → Analytics → FastAPI → React Workspaces
```

Documentação detalhada: [docs/architecture/architecture.md](docs/architecture/architecture.md)

> **Nota:** Este projeto **não** usa Flask, Jinja2, Bootstrap ou Chart.js. A stack documentada acima reflete o código atual.

---

## Estrutura do projeto

```text
skytrax/
├── api/                    # REST API FastAPI
│   └── routers/            # reviews, intelligence, aviation, operations…
├── app/                    # Config, middleware, observability
├── analytics/              # Engines: reputation, forecast, anomaly, semantic…
├── aviation/               # Master data, coverage, validation
├── database/               # ORM models + Alembic migrations
├── nlp/                    # Pipeline NLP
├── scraper/                # Spiders Scrapy
├── worker/                 # Jobs RQ + orchestration
├── frontend/               # React SPA (workspaces modulares)
│   └── src/workspaces/     # executive, forecasting, hubs, alliances…
├── tests/                  # Pytest
├── docs/                   # Documentação técnica
│   ├── architecture/       # Inventário, dívida técnica, arquitetura
│   ├── modules/            # Mapa de módulos
│   ├── deployment/         # Deploy e ops
│   ├── roadmap/            # Roadmap versionado
│   └── screenshots/        # Capturas (placeholders)
├── ops/                    # Prometheus + Grafana
├── scripts/                # Seed, bootstrap, smoke tests
└── README.md
```

Inventário completo: [docs/architecture/project_inventory.md](docs/architecture/project_inventory.md)

---

## Instalação

### Opção A — Docker (recomendado)

```bash
git clone https://github.com/willianpina/SkyTrax_Project.git
cd SkyTrax_Project
cp .env.example .env
docker compose up --build
```

Inicializar dados:

```bash
docker compose exec app alembic upgrade head
docker compose exec app python scripts/seed_airlines.py
docker compose exec app scrapy crawl airlinequality_reviews -a max_pages=3
```

### Opção B — Desenvolvimento local

**Backend**

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn api.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

| Serviço | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Dashboard (dev) | http://localhost:5173 |
| Health | http://localhost:8000/health |

---

## Capturas de tela

> Adicione imagens em `docs/screenshots/` e referencie aqui antes do release público.

| Módulo | Arquivo sugerido |
|--------|------------------|
| Executive | `docs/screenshots/executive.png` |
| Forecasting | `docs/screenshots/forecasting.png` |
| Benchmarking | `docs/screenshots/benchmarking.png` |
| Anomalies | `docs/screenshots/anomalies.png` |
| Semantic Intelligence | `docs/screenshots/semantic.png` |
| Aviation / Hubs | `docs/screenshots/hubs.png` |

---

## Roadmap

| Versão | Entrega |
|--------|---------|
| **v1** | Dashboard Executivo, reputação, coleta Scrapy |
| **v2** | Forecasting, anomalias, benchmarking |
| **v3** | Semantic Intelligence, busca vetorial |
| **v4** | Network Intelligence (aviação, hubs, alianças, geo) |
| **v5** | Enterprise (auth, alertas, E2E) — planejado |

Detalhes: [docs/roadmap/roadmap.md](docs/roadmap/roadmap.md)

---

## Desenvolvimento

```bash
make help          # Targets disponíveis
make test          # Pytest + coverage
make lint          # Ruff
make frontend-dev  # Vite :5173
```

Guias:

- [Development](docs/development.md)
- [Frontend setup](docs/FRONTEND_RUNTIME_SETUP.md)
- [Deployment](docs/deployment/deployment.md)
- [Dívida técnica](docs/architecture/technical_debt.md)

---

## Contribuir

Leia [CONTRIBUTING.md](CONTRIBUTING.md) e o [Código de Conduta](CODE_OF_CONDUCT.md).

---

## Licença

Este projeto está licenciado sob a **MIT License** — veja [LICENSE](LICENSE).
