"""Run one substantive ChatGPT product turn through B4PT0R's SDK.

The process is ephemeral.  Durable conversation state and the useful response
are committed to a private GitHub repository; provider HTTP metadata is sent to
the same Network/Operator admission endpoint used by the Free edge.
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import zipfile
from pathlib import Path

from codex_backend_sdk import CodexClient
from codex_backend_sdk.storage import TokenStore


LANES = {
    "provider": """Own implementation of the single ChatGPT.com product adapter and durable stream contract in the supplied Cognilode Core source. Preserve errors, approvals, tool events, deltas, terminal status, attachments, model, reasoning level, account, network route and request attribution without polling full history. Produce concrete replacement source or a precise patch against the supplied application. Work substantively through completion.""",
    "corpus": """Own the off-D1 corpus cutover for Cognilode Core. Implement cloud persistence for complete recent conversations, summaries, incremental committed provider events, Operator live readback, and generated foreground context. Use genuinely free services and the supplied B4PT0R session model. Produce concrete source and migration work that replaces D1 consumers and permits deletion of all databases. Work substantively through completion.""",
    "plugins": """Own the Plugin Admin cutover. Replace its failed legacy provider lane with the supplied Cognilode Core contract while preserving read, write, mutate, delete, search, credential custody and plugin factory operations. Integrate persistent Network/Operator request reporting. Produce concrete code or a reviewable patch and exercise a meaningful operation in your sandbox. Work substantively through completion.""",
    "organization": """Own the recurring organization rotor. Implement a manager-to-specialist-to-contributor loop over the supplied Framework/Harness application and its single ChatGPT product adapter. Every turn must be provider-accepted, stream into the shared corpus and Operator, return useful work, and alter the manager's next action. Produce concrete implementation artifacts and deployment handoff. Work substantively through completion.""",
}
NETWORK_EVENTS = []


def github(method, path, data=None):
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
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response) if response.length != 0 else {}


