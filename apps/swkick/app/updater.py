from __future__ import annotations

from typing import Iterator, Protocol

from app.models import HostConn, RunResult


def parse_upgradable(output: str) -> list[str]:
    packages: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("Listing"):
            continue
        if "/" in line:
            packages.append(line.split("/", 1)[0])
    return packages


class Executor(Protocol):
    def run(self, host: HostConn, command: str, *, sudo: bool = False) -> RunResult: ...
    def stream(self, host: HostConn, command: str, result: RunResult, *,
               sudo: bool = False) -> Iterator[str]: ...


class Updater(Protocol):
    def check(self, ex: "Executor", host: HostConn) -> list[str]: ...
    def upgrade(self, ex: "Executor", host: HostConn,
                result: RunResult) -> Iterator[str]: ...


class AptUpdater:
    def check(self, ex: "Executor", host: HostConn) -> list[str]:
        ex.run(host, "apt-get update -qq", sudo=True)
        r = ex.run(host, "apt list --upgradable 2>/dev/null", sudo=False)
        return parse_upgradable(r.output)

    def upgrade(self, ex: "Executor", host: HostConn,
                result: RunResult) -> Iterator[str]:
        yield from ex.stream(
            host,
            "DEBIAN_FRONTEND=noninteractive apt-get update && "
            "DEBIAN_FRONTEND=noninteractive apt-get -y upgrade",
            result, sudo=True,
        )
