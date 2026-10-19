from app.security import hash_password, verify_password, make_session, read_session


def test_password_hash_roundtrip():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_session_token_roundtrip():
    secret = "s3cr3t"
    token = make_session("admin", secret)
    assert read_session(token, secret) == "admin"


def test_session_token_rejects_bad_secret():
    token = make_session("admin", "secretA")
    assert read_session(token, "secretB") is None


def test_session_token_rejects_garbage():
    assert read_session("not-a-token", "secret") is None
