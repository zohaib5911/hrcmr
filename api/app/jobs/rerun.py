"""Which scheduled jobs a platform admin may run again after a failure (T17.6, owner answer 3).

A job is listed only if running it a second time is harmless: it reads, upserts, replaces or deletes
state that a second pass leaves the same, and it sends nothing. A job that sends mail or writes
notifications (reminders, digests, deletion and export e-mails, the email sweep) is never listed:
its owner re-runs the business action instead, and a retry could double-send. Jobs that take
arguments are never listed either, because their arguments are never stored (jobs/audit.py).

Checked by reading each job (2026-11-08): ``rtw_status_daily`` only counts rows;
``bank_holidays_weekly`` upserts (``on_conflict_do_update``); ``cloudflare_ranges_weekly`` replaces
the stored ranges; ``files_orphans_daily`` deletes only files no row points to;
``report_jobs_sweep`` claims queued report jobs.
"""

from __future__ import annotations

RERUNNABLE: frozenset[str] = frozenset(
    {
        "rtw_status_daily",
        "bank_holidays_weekly",
        "cloudflare_ranges_weekly",
        "files_orphans_daily",
        "report_jobs_sweep",
    }
)
RERUN_PREFIX = "rerun_"


def rerun_name(job: str) -> str:
    """The ARQ function name a re-run is enqueued under. It differs from the cron job's name, which
    ARQ would otherwise overwrite in its function table."""
    return f"{RERUN_PREFIX}{job}"
