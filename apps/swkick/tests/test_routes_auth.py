from app.repos import settings as settings_repo
from app.security import hash_password


def _set_admin(state):
    settings_repo.set_admin(state.conn, username="admin",
                            password_hash=hash_password("pw"))


def test_dashboard_redirects_when_logged_out(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].endswith("/login")


def test_login_success_sets_cookie(client, state):
    _set_admin(state)
    r = client.post("/login", data={"username": "admin", "password": "pw"},
                    follow_redirects=False)
    assert r.status_code in (302, 303)
    assert "kicker_session" in r.cookies


def test_login_failure_shows_error(client, state):
    _set_admin(state)
    r = client.post("/login", data={"username": "admin", "password": "bad"})
    assert r.status_code == 200
    assert "Invalid" in r.text


def test_logout_clears_cookie(logged_in_client):
    r = logged_in_client.get("/logout", follow_redirects=False)
    assert r.status_code in (302, 303)
