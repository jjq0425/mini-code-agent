#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")" && pwd)
HELICONE_DIR="$ROOT_DIR/helicone"

if [ ! -d "$HELICONE_DIR/.git" ]; then
  echo "[gateway] Cloning Helicone repository..."
  git clone https://github.com/Helicone/helicone.git "$HELICONE_DIR"
fi

cd "$HELICONE_DIR"

if [ -f ".env.example" ] && [ ! -f ".env" ]; then
  echo "[gateway] Copying .env.example -> .env (please edit before production use)"
  cp .env.example .env
fi

echo "[gateway] Starting Helicone via docker compose..."
docker compose up -d

echo "[gateway] Done. Edit $HELICONE_DIR/.env as needed and check docker compose ps."
