from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from app.app import templates
from app.models import RunResult
from app.repos import hosts as hosts_repo
from app.repos import jobs as jobs_repo
from app.routes.auth import require_login
from app.runner import build_host_conn, run_check

router = APIRouter()


@router.post("/hosts/{host_id}/upgrade")
async def trigger_upgrade(request: Request, host_id: int,
                          user: str = Depends(require_login)):
    k = request.app.state.kicker
    loop = asyncio.get_running_loop()
    # create the job synchronously so we can return its id immediately
    jid = jobs_repo.create(k.conn, host_id=host_id, kind="upgrade", trigger="manual")

    def work():
        result = RunResult()
        try:
            hc = build_host_conn(k.conn, k.vault, host_id)
            for line in k.updater.upgrade(k.executor, hc, result):
                jobs_repo.append_output(k.conn, jid, line)
                if k.broadcaster:
                    k.broadcaster.publish(jid, line)
            status = "success" if (result.exit_code or 0) == 0 else "failed"
            jobs_repo.finish(k.conn, jid, status=status,
                             exit_code=result.exit_code or 0)
        except Exception as exc:  # noqa: BLE001
            jobs_repo.append_output(k.conn, jid, f"ERROR: {exc}\n")
            jobs_repo.finish(k.conn, jid, status="failed", exit_code=1)
        finally:
            if k.broadcaster:
                k.broadcaster.close(jid)

    loop.run_in_executor(None, work)
    return {"job_id": jid}


@router.post("/hosts/{host_id}/check")
async def trigger_check(request: Request, host_id: int,
                        user: str = Depends(require_login)):
    k = request.app.state.kicker
    loop = asyncio.get_running_loop()
    jid_holder: dict[str, int] = {}

    def work():
        jid_holder["id"] = run_check(k.conn, k.vault, k.executor, k.updater,
                                     host_id, trigger="manual")

    await loop.run_in_executor(None, work)
    return {"job_id": jid_holder["id"]}


@router.post("/check-all")
async def check_all(request: Request, user: str = Depends(require_login)):
    k = request.app.state.kicker

    def work():
        for h in hosts_repo.list_enabled(k.conn):
            run_check(k.conn, k.vault, k.executor, k.updater, h["id"],
                      trigger="manual")

    await asyncio.get_running_loop().run_in_executor(None, work)
    return {"status": "ok"}


@router.get("/jobs/{job_id}/output")
def job_output(request: Request, job_id: int, user: str = Depends(require_login)):
    job = jobs_repo.get(request.app.state.kicker.conn, job_id)
    return {"status": job["status"], "output": job["output_log"]}


@router.get("/jobs/{job_id}/stream")
async def job_stream(request: Request, job_id: int,
                     user: str = Depends(require_login)):
    k = request.app.state.kicker
    broadcaster = k.broadcaster
    queue = await broadcaster.subscribe(job_id)

    existing = jobs_repo.get(k.conn, job_id)
    prefix = existing["output_log"] if existing else ""

    async def event_gen():
        if prefix:
            for line in prefix.splitlines(keepends=True):
                yield f"data: {line.rstrip(chr(10))}\n\n"
        try:
            while True:
                line = await queue.get()
                if line is None:
                    yield "event: done\ndata: end\n\n"
                    break
                yield f"data: {line.rstrip(chr(10))}\n\n"
        finally:
            broadcaster.unsubscribe(job_id, queue)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request, user: str = Depends(require_login)):
    conn = request.app.state.kicker.conn
    jobs = jobs_repo.list_recent(conn, limit=200)
    return templates.TemplateResponse("logs.html", {"request": request, "jobs": jobs})