def network_event(method, path, status, content_type, elapsed_ms):
    endpoint = os.environ.get("NETWORK_INGEST_URL")
    bearer = os.environ.get("OPERATOR_TOKEN")
    if not endpoint or not bearer:
        return
    event = {
        "event_id": str(uuid.uuid4()),
        "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": "chatgpt.com",
        "producer": "cognilode-core-b4pt0r-chatmode",
        "operation": "chatmode_prompt" if path == "/backend-api/f/conversation" else "chatmode_support",
        "phase": "provider_http_response",
        "method": method,
        "url": "https://chatgpt.com" + path,
        "response_status": status,
        "elapsed_ms": elapsed_ms,
        "network_route": "github-actions-free-native",
        "environment_id": os.environ.get("GITHUB_RUN_ID"),
        "credential_ref": "chatgpt.product-session.owner-personal",
        "response_headers": {"content-type": content_type},
    }
    NETWORK_EVENTS.append(event)
    request = urllib.request.Request(
        endpoint,
        method="POST",
        data=json.dumps(event).encode(),
        headers={"Authorization": "Bearer " + bearer, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30):
            pass
    except Exception:
        # The same compact event is committed with the durable turn receipt.
        # Projection failure must never cancel an accepted upstream operation.
        event["operator_projection_pending"] = True


def payloads(response):
    lines = []
    for line in response.iter_lines(chunk_size=1, decode_unicode=True):
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        if not line:
            if lines:
                yield "\n".join(lines)
                lines = []
        elif line.startswith("data:"):
            lines.append(line[5:].lstrip())


def publish(lane, receipt, text):
    repo = os.environ.get("STATE_REPOSITORY", "evanbrown3000/cognilode-agent-turns")
    title = "ChatMode lane: " + lane
    issues = github("GET", "/repos/{}/issues?state=open&per_page=100".format(repo))
    issue = next((item for item in issues if item.get("title") == title), None)
    if issue is None:
        issue = github("POST", "/repos/{}/issues".format(repo), {
            "title": title,
            "body": "Durable response stream for the {} implementation lane.".format(lane),
        })
    header = "```json\n{}\n```\n\n".format(json.dumps(receipt, indent=2, sort_keys=True))
    chunks = [text[i:i + 55000] for i in range(0, len(text), 55000)] or [""]
    for index, chunk in enumerate(chunks, 1):
        github("POST", "/repos/{}/issues/{}/comments".format(repo, issue["number"]), {
            "body": (header if index == 1 else "") + chunk,
        })
    return issue["number"]


def publish_responsibility(receipt, text):
    repo = os.environ.get("STATE_REPOSITORY", "evanbrown3000/cognilode-agent-turns")
    number = os.environ["COGNILODE_RESPONSIBILITY_ISSUE"]
    header = "```json\n{}\n```\n\n".format(json.dumps(receipt, indent=2, sort_keys=True))
    chunks = [text[i:i + 55000] for i in range(0, len(text), 55000)] or [""]
    first = None
    for index, chunk in enumerate(chunks):
        comment = github("POST", "/repos/{}/issues/{}/comments".format(repo, number), {
            "body": (header if index == 0 else "") + chunk,
        })
        first = first or comment["html_url"]
    return first


def main():
    lane = sys.argv[1]
    assignment = os.environ.get("COGNILODE_ASSIGNMENT") or LANES[lane]
    plan = Path("core/ARCHITECTURE_PLAN.md")
    bundle = Path("cognilode-core-input.zip")
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(plan, "ARCHITECTURE_PLAN.md")
        for source in sorted(Path("core/application").rglob("*.py")):
            archive.write(source, source.relative_to("core"))
        for source in sorted(Path("core/tests").rglob("*.py")):
            archive.write(source, source.relative_to("core"))
    client = CodexClient(store=TokenStore(
        access_token=os.environ["CHATGPT_ACCESS_TOKEN"],
        account_id=os.environ["CHATGPT_ACCOUNT_ID"],
        refresh_token="",
        id_token_raw="",
    ), timeout=(15, 240), max_retries=0)
    client._session.headers.pop("OpenAI-Beta", None)
    client._session.headers.pop("originator", None)
    browser_headers = json.loads(os.environ.get("CHATGPT_BROWSER_HEADERS", "{}"))
    allowed = {"user-agent", "accept-language", "oai-device-id", "oai-did", "oai-language", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"}
    for key, value in browser_headers.items():
        if key.lower() in allowed and isinstance(value, str):
            client._session.headers[key] = value
    if os.environ.get("CHATGPT_COOKIE"):
        client._session.headers["Cookie"] = os.environ["CHATGPT_COOKIE"]

    original = client._session.request
    def observed(method, url, **kwargs):
        started = time.time()
        response = original(method, url, **kwargs)
        path = response.request.path_url.split("?", 1)[0]
        network_event(method.upper(), path, response.status_code, response.headers.get("content-type", ""), round((time.time() - started) * 1000))
        return response
    client._session.request = observed

    uploaded = client.files.upload(bundle)
    attachment = {"id": uploaded.file_id, "name": uploaded.file_name, "mime_type": uploaded.mime_type, "size": uploaded.file_size_bytes}
    message_id = str(uuid.uuid4())
    body = {
        "action": "next",
        "model": "gpt-5-6-thinking",
        "thinking_effort": "extended",
        "parent_message_id": str(uuid.uuid4()),
        "timezone": "America/Matamoros",
        "messages": [{
            "id": message_id,
            "author": {"role": "user"},
            "content": {"content_type": "text", "parts": [assignment]},
            "metadata": {"attachments": [attachment]},
        }],
    }
    client.chatgpt.conversations.prepare(body)
    response = client.chatgpt.conversations.create_stream(body)
    response.raise_for_status()
    conversation_id = None
    texts = {}
    terminal = False
    events = []
    for raw in payloads(response):
        if raw == "[DONE]":
            break
        value = json.loads(raw)
        if value.get("conversation_id"):
            conversation_id = value["conversation_id"]
        if value.get("error"):
            events.append({"type": "error", "value": value["error"]})
        message = value.get("message")
        if isinstance(message, dict) and message.get("author", {}).get("role") == "assistant":
            parts = message.get("content", {}).get("parts", [])
            text = "\n".join(part for part in parts if isinstance(part, str))
            if text:
                texts[message.get("id", str(len(texts)))] = text
            terminal = terminal or bool(message.get("end_turn") and message.get("status") == "finished_successfully")
        elif value.get("type") not in (None, "ping", "heartbeat"):
            events.append({"type": value.get("type"), "request_id": value.get("request_id")})
    final_text = "\n\n".join(texts.values())
    receipt = {
        "schema": "cognilode.chatmode-turn.v1",
        "lane": lane,
        "provider": "chatgpt.com",
        "conversation_id": conversation_id,
        "accepted": response.status_code == 200,
        "terminal": terminal,
        "response_characters": len(final_text),
        "event_summaries": events[-50:],
        "provider_http": NETWORK_EVENTS,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }
    if os.environ.get("COGNILODE_RESPONSIBILITY_ISSUE"):
        receipt["responsibility_id"] = os.environ.get("COGNILODE_RESPONSIBILITY_ID")
        receipt["result_comment_url"] = publish_responsibility(receipt, final_text)
        Path("turn-result.json").write_text(json.dumps({
            "conversation_id": conversation_id,
            "terminal": terminal,
            "comment_url": receipt["result_comment_url"],
            "text": final_text,
        }) + "\n")
    else:
        receipt["state_issue"] = publish(lane, receipt, final_text)
    Path("turn-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"lane": lane, "accepted": receipt["accepted"], "terminal": terminal, "response_characters": len(final_text), "state_issue": receipt.get("state_issue"), "responsibility_id": receipt.get("responsibility_id")}))
    if not receipt["accepted"] or not terminal or not final_text:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
