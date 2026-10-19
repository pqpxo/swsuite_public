# version 3
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.app import templates
from app.repos import credentials as creds_repo
from app.routes.auth import require_login

router = APIRouter()


def _validate_type(type: str) -> None:
    if type not in ("password", "ssh_key"):
        raise HTTPException(status_code=422, detail="Invalid credential type")


@router.get("/credentials", response_class=HTMLResponse)
def page(request: Request, user: str = Depends(require_login)):
    items = creds_repo.list_all(request.app.state.kicker.conn)
    return templates.TemplateResponse("credentials.html", {
        "request": request, "items": items, "credential": None,
    })


@router.get("/credentials/{cred_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, cred_id: int, user: str = Depends(require_login)):
    credential = creds_repo.get_metadata(request.app.state.kicker.conn, cred_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return templates.TemplateResponse("credentials.html", {
        "request": request, "items": creds_repo.list_all(request.app.state.kicker.conn),
        "credential": credential,
    })



@router.post("/credentials/quick-create", status_code=201)
def quick_create(request: Request, name: str = Form(...), type: str = Form(...),
                 private_key: str = Form(""), passphrase: str = Form(""),
                 password: str = Form(""), sudo_password: str = Form(""),
                 user: str = Depends(require_login)):
    """Save a credential without navigating away from an unfinished host form.

    Return safe metadata only: SSH secrets must never be sent to the browser.
    """
    _validate_type(type)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Enter a credential name")
    if type == "password" and not password:
        raise HTTPException(status_code=422, detail="Enter the SSH login password")
    if type == "ssh_key" and not private_key.strip():
        raise HTTPException(status_code=422, detail="Enter an SSH private key")
    k = request.app.state.kicker
    cred_id = creds_repo.create(
        k.conn, k.vault, name=name, type=type,
        private_key=private_key if type == "ssh_key" else None,
        passphrase=passphrase or None if type == "ssh_key" else None,
        password=password if type == "password" else None,
        sudo_password=sudo_password or None,
    )
    return {"id": cred_id, "name": name, "type": type}


@router.post("/credentials/new")
def create(request: Request, name: str = Form(...), type: str = Form(...),
           private_key: str = Form(""), passphrase: str = Form(""),
           password: str = Form(""), sudo_password: str = Form(""),
           user: str = Depends(require_login)):
    _validate_type(type)
    k = request.app.state.kicker
    creds_repo.create(
        k.conn, k.vault, name=name.strip(), type=type,
        private_key=(private_key or None) if type == "ssh_key" else None,
        passphrase=(passphrase or None) if type == "ssh_key" else None,
        password=(password or None) if type == "password" else None,
        sudo_password=sudo_password or None,
    )
    return RedirectResponse("/credentials", status_code=303)


@router.post("/credentials/{cred_id}/edit")
def edit(request: Request, cred_id: int, name: str = Form(...),
         type: str = Form(...), private_key: str = Form(""),
         passphrase: str = Form(""), password: str = Form(""),
         sudo_password: str = Form(""),
         clear_private_key: bool = Form(False),
         clear_passphrase: bool = Form(False),
         clear_password: bool = Form(False),
         clear_sudo_password: bool = Form(False),
         user: str = Depends(require_login)):
    _validate_type(type)
    k = request.app.state.kicker
    existing = creds_repo.get_metadata(k.conn, cred_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    if existing["type"] != type:
        new_auth = private_key.strip() if type == "ssh_key" else password.strip()
        if not new_auth:
            raise HTTPException(
                status_code=422,
                detail="Provide a new SSH key or login password when changing credential type",
            )
    creds_repo.update(
        k.conn, k.vault, cred_id, name=name.strip(), type=type,
        private_key=private_key or None, passphrase=passphrase or None,
        password=password or None, sudo_password=sudo_password or None,
        clear_private_key=clear_private_key,
        clear_passphrase=clear_passphrase,
        clear_password=clear_password,
        clear_sudo_password=clear_sudo_password,
    )
    return RedirectResponse("/credentials", status_code=303)


@router.post("/credentials/{cred_id}/delete")
def delete(request: Request, cred_id: int, user: str = Depends(require_login)):
    creds_repo.delete(request.app.state.kicker.conn, cred_id)
    return RedirectResponse("/credentials", status_code=303)
