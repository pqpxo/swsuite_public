from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.app import templates
from app.repos import settings as settings_repo
from app.security import make_session, read_session, verify_password

router = APIRouter()

COOKIE = "kicker_session"


class _Redirect(Exception):
    def __init__(self, location: str):
        self.location = location


def current_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    return read_session(token, request.app.state.kicker.session_secret)


def require_login(request: Request) -> str:
    user = current_user(request)
    if user is None:
        raise _Redirect("/login")
    return user


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    s = settings_repo.get(request.app.state.kicker.conn)
    ok = (s["admin_username"] == username and s["admin_password_hash"]
          and verify_password(password, s["admin_password_hash"]))
    if not ok:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Invalid credentials"},
            status_code=200)
    token = make_session(username, request.app.state.kicker.session_secret)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax")
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp
