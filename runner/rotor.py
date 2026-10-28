"""One-owner, spaced ChatGPT product rotor backed by a private GitHub issue.

The controller never polls provider history.  It starts at most one provider
turn, and the turn process owns that response stream through termination.
"""

import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import organization

REPO = os.environ.get("ROTOR_STATE_REPOSITORY", "evanbrown3000/cognilode-agent-turns")
TITLE = "ChatMode rotor state"
LANES = ("provider", "corpus", "plugins", "organization")


def api(method, path, data=None):
    request = urllib.request.Request(
        "https://api.github.com" + path,
        method=method,
        data=None if data is None else json.dumps(data).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["CORE_REPO_TOKEN"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        return error.code, {"error": error.read(1000).decode("utf-8", "replace")}


def state_issue():
    status, issues = api("GET", f"/repos/{REPO}/issues?state=open&per_page=100")
    if status != 200:
        raise RuntimeError("rotor state unavailable")
    issue = next((item for item in issues if item.get("title") == TITLE), None)
    if issue:
        try:
            return issue, json.loads(issue.get("body") or "{}")
        except ValueError:
            return issue, {}
    initial = {
        "schema": "cognilode.chatmode-rotor.v1",
        "next_lane": 0,
        "active_turn": None,
        "pause_until": None,
        "last_outcome": None,
    }
    status, issue = api("POST", f"/repos/{REPO}/issues", {"title": TITLE, "body": json.dumps(initial, indent=2)})
    if status != 201:
        raise RuntimeError("rotor state creation failed")
    return issue, initial


def save(issue, state):
    status, _ = api("PATCH", f"/repos/{REPO}/issues/{issue['number']}", {"body": json.dumps(state, indent=2, sort_keys=True)})
    if status != 200:
        raise RuntimeError("rotor state commit failed")


def open_issues():
    status, issues = api("GET", f"/repos/{REPO}/issues?state=open&per_page=100")
    if status != 200:
        raise RuntimeError("organization state unavailable")
    return issues


def update_issue(issue, value):
    status, updated = api("PATCH", f"/repos/{REPO}/issues/{issue['number']}", {"body": organization.encode(value)})
    if status != 200:
        raise RuntimeError("responsibility state commit failed")
    return updated


def create_issue(value):
    title = organization.TITLE_PREFIX + value["responsibility_id"]
    status, issue = api("POST", f"/repos/{REPO}/issues", {"title": title, "body": organization.encode(value)})
    if status != 201:
        raise RuntimeError("responsibility creation failed")
    return issue


def run_responsibility(issue, value, run_id):
    value = organization.claim(value, run_id)
    update_issue(issue, value)
    environment = dict(os.environ)
    environment["COGNILODE_ASSIGNMENT"] = """You are Employee {employee_id}, serving as {role} on project {project_id} under manager {manager_id}.

Responsibility ID: {responsibility_id}

{instructions}

Complete substantive work, preserve useful artifacts and return enough detail for your manager to inspect and act on the result.
""".format(
        employee_id=value["employee"]["id"], role=value["employee"]["role"],
        project_id=value["project_id"], manager_id=value["manager_id"],
        responsibility_id=value["responsibility_id"], instructions=value["instructions"],
    )
    environment["COGNILODE_RESPONSIBILITY_ISSUE"] = str(issue["number"])
    environment["COGNILODE_RESPONSIBILITY_ID"] = value["responsibility_id"]
    process = subprocess.run(
        [sys.executable, "runner/turn.py", "organization"],
        text=True, capture_output=True, env=environment,
    )
    if process.returncode:
        # Leave a visible failed return without creating retry traffic. A manager
        # or operator can revise/requeue the responsibility after account pause.
        value["status"] = "failed"
        value["claim"] = None
        value["failure"] = {"run_id": run_id, "at": now().isoformat(), "summary": process.stderr[-2000:]}
        update_issue(issue, value)
        return process, value

    artifact = json.loads(open("turn-result.json").read())
    value = organization.returned(
        value, artifact["comment_url"], artifact.get("conversation_id"), artifact.get("terminal"),
    )
    update_issue(issue, value)
    if value.get("kind") == "manager_review":
        directive = organization.next_directive(artifact.get("text", ""))
        parent_id = value.get("parent_id")
        for parent_issue in open_issues():
            parent = organization.decode(parent_issue)
            if parent and parent["responsibility_id"] == parent_id:
                update_issue(parent_issue, organization.consumed(parent, value["responsibility_id"]))
                break
        if directive:
            create_issue(organization.new_responsibility(
                project_id=value["project_id"],
                employee_id=directive["employee_id"], role=directive["role"],
                manager_id=value.get("manager_id") or value["employee"]["id"],
                instructions=directive["instructions"],
                parent_id=value["responsibility_id"], priority=directive["priority"],
            ))
            update_issue(issue, organization.consumed(value, value["responsibility_id"]))
    else:
        create_issue(organization.manager_review(value, artifact.get("text", "")))
    return process, value


def now():
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value):
    return None if not value else dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    issue, state = state_issue()
    if state.get("active_turn"):
        print(json.dumps({"started": False, "reason": "active_turn_owned", "active_turn": state["active_turn"]}))
        return
    pause = parse_time(state.get("pause_until"))
    if pause and pause > now():
        print(json.dumps({"started": False, "reason": "account_pause", "pause_until": state["pause_until"]}))
        return
    candidates = organization.ready(open_issues())
    if candidates:
        responsibility_issue, responsibility = candidates[0]
        process, returned_state = run_responsibility(
            responsibility_issue, responsibility, os.environ.get("GITHUB_RUN_ID"),
        )
        outcome = {
            "responsibility_id": responsibility["responsibility_id"],
            "employee_id": responsibility["employee"]["id"],
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "finished_at": now().isoformat(),
            "exit_code": process.returncode,
            "status": returned_state["status"],
        }
        state["last_outcome"] = outcome
        state["pause_until"] = (now() + dt.timedelta(hours=4 if process.returncode == 0 else 12)).isoformat()
        save(issue, state)
        print(json.dumps(outcome))
        if process.returncode:
            raise SystemExit(process.returncode)
        return
    index = int(state.get("next_lane", 0)) % len(LANES)
    lane = LANES[index]
    run_id = os.environ.get("GITHUB_RUN_ID")
    state["active_turn"] = {"lane": lane, "run_id": run_id, "started_at": now().isoformat()}
    save(issue, state)
    process = subprocess.run([sys.executable, "runner/turn.py", lane], text=True, capture_output=True)
    outcome = {
        "lane": lane,
        "run_id": run_id,
        "finished_at": now().isoformat(),
        "exit_code": process.returncode,
        "summary": (process.stdout.strip().splitlines() or [""])[-1][:2000],
    }
    state["active_turn"] = None
    state["last_outcome"] = outcome
    if process.returncode == 0:
        state["next_lane"] = (index + 1) % len(LANES)
        state["pause_until"] = (now() + dt.timedelta(hours=4)).isoformat()
    else:
        # A provider rejection is account state, not permission to retry rapidly.
        state["pause_until"] = (now() + dt.timedelta(hours=12)).isoformat()
    save(issue, state)
    print(json.dumps(outcome))
    if process.returncode:
        raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
