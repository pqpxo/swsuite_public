from app.models import Credential, HostConn, RunResult
from app.updater import AptUpdater


class FakeExecutor:
    def __init__(self, upgradable_output, upgrade_lines, upgrade_exit=0):
        self.upgradable_output = upgradable_output
        self.upgrade_lines = upgrade_lines
        self.upgrade_exit = upgrade_exit
        self.commands = []

    def run(self, host, command, *, sudo=False):
        self.commands.append((command, sudo))
        if command.startswith("apt list"):
            return RunResult(exit_code=0, output=self.upgradable_output)
        return RunResult(exit_code=0, output="")

    def stream(self, host, command, result, *, sudo=False):
        self.commands.append((command, sudo))
        for line in self.upgrade_lines:
            yield line
        result.exit_code = self.upgrade_exit


def _host():
    return HostConn("10.0.0.1", 22, "admin",
                    Credential(1, "c", "password", password="pw", sudo_password="sp"))


def test_check_returns_package_names():
    ex = FakeExecutor(
        "Listing...\ncurl/jammy 1 amd64 [upgradable from: 0]\n", [])
    pkgs = AptUpdater().check(ex, _host())
    assert pkgs == ["curl"]
    assert ("apt-get update -qq", True) in ex.commands


def test_upgrade_streams_lines_and_sets_exit():
    ex = FakeExecutor("", ["Reading...\n", "Done\n"], upgrade_exit=0)
    result = RunResult()
    lines = list(AptUpdater().upgrade(ex, _host(), result))
    assert lines == ["Reading...\n", "Done\n"]
    assert result.exit_code == 0
