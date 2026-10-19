from app import db


def test_connect_and_init_schema(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(conn)
    tables = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"hosts", "credentials", "groups", "host_groups", "jobs", "settings"} <= tables


def test_foreign_keys_enabled(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite"))
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_settings_seeded_single_row(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(conn)
    rows = conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()
    assert rows["c"] == 1
