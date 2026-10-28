#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Import a SWOps backup ZIP (Settings → Backup in the app) into the running
# suite. Run from this machine; the ZIP is pushed to the host and applied there.
#
#   ./scripts/import-swops-backup.sh user@suite-host ~/Downloads/netinventory_backup_20260514_214126.zip
#
# What it does on the host:
#   1. checks the ZIP holds inventory.db (and optionally uploads/)
#   2. stops the SWOps container so SQLite is not written mid-copy
#   3. moves the current data aside to data/inventory.pre-import-<timestamp>/
#   4. puts the backup's inventory.db and uploads/ in place
#   5. starts the container — the app migrates the schema on start-up
#   6. reports what the app now sees
# Nothing is deleted: the previous data directory is kept beside the new one.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

TARGET_HOST="${1:-}"; ZIP="${2:-}"
TARGET_PATH="${3:-/home/${TARGET_HOST%%@*}/docker/swsuite}"
if [ -z "$TARGET_HOST" ] || [ -z "$ZIP" ]; then
  echo "usage: $0 <user@host> <backup.zip> [remote-suite-path]" >&2; exit 1
fi
[ -f "$ZIP" ] || { echo "not found: $ZIP" >&2; exit 1; }

echo "==> Checking the ZIP"
python - "$ZIP" <<'PY'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as a:
    names = a.namelist()
    assert "inventory.db" in names, "ZIP does not contain inventory.db — is this a SWOps backup?"
    ups = [n for n in names if n.startswith("uploads/") and not n.endswith("/")]
    print(f"    inventory.db present, {len(ups)} uploaded files")
PY

echo "==> Copying to $TARGET_HOST"
REMOTE_ZIP="/tmp/swops-import-$$.zip"
scp -q "$ZIP" "$TARGET_HOST:$REMOTE_ZIP"

# No -n here: the remote script travels on stdin.
ssh "$TARGET_HOST" bash -s -- "$TARGET_PATH" "$REMOTE_ZIP" <<'REMOTE'
set -euo pipefail
SUITE="$1"; ZIP="$2"
cd "$SUITE"
DATA="$(grep -E '^SUITE_DATA=' .env 2>/dev/null | cut -d= -f2-)"; DATA="${DATA:-./data}"
INV="$DATA/inventory"
STAMP="$(date +%Y%m%d-%H%M%S)"

echo "==> Stopping SWOps"
docker compose stop homelab-inventory >/dev/null

echo "==> Keeping the current data at $INV.pre-import-$STAMP"
if [ -d "$INV" ]; then sudo mv "$INV" "$INV.pre-import-$STAMP" 2>/dev/null || mv "$INV" "$INV.pre-import-$STAMP"; fi
mkdir -p "$INV/uploads"

echo "==> Unpacking the backup"
TMP="$(mktemp -d)"
python3 - "$ZIP" "$TMP" <<'PY'
import sys, zipfile, os
with zipfile.ZipFile(sys.argv[1]) as a:
    for m in a.infolist():
        # only the two things a backup may contain; never anything outside them
        if m.filename == "inventory.db" or (m.filename.startswith("uploads/") and ".." not in m.filename):
            a.extract(m, sys.argv[2])
PY
cp "$TMP/inventory.db" "$INV/inventory.db"
if [ -d "$TMP/uploads" ]; then cp -a "$TMP/uploads/." "$INV/uploads/"; fi
rm -rf "$TMP" "$ZIP"
printf "    inventory.db %s bytes, %s uploaded files\n" "$(stat -c %s "$INV/inventory.db")" "$(find "$INV/uploads" -type f | wc -l)"

echo "==> Starting SWOps (schema migrates on start-up)"
docker compose start homelab-inventory >/dev/null
sleep 6

echo "==> What the app sees now"
# docker exec needs -i to pass the heredoc through to python's stdin.
docker exec -i swsuite-inventory python3 - <<'PY'
import os, sqlite3
c = sqlite3.connect("/app/data/inventory.db")
def n(t):
    try: return c.execute(f"select count(*) from {t}").fetchone()[0]
    except Exception as e: return f"- ({e})"
print(f"    assets={n('asset')} categories={n('category')} photos={n('asset_photo')}")
# The backup carries the old instance's QR base address in its settings table. Printed
# labels are built from base + /ops/a/<key>, so a stale base would point every new label
# at the old host. Clear it, and the suite's INVENTORY_BASE_URL (APP_BASE_URL here) applies.
row = c.execute("select value from app_setting where key='qr_base_url'").fetchone()
stored = row[0] if row and row[0] else ""
want = os.environ.get("APP_BASE_URL", "")
if stored and stored.rstrip("/") != want.rstrip("/"):
    c.execute("update app_setting set value=NULL where key='qr_base_url'"); c.commit()
    print(f"    qr_base_url: was {stored} (the old instance) -> cleared; new labels use {want or 'the request host'}")
else:
    print(f"    qr_base_url: {stored or '(not set)'} -> new labels use {want or 'the request host'}")
PY
printf "    app answers: %s\n" "$(curl -s -o /dev/null -w '%{http_code}' -m 15 http://localhost/ops/)"
REMOTE
echo "==> Done. Previous data kept on the host as data/inventory.pre-import-<timestamp>; remove it once you are happy."
