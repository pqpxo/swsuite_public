# version 2
from app.repos import groups as groups_repo
from app.repos import hosts as hosts_repo


def _make_host(state):
    return hosts_repo.create(
        state.conn, name="nas-old", hostname="192.168.1.7",
        ssh_port=22, ssh_username="root", credential_id=None, os_label=None,
    )


def test_dashboard_summary_and_search(logged_in_client, state):
    _make_host(state)
    response = logged_in_client.get("/")
    assert response.status_code == 200
    assert "Host Overview" in response.text
    assert "host-search" in response.text
    assert "nas-old" in response.text
    assert "Not checked" in response.text


def test_host_edit_form_and_save(logged_in_client, state):
    host_id = _make_host(state)
    group_id = groups_repo.create(state.conn, "priority", "Critical")
    form = logged_in_client.get(f"/hosts/{host_id}/edit")
    assert form.status_code == 200
    assert "nas-old" in form.text
    response = logged_in_client.post(
        f"/hosts/{host_id}/edit",
        data={
            "name": "nas-updated",
            "hostname": "192.168.1.8",
            "ssh_port": "2222",
            "ssh_username": "admin",
            "credential_id": "",
            "os_label": "Debian",
            "group_ids": str(group_id),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    host = hosts_repo.get(state.conn, host_id)
    assert host["name"] == "nas-updated"
    assert host["ssh_port"] == 2222
    assert host["hostname"] == "192.168.1.8"
    assert hosts_repo.group_ids_for(state.conn, host_id) == [group_id]


def test_host_edit_unknown_id(logged_in_client):
    assert logged_in_client.get("/hosts/999/edit").status_code == 404
    assert logged_in_client.post(
        "/hosts/999/edit",
        data={"name": "x", "hostname": "localhost", "ssh_username": "root"},
    ).status_code == 404


def test_host_edit_rejects_invalid_port(logged_in_client, state):
    host_id = _make_host(state)
    response = logged_in_client.post(
        f"/hosts/{host_id}/edit",
        data={"name": "x", "hostname": "localhost",
              "ssh_username": "root", "ssh_port": "65536"},
    )
    assert response.status_code == 422
    assert hosts_repo.get(state.conn, host_id)["ssh_port"] == 22


def test_navigation_available_on_hosts_and_hidden_on_login(client, logged_in_client):
    assert "Managed Hosts" in logged_in_client.get("/hosts").text
    assert 'class="mobile-nav"' in logged_in_client.get("/hosts").text
    assert 'class="mobile-nav"' not in client.get("/login").text
