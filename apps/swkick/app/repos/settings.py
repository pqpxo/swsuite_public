from __future__ import annotations

import json
import sqlite3

from app.vault import Vault


def get(conn: sqlite3.Connection) -> sqlite3.Row:
    return conn.execute("SELECT * FROM settings WHERE id=1").fetchone()


def set_admin(conn: sqlite3.Connection, *, username: str, password_hash: str) -> None:
    conn.execute(
        "UPDATE settings SET admin_username=?, admin_password_hash=? WHERE id=1",
        (username, password_hash),
    )
    conn.commit()


def set_poll_interval(conn: sqlite3.Connection, hours: int) -> None:
    conn.execute("UPDATE settings SET poll_interval_hours=? WHERE id=1", (hours,))
    conn.commit()


def set_pushover(conn: sqlite3.Connection, vault: Vault, *, token: str | None,
                 user: str | None) -> None:
    conn.execute(
        "UPDATE settings SET enc_pushover_token=?, enc_pushover_user=? WHERE id=1",
        (vault.encrypt(token), vault.encrypt(user)),
    )
    conn.commit()


def get_pushover(conn: sqlite3.Connection, vault: Vault) -> tuple[str | None, str | None]:
    row = get(conn)
    return vault.decrypt(row["enc_pushover_token"]), vault.decrypt(row["enc_pushover_user"])


def set_notified_state(conn: sqlite3.Connection, state: dict) -> None:
    conn.execute(
        "UPDATE settings SET last_notified_state_json=? WHERE id=1",
        (json.dumps(state),),
    )
    conn.commit()


def get_notified_state(conn: sqlite3.Connection) -> dict:
    return json.loads(get(conn)["last_notified_state_json"])
