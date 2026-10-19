from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS credentials (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('ssh_key','password')),
    enc_private_key BLOB,
    enc_passphrase  BLOB,
    enc_password    BLOB,
    enc_sudo_password BLOB,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS hosts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    hostname        TEXT NOT NULL,
    ssh_port        INTEGER NOT NULL DEFAULT 22,
    ssh_username    TEXT NOT NULL,
    credential_id   INTEGER REFERENCES credentials(id) ON DELETE SET NULL,
    os_label        TEXT,
    last_checked_at TEXT,
    update_count    INTEGER NOT NULL DEFAULT 0,
    reachable       INTEGER NOT NULL DEFAULT 1,
    enabled         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dimension   TEXT NOT NULL CHECK (dimension IN ('priority','host_type','device_type')),
    name        TEXT NOT NULL,
    UNIQUE(dimension, name)
);

CREATE TABLE IF NOT EXISTS host_groups (
    host_id  INTEGER NOT NULL REFERENCES hosts(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (host_id, group_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    host_id      INTEGER REFERENCES hosts(id) ON DELETE SET NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('check','upgrade')),
    trigger      TEXT NOT NULL CHECK (trigger IN ('manual','scheduled')),
    status       TEXT NOT NULL CHECK (status IN ('running','success','failed')),
    started_at   TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at  TEXT,
    packages_json TEXT,
    output_log   TEXT NOT NULL DEFAULT '',
    exit_code    INTEGER
);

CREATE TABLE IF NOT EXISTS settings (
    id                   INTEGER PRIMARY KEY CHECK (id = 1),
    admin_username       TEXT,
    admin_password_hash  TEXT,
    poll_interval_hours  INTEGER NOT NULL DEFAULT 6,
    enc_pushover_token   BLOB,
    enc_pushover_user    BLOB,
    notify_on            TEXT NOT NULL DEFAULT 'new_updates',
    last_notified_state_json TEXT NOT NULL DEFAULT '{}'
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")
    conn.commit()
