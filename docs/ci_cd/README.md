# CI/CD — SkyTrax Analytics

| Documento | Conteúdo |
|-----------|----------|
| [workflow_inventory.md](workflow_inventory.md) | Jobs, gatilhos, steps |
| [root_cause_analysis.md](root_cause_analysis.md) | Por que CI #18–#42 falhavam |
| [dependency_audit.md](dependency_audit.md) | requirements vs imports |
| [docker_audit.md](docker_audit.md) | Dockerfile e compose |
| [remediation_plan.md](remediation_plan.md) | Plano de ação e critérios de sucesso |

## Comandos locais (espelham CI)

```bash
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
python -c "from api.main import app"
pytest --cov --cov-fail-under=45 -q
cd frontend && npm ci && npm run build
```

Entrypoint da API: `uvicorn main:app` ou `python main.py` (não existe `app.py`).
