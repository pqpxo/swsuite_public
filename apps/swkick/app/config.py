from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    master_key_file: str
    db_path: str
    poll_interval_hours: int
    session_secret: str

    @classmethod
    def from_env(cls) -> "Config":
        master_key_file = os.environ.get("KICKER_MASTER_KEY_FILE")
        if not master_key_file:
            raise RuntimeError("KICKER_MASTER_KEY_FILE is required")
        return cls(
            master_key_file=master_key_file,
            db_path=os.environ.get("KICKER_DB_PATH", "/data/kicker.sqlite"),
            poll_interval_hours=int(os.environ.get("KICKER_POLL_INTERVAL_HOURS", "6")),
            session_secret=os.environ.get("KICKER_SESSION_SECRET", "change-me-in-prod"),
        )
