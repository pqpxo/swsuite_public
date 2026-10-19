from __future__ import annotations

import io
from typing import Callable, Iterator

import paramiko

from app.models import HostConn, RunResult


def _default_connect(host: HostConn) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # trust-on-first-use
    cred = host.credential
    kwargs = dict(hostname=host.hostname, port=host.port, username=host.username,
                  timeout=15, banner_timeout=15, auth_timeout=15)
    if cred.type == "ssh_key" and cred.private_key:
        pkey = paramiko.RSAKey.from_private_key(
            io.StringIO(cred.private_key), password=cred.passphrase)
        client.connect(pkey=pkey, **kwargs)
    else:
        client.connect(password=cred.password, **kwargs)
    return client


def _wrap_sudo(command: str) -> str:
    # -S reads the sudo password from stdin; -p '' suppresses the prompt text
    escaped = command.replace('"', '\\"')
    return f'sudo -S -p "" bash -c "{escaped}"'


class ParamikoExecutor:
    def __init__(self, connect: Callable[[HostConn], "paramiko.SSHClient"] | None = None):
        self._connect = connect or _default_connect

    def run(self, host: HostConn, command: str, *, sudo: bool = False) -> RunResult:
        client = self._connect(host)
        try:
            cmd = _wrap_sudo(command) if sudo else command
            stdin, stdout, stderr = client.exec_command(cmd, get_pty=False)
            if sudo and host.credential.sudo_password:
                stdin.write(host.credential.sudo_password + "\n")
                stdin.flush()
            out = stdout.read()
            err = stderr.read()
            text = (out.decode() if isinstance(out, bytes) else out) + \
                   (err.decode() if isinstance(err, bytes) else err)
            exit_code = stdout.channel.recv_exit_status()
            return RunResult(exit_code=exit_code, output=text)
        finally:
            client.close()

    def stream(self, host: HostConn, command: str, result: RunResult, *,
               sudo: bool = False) -> Iterator[str]:
        client = self._connect(host)
        try:
            cmd = _wrap_sudo(command) if sudo else command
            stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
            if sudo and host.credential.sudo_password:
                stdin.write(host.credential.sudo_password + "\n")
                stdin.flush()
            for line in stdout:
                yield line if isinstance(line, str) else line.decode()
            result.exit_code = stdout.channel.recv_exit_status()
        finally:
            client.close()
