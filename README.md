<p align="center">
  <img src="portal/assets/logo-192.png" alt="SWSuite logo" width="140" height="140">
</p>

<h1 align="center">SWSuite</h1>

<p align="center">
  Five self-hosted homelab apps behind one portal and one <code>docker compose up</code>.
</p>

<p align="center">
  <a href="LICENSE"><img alt="Licence: MIT" src="https://img.shields.io/badge/licence-MIT-5b9975"></a>
  <img alt="Docker Compose" src="https://img.shields.io/badge/docker-compose-242e42?logo=docker&logoColor=white">
  <img alt="Self-hosted" src="https://img.shields.io/badge/self--hosted-LAN-242e42">
</p>

<p align="center">
  <img src=".github/assets/portal.png" alt="The SWSuite portal: five app tiles with live status, SWKick selected" width="900">
</p>

| App | What it does | Path | Direct port |
|---|---|---|---|
| **Portal** | The launcher, with a live status light per app | `/` | `80` |
| **SWRack** | Visual rack and data-cabinet documentation | `/rack` | `8088` |
| **SWOps** | Asset inventory, connection trails and QR labels | `/ops` | `8085` |
| **SWScan** | Walk a room on video, get an AI-built item catalogue | `/scan` | `7734` |
| **SWAps** | Generate and deploy Linux provisioning over SSH | `/swaps` | `8080` |
| **SWKick** | Pending apt updates and live upgrades across Linux hosts | `/kick` | `8000` |

Everything is served from one hostname, so a reverse proxy in front of it
needs a single entry.

## The apps

### <img src="portal/assets/apps/rack.png" width="28" height="28" align="top" alt=""> SWRack

Visual documentation for server racks and data cabinets. Build interactive rack
elevations to scale, place equipment from reusable templates (including 0.5U
devices and blanking panels), and upload your own images and icons for each
piece of kit. Colour-coded categories make it easy to pick out storage,
networking or power at a glance, and every device with an IP address gets a
live ping check shown as a status LED on the rack.

*Svelte front end, Fastify and Prisma API, PostgreSQL.*

### <img src="portal/assets/apps/inventory.png" width="28" height="28" align="top" alt=""> SWOps

An asset inventory for everything in a homelab: servers, network gear,
Raspberry Pis, PCs, cables and accessories. Each asset has its own category,
icon, photos and custom fields, and assets link parent to child so you can
follow a connection trail from a device back to the switch and rack it hangs
off. Every asset gets a QR code, and three-up QR labels print straight from the
browser, so scanning the label on a device opens its record. Includes backup
and restore, and remembers brands and locations as you type.

*Flask and gunicorn, SQLite, with a small Node service that renders the QR codes.*

### <img src="portal/assets/apps/scan.png" width="28" height="28" align="top" alt=""> SWScan

Turns a walkthrough video of a room, workshop or storeroom into a searchable
catalogue. Upload a video and SWScan pulls out distinct frames with FFmpeg,
drops near-duplicates, and sends the rest to a vision model (Anthropic Claude,
OpenAI or Google Gemini) to identify what is in shot. The result is a list of
items with quantities, condition, type and location that you can group, search
and edit, with a frame gallery for each scan, optional image lookup through
your own SearXNG instance, and QR labels sized for 62 mm Brother QL tape.
Needs an API key for at least one of the providers.

*Flask, SQLite, FFmpeg.*

### <img src="portal/assets/apps/provision.png" width="28" height="28" align="top" alt=""> SWAps

Point-and-click provisioning for new Linux servers. Choose the software you want
(Docker, Portainer, Netdata, monitoring and admin tools), then configure the
host: SSH hardening, UFW firewall presets, fail2ban, cron jobs, a custom
`.bashrc` and authorised keys. SWAps generates a bash script with a
live preview and a diff view, and deploys it to one or several hosts over SSH
from the browser, streaming the output as it runs. Supports dry runs, rollback
scripts and Ansible export, and keeps SSH credentials in a vault encrypted in
your browser. Targets Ubuntu and Raspberry Pi OS.

