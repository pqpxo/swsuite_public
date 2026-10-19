from app.repos import settings as settings_repo
from app.security import verify_password


def test_bootstrap_seeds_admin_when_missing(state, monkeypatch):
    monkeypatch.setenv("KICKER_BOOTSTRAP_PASSWORD", "firstpass")
    from app.app import maybe_bootstrap_admin
    maybe_bootstrap_admin(state.conn)
    s = settings_repo.get(state.conn)
    assert s["admin_username"] == "admin"
    assert verify_password("firstpass", s["admin_password_hash"])


def test_bootstrap_noop_when_admin_exists(state, monkeypatch):
    settings_repo.set_admin(state.conn, username="me", password_hash="x")
    monkeypatch.setenv("KICKER_BOOTSTRAP_PASSWORD", "ignored")
    from app.app import maybe_bootstrap_admin
    maybe_bootstrap_admin(state.conn)
    assert settings_repo.get(state.conn)["admin_username"] == "me"
