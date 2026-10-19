#!/usr/bin/env bash
# Prepare a fresh checkout of SWSuite for its first run.
set -euo pipefail

cd "$(dirname "$0")/.."

say() { printf '\n\033[1;33m==>\033[0m %s\n' "$1"; }

say "Checking prerequisites"
command -v docker >/dev/null || { echo "docker not found"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "docker compose v2 not found"; exit 1; }
command -v git >/dev/null || { echo "git not found"; exit 1; }

say "Preparing configuration"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from the template."
  echo "Edit it now — at minimum set SUITE_DOMAIN and the two passwords."
else
  echo ".env already exists, leaving it alone."
fi

say "Creating data directories"
# shellcheck disable=SC1091
SUITE_DATA="$(grep -E '^SUITE_DATA=' .env | cut -d= -f2-)"
SUITE_DATA="${SUITE_DATA:-./data}"
mkdir -p "$SUITE_DATA"/{inventory,scan,sec/reports,kick}
echo "Data root: $SUITE_DATA"

say "Preparing SWKick secrets"
./scripts/init-swkick.sh

say "Next steps"
echo "  - Edit .env             — set POSTGRES_PASSWORD, INVENTORY_SECRET_KEY,"
echo "                             and INVENTORY_BASE_URL (this host's IP and port)"
echo "  - Start everything      — docker compose up -d --build"
echo
echo "  The portal is then at http://<this-host-ip> — no DNS needed."
echo "  Adding a domain later? See the README."
