import json
import pytest

from app import db
from app.repos import jobs as repo
from app.repos import hosts as hosts_repo


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(c)
    return c


@pytest.fixture
def host_id(conn):
    return hosts_repo.create(conn, name="h", hostname="10.0.0.1", ssh_port=22,
                             ssh_username="a", credential_id=None, os_label=None)


def test_create_starts_running(conn, host_id):
    jid = repo.create(conn, host_id=host_id, kind="upgrade", trigger="manual")
    job = repo.get(conn, jid)
    assert job["status"] == "running"
    assert job["output_log"] == ""


def test_append_output_accumulates(conn, host_id):
    jid = repo.create(conn, host_id=host_id, kind="upgrade", trigger="manual")
    repo.append_output(conn, jid, "line 1\n")
    repo.append_output(conn, jid, "line 2\n")
    assert repo.get(conn, jid)["output_log"] == "line 1\nline 2\n"


def test_finish_records_result(conn, host_id):
    jid = repo.create(conn, host_id=host_id, kind="check", trigger="scheduled")
    repo.finish(conn, jid, status="success", exit_code=0,
                packages=["libssl3", "curl"])
    job = repo.get(conn, jid)
    assert job["status"] == "success"
    assert job["exit_code"] == 0
    assert json.loads(job["packages_json"]) == ["libssl3", "curl"]
    assert job["finished_at"] is not None


def test_list_recent_desc(conn, host_id):
    a = repo.create(conn, host_id=host_id, kind="check", trigger="manual")
    b = repo.create(conn, host_id=host_id, kind="upgrade", trigger="manual")
    ids = [j["id"] for j in repo.list_recent(conn, limit=10)]
    assert ids == [b, a]
