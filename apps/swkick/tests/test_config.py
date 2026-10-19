from app.config import Config


def test_config_reads_env(tmp_path, monkeypatch):
    keyfile = tmp_path / "master.key"
    keyfile.write_text("xxx")
    monkeypatch.setenv("KICKER_MASTER_KEY_FILE", str(keyfile))
    monkeypatch.setenv("KICKER_DB_PATH", str(tmp_path / "kicker.sqlite"))
    monkeypatch.setenv("KICKER_POLL_INTERVAL_HOURS", "3")

    cfg = Config.from_env()

    assert cfg.master_key_file == str(keyfile)
    assert cfg.db_path == str(tmp_path / "kicker.sqlite")
    assert cfg.poll_interval_hours == 3


def test_config_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("KICKER_MASTER_KEY_FILE", str(tmp_path / "k"))
    monkeypatch.delenv("KICKER_DB_PATH", raising=False)
    monkeypatch.delenv("KICKER_POLL_INTERVAL_HOURS", raising=False)
    cfg = Config.from_env()
    assert cfg.db_path == "/data/kicker.sqlite"
    assert cfg.poll_interval_hours == 6


def test_config_requires_master_key_file(monkeypatch):
    monkeypatch.delenv("KICKER_MASTER_KEY_FILE", raising=False)
    import pytest
    with pytest.raises(RuntimeError):
        Config.from_env()
