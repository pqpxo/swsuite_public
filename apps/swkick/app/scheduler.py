from __future__ import annotations

import sqlite3

from apscheduler.schedulers.background import BackgroundScheduler

from app.notify import Notifier, newly_updated_hosts
from app.repos import hosts as hosts_repo
from app.repos import settings as settings_repo
from app.runner import run_check
from app.updater import Updater
from app.vault import Vault


def poll_all(conn: sqlite3.Connection, vault: Vault, executor, updater: Updater,
             notifier: Notifier) -> None:
    for host in hosts_repo.list_enabled(conn):
        run_check(conn, vault, executor, updater, host["id"], trigger="scheduled")

    new_state = {h["name"]: h["update_count"] for h in hosts_repo.list_all(conn)}
    prev_state = settings_repo.get_notified_state(conn)
    new_hosts = newly_updated_hosts(prev_state, new_state)
    if new_hosts:
        lines = "\n".join(f"{n}: {new_state[n]} updates" for n in new_hosts)
        notifier.send("Kicker: updates available", lines)
    settings_repo.set_notified_state(conn, new_state)


def make_scheduler(get_conn, vault, executor, updater, get_notifier,
                   interval_hours: int) -> BackgroundScheduler:
    sched = BackgroundScheduler()

    def job():
        conn = get_conn()
        try:
            poll_all(conn, vault, executor, updater, get_notifier(conn))
        finally:
            conn.close()

    sched.add_job(job, "interval", hours=interval_hours, id="poll_all",
                  next_run_time=None)
    return sched
