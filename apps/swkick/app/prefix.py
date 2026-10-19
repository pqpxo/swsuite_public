# version 1
"""Mount-path support for running behind a path-routing reverse proxy.

The SWSuite proxy serves SWKick under /kick: it strips the prefix before
forwarding, so routing here is unchanged, and sends X-Forwarded-Prefix: /kick
so the app knows what to put back into the URLs it emits.

This module puts it back in three places:

* redirects  - a root-relative Location header gets the prefix prepended
* cookies    - the session cookie is scoped to the prefix rather than "/",
               so it is not sent to the other apps sharing the hostname
* pages      - templates read ``base`` (via ``context``) for their links,
               and app.js reads it from <html data-base>

With no header, or a malformed one, the prefix is "" and nothing changes, so
SWKick still runs standalone on its own port exactly as before.
"""
from __future__ import annotations

import re

HEADER = b"x-forwarded-prefix"
SCOPE_KEY = "swkick.prefix"

# One or more /segment parts, no trailing slash, no "." or ".." segments.
# Anything else is ignored rather than echoed into pages and headers.
_VALID = re.compile(r"^(/(?!\.+(?:/|$))[A-Za-z0-9._~-]+)+$")
_COOKIE_ROOT_PATH = re.compile(rb"(;\s*[Pp]ath=)/(?=;|$)")


def parse(raw: bytes | None) -> str:
    if not raw:
        return ""
    value = raw.decode("latin-1").strip().rstrip("/")
    return value if _VALID.match(value) else ""


def from_scope(scope) -> str:
    for key, value in scope.get("headers", []):
        if key == HEADER:
            return parse(value)
    return ""


def context(request) -> dict:
    """Jinja context processor: exposes the prefix to templates as ``base``."""
    return {"base": request.scope.get(SCOPE_KEY, "")}


class PrefixMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        prefix = from_scope(scope)
        scope[SCOPE_KEY] = prefix
        if not prefix:
            await self.app(scope, receive, send)
            return

        encoded = prefix.encode("latin-1")

        async def send_with_prefix(message):
            if message["type"] == "http.response.start":
                headers = []
                for key, value in message.get("headers", []):
                    if key == b"location" and value.startswith(b"/") and not value.startswith(b"//"):
                        value = encoded + value
                    elif key == b"set-cookie":
                        value = _COOKIE_ROOT_PATH.sub(rb"\g<1>" + encoded, value, count=1)
                    headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_prefix)
