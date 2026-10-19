# SWScan v1.0

Self-hosted video inventory scanner. Upload a walkthrough video of your office or workshop, SWScan extracts distinct frames with FFmpeg, sends them to a vision model (Anthropic, OpenAI or Gemini), and builds a searchable, groupable catalog of everything it sees. Print QR labels for bins and drawers.

## Features

- **Scan**: video upload, scene-change frame extraction, perceptual-hash dedupe, AI item recognition
- **Catalog**: items with name, amount, type, condition, zone and notes; group by type or zone; full search
- **Providers**: Anthropic Claude (default), OpenAI, Google Gemini, switchable per scan
- **Find images**: web image search per item via your own SearXNG instance
- **Gallery**: browse extracted frames per scan, set item images from frames
- **QR labels**: per-item QR code linking back to the item page, print layout sized for 62mm Brother QL media
- **Control panel**: scan history, live progress, provider status, stats

## Quick start

```bash
docker compose up -d --build
```

Open http://host:7734, go to **Settings**, add at least one API key, then run a scan.

## API keys (important)

ChatGPT Plus and Gemini subscriptions do **not** include API access. You need
pay-as-you-go API keys:

- Anthropic: console.anthropic.com
- OpenAI: platform.openai.com
- Gemini: aistudio.google.com (has a free tier)

## Pipeline

```
video -> ffmpeg select=scene -> dHash dedupe -> vision provider (JSON) -> grouped items
```

- Scene threshold, max frames and dedupe distance are tunable in Settings.
- Static footage falls back to 0.5 fps sampling.
- Duplicate detections across frames are merged by normalised name + category.

## Find images

Point `SearXNG base URL` in Settings at an instance with JSON output enabled
(`search.formats: [html, json]` in settings.yml).

## Data

Everything lives in `./data` (SQLite DB, uploads, frames). Back that up and you have the lot.

## Filming tips

Move slowly, pause 2 to 3 seconds on each pile or shelf, get close. Distinct
viewpoints beat continuous panning, because scene-change detection picks the frames.

## Roadmap

- v1.1: Coral TPU pre-filter companion service (Frigate-style gating to cut API cost)
- v1.1: image crop editor for item thumbnails
- v1.2: CSV export, NetInventory sync
