# version 2
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.app import templates
from app.repos import hosts as hosts_repo
from app.repos import jobs as jobs_repo
from app.routes.auth import require_login

router = APIRouter()

DIMENSIONS = [("priority", "Priority"), ("host_type", "Host Type"),
              ("device_type", "Device Type")]
_LABELS = dict(DIMENSIONS)


def _status(host) -> str:
    if host["last_checked_at"] is None:
        return "unknown"
    if not host["reachable"]:
        return "offline"
    if host["update_count"] == 0:
        return "ok"
    if host["update_count"] <= 5:
        return "some"
    return "many"


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, group_by: str = "priority",
              user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    if group_by not in _LABELS:
        group_by = "priority"
    grouped = hosts_repo.list_grouped(conn, group_by)
    all_hosts = hosts_repo.list_all(conn)
    total_updates = sum(h["update_count"] for h in all_hosts)
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "grouped": grouped, "group_by": group_by,
        "group_label": _LABELS[group_by],
        "dimensions": DIMENSIONS, "status_of": _status,
        "host_count": len(all_hosts), "total_updates": total_updates,
        "online_count": sum(h["reachable"] and h["last_checked_at"] is not None for h in all_hosts),
        "offline_count": sum(not h["reachable"] and h["last_checked_at"] is not None for h in all_hosts),
    })


@router.get("/hosts/{host_id}", response_class=HTMLResponse)
def host_detail(request: Request, host_id: int,
                user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    host = hosts_repo.get(conn, host_id)
    history = jobs_repo.list_recent(conn, host_id=host_id, limit=50)
    return templates.TemplateResponse("host_detail.html", {
        "request": request, "host": host, "history": history,
    })
