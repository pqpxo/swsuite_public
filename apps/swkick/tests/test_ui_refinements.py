# version 2
"""Coverage for Kicker UI refinements, group management, and credential editing."""

from app.repos import credentials as credentials_repo
from app.repos import groups as groups_repo
from app.repos import hosts as hosts_repo


def _make_credential(state, type="ssh_key"):
    return credentials_repo.create(
        state.conn, state.vault, name="Primary key", type=type,
        private_key="SECRET_PRIVATE_KEY" if type == "ssh_key" else None,
        passphrase="SECRET_PASSPHRASE" if type == "ssh_key" else None,
        password="SECRET_LOGIN" if type == "password" else None,
        sudo_password="SECRET_SUDO",
    )


def test_edit_page_never_discloses_existing_secrets(logged_in_client, state):
    credential_id = _make_credential(state)
    response = logged_in_client.get(f"/credentials/{credential_id}/edit")
    assert response.status_code == 200
    assert "Primary key" in response.text
    assert "Leave blank to keep saved key" in response.text
    for secret in ("SECRET_PRIVATE_KEY", "SECRET_PASSPHRASE", "SECRET_SUDO"):
        assert secret not in response.text


def test_credential_edit_preserves_unmodified_secrets(logged_in_client, state):
    credential_id = _make_credential(state)
    response = logged_in_client.post(
        f"/credentials/{credential_id}/edit",
        data={"name": "Updated name", "type": "ssh_key", "sudo_password": "NEW_SUDO"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    saved = credentials_repo.get(state.conn, state.vault, credential_id)
    assert saved.name == "Updated name"
    assert saved.private_key == "SECRET_PRIVATE_KEY"
    assert saved.passphrase == "SECRET_PASSPHRASE"
    assert saved.sudo_password == "NEW_SUDO"


def test_credential_edit_clear_requested_secret(logged_in_client, state):
    credential_id = _make_credential(state)
    response = logged_in_client.post(
        f"/credentials/{credential_id}/edit",
        data={"name": "Primary key", "type": "ssh_key", "clear_passphrase": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    saved = credentials_repo.get(state.conn, state.vault, credential_id)
    assert saved.passphrase is None
    assert saved.private_key == "SECRET_PRIVATE_KEY"
    assert saved.sudo_password == "SECRET_SUDO"


def test_switch_credential_type_purges_other_auth_fields(logged_in_client, state):
    credential_id = _make_credential(state)
    response = logged_in_client.post(
        f"/credentials/{credential_id}/edit",
        data={"name": "Login", "type": "password", "password": "NEW_PASSWORD"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    saved = credentials_repo.get(state.conn, state.vault, credential_id)
    assert saved.type == "password"
    assert saved.password == "NEW_PASSWORD"
    assert saved.private_key is None
    assert saved.passphrase is None
    assert saved.sudo_password == "SECRET_SUDO"


def test_switch_type_requires_new_authentication(logged_in_client, state):
    credential_id = _make_credential(state)
    response = logged_in_client.post(
        f"/credentials/{credential_id}/edit",
        data={"name": "Unused", "type": "password"},
    )
    assert response.status_code == 422
    assert credentials_repo.get(state.conn, state.vault, credential_id).type == "ssh_key"


def test_missing_credential_returns_404(logged_in_client):
    assert logged_in_client.get("/credentials/999/edit").status_code == 404
    assert logged_in_client.post(
        "/credentials/999/edit", data={"name": "any", "type": "password"},
    ).status_code == 404


def test_create_credential_discards_hidden_type_fields(logged_in_client, state):
    response = logged_in_client.post(
        "/credentials/new",
        data={
            "name": "Password auth", "type": "password",
            "password": "HELLO", "private_key": "SHOULD_NOT_BE_SAVED",
            "passphrase": "SHOULD_NOT_BE_SAVED",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    cred_id = credentials_repo.list_all(state.conn)[0]["id"]
    saved = credentials_repo.get(state.conn, state.vault, cred_id)
    assert saved.password == "HELLO"
    assert saved.private_key is None
    assert saved.passphrase is None


def test_group_quick_add_and_remove_unassigns_host(logged_in_client, state):
    response = logged_in_client.post(
        "/groups/quick-create",
        data={"dimension": "device_type", "name": "Bare Metal"},
    )
    assert response.status_code == 200
    group_id = response.json()["id"]
    assert response.json()["dimension_label"] == "Device Type"
    host_id = hosts_repo.create(
        state.conn, name="srv01", hostname="10.0.0.3", ssh_port=22,
        ssh_username="admin", credential_id=None, os_label=None,
    )
    hosts_repo.set_groups(state.conn, host_id, [group_id])
    assert "Device Type: Bare Metal" in logged_in_client.get("/hosts/new/form").text
    assert "1 host" in logged_in_client.get("/groups").text

    removed = logged_in_client.post(f"/groups/{group_id}/quick-delete")
    assert removed.status_code == 200
    assert removed.json()["status"] == "ok"
    assert hosts_repo.group_ids_for(state.conn, host_id) == []
    assert groups_repo.get(state.conn, group_id) is None


def test_duplicate_quick_group_returns_conflict(logged_in_client):
    data = {"dimension": "priority", "name": "Critical"}
    assert logged_in_client.post("/groups/quick-create", data=data).status_code == 200
    conflict = logged_in_client.post("/groups/quick-create", data=data)
    assert conflict.status_code == 409
    assert "already exists" in conflict.json()["detail"]


def test_group_quick_routes_require_login(client):
    response = client.post(
        "/groups/quick-create", data={"dimension": "priority", "name": "X"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_dashboard_and_nav_refinements(logged_in_client):
    dashboard = logged_in_client.get("/").text
    assert 'class="refresh-icon"' in dashboard
    assert 'class="chip add-host-button"' in dashboard
    assert 'aria-busy="false"' in dashboard
    assert 'class="theme-icon"' in dashboard


def test_credential_form_type_specific_sections(logged_in_client):
    html = logged_in_client.get("/credentials").text
    assert 'data-credential-type="ssh_key" hidden' in html
    assert 'data-credential-type="password" hidden' in html
    assert 'onchange="syncCredentialFields()"' in html
    assert 'href="/credentials/' not in html


def test_swkick_branding_and_logo(logged_in_client):
    dashboard = logged_in_client.get("/")
    assert dashboard.status_code == 200
    assert "SWKick" in dashboard.text
    assert 'src="/static/swkick-logo.png?v=1"' in dashboard.text
    assert "KICKER</strong>" not in dashboard.text
    assert "<title>Dashboard — SWKick</title>" in dashboard.text
    login = logged_in_client.get("/login")
    assert "SWKick" in login.text
    icon = logged_in_client.get("/static/swkick-logo.png")
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/png")
    assert logged_in_client.app.title == "SWKick"
