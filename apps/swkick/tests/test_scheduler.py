import pytest

from app import db
from app.vault import Vault, generate_key
from app.repos import hosts as hosts_repo
from app.repos import settings as settings_repo
from app.models import RunResult
from app.scheduler import poll_all


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(c)
    return c


@pytest.fixture
def vault():
    return Vault(generate_key())


class FakeExecutor:
    def __init__(self, count):
        self.count = count

    def run(self, host, command, *, sudo=False):
        if command.startswith("apt list"):
            body = "Listing...\n" + "".join(
                f"pkg{i}/j 1 amd64 [upgradable from: 0]\n" for i in range(self.count))
            return RunResult(0, body)
        return RunResult(0, "")

    def stream(self, host, command, result, *, sudo=False):
        result.exit_code = 0
        return iter(())


class RecordingNotifier:
    def __init__(self):
        self.sent = []

    def send(self, title, message):
        self.sent.append((title, message))


def test_poll_checks_all_enabled_and_notifies_new(conn, vault):
    hosts_repo.create(conn, name="web-01", hostname="10.0.0.1", ssh_port=22,
                      ssh_username="a", credential_id=None, os_label=None)
    from app.updater import AptUpdater
    notifier = RecordingNotifier()

    poll_all(conn, vault, FakeExecutor(3), AptUpdater(), notifier)

    h = hosts_repo.get(conn, 1)
    assert h["update_count"] == 3
    assert len(notifier.sent) == 1            # newly has updates -> one notification
    assert "web-01" in notifier.sent[0][1]


def test_poll_dedupes_second_run(conn, vault):
    hosts_repo.create(conn, name="web-01", hostname="10.0.0.1", ssh_port=22,
                      ssh_username="a", credential_id=None, os_label=None)
    from app.updater import AptUpdater
    notifier = RecordingNotifier()
    poll_all(conn, vault, FakeExecutor(3), AptUpdater(), notifier)
    poll_all(conn, vault, FakeExecutor(3), AptUpdater(), notifier)
    assert len(notifier.sent) == 1            # second run: same set, no repeat
