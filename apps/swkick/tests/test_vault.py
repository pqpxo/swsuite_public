import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.vault import Vault, generate_key, load_key


def test_roundtrip():
    v = Vault(generate_key())
    blob = v.encrypt("super-secret")
    assert blob != b"super-secret"
    assert v.decrypt(blob) == "super-secret"


def test_encrypt_none_returns_none():
    v = Vault(generate_key())
    assert v.encrypt(None) is None
    assert v.decrypt(None) is None


def test_tamper_rejected():
    v = Vault(generate_key())
    blob = bytearray(v.encrypt("secret"))
    blob[-1] ^= 0x01
    with pytest.raises(InvalidToken):
        v.decrypt(bytes(blob))


def test_load_key_from_file(tmp_path):
    key = generate_key()
    p = tmp_path / "master.key"
    p.write_bytes(key)
    assert load_key(str(p)) == key
