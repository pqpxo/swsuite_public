from app.repos import credentials as creds_repo
from app.repos import groups as groups_repo
from app.repos import hosts as hosts_repo


def test_create_host_via_form(logged_in_client, state):
    cid = creds_repo.create(state.conn, state.vault, name="c", type="password",
                            private_key=None, passphrase=None,
                            password="pw", sudo_password="sp")
    r = logged_in_client.post("/hosts/new", data={
        "name": "web-01", "hostname": "10.0.0.1", "ssh_port": "22",
        "ssh_username": "admin", "credential_id": str(cid),
        "os_label": "Ubuntu 22.04",
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert hosts_repo.list_all(state.conn)[0]["name"] == "web-01"


def test_create_credential_via_form(logged_in_client, state):
    r = logged_in_client.post("/credentials/new", data={
        "name": "prod", "type": "password",
        "password": "secret", "sudo_password": "sudo",
        "private_key": "", "passphrase": "",
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert creds_repo.list_all(state.conn)[0]["name"] == "prod"


def test_create_group_via_form(logged_in_client, state):
    r = logged_in_client.post("/groups/new", data={
        "dimension": "priority", "name": "Critical"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert groups_repo.list_by_dimension(state.conn, "priority")[0]["name"] == "Critical"


def test_credentials_page_never_shows_secret(logged_in_client, state):
    creds_repo.create(state.conn, state.vault, name="c", type="password",
                      private_key=None, passphrase=None,
                      password="TOPSECRETVALUE", sudo_password=None)
    r = logged_in_client.get("/credentials")
    assert "TOPSECRETVALUE" not in r.text
