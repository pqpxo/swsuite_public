# version 2
from __future__ import annotations

import sqlite3

from app.models import Credential
from app.vault import Vault


def create(conn: sqlite3.Connection, vault: Vault, *, name: str, type: str,
           private_key: str | None, passphrase: str | None,
           password: str | None, sudo_password: str | None) -> int:
    cur = conn.execute(
        """INSERT INTO credentials
           (name, type, enc_private_key, enc_passphrase, enc_password, enc_sudo_password)
           VALUES (?,?,?,?,?,?)""",
        (name, type,
         vault.encrypt(private_key), vault.encrypt(passphrase),
         vault.encrypt(password), vault.encrypt(sudo_password)),
    )
    conn.commit()
    return cur.lastrowid


def get(conn: sqlite3.Connection, vault: Vault, cred_id: int) -> Credential | None:
    row = conn.execute("SELECT * FROM credentials WHERE id=?", (cred_id,)).fetchone()
    if row is None:
        return None
    return Credential(
        id=row["id"], name=row["name"], type=row["type"],
        private_key=vault.decrypt(row["enc_private_key"]),
        passphrase=vault.decrypt(row["enc_passphrase"]),
        password=vault.decrypt(row["enc_password"]),
        sudo_password=vault.decrypt(row["enc_sudo_password"]),
    )


def get_metadata(conn: sqlite3.Connection, cred_id: int) -> sqlite3.Row | None:
    """Read only safe metadata and presence flags; never return decrypted secrets."""
    return conn.execute(
        """SELECT id, name, type, created_at,
                  (enc_private_key IS NOT NULL) AS has_private_key,
                  (enc_passphrase IS NOT NULL) AS has_passphrase,
                  (enc_password IS NOT NULL) AS has_password,
                  (enc_sudo_password IS NOT NULL) AS has_sudo_password
           FROM credentials WHERE id=?""",
        (cred_id,),
    ).fetchone()


def update(conn: sqlite3.Connection, vault: Vault, cred_id: int, *,
           name: str, type: str,
           private_key: str | None = None, passphrase: str | None = None,
           password: str | None = None, sudo_password: str | None = None,
           clear_private_key: bool = False, clear_passphrase: bool = False,
           clear_password: bool = False, clear_sudo_password: bool = False) -> bool:
    """Update an entry without revealing stored values.

    Blank fields preserve encrypted values; explicit clear flags remove them.
    Credentials for the other authentication type are always removed.
    """
    if type not in ("ssh_key", "password"):
        raise ValueError("Unsupported credential type")
    if get_metadata(conn, cred_id) is None:
        return False

    columns = {"name": name, "type": type}
    secret_fields = {
        "enc_private_key": (private_key, clear_private_key, type == "ssh_key"),
        "enc_passphrase": (passphrase, clear_passphrase, type == "ssh_key"),
        "enc_password": (password, clear_password, type == "password"),
        "enc_sudo_password": (sudo_password, clear_sudo_password, True),
    }
    for column, (value, clear, applicable) in secret_fields.items():
        if not applicable or clear:
            columns[column] = None
        elif value:
            columns[column] = vault.encrypt(value)

    assignments = ", ".join(f"{column}=?" for column in columns)
    conn.execute(
        f"UPDATE credentials SET {assignments} WHERE id=?",
        (*columns.values(), cred_id),
    )
    conn.commit()
    return True


def list_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, type, created_at FROM credentials ORDER BY name"
    ).fetchall()


def delete(conn: sqlite3.Connection, cred_id: int) -> None:
    conn.execute("DELETE FROM credentials WHERE id=?", (cred_id,))
    conn.commit()
