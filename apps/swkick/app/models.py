from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Credential:
    id: int
    name: str
    type: str  # 'ssh_key' | 'password'
    private_key: str | None = None
    passphrase: str | None = None
    password: str | None = None
    sudo_password: str | None = None


@dataclass
class HostConn:
    hostname: str
    port: int
    username: str
    credential: Credential


@dataclass
class RunResult:
    exit_code: int | None = None
    output: str = ""