*Node.js and Express, React, WebSockets.*

### <img src="portal/assets/apps/kick.png" width="28" height="28" align="top" alt=""> SWKick

An update dashboard for apt-based Linux hosts (Debian, Ubuntu, Raspberry Pi OS,
Proxmox). It connects to each host over SSH without installing an agent, checks
for pending updates on a schedule, and shows how many are waiting on each
machine. One click runs `apt-get upgrade` with the output streamed live, and
every run is logged. Hosts can be grouped by priority, host type and device
type, Pushover notifications tell you when a host newly has updates, and SSH
keys, passwords and sudo passwords are stored encrypted. Has its own admin
login.

*FastAPI, SQLite, Paramiko.*

## Requirements

- A Linux host with Docker Engine and the Compose v2 plugin
- About 4 GB of RAM and a few GB of disk for images
- Optional: an Anthropic, OpenAI or Google API key for SWScan's vision features

## Install

```bash
git clone https://github.com/pqpxo/swsuite_public.git swsuite
cd swsuite
./scripts/bootstrap.sh
```

`bootstrap.sh` creates `.env` from `.env.example`, makes the data folders,
and runs `scripts/init-swkick.sh`, which generates SWKick's vault key and
secrets and prints its first `admin` password.

Then edit `.env`:

- `POSTGRES_PASSWORD` and `INVENTORY_SECRET_KEY`: set both to long random values.
- `INVENTORY_BASE_URL`: this host's address as other devices reach it, for
  example `http://192.168.1.50`, so printed QR labels open from a phone.
- AI provider keys, if you want SWScan's vision features.

Start it:

```bash
docker compose up -d --build
```

The portal is then at `http://<this-host>`. The first build takes a few
minutes.

## How it works

Caddy serves the portal at `/` and routes each path to its app's container.
It strips the prefix before forwarding and sends `X-Forwarded-Prefix`, so
every app still sees itself at its own root and puts the prefix back into the
links it emits.

```
  browser  →  <host>:80  →  Caddy
                             ├── /        portal
                             ├── /rack    SWRack
                             ├── /ops     SWOps
                             ├── /scan    SWScan
                             ├── /swaps   SWAps
                             └── /kick    SWKick
```

Each app also publishes its own port for direct access. SWRack and SWOps have
their mount path built in, so use them through the portal.

The portal's tiles can be reordered: press the pencil button at the top right,
then drag. The order is saved per browser.

## Adding a domain and HTTPS

Put any reverse proxy in front (NGINX Proxy Manager, Traefik, another Caddy)
and point one hostname at `<this-host>:80`. Turn on WebSocket support (SWAps'
deploy console), turn off response buffering (SWKick's live upgrade output),
and allow large uploads (SWScan accepts video up to 2 GB). Then set
`INVENTORY_BASE_URL` to the new `https://` address and run
`docker compose up -d homelab-inventory`.

## Data and backups

- `./data` (or `SUITE_DATA` in `.env`): SWOps, SWScan and SWKick data.
- `./secrets/swkick-master.key`: decrypts the SSH credentials SWKick stores.
  Back it up, but not alongside `./data`.
- Docker volumes `swsuite_rack_postgres_data` and `swsuite_rack_asset_data`:
  SWRack's database and uploads.

## Updating

```bash
git pull --ff-only
docker compose up -d --build
docker compose restart proxy     # only needed when caddy/Caddyfile changed
```

## Security

This is built for a trusted LAN. Only SWKick has a login of its own; the
portal and the other apps have none. SWAps and SWKick hold SSH access to your
hosts. Do not expose the suite to the internet without adding authentication
at your reverse proxy first.

## Adding your own app

Put it in `apps/<name>`, add a service to `docker-compose.yml`, add a
`handle_path` route and a `/healthz/<id>` probe to `caddy/Caddyfile`, and add
an entry and a 256×256 logo to `portal/config.js` and `portal/assets/apps/`.
SWKick is the most recent example to copy.

## Licence

MIT. See [LICENSE](LICENSE).
