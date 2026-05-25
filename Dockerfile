FROM python:3.11-slim AS base

ENV PIP_DEFAULT_TIMEOUT=100 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTORCH_ENABLE_MPS_FALLBACK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --default-timeout=100 --no-cache-dir -r requirements.txt

ARG INSTALL_PLAYWRIGHT=true
RUN if [ "$INSTALL_PLAYWRIGHT" = "true" ]; then playwright install --with-deps chromium; fi

COPY . .

RUN groupadd --gid 1000 skytrax \
    && useradd --uid 1000 --gid skytrax --create-home skytrax \
    && chown -R skytrax:skytrax /app

USER skytrax

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
