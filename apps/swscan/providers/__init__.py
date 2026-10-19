"""Vision provider abstraction. Each provider takes JPEG bytes and returns a
list of detected item dicts: {name, category, quantity, condition}."""
import base64
import json
import re
import requests

PROMPT = (
    "You are an inventory cataloguing assistant. Identify every distinct physical item "
    "or group of items visible in this image of a home office / workshop. Be specific "
    "(e.g. 'ESP32 dev board' not 'circuit board', 'HDMI cable' not 'cable' where possible). "
    "For tangled or bulk items give an estimated quantity like '~6' or 'several'.\n"
    "Respond with ONLY a JSON array, no markdown fences, no prose. Each element:\n"
    '{"name": str, "category": str (one of: cables, electronics, computing, tools, '
    'peripherals, storage-media, stationery, furniture, networking, audio-video, other), '
    '"quantity": str, "condition": str (new/used/worn/unknown), '
    '"box": [x0, y0, x1, y1] ints 0-1000 normalised to image width/height, the tightest '
    'bounding box around the item or pile}\n'
    "If nothing identifiable is visible, respond with []."
)

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-5.4-mini",
    "gemini": "gemini-2.0-flash",
}

PROVIDER_LABELS = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI (ChatGPT)",
    "gemini": "Google (Gemini)",
}


def _parse_items(text):
    """Extract a JSON array from a model response, tolerating fences/preamble."""
    text = text.strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    items = []
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, dict) and entry.get("name"):
            box = entry.get("box")
            if not (isinstance(box, list) and len(box) == 4
                    and all(isinstance(v, (int, float)) for v in box)):
                box = None
            else:
                box = [max(0, min(1000, int(v))) for v in box]
            items.append({
                "name": str(entry.get("name"))[:200],
                "category": str(entry.get("category", "other")).lower()[:100],
                "quantity": str(entry.get("quantity", "1"))[:40],
                "condition": str(entry.get("condition", "unknown"))[:80],
                "box": box,
            })
    return items


def _anthropic(image_b64, api_key, model, prompt):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1500,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                     "media_type": "image/jpeg", "data": image_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        },
        timeout=90,
    )
    r.raise_for_status()
    blocks = r.json().get("content", [])
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return _parse_items(text)


def _openai(image_b64, api_key, model, prompt):
    body = {
        "model": model,
        # GPT-5.x renamed max_tokens -> max_completion_tokens; retry handles older models
        "max_completion_tokens": 1500,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.post("https://api.openai.com/v1/chat/completions",
                      headers=headers, json=body, timeout=90)
    if r.status_code == 400 and "max_completion_tokens" in r.text:
        body["max_tokens"] = body.pop("max_completion_tokens")
        r = requests.post("https://api.openai.com/v1/chat/completions",
                          headers=headers, json=body, timeout=90)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return _parse_items(text)


def _gemini(image_b64, api_key, model, prompt):
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": api_key},
        json={
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                    {"text": prompt},
                ],
            }],
        },
        timeout=90,
    )
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    text = "\n".join(p.get("text", "") for p in parts)
    return _parse_items(text)


_DISPATCH = {"anthropic": _anthropic, "openai": _openai, "gemini": _gemini}


def analyze_frame(image_bytes, provider, api_key, model, prompt=None):
    """Returns (items, error). Never raises."""
    fn = _DISPATCH.get(provider)
    if not fn:
        return [], f"Unknown provider '{provider}'"
    if not api_key:
        return [], f"No API key configured for {provider}"
    b64 = base64.b64encode(image_bytes).decode()
    try:
        return fn(b64, api_key, model, prompt or PROMPT), None
    except requests.HTTPError as e:
        body = e.response.text[:300] if e.response is not None else ""
        return [], f"{provider} HTTP {e.response.status_code if e.response is not None else '?'}: {body}"
    except Exception as e:  # noqa: BLE001
        return [], f"{provider} error: {e}"
