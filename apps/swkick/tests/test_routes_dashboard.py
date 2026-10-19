from app.repos import hosts as hosts_repo
from app.repos import groups as groups_repo


def test_dashboard_groups_by_default_priority(logged_in_client, state):
    gid = groups_repo.create(state.conn, "priority", "Critical")
    hid = hosts_repo.create(state.conn, name="web-01", hostname="10.0.0.1",
                            ssh_port=22, ssh_username="a", credential_id=None,
                            os_label="Ubuntu 22.04")
    hosts_repo.set_groups(state.conn, hid, [gid])

    r = logged_in_client.get("/")
    assert r.status_code == 200
    assert "web-01" in r.text
    assert "Critical" in r.text


def test_dashboard_group_by_param(logged_in_client, state):
    gid = groups_repo.create(state.conn, "device_type", "NAS")
    hid = hosts_repo.create(state.conn, name="nas-01", hostname="10.0.0.2",
                            ssh_port=22, ssh_username="a", credential_id=None,
                            os_label=None)
    hosts_repo.set_groups(state.conn, hid, [gid])
    r = logged_in_client.get("/?group_by=device_type")
    assert "NAS" in r.text


def test_host_detail_shows_job_history(logged_in_client, state):
    hid = hosts_repo.create(state.conn, name="web-01", hostname="10.0.0.1",
                            ssh_port=22, ssh_username="a", credential_id=None,
                            os_label=None)
    r = logged_in_client.get(f"/hosts/{hid}")
    assert r.status_code == 200
    assert "web-01" in r.text
