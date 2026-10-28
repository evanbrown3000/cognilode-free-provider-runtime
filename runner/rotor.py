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
