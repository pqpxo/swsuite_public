# version 2
from __future__ import annotations

import sqlite3

DIMENSIONS = ("priority", "host_type", "device_type")


def create(conn: sqlite3.Connection, dimension: str, name: str) -> int:
    if dimension not in DIMENSIONS:
        raise ValueError(f"invalid dimension: {dimension}")
    name = name.strip()
    if not name:
        raise ValueError("Group name is required")
    cur = conn.execute(
        "INSERT INTO groups (dimension, name) VALUES (?,?)", (dimension, name)
    )
    conn.commit()
    return cur.lastrowid


def get(conn: sqlite3.Connection, group_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM groups WHERE id=?", (group_id,)).fetchone()


def count_hosts(conn: sqlite3.Connection, group_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS host_count FROM host_groups WHERE group_id=?", (group_id,)
    ).fetchone()
    return row["host_count"]


def list_by_dimension(conn: sqlite3.Connection, dimension: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM groups WHERE dimension=? ORDER BY name", (dimension,)
    ).fetchall()


def list_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM groups ORDER BY dimension, name").fetchall()


def delete(conn: sqlite3.Connection, group_id: int) -> None:
    conn.execute("DELETE FROM groups WHERE id=?", (group_id,))
    conn.commit()
