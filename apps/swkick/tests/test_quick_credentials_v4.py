# version 1
"""Quick credential workflow should preserve host creation state and secrets."""

from app.repos import credentials as creds_repo
from app.repos import hosts as hosts_repo


def test_add_host_page_has_separate_credential_dialog(logged_in_client):
    response = logged_in_client.get("/hosts/new/form")
    assert response.status_code == 200
    html = response.text
    assert "Add Host" in html
    assert 'id="host-credential"' in html
    assert 'id="quick-credential-dialog"' in html
    assert 'id="quick-credential-form"' in html
    assert 'action="/credentials/quick-create"' in html
    assert 'onsubmit="saveQuickCredential(event)"' in html
    assert 'onclick="openCredentialDialog()"' in html
    assert html.index('id="quick-credential-form"') > html.index("</main>")


def test_edit_host_also_has_credential_dialog(logged_in_client, state):
    host_id = hosts_repo.create(
        state.conn, name="test01", hostname="10.0.0.1", ssh_port=22,
        ssh_username="user", credential_id=None, os_label=None,
    )
    html = logged_in_client.get(f"/hosts/{host_id}/edit").text
    assert "Edit Host" in html
    assert 'id="quick-credential-dialog"' in html


def test_quick_create_password_returns_only_metadata(logged_in_client, state):
    response = logged_in_client.post(
        "/credentials/quick-create",
        data={"name": "  My New Password  ", "type": "password",
              "password": "TOPSECRET", "sudo_password": "SUDOSECRET",
              "private_key": "WRONG_TYPE_SECRET"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"id", "name", "type"}
    assert payload["name"] == "My New Password"
    assert payload["type"] == "password"
    assert "TOPSECRET" not in response.text
    assert "WRONG_TYPE_SECRET" not in response.text
    saved = creds_repo.get(state.conn, state.vault, payload["id"])
    assert saved.name == "My New Password"
    assert saved.password == "TOPSECRET"
    assert saved.sudo_password == "SUDOSECRET"
    assert saved.private_key is None

    host_response = logged_in_client.post(
        "/hosts/new",
        data={"name": "host-with-key", "hostname": "192.168.1.2",
              "ssh_username": "admin", "credential_id": str(payload["id"])},
        follow_redirects=False,
    )
    assert host_response.status_code == 303
    assert hosts_repo.list_all(state.conn)[0]["credential_id"] == payload["id"]


def test_quick_create_ssh_key_encrypts_and_returns_metadata(logged_in_client, state):
    response = logged_in_client.post(
        "/credentials/quick-create",
        data={"name": "New SSH", "type": "ssh_key",
              "private_key": "PRIVATE_KEY_CONTENT",
              "passphrase": "KEY_PASSPHRASE",
              "password": "SHOULD_BE_IGNORED"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "New SSH"
    assert "PRIVATE_KEY_CONTENT" not in response.text
    saved = creds_repo.get(state.conn, state.vault, payload["id"])
    assert saved.private_key == "PRIVATE_KEY_CONTENT"
    assert saved.passphrase == "KEY_PASSPHRASE"
    assert saved.password is None
    ciphertext = state.conn.execute(
        "SELECT enc_private_key FROM credentials WHERE id=?", (payload["id"],)
    ).fetchone()["enc_private_key"]
    assert b"PRIVATE_KEY_CONTENT" not in ciphertext


def test_quick_create_requires_auth_data(logged_in_client, state):
    for typ, fields in (
        ("password", {"password": ""}),
        ("ssh_key", {"private_key": "   "}),
    ):
        response = logged_in_client.post(
            "/credentials/quick-create",
            data={"name": "No secret", "type": typ, **fields},
        )
        assert response.status_code == 422
    assert creds_repo.list_all(state.conn) == []


def test_quick_create_rejects_bad_type_and_empty_name(logged_in_client):
    bad_type = logged_in_client.post(
        "/credentials/quick-create",
        data={"name": "X", "type": "invalid", "password": "x"},
    )
    assert bad_type.status_code == 422
    bad_name = logged_in_client.post(
        "/credentials/quick-create",
        data={"name": "   ", "type": "password", "password": "x"},
    )
    assert bad_name.status_code == 422


def test_quick_create_requires_authentication(client, state):
    response = client.post(
        "/credentials/quick-create",
        data={"name": "Nope", "type": "password", "password": "pass"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    assert creds_repo.list_all(state.conn) == []


def test_headings_and_host_buttons(logged_in_client, state):
    dashboard = logged_in_client.get("/").text
    assert "Host Overview" in dashboard
    assert "Host overview" not in dashboard
    assert "Managed Hosts" in logged_in_client.get("/hosts").text

    host_id = hosts_repo.create(
        state.conn, name="server01", hostname="10.0.0.1", ssh_port=22,
        ssh_username="root", credential_id=None, os_label=None,
    )
    dashboard = logged_in_client.get("/").text
    detail = logged_in_client.get(f"/hosts/{host_id}").text
    for html in (dashboard, detail):
        assert 'class="btn-muted check-host-button"' in html or 'class="chip check-host-button"' in html
        assert 'aria-busy="false"' in html
        assert 'class="refresh-icon"' in html
        assert ", this)" in html
