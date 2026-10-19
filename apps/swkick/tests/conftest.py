import pytest
from fastapi.testclient import TestClient

from app import db
from app.app import build_app, AppState
from app.vault import Vault, generate_key
from app.models import RunResult


class FakeExecutor:
    """Configurable fake used across route tests."""

    def __init__(self):
        self.upgradable = "Listing...\n"
        self.up_lines = ["Reading package lists...\n", "Done\n"]
        self.up_exit = 0

    def run(self, host, command, *, sudo=False):
        if command.startswith("apt list"):
            return RunResult(0, self.upgradable)
        return RunResult(0, "")

    def stream(self, host, command, result, *, sudo=False):
        for ln in self.up_lines:
            yield ln
        result.exit_code = self.up_exit


@pytest.fixture
def state(tmp_path):
    conn = db.connect(str(tmp_path / "t.sqlite"))
    db.init_schema(conn)
    return AppState(
        config=None,
        conn=conn,
        vault=Vault(generate_key()),
        executor=FakeExecutor(),
        session_secret="test-secret",
    )


@pytest.fixture
def client(state):
    app = build_app(state)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def logged_in_client(client, state):
    from app.repos import settings as settings_repo
    from app.security import hash_password
    settings_repo.set_admin(state.conn, username="admin",
                            password_hash=hash_password("pw"))
    client.post("/login", data={"username": "admin", "password": "pw"},
                follow_redirects=False)
    return client
