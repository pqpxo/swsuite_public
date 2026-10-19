from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.app import templates
from app.repos import settings as settings_repo
from app.routes.auth import require_login
from app.security import hash_password

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
def page(request: Request, user: str = Depends(require_login)):
    s = settings_repo.get(request.app.state.kicker.conn)
    return templates.TemplateResponse("settings.html", {"request": request, "s": s})


@router.post("/settings/admin")
def set_admin(request: Request, username: str = Form(...), password: str = Form(...),
              user: str = Depends(require_login)):
    settings_repo.set_admin(request.app.state.kicker.conn,
                            username=username, password_hash=hash_password(password))
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/poll")
def set_poll(request: Request, poll_interval_hours: int = Form(...),
             user: str = Depends(require_login)):
    settings_repo.set_poll_interval(request.app.state.kicker.conn, poll_interval_hours)
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/pushover")
def set_pushover(request: Request, token: str = Form(""),
                 user_key: str = Form("", alias="user"),
                 user: str = Depends(require_login)):
    k = request.app.state.kicker
    settings_repo.set_pushover(k.conn, k.vault, token=token or None,
                               user=user_key or None)
    return RedirectResponse("/settings", status_code=303)
