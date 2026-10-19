from __future__ import annotations

from app import db
from app.app import AppState, build_app
from app.config import Config
from app.ssh import ParamikoExecutor
from app.vault import Vault, load_key


def create():
    cfg = Config.from_env()
    conn = db.connect(cfg.db_path)
    db.init_schema(conn)
    state = AppState(
        config=cfg,
        conn=conn,
        vault=Vault(load_key(cfg.master_key_file)),
        executor=ParamikoExecutor(),
        session_secret=cfg.session_secret,
    )
    return build_app(state)


app = create()
