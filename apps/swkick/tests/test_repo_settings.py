import pytest

from app import db
from app.vault import Vault, generate_key
from app.repos import settings as repo


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(c)
    return c


def test_get_defaults(conn):
    s = repo.get(conn)
    assert s["poll_interval_hours"] == 6
    assert s["notify_on"] == "new_updates"
    assert s["last_notified_state_json"] == "{}"


def test_set_admin_and_poll(conn):
    repo.set_admin(conn, username="admin", password_hash="hash123")
    repo.set_poll_interval(conn, 12)
    s = repo.get(conn)
    assert s["admin_username"] == "admin"
    assert s["admin_password_hash"] == "hash123"
    assert s["poll_interval_hours"] == 12


def test_pushover_encrypted(conn):
    v = Vault(generate_key())
    repo.set_pushover(conn, v, token="tok", user="usr")
    raw = conn.execute("SELECT enc_pushover_token FROM settings WHERE id=1").fetchone()
    assert b"tok" not in (raw["enc_pushover_token"] or b"")
    tok, usr = repo.get_pushover(conn, v)
    assert (tok, usr) == ("tok", "usr")


def test_notified_state_roundtrip(conn):
    repo.set_notified_state(conn, {"web-01": 3})
    assert repo.get_notified_state(conn) == {"web-01": 3}
