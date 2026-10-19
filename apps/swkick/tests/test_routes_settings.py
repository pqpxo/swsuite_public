from app.repos import settings as settings_repo
from app.security import verify_password


def test_set_admin_password(logged_in_client, state):
    r = logged_in_client.post("/settings/admin", data={
        "username": "admin", "password": "newpass"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    s = settings_repo.get(state.conn)
    assert verify_password("newpass", s["admin_password_hash"])


def test_set_poll_interval(logged_in_client, state):
    logged_in_client.post("/settings/poll", data={"poll_interval_hours": "12"},
                          follow_redirects=False)
    assert settings_repo.get(state.conn)["poll_interval_hours"] == 12


def test_set_pushover(logged_in_client, state):
    logged_in_client.post("/settings/pushover", data={
        "token": "TOK", "user": "USR"}, follow_redirects=False)
    tok, usr = settings_repo.get_pushover(state.conn, state.vault)
    assert (tok, usr) == ("TOK", "USR")
