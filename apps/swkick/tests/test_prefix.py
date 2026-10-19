# version 1
"""Mount-path support: SWKick served under /kick by the SWSuite proxy."""
import pytest

from app import prefix
from app.repos import settings as settings_repo
from app.security import hash_password

KICK = {"X-Forwarded-Prefix": "/kick"}


def _set_admin(state):
    settings_repo.set_admin(state.conn, username="admin",
                            password_hash=hash_password("pw"))


def _login(client, headers=None):
    r = client.post("/login", data={"username": "admin", "password": "pw"},
                    headers=headers or {}, follow_redirects=False)
    return r


@pytest.mark.parametrize("raw, expected", [
    (b"/kick", "/kick"),
    (b"/kick/", "/kick"),
    (b"/suite/kick", "/suite/kick"),
    (b"", ""),
    (None, ""),
    (b"kick", ""),
    (b"//evil.example", ""),
    (b"/kick/..", ""),
    (b"/.", ""),
    (b'/kick"><script>', ""),
    (b"/kick?x=1", ""),
])
def test_parse(raw, expected):
    assert prefix.parse(raw) == expected


def test_standalone_is_unchanged(client, state):
    _set_admin(state)
    assert client.get("/", follow_redirects=False).headers["location"] == "/login"
    r = _login(client)
    assert r.headers["location"] == "/"
    assert "Path=/;" in r.headers["set-cookie"] or r.headers["set-cookie"].endswith("Path=/")
    page = client.get("/").text
    assert 'data-base=""' in page
    assert 'href="/hosts"' in page
    assert 'src="/static/app.js?v=5"' in page


def test_redirects_get_the_prefix(client, state):
    _set_admin(state)
    assert client.get("/", headers=KICK, follow_redirects=False).headers["location"] == "/kick/login"
    r = _login(client, KICK)
    assert r.headers["location"] == "/kick/"
    out = client.get("/logout", headers=KICK, follow_redirects=False)
    assert out.headers["location"] == "/kick/login"
    assert "Path=/kick" in out.headers["set-cookie"]


def test_session_cookie_is_scoped_to_the_prefix(client, state):
    _set_admin(state)
    cookie = _login(client, KICK).headers["set-cookie"]
    assert "kicker_session=" in cookie
    assert "Path=/kick" in cookie
    assert "Path=/;" not in cookie and not cookie.endswith("Path=/")


def test_pages_link_under_the_prefix(client, state):
    _set_admin(state)
    token = _login(client, KICK).cookies["kicker_session"]
    client.cookies.clear()
    headers = {**KICK, "Cookie": f"kicker_session={token}"}
    for path in ("/", "/hosts", "/groups", "/credentials", "/settings", "/hosts/new/form"):
        page = client.get(path, headers=headers)
        assert page.status_code == 200, path
        html = page.text
        assert 'data-base="/kick"' in html
        assert 'src="/kick/static/app.js?v=5"' in html
        assert 'href="/kick/hosts"' in html
        # No root-relative link, form or asset may escape the mount path.
        for attr in ("href", "src", "action"):
            assert f'{attr}="/' not in html.replace(f'{attr}="/kick', ""), (path, attr)


def test_login_page_links_under_the_prefix(client, state):
    html = client.get("/login", headers=KICK).text
    assert 'action="/kick/login"' in html
    assert 'src="/kick/static/swkick-logo.png?v=1"' in html


def test_bad_prefix_is_ignored(client, state):
    _set_admin(state)
    r = client.get("/", headers={"X-Forwarded-Prefix": "//evil.example"},
                   follow_redirects=False)
    assert r.headers["location"] == "/login"


def test_static_and_health_still_served(client):
    assert client.get("/healthz", headers=KICK).json() == {"status": "ok"}
    assert client.get("/static/app.js", headers=KICK).status_code == 200
