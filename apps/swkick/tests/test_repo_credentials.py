import pytest

from app import db
from app.vault import Vault, generate_key
from app.repos import credentials as repo


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(c)
    return c


@pytest.fixture
def vault():
    return Vault(generate_key())


def test_create_and_get_decrypts(conn, vault):
    cid = repo.create(
        conn, vault,
        name="prod-key", type="ssh_key",
        private_key="-----KEY-----", passphrase="pp",
        password=None, sudo_password="sudopw",
    )
    cred = repo.get(conn, vault, cid)
    assert cred.name == "prod-key"
    assert cred.private_key == "-----KEY-----"
    assert cred.passphrase == "pp"
    assert cred.sudo_password == "sudopw"


def test_secrets_stored_encrypted(conn, vault):
    cid = repo.create(
        conn, vault, name="p", type="password",
        private_key=None, passphrase=None,
        password="plaintextpw", sudo_password=None,
    )
    raw = conn.execute(
        "SELECT enc_password FROM credentials WHERE id=?", (cid,)
    ).fetchone()["enc_password"]
    assert b"plaintextpw" not in raw


def test_list_omits_secrets(conn, vault):
    repo.create(conn, vault, name="p", type="password",
                private_key=None, passphrase=None,
                password="pw", sudo_password=None)
    listed = repo.list_all(conn)
    assert listed[0]["name"] == "p"
    assert "enc_password" not in listed[0].keys()
    assert set(listed[0].keys()) == {"id", "name", "type", "created_at"}


def test_delete(conn, vault):
    cid = repo.create(conn, vault, name="p", type="password",
                      private_key=None, passphrase=None,
                      password="pw", sudo_password=None)
    repo.delete(conn, cid)
    assert repo.get(conn, vault, cid) is None
