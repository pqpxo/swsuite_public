# version 3
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db as _db
from app import prefix as _prefix
from app.repos import settings as _settings_repo
from app.runner import JobBroadcaster
from app.security import hash_password as _hash_password
from app.updater import AptUpdater


@dataclass
class AppState:
    config: object
    conn: object
    vault: object
    executor: object
    session_secret: str
    updater: object = field(default_factory=AptUpdater)
    broadcaster: JobBroadcaster | None = None


_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR),
                            context_processors=[_prefix.context])


def maybe_bootstrap_admin(conn) -> None:
    """Create a first-run admin account if none exists yet."""
    s = _settings_repo.get(conn)
    if s["admin_username"]:
        return
    pw = os.environ.get("KICKER_BOOTSTRAP_PASSWORD", "admin")
    _settings_repo.set_admin(conn, username="admin", password_hash=_hash_password(pw))


def build_app(state: AppState) -> FastAPI:
    app = FastAPI(title="SWKick")
    app.state.kicker = state
    # Mount-path support for the SWSuite proxy; a no-op when run standalone.
    app.add_middleware(_prefix.PrefixMiddleware)

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.on_event("startup")
    async def _startup():
        if state.broadcaster is None:
            state.broadcaster = JobBroadcaster(asyncio.get_running_loop())
        maybe_bootstrap_admin(state.conn)
        if getattr(state, "config", None) is not None:
            from app.notify import NullNotifier, PushoverNotifier
            from app.repos import settings as settings_repo
            from app.scheduler import make_scheduler

            def get_notifier(conn):
                tok, usr = settings_repo.get_pushover(conn, state.vault)
                return PushoverNotifier(tok, usr) if tok and usr else NullNotifier()

            sched = make_scheduler(
                get_conn=lambda: _db.connect(state.config.db_path),
                vault=state.vault, executor=state.executor,
                updater=state.updater, get_notifier=get_notifier,
                interval_hours=state.config.poll_interval_hours,
            )
            sched.start()
            app.state.scheduler = sched

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    from app.routes.auth import _Redirect

    @app.exception_handler(_Redirect)
    async def _redirect_handler(request, exc):  # noqa: ANN001
        return RedirectResponse(exc.location, status_code=302)

    from app.routes import (auth, credentials, dashboard, groups, hosts, jobs,
                            settings)
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(hosts.router)
    app.include_router(groups.router)
    app.include_router(credentials.router)
    app.include_router(jobs.router)
    app.include_router(settings.router)
    return app
