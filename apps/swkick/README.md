# SWKick — Linux Update Dashboard

<img src="app/static/swkick-logo.png" alt="SWKick logo" width="110" height="110">

SWKick was previously branded as **Kicker**. Repository paths, Docker service/volume names,
internal paths, and existing `KICKER_*` environment variables are intentionally unchanged
for backwards compatibility with existing deployments.

Self-hosted dashboard for apt-based Linux hosts (Debian, Ubuntu, Raspberry Pi OS,
Proxmox). Shows pending updates, runs `apt-get update`/`upgrade` over agentless SSH
with live output, sends Pushover notifications, logs every run, groups hosts, and
stores credentials in an encrypted vault.

## Quick start (Docker)

1. **Generate a master key** (encrypts the credential vault). Keep it OUTSIDE the
   repo and back it up — losing it means losing stored credentials.
   ```bash
   python -c "from cryptography.fernet import Fernet; open('master.key','wb').write(Fernet.generate_key())"
   ```
2. **Set environment** (a strong random session secret + a first-run admin password):
   ```bash
   export KICKER_SESSION_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
   export KICKER_BOOTSTRAP_PASSWORD='choose-a-strong-password'
   ```
3. **Start it:**
   ```bash
   docker compose up -d --build
   ```
4. Open `http://<host-ip>:8000` and log in as `admin` with the bootstrap password.
   Change it under **Settings**.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `KICKER_MASTER_KEY_FILE` | (required) | Path to the Fernet master key |
| `KICKER_DB_PATH` | `/data/kicker.sqlite` | SQLite database path |
| `KICKER_POLL_INTERVAL_HOURS` | `6` | Background update-check interval |
| `KICKER_SESSION_SECRET` | `change-me-in-prod` | Signs session cookies |
| `KICKER_BOOTSTRAP_PASSWORD` | `admin` | First-run admin password (used only if no admin set) |

## Adding hosts

1. **Credentials** → add an SSH key or password, plus the sudo password for that host.
2. **Add host** → name, IP, SSH user, pick the credential, assign groups.
3. The app SSHes in, runs `apt-get update` + `apt list --upgradable`, and shows the count.
4. Click **Update & Upgrade** to run `apt-get -y upgrade` with live output.

## Grouping

Hosts can be grouped along three user-managed dimensions — **Priority**, **Host Type**,
and **Device Type**. Define the values under **Groups**, assign them when adding a host,
and switch the dashboard view with the **Group by** filter.

## Notifications

Set your Pushover API token + user key under **Settings**. You get a push when a host
*newly* has updates (de-duplicated — no repeats for the same pending set).

## Running under a path prefix

Behind a reverse proxy that serves SWKick under a sub-path (SWSuite uses `/kick`),
the proxy should strip the prefix and send `X-Forwarded-Prefix: /kick`. SWKick then
prefixes its links, redirects and API calls, and scopes its session cookie to that
path. Without the header nothing changes, so it still runs standalone on its own port.

## Security notes

- Credentials (SSH keys, passwords, sudo passwords, Pushover tokens) are encrypted at
  rest with the master key. The master key must live outside the repo and the data
  volume, with restricted file permissions.
- The sudo password is sent over the SSH channel via stdin, never on the command line.
- Single admin login; passwords are bcrypt-hashed.
- **Run on a trusted LAN.** For anything beyond that, put kicker behind a reverse proxy
  with HTTPS and do not expose it to the internet.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt   # Windows: .venv/Scripts/pip
.venv/bin/pytest                             # run the test suite
```

Run locally without Docker:

```bash
python -c "from cryptography.fernet import Fernet; open('dev-master.key','wb').write(Fernet.generate_key())"
KICKER_MASTER_KEY_FILE=dev-master.key KICKER_DB_PATH=dev.sqlite \
  .venv/bin/uvicorn main:app --port 8000
```
