from __future__ import annotations

from typing import Protocol

import httpx


def newly_updated_hosts(prev: dict[str, int], new: dict[str, int]) -> list[str]:
    """Hosts that should trigger a notification: those whose upgradable count
    rose (including 0 -> n and a new host appearing with n>0, or n increasing)."""
    result = []
    for name, count in new.items():
        if count > 0 and count > prev.get(name, 0):
            result.append(name)
    return result


class Notifier(Protocol):
    def send(self, title: str, message: str) -> None: ...


class PushoverNotifier:
    API = "https://api.pushover.net/1/messages.json"

    def __init__(self, token: str, user: str,
                 client: httpx.Client | None = None) -> None:
        self._token = token
        self._user = user
        self._client = client or httpx.Client(timeout=10)

    def send(self, title: str, message: str) -> None:
        self._client.post(self.API, data={
            "token": self._token, "user": self._user,
            "title": title, "message": message,
        })


class NullNotifier:
    def send(self, title: str, message: str) -> None:
        return None
