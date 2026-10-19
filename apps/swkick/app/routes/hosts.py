# version 2
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.app import templates
from app.repos import credentials as creds_repo
from app.repos import groups as groups_repo
from app.repos import hosts as hosts_repo
from app.routes.auth import require_login

router = APIRouter()


@router.get("/hosts", response_class=HTMLResponse)
def page(request: Request, user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    return templates.TemplateResponse("hosts.html", {
        "request": request, "hosts": hosts_repo.list_all(conn)})


@router.get("/hosts/new/form", response_class=HTMLResponse)
def new_form(request: Request, user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    return templates.TemplateResponse("host_form.html", {
        "request": request, "host": None,
        "credentials": creds_repo.list_all(conn),
        "groups": groups_repo.list_all(conn), "selected_groups": []})


@router.post("/hosts/new")
def create(request: Request, name: str = Form(...), hostname: str = Form(...),
           ssh_port: int = Form(22), ssh_username: str = Form(...),
           credential_id: str = Form(""), os_label: str = Form(""),
           group_ids: list[int] = Form(default=[]),
           user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    hid = hosts_repo.create(conn, name=name, hostname=hostname, ssh_port=ssh_port,
                            ssh_username=ssh_username,
                            credential_id=int(credential_id) if credential_id else None,
                            os_label=os_label or None)
    if group_ids:
        hosts_repo.set_groups(conn, hid, group_ids)
    return RedirectResponse("/", status_code=303)


@router.post("/hosts/{host_id}/delete")
def delete(request: Request, host_id: int, user: str = Depends(require_login)):
    hosts_repo.delete(request.app.state.kicker.conn, host_id)
    return RedirectResponse("/hosts", status_code=303)


@router.get("/hosts/{host_id}/edit", response_class=HTMLResponse)
def edit_form(request: Request, host_id: int, user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    host = hosts_repo.get(conn, host_id)
    if host is None:
        raise HTTPException(status_code=404, detail="Host not found")
    return templates.TemplateResponse("host_form.html", {
        "request": request, "host": host,
        "credentials": creds_repo.list_all(conn),
        "groups": groups_repo.list_all(conn),
        "selected_groups": hosts_repo.group_ids_for(conn, host_id),
    })


@router.post("/hosts/{host_id}/edit")
def edit(request: Request, host_id: int, name: str = Form(...),
         hostname: str = Form(...), ssh_port: int = Form(22),
         ssh_username: str = Form(...), credential_id: str = Form(""),
         os_label: str = Form(""), group_ids: list[int] = Form(default=[]),
         user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    if hosts_repo.get(conn, host_id) is None:
        raise HTTPException(status_code=404, detail="Host not found")
    if not 1 <= ssh_port <= 65535:
        raise HTTPException(status_code=422, detail="Invalid SSH port")
    hosts_repo.update(conn, host_id, name=name, hostname=hostname,
                      ssh_port=ssh_port, ssh_username=ssh_username,
                      credential_id=int(credential_id) if credential_id else None,
                      os_label=os_label or None)
    hosts_repo.set_groups(conn, host_id, group_ids)
    return RedirectResponse(f"/hosts/{host_id}", status_code=303)
