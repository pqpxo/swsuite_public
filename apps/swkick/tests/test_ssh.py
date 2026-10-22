from app.models import Credential, HostConn, RunResult
from app.ssh import ParamikoExecutor


class FakeStd:
    def __init__(self, lines, exit_code):
        self._lines = list(lines)
        self.channel = type("C", (), {"recv_exit_status": staticmethod(lambda: exit_code),
                                      "set_combine_stderr": lambda self, v: None})()

    def __iter__(self):
        return iter(self._lines)

    def read(self):
        return "".join(self._lines).encode()


class FakeStdIn:
    def __init__(self, sink):
        self._sink = sink

    def write(self, data):
        self._sink.append(data)

    def flush(self):
        pass


class FakeClient:
    def __init__(self, out_lines, exit_code):
        self.out_lines = out_lines
        self.exit_code = exit_code
        self.stdin_writes = []
        self.closed = False
        self.last_command = None

    def exec_command(self, command, get_pty=False):
        self.last_command = command
        self.last_get_pty = get_pty
        stdin = FakeStdIn(self.stdin_writes)
        stdout = FakeStd(self.out_lines, self.exit_code)
        stderr = FakeStd([], self.exit_code)
        return stdin, stdout, stderr

    def close(self):
        self.closed = True


def _host():
    return HostConn("10.0.0.1", 22, "admin",
                    Credential(1, "c", "password", password="pw", sudo_password="sp"))


def test_run_collects_output_and_exit():
    fake = FakeClient(["hello\n", "world\n"], 0)
    ex = ParamikoExecutor(connect=lambda host: fake)
    result = ex.run(_host(), "echo hi")
    assert result.output == "hello\nworld\n"
    assert result.exit_code == 0
    assert fake.closed is True


def test_run_sudo_prefixes_and_sends_password():
    fake = FakeClient(["ok\n"], 0)
    ex = ParamikoExecutor(connect=lambda host: fake)
    ex.run(_host(), "apt-get update", sudo=True)
    assert fake.last_command.startswith('sudo -S -p ""')
    assert "sp\n" in fake.stdin_writes  # the sudo_password, sent via stdin


def test_stream_yields_lines_and_sets_exit():
    fake = FakeClient(["a\n", "b\n"], 0)
    ex = ParamikoExecutor(connect=lambda host: fake)
    result = RunResult()
    lines = list(ex.stream(_host(), "apt-get -y upgrade", result, sudo=True))
    assert lines == ["a\n", "b\n"]
    assert result.exit_code == 0


def test_stream_never_echoes_the_sudo_password():
    # A pty would echo the password written to stdin back into the output.
    fake = FakeClient(["sp\n", "Reading package lists... sp done\n"], 0)
    ex = ParamikoExecutor(connect=lambda host: fake)
    lines = list(ex.stream(_host(), "apt-get -y upgrade", RunResult(), sudo=True))
    assert fake.last_get_pty is False
    assert "sp\n" in fake.stdin_writes
    assert not any("sp" in l for l in lines), lines
