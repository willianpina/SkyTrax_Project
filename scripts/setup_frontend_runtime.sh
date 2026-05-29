#!/usr/bin/env zsh
# SkyTrax — automated Node.js/npm setup + frontend validation (macOS arm64/x64)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"
NODE_VERSION="${SKYTRAX_NODE_VERSION:-20.18.1}"
LOCAL_NODE="$HOME/.local/node"
ZSHRC="$HOME/.zshrc"
MARKER="# SkyTrax Node.js PATH"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64) NODE_ARCH="arm64" ;;
  x86_64) NODE_ARCH="x64" ;;
  *) echo "Unsupported arch: $ARCH"; exit 1 ;;
esac

log() { echo "[SKYTRAX_SETUP] $*"; }

ensure_path() {
  export PATH="$LOCAL_NODE/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
  [[ -f "$ZSHRC" ]] || touch "$ZSHRC"
  if ! grep -qF "$MARKER" "$ZSHRC" 2>/dev/null; then
    {
      echo ""
      echo "$MARKER"
      echo 'export PATH="$HOME/.local/node/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"'
    } >> "$ZSHRC"
    log "Appended Node PATH to $ZSHRC"
  fi
}

install_node_local() {
  if [[ -x "$LOCAL_NODE/bin/node" ]]; then
    log "Node already present at $LOCAL_NODE"
    return 0
  fi
  mkdir -p "$HOME/.local"
  TARBALL="node-v${NODE_VERSION}-darwin-${NODE_ARCH}.tar.xz"
  URL="https://nodejs.org/dist/v${NODE_VERSION}/${TARBALL}"
  TMP="$(mktemp -d)"
  log "Downloading Node v${NODE_VERSION} (${NODE_ARCH})..."
  curl -fsSL "$URL" -o "$TMP/$TARBALL"
  tar -xJf "$TMP/$TARBALL" -C "$TMP"
  rm -rf "$LOCAL_NODE"
  mv "$TMP/node-v${NODE_VERSION}-darwin-${NODE_ARCH}" "$LOCAL_NODE"
  rm -rf "$TMP"
  log "Installed Node to $LOCAL_NODE"
}

try_brew_node() {
  if command -v brew >/dev/null 2>&1; then
    log "Homebrew found — installing node..."
    brew install node 2>/dev/null || brew upgrade node 2>/dev/null || true
    return 0
  fi
  return 1
}

install_homebrew_if_requested() {
  if [[ "${SKYTRAX_INSTALL_BREW:-0}" != "1" ]]; then
    return 1
  fi
  if command -v brew >/dev/null 2>&1; then
    return 0
  fi
  log "Installing Homebrew (SKYTRAX_INSTALL_BREW=1)..."
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}

main() {
  log "macOS $(sw_vers -productVersion 2>/dev/null || echo unknown) arch=$ARCH"
  install_homebrew_if_requested || true
  if ! try_brew_node; then
    install_node_local
  fi
  ensure_path

  if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: node still not in PATH after setup"
    exit 1
  fi

  log "node $(node -v) npm $(npm -v)"
  cd "$FRONTEND"
  log "npm install..."
  npm install
  log "npm run build..."
  npm run build
  if npm run | grep -qE '^\s*lint'; then
    log "npm run lint..."
    npm run lint
  else
    log "No lint script in package.json — skipping"
  fi
  log "Frontend validation complete."
}

main "$@"
