import json
from datetime import datetime
import frappe
from frappe.utils import now_datetime
import math

EVENT_START = "Start"
EVENT_PAUSE = "Pause"
EVENT_RESUME = "Resume"
EVENT_FINISH = "Finish"
EVENT_CANCELLED = "Cancelled"

def _load_log(doc):
    try:
        return json.loads(doc.custom_timer_log_json or "[]")
    except Exception:
        return []

def _save_log(doc, log):
    doc.custom_timer_log_json = json.dumps(log, default=str)

def _append_log(doc, action, ts):
    log = _load_log(doc)
    log.append({"action": action, "ts": ts.isoformat()})
    _save_log(doc, log)

def _add_run_seconds(doc, seconds):
    doc.custom_timer_total_seconds = ((doc.custom_timer_total_seconds or 0) + int(seconds))

def _diff_seconds(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds())

def _prev_workflow_state(doc):
    # Use DB value (None if new)
    if doc.is_new():
        return None
    return frappe.db.get_value(doc.doctype, doc.name, "workflow_state") or frappe.db.get_value(doc.doctype, doc.name, "status")

def _cur_state(doc):
    # Prefer workflow_state; fall back to status on setups that change status directly
    return getattr(doc, "workflow_state", None) or getattr(doc, "status", None)

def on_before_save(doc, method=None):
    """
    Runs on every save; we detect transitions by comparing DB's workflow_state/status vs current.
    """
    prev = _prev_workflow_state(doc)
    curr = _cur_state(doc)

    # Ignore if no state yet
    if not curr:
        return

    now = now_datetime()

    # START (Not Started -> In Progress)
    if (prev in (None, "Not Started") and curr == "In Progress") or _is_action(doc, EVENT_START):
        if not doc.custom_timer_start:
            doc.custom_timer_start = now
        # Start/resume counting from now
        doc.custom_timer_last_resume_at = now
        _append_log(doc, EVENT_START, now)

    # PAUSE (In Progress -> Paused)
    if prev == "In Progress" and curr == "Paused" or _is_action(doc, EVENT_PAUSE):
        if doc.custom_timer_last_resume_at:
            _add_run_seconds(doc, _diff_seconds(doc.custom_timer_last_resume_at, now))
            doc.custom_timer_last_resume_at = None
        _append_log(doc, EVENT_PAUSE, now)

    # RESUME (Paused -> In Progress)
    if prev == "Paused" and curr == "In Progress" or _is_action(doc, EVENT_RESUME):
        doc.custom_timer_last_resume_at = now
        _append_log(doc, EVENT_RESUME, now)

    # FINISH/COMPLETE (In Progress -> Completed)
    if curr in ("Completed", "Finished") or _is_action(doc, EVENT_FINISH):
        # finalize accumulation if still running
        if doc.custom_timer_last_resume_at:
            _add_run_seconds(doc, _diff_seconds(doc.custom_timer_last_resume_at, now))
            doc.custom_timer_last_resume_at = None
        if not doc.custom_timer_finish:
            doc.custom_timer_finish = now
        _append_log(doc, EVENT_FINISH, now)

    # CANCELLED (optional)
    if curr == "Cancelled" or _is_action(doc, EVENT_CANCELLED):
        # If it was running, stop counting at cancel time
        if doc.custom_timer_last_resume_at:
            _add_run_seconds(doc, _diff_seconds(doc.custom_timer_last_resume_at, now))
            doc.custom_timer_last_resume_at = None
        _append_log(doc, EVENT_CANCELLED, now)

def _is_action(doc, label):
    """
    Fallback if you choose to pass a client hint via doc._workflow_clicked_action (set in client script).
    """
    return getattr(doc, "_workflow_clicked_action", None) == label

def on_submit(doc, method=None):
    """
    Safety: ensure totals are finalized on submit (Completed).
    """


    if getattr(doc, "status", None) in ("Completed", "Finished") or getattr(doc, "workflow_state", None) in ("Completed", "Finished"):
        now = now_datetime()
        if doc.custom_timer_last_resume_at:
            _add_run_seconds(doc, _diff_seconds(doc.custom_timer_last_resume_at, now))
            doc.custom_timer_last_resume_at = None
        if not doc.custom_timer_finish:
            doc.custom_timer_finish = now
            #doc.save()
        # Append FINISH if it wasn't logged yet
        log = _load_log(doc)
        if not any(e.get("action") == EVENT_FINISH for e in log):
            _append_log(doc, EVENT_FINISH, now)

