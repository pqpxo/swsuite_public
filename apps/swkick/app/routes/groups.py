# version 2
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.app import templates
from app.repos import groups as groups_repo
from app.routes.auth import require_login

router = APIRouter()

DIMENSIONS = [("priority", "Priority"), ("host_type", "Host Type"),
              ("device_type", "Device Type")]
LABELS = dict(DIMENSIONS)


def _create_group(conn, dimension: str, name: str) -> int:
    if dimension not in LABELS or not name.strip():
        raise HTTPException(status_code=422, detail="Select a dimension and enter a group name")
    try:
        return groups_repo.create(conn, dimension, name)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="This group already exists in that dimension"
        ) from exc


@router.get("/groups", response_class=HTMLResponse)
def page(request: Request, user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    by_dim = {label: groups_repo.list_by_dimension(conn, dim)
              for dim, label in DIMENSIONS}
    counts = {g["id"]: groups_repo.count_hosts(conn, g["id"])
              for groups in by_dim.values() for g in groups}
    return templates.TemplateResponse("groups.html", {
        "request": request, "by_dim": by_dim,
        "dimensions": DIMENSIONS, "host_counts": counts,
    })


@router.post("/groups/new")
def create(request: Request, dimension: str = Form(...), name: str = Form(...),
           user: str = Depends(require_login)):
    _create_group(request.app.state.kicker.conn, dimension, name)
    return RedirectResponse("/groups", status_code=303)


@router.post("/groups/quick-create")
def quick_create(request: Request, dimension: str = Form(...),
                 name: str = Form(...), user: str = Depends(require_login)):
    group_id = _create_group(request.app.state.kicker.conn, dimension, name)
    return {"id": group_id, "dimension": dimension,
            "dimension_label": LABELS[dimension], "name": name.strip()}


@router.post("/groups/{group_id}/quick-delete")
def quick_delete(request: Request, group_id: int,
                 user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    if groups_repo.get(conn, group_id) is None:
        raise HTTPException(status_code=404, detail="Group not found")
    groups_repo.delete(conn, group_id)
    return {"status": "ok"}


@router.post("/groups/{group_id}/delete")
def delete(request: Request, group_id: int, user: str = Depends(require_login)):
    groups_repo.delete(request.app.state.kicker.conn, group_id)
    return RedirectResponse("/groups", status_code=303)
