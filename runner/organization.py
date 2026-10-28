"""Durable organization state for the zero-paid GitHub-backed rotor.

GitHub issues are the checkpoint/outbox, not a second provider queue.  The
single rotor claims one responsibility and the existing provider driver owns
the resulting upstream turn through completion.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid


SCHEMA = "cognilode.responsibility.v1"
TITLE_PREFIX = "Responsibility: "
READY = "ready"
RUNNING = "running"
RETURNED = "returned"
CONSUMED = "consumed"


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def decode(issue):
    if not str(issue.get("title", "")).startswith(TITLE_PREFIX):
        return None
    try:
        value = json.loads(issue.get("body") or "{}")
    except (TypeError, ValueError):
        return None
    if value.get("schema") != SCHEMA or not value.get("responsibility_id"):
        return None
    return value


def encode(value):
    return json.dumps(value, indent=2, sort_keys=True)


def ready(issues):
    """Return ready records in deterministic priority/age order."""
    records = []
    by_id = {}
    for issue in issues:
        value = decode(issue)
        if value:
            by_id[value["responsibility_id"]] = value
            records.append((issue, value))
    candidates = []
    for issue, value in records:
        if value.get("status") != READY:
            continue
        dependencies = value.get("depends_on") or []
        if any(by_id.get(item, {}).get("status") != CONSUMED for item in dependencies):
            continue
        candidates.append((issue, value))
    candidates.sort(key=lambda row: (
        int(row[1].get("priority", 100)),
        row[1].get("created_at", ""),
        row[1]["responsibility_id"],
    ))
    return candidates


def claim(value, run_id):
    if value.get("status") != READY:
        raise ValueError("responsibility is not ready")
    result = dict(value)
    result["status"] = RUNNING
    result["claim"] = {"owner": "chatmode-single-owner", "run_id": run_id, "claimed_at": utcnow()}
    result["attempt_count"] = int(result.get("attempt_count", 0)) + 1
    result["updated_at"] = utcnow()
    return result


def returned(value, result_comment_url, conversation_id, terminal):
    result = dict(value)
    result["status"] = RETURNED
    result["claim"] = None
    result["return"] = {
        "comment_url": result_comment_url,
        "conversation_id": conversation_id,
        "terminal": bool(terminal),
        "returned_at": utcnow(),
    }
    result["updated_at"] = utcnow()
    return result


def consumed(value, manager_responsibility_id):
    result = dict(value)
    result["status"] = CONSUMED
    result["consumed_by"] = manager_responsibility_id
    result["consumed_at"] = utcnow()
    result["updated_at"] = utcnow()
    return result


def new_responsibility(*, project_id, employee_id, role, manager_id, instructions,
                       parent_id=None, depends_on=None, priority=100, kind="work"):
    timestamp = utcnow()
    return {
        "schema": SCHEMA,
        "responsibility_id": str(uuid.uuid4()),
        "project_id": project_id,
        "employee": {"id": employee_id, "role": role},
        "manager_id": manager_id,
        "kind": kind,
        "instructions": instructions,
        "parent_id": parent_id,
        "depends_on": list(depends_on or []),
        "priority": int(priority),
        "status": READY,
        "attempt_count": 0,
        "claim": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def manager_review(subordinate, result_text):
    employee = subordinate.get("employee") or {}
    manager_id = subordinate.get("manager_id") or "company-manager"
    clipped = result_text[-30000:]
    instructions = f"""You are {manager_id}, the durable manager responsible for project {subordinate['project_id']}.

Consume the returned work from {employee.get('id')} ({employee.get('role')}). Assess it substantively, decide what the project now needs, and issue the next meaningful responsibility. Do not merely summarize or acknowledge it.

RETURNED WORK
{clipped}

End with exactly one fenced JSON object using this shape:
```json
{{"employee_id":"durable-role-id","role":"manager|specialist|contributor","instructions":"complete next responsibility","priority":100}}
```
"""
    return new_responsibility(
        project_id=subordinate["project_id"],
        employee_id=manager_id,
        role="manager",
        manager_id=manager_id,
        instructions=instructions,
        parent_id=subordinate["responsibility_id"],
        priority=max(1, int(subordinate.get("priority", 100)) - 1),
        kind="manager_review",
    )


def next_directive(text):
    blocks = re.findall(r"```json\s*([\s\S]*?)\s*```", text or "", re.I)
    for raw in reversed(blocks):
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if all(isinstance(value.get(key), str) and value[key].strip()
               for key in ("employee_id", "role", "instructions")):
            return {
                "employee_id": value["employee_id"].strip(),
                "role": value["role"].strip(),
                "instructions": value["instructions"].strip(),
                "priority": int(value.get("priority", 100)),
            }
    return None

