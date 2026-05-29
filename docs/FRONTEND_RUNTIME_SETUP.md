# Frontend runtime setup (macOS)

## One-command setup

```bash
./scripts/setup_frontend_runtime.sh
```

Installs Node.js v20 LTS to `~/.local/node` (no Homebrew required), runs `npm install` and `npm run build`.

## Optional: Homebrew path

```bash
SKYTRAX_INSTALL_BREW=1 ./scripts/setup_frontend_runtime.sh
```

## After install

New terminals load Node via `~/.zshrc`. Current shell:

```bash
export PATH="$HOME/.local/node/bin:$PATH"
```

## Commands

```bash
cd frontend
npm run dev      # http://localhost:5173
npm run build
npm run lint     # alias: production build (JSX/Babel validation)
```

## Docker

```bash
docker compose restart frontend app worker
# or
docker compose up -d
```

Frontend container uses `node:20-alpine` with volume `./frontend` — local fixes apply on restart.
