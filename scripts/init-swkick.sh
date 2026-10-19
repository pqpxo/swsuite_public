#!/usr/bin/env bash
# version 1
# One-off setup for SWKick. Safe to re-run: it never replaces a key or a value
# that already exists.
#
#   ./scripts/init-swkick.sh
#
# Creates:
#   secrets/swkick-master.key   Fernet key that encrypts SWKick's credential
#                               vault (SSH keys, passwords, Pushover tokens).
#   data/kick/                  SWKick's SQLite database lives here.
# Fills in, in .env:
#   KICK_SESSION_SECRET         signs login cookies
#   KICK_BOOTSTRAP_PASSWORD     first-run password for the "admin" user
#
# Moving an existing SWKick install in? Copy its master.key to
# secrets/swkick-master.key and its kicker.sqlite to data/kick/ BEFORE running
# this, and the existing hosts and credentials carry straight over.
set -euo pipefail

cd "$(dirname "$0")/.."

say() { printf '\n\033[1;33m==>\033[0m %s\n' "$1"; }
random() { head -c "$1" /dev/urandom | base64 | tr -d '\n=' | tr '+/' '-_'; }

[ -f .env ] || { echo ".env not found. Run: cp .env.example .env"; exit 1; }

say "Vault master key"
key="secrets/swkick-master.key"
mkdir -p secrets
chmod 700 secrets
if [ -d "$key" ]; then
  # Docker creates a directory here if the stack was started before this ran.
  rmdir "$key" 2>/dev/null || { echo "$key is a non-empty directory; fix by hand."; exit 1; }
fi
if [ -s "$key" ]; then
  echo "Keeping existing $key"
else
  # A Fernet key is 32 random bytes, URL-safe base64 encoded, with padding.
  ( umask 077; printf '%s=\n' "$(random 32)" > "$key" )
  echo "Created $key  (back this up somewhere other than ./data)"
fi
chmod 600 "$key"

say "Data directory"
SUITE_DATA="$(grep -E '^SUITE_DATA=' .env | cut -d= -f2- || true)"
SUITE_DATA="${SUITE_DATA:-./data}"
mkdir -p "$SUITE_DATA/kick"
echo "$SUITE_DATA/kick"

# Set NAME=value in .env only if NAME is missing or empty.
set_if_empty() {
  local name="$1" value="$2"
  if grep -qE "^${name}=.+" .env; then
    echo "Keeping existing $name"
    return 1
  elif grep -qE "^${name}=" .env; then
    sed -i "s|^${name}=.*|${name}=${value}|" .env
  else
    printf '%s=%s\n' "$name" "$value" >> .env
  fi
  echo "Set $name"
}

say "Secrets in .env"
set_if_empty KICK_SESSION_SECRET "$(random 32)" || true
password="$(random 12)"
if set_if_empty KICK_BOOTSTRAP_PASSWORD "$password"; then
  printf '\n  First login:  admin / %s\n  Change it under Settings once you are in.\n' "$password"
fi

say "Done"
echo "  Start it with:  docker compose up -d --build swkick proxy"
