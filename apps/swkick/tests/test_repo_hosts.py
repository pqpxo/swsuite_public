import pytest

from app import db
from app.repos import hosts as repo
from app.repos import groups as groups_repo


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(c)
    return c


def _mk(conn, name="web-01"):
    return repo.create(
        conn, name=name, hostname="10.0.0.11", ssh_port=22,
        ssh_username="admin", credential_id=None, os_label="Ubuntu 22.04",
    )


def test_create_and_get(conn):
    hid = _mk(conn)
    h = repo.get(conn, hid)
    assert h["name"] == "web-01"
    assert h["update_count"] == 0
    assert h["enabled"] == 1


def test_update_status(conn):
    hid = _mk(conn)
    repo.update_status(conn, hid, update_count=7, reachable=True,
                       last_checked_at="2026-06-14T10:00:00", os_label="Ubuntu 24.04")
    h = repo.get(conn, hid)
    assert h["update_count"] == 7
    assert h["reachable"] == 1
    assert h["os_label"] == "Ubuntu 24.04"


def test_set_groups_and_grouped_view(conn):
    hid1 = _mk(conn, "web-01")
    hid2 = _mk(conn, "db-01")
    crit = groups_repo.create(conn, "priority", "Critical")
    std = groups_repo.create(conn, "priority", "Standard")
    repo.set_groups(conn, hid1, [crit])
    repo.set_groups(conn, hid2, [std])

    grouped = repo.list_grouped(conn, "priority")
    assert [h["name"] for h in grouped["Critical"]] == ["web-01"]
    assert [h["name"] for h in grouped["Standard"]] == ["db-01"]


def test_ungrouped_bucket(conn):
    _mk(conn, "lonely")
    grouped = repo.list_grouped(conn, "priority")
    assert [h["name"] for h in grouped["Ungrouped"]] == ["lonely"]


def test_list_enabled(conn):
    hid = _mk(conn)
    repo.set_enabled(conn, hid, False)
    assert repo.list_enabled(conn) == []


def test_delete(conn):
    hid = _mk(conn)
    repo.delete(conn, hid)
    assert repo.get(conn, hid) is None
