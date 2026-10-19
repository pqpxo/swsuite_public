import time

from app.repos import hosts as hosts_repo
from app.repos import jobs as jobs_repo


def _host(state):
    return hosts_repo.create(state.conn, name="web-01", hostname="10.0.0.1",
                             ssh_port=22, ssh_username="a", credential_id=None,
                             os_label=None)


def test_trigger_upgrade_returns_job_id(logged_in_client, state):
    hid = _host(state)
    r = logged_in_client.post(f"/hosts/{hid}/upgrade")
    assert r.status_code == 200
    jid = r.json()["job_id"]
    for _ in range(60):
        job = jobs_repo.get(state.conn, jid)
        if job["status"] != "running":
            break
        time.sleep(0.05)
    assert jobs_repo.get(state.conn, jid)["status"] == "success"


def test_check_now_endpoint(logged_in_client, state):
    hid = _host(state)
    r = logged_in_client.post(f"/hosts/{hid}/check")
    assert r.status_code == 200
    assert jobs_repo.get(state.conn, r.json()["job_id"])["kind"] == "check"


def test_logs_page_lists_jobs(logged_in_client, state):
    hid = _host(state)
    jobs_repo.create(state.conn, host_id=hid, kind="check", trigger="manual")
    r = logged_in_client.get("/logs")
    assert r.status_code == 200
    assert "check" in r.text


def test_job_output_endpoint(logged_in_client, state):
    hid = _host(state)
    jid = jobs_repo.create(state.conn, host_id=hid, kind="upgrade", trigger="manual")
    jobs_repo.append_output(state.conn, jid, "hello\n")
    r = logged_in_client.get(f"/jobs/{jid}/output")
    assert "hello" in r.json()["output"]
