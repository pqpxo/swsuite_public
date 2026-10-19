import pytest

from app import db
from app.repos import groups as repo


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(c)
    return c


def test_create_and_list_by_dimension(conn):
    repo.create(conn, "priority", "Critical")
    repo.create(conn, "priority", "Standard")
    repo.create(conn, "host_type", "VM")
    crit = repo.list_by_dimension(conn, "priority")
    assert [g["name"] for g in crit] == ["Critical", "Standard"]


def test_invalid_dimension_rejected(conn):
    with pytest.raises(ValueError):
        repo.create(conn, "colour", "Blue")


def test_duplicate_rejected(conn):
    repo.create(conn, "priority", "Critical")
    with pytest.raises(Exception):
        repo.create(conn, "priority", "Critical")


def test_delete(conn):
    gid = repo.create(conn, "priority", "Low")
    repo.delete(conn, gid)
    assert repo.list_by_dimension(conn, "priority") == []
