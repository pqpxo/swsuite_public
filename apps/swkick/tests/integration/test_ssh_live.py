import os
import pytest

from app.models import Credential, HostConn
from app.ssh import ParamikoExecutor

pytestmark = pytest.mark.skipif(
    not os.environ.get("KICKER_TEST_SSH_HOST"),
    reason="set KICKER_TEST_SSH_HOST/USER/PASSWORD to run live SSH test",
)


def _host():
    return HostConn(
        hostname=os.environ["KICKER_TEST_SSH_HOST"],
        port=int(os.environ.get("KICKER_TEST_SSH_PORT", "22")),
        username=os.environ["KICKER_TEST_SSH_USER"],
        credential=Credential(
            1, "live", "password",
            password=os.environ["KICKER_TEST_SSH_PASSWORD"],
            sudo_password=os.environ.get("KICKER_TEST_SSH_PASSWORD"),
        ),
    )


def test_real_echo():
    ex = ParamikoExecutor()
    r = ex.run(_host(), "echo kicker-ok")
    assert "kicker-ok" in r.output
    assert r.exit_code == 0


def test_real_apt_list_upgradable():
    ex = ParamikoExecutor()
    r = ex.run(_host(), "apt list --upgradable 2>/dev/null")
    assert r.exit_code == 0  # output may be empty if fully patched
