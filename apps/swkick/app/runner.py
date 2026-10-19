from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from app.models import Credential, HostConn, RunResult
from app.repos import credentials as creds_repo
from app.repos import hosts as hosts_repo
from app.repos import jobs as jobs_repo
from app.updater import Updater
from app.vault import Vault


class JobBroadcaster:
    """Bridges blocking worker threads to async SSE subscribers."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._subs: dict[int, set[asyncio.Queue]] = {}

    async def subscribe(self, job_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(job_id, set()).add(q)
        return q

    def unsubscribe(self, job_id: int, q: asyncio.Queue) -> None:
        subs = self._subs.get(job_id)
        if subs and q in subs:
            subs.discard(q)

    def publish(self, job_id: int, line: Optional[str]) -> None:
        for q in list(self._subs.get(job_id, ())):
            self._loop.call_soon_threadsafe(q.put_nowait, line)

    def close(self, job_id: int) -> None:
        self.publish(job_id, None)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_host_conn(conn: sqlite3.Connection, vault: Vault, host_id: int) -> HostConn:
    h = hosts_repo.get(conn, host_id)
    if h is None:
        raise ValueError(f"unknown host {host_id}")
    cred: Credential | None = None
    if h["credential_id"] is not None:
        cred = creds_repo.get(conn, vault, h["credential_id"])
    if cred is None:
        cred = Credential(id=0, name="(none)", type="password")
    return HostConn(hostname=h["hostname"], port=h["ssh_port"],
                    username=h["ssh_username"], credential=cred)


def run_check(conn, vault, ex, updater: Updater, host_id: int, *,
              trigger: str) -> int:
    jid = jobs_repo.create(conn, host_id=host_id, kind="check", trigger=trigger)
    try:
        hc = build_host_conn(conn, vault, host_id)
        packages = updater.check(ex, hc)
        hosts_repo.update_status(conn, host_id, update_count=len(packages),
                                 reachable=True, last_checked_at=_now())
        jobs_repo.append_output(conn, jid,
                                f"{len(packages)} package(s) upgradable\n")
        jobs_repo.finish(conn, jid, status="success", exit_code=0,
                         packages=packages)
    except Exception as exc:  # noqa: BLE001 - record and continue
        hosts_repo.update_status(conn, host_id, update_count=0, reachable=False,
                                 last_checked_at=_now())
        jobs_repo.append_output(conn, jid, f"ERROR: {exc}\n")
        jobs_repo.finish(conn, jid, status="failed", exit_code=1)
    return jid


def run_upgrade(conn, vault, ex, updater: Updater, host_id: int, *,
                trigger: str, broadcaster: "JobBroadcaster | None" = None) -> int:
    jid = jobs_repo.create(conn, host_id=host_id, kind="upgrade", trigger=trigger)
    result = RunResult()
    try:
        hc = build_host_conn(conn, vault, host_id)
        for line in updater.upgrade(ex, hc, result):
            jobs_repo.append_output(conn, jid, line)
            if broadcaster is not None:
                broadcaster.publish(jid, line)
        status = "success" if (result.exit_code or 0) == 0 else "failed"
        jobs_repo.finish(conn, jid, status=status, exit_code=result.exit_code or 0)
        # refresh update count after an upgrade
        try:
            packages = updater.check(ex, hc)
            hosts_repo.update_status(conn, host_id, update_count=len(packages),
                                     reachable=True, last_checked_at=_now())
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        jobs_repo.append_output(conn, jid, f"ERROR: {exc}\n")
        hosts_repo.update_status(conn, host_id, update_count=0, reachable=False,
                                 last_checked_at=_now())
        jobs_repo.finish(conn, jid, status="failed", exit_code=1)
    finally:
        if broadcaster is not None:
            broadcaster.close(jid)
    return jid
