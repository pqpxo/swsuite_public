import asyncio
import pytest

from app import db
from app.vault import Vault, generate_key
from app.repos import hosts as hosts_repo
from app.repos import credentials as creds_repo
from app.repos import jobs as jobs_repo
from app.models import RunResult
from app.runner import run_check, run_upgrade, JobBroadcaster, build_host_conn


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(c)
    return c


@pytest.fixture
def vault():
    return Vault(generate_key())


@pytest.fixture
def host_id(conn, vault):
    cid = creds_repo.create(conn, vault, name="c", type="password",
                            private_key=None, passphrase=None,
                            password="pw", sudo_password="sp")
    return hosts_repo.create(conn, name="h", hostname="10.0.0.1", ssh_port=22,
                             ssh_username="admin", credential_id=cid, os_label=None)


class FakeExecutor:
    def __init__(self, upgradable="", up_lines=None, up_exit=0, fail=False):
        self.upgradable = upgradable
        self.up_lines = up_lines or []
        self.up_exit = up_exit
        self.fail = fail

    def run(self, host, command, *, sudo=False):
        if self.fail:
            raise OSError("connection refused")
        if command.startswith("apt list"):
            return RunResult(0, self.upgradable)
        return RunResult(0, "")

    def stream(self, host, command, result, *, sudo=False):
        for ln in self.up_lines:
            yield ln
        result.exit_code = self.up_exit


def test_build_host_conn_decrypts(conn, vault, host_id):
    hc = build_host_conn(conn, vault, host_id)
    assert hc.credential.password == "pw"
    assert hc.credential.sudo_password == "sp"


def test_run_check_updates_host_and_logs_job(conn, vault, host_id):
    ex = FakeExecutor(upgradable="Listing...\ncurl/j 1 amd64 [upgradable from: 0]\n")
    from app.updater import AptUpdater
    jid = run_check(conn, vault, ex, AptUpdater(), host_id, trigger="manual")

    host = hosts_repo.get(conn, host_id)
    assert host["update_count"] == 1
    assert host["reachable"] == 1
    job = jobs_repo.get(conn, jid)
    assert job["status"] == "success"
    assert job["kind"] == "check"


def test_run_check_marks_unreachable_on_error(conn, vault, host_id):
    ex = FakeExecutor(fail=True)
    from app.updater import AptUpdater
    jid = run_check(conn, vault, ex, AptUpdater(), host_id, trigger="scheduled")
    host = hosts_repo.get(conn, host_id)
    assert host["reachable"] == 0
    assert jobs_repo.get(conn, jid)["status"] == "failed"


@pytest.mark.asyncio
async def test_run_upgrade_streams_and_records(conn, vault, host_id):
    ex = FakeExecutor(up_lines=["Reading...\n", "Done\n"], up_exit=0)
    from app.updater import AptUpdater
    loop = asyncio.get_running_loop()
    b = JobBroadcaster(loop)

    jid = await loop.run_in_executor(
        None,
        lambda: run_upgrade(conn, vault, ex, AptUpdater(), host_id,
                            trigger="manual", broadcaster=b),
    )
    job = jobs_repo.get(conn, jid)
    assert job["status"] == "success"
    assert "Done\n" in job["output_log"]
    assert job["exit_code"] == 0
