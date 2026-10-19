from __future__ import annotations

import sqlite3


def create(conn: sqlite3.Connection, *, name: str, hostname: str, ssh_port: int,
           ssh_username: str, credential_id: int | None, os_label: str | None) -> int:
    cur = conn.execute(
        """INSERT INTO hosts (name, hostname, ssh_port, ssh_username, credential_id, os_label)
           VALUES (?,?,?,?,?,?)""",
        (name, hostname, ssh_port, ssh_username, credential_id, os_label),
    )
    conn.commit()
    return cur.lastrowid


def get(conn: sqlite3.Connection, host_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM hosts WHERE id=?", (host_id,)).fetchone()


def list_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM hosts ORDER BY name").fetchall()


def list_enabled(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM hosts WHERE enabled=1 ORDER BY name").fetchall()


def update(conn: sqlite3.Connection, host_id: int, *, name: str, hostname: str,
           ssh_port: int, ssh_username: str, credential_id: int | None,
           os_label: str | None) -> None:
    conn.execute(
        """UPDATE hosts SET name=?, hostname=?, ssh_port=?, ssh_username=?,
           credential_id=?, os_label=? WHERE id=?""",
        (name, hostname, ssh_port, ssh_username, credential_id, os_label, host_id),
    )
    conn.commit()


def update_status(conn: sqlite3.Connection, host_id: int, *, update_count: int,
                  reachable: bool, last_checked_at: str,
                  os_label: str | None = None) -> None:
    if os_label is None:
        conn.execute(
            "UPDATE hosts SET update_count=?, reachable=?, last_checked_at=? WHERE id=?",
            (update_count, 1 if reachable else 0, last_checked_at, host_id),
        )
    else:
        conn.execute(
            """UPDATE hosts SET update_count=?, reachable=?, last_checked_at=?,
               os_label=? WHERE id=?""",
            (update_count, 1 if reachable else 0, last_checked_at, os_label, host_id),
        )
    conn.commit()


def set_enabled(conn: sqlite3.Connection, host_id: int, enabled: bool) -> None:
    conn.execute("UPDATE hosts SET enabled=? WHERE id=?",
                 (1 if enabled else 0, host_id))
    conn.commit()


def set_groups(conn: sqlite3.Connection, host_id: int, group_ids: list[int]) -> None:
    conn.execute("DELETE FROM host_groups WHERE host_id=?", (host_id,))
    conn.executemany(
        "INSERT INTO host_groups (host_id, group_id) VALUES (?,?)",
        [(host_id, gid) for gid in group_ids],
    )
    conn.commit()


def group_ids_for(conn: sqlite3.Connection, host_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT group_id FROM host_groups WHERE host_id=?", (host_id,)
    ).fetchall()
    return [r["group_id"] for r in rows]


def list_grouped(conn: sqlite3.Connection, dimension: str) -> dict[str, list[sqlite3.Row]]:
    """Return {group_name: [host rows]} for one dimension.
    Hosts with no group in this dimension go under 'Ungrouped'."""
    hosts = list_all(conn)
    result: dict[str, list[sqlite3.Row]] = {}
    for h in hosts:
        row = conn.execute(
            """SELECT g.name AS gname FROM host_groups hg
               JOIN groups g ON g.id = hg.group_id
               WHERE hg.host_id=? AND g.dimension=?""",
            (h["id"], dimension),
        ).fetchone()
        key = row["gname"] if row else "Ungrouped"
        result.setdefault(key, []).append(h)
    return result


def delete(conn: sqlite3.Connection, host_id: int) -> None:
    conn.execute("DELETE FROM hosts WHERE id=?", (host_id,))
    conn.commit()
