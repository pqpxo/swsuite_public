## version 1
import json
import os
import urllib.error
import urllib.request


class MiniQrRenderError(RuntimeError):
    pass


def render_mini_qr_png(data: str) -> bytes:
    render_url = os.environ.get("MINI_QR_RENDER_URL", "http://mini-qr-renderer:3000/render").strip()
    payload = json.dumps({"data": data}).encode("utf-8")

    request_obj = urllib.request.Request(
        render_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=20) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")

            if response.status != 200:
                raise MiniQrRenderError(f"Renderer returned HTTP {response.status}")

            if "image/png" not in content_type.lower():
                raise MiniQrRenderError(f"Renderer returned unexpected content type: {content_type}")

            return body
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise MiniQrRenderError(f"Renderer HTTP error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise MiniQrRenderError(f"Renderer connection error: {exc.reason}") from exc
    except Exception as exc:
        raise MiniQrRenderError(f"Renderer failed: {exc}") from exc
