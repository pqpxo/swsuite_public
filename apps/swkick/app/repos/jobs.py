from __future__ import annotations

import json
import sqlite3


def create(conn: sqlite3.Connection, *, host_id: int | None, kind: str,
           trigger: str) -> int:
    cur = conn.execute(
        "INSERT INTO jobs (host_id, kind, trigger, status) VALUES (?,?,?, 'running')",
        (host_id, kind, trigger),
    )
    conn.commit()
    return cur.lastrowid


def append_output(conn: sqlite3.Connection, job_id: int, text: str) -> None:
    conn.execute(
        "UPDATE jobs SET output_log = output_log || ? WHERE id=?", (text, job_id)
    )
    conn.commit()


def finish(conn: sqlite3.Connection, job_id: int, *, status: str,
           exit_code: int | None, packages: list[str] | None = None) -> None:
    conn.execute(
        """UPDATE jobs SET status=?, exit_code=?, packages_json=?,
           finished_at=datetime('now') WHERE id=?""",
        (status, exit_code, json.dumps(packages) if packages is not None else None,
         job_id),
    )
    conn.commit()


def get(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()


def list_recent(conn: sqlite3.Connection, *, limit: int = 100,
                host_id: int | None = None) -> list[sqlite3.Row]:
    if host_id is None:
        return conn.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return conn.execute(
        "SELECT * FROM jobs WHERE host_id=? ORDER BY id DESC LIMIT ?",
        (host_id, limit),
    ).fetchall()
