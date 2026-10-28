"""Semantic conversation admission for the one ChatGPT product turn owner.

The provider stream remains owned by turn.py. This module commits only useful
semantic projections: the complete user prompt, the final assistant message,
compact activities/errors/approvals and a terminal outcome. It never polls
provider history and never stores raw HTTP bodies or headers.
"""
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request
import uuid


def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def stable(value):
    return re.sub(r"[^A-Za-z0-9._:-]", "-", str(value))[:192].strip("-") or uuid.uuid4().hex


class Projection:
    def __init__(self, lane, assignment, model, reasoning):
        self.lane = lane
        self.assignment = assignment
        self.model = model
        self.reasoning = reasoning
        self.run_id = stable(os.environ.get("GITHUB_RUN_ID") or uuid.uuid4().hex)
        self.conversation_id = stable("chatmode-rotor-{}-{}".format(self.run_id, lane))
        self.endpoint = os.environ.get("KNOWLEDGE_INGEST_URL", "https://cognilode-conversation-corpus-operator.evanbrown3000.workers.dev/v1/events")
        self.token = os.environ.get("OPERATOR_TOKEN", "")
        self.revision = 0
        self.receipts = []

    def source(self, native_conversation_id=None):
        value = {
            "provider": "chatgpt.com",
            "account": "chatgpt.product-session.owner-personal",
            "producer": "cognilode-core-b4pt0r-chatmode",
            "native_turn_id": self.run_id,
        }
        if native_conversation_id:
            value["native_conversation_id"] = str(native_conversation_id)
        return value

    def admit(self, event_type, content, native_conversation_id=None, event_id=None, occurred_at=None):
        self.revision += 1
        event = {
            "event_id": stable(event_id or "{}-{:03d}-{}".format(self.conversation_id, self.revision, event_type)),
            "conversation_id": self.conversation_id,
            "type": event_type,
            "revision": 1,
            "occurred_at": occurred_at or timestamp(),
            "source": self.source(native_conversation_id),
            "content": content,
        }
        request = urllib.request.Request(self.endpoint, method="POST", data=json.dumps(event).encode(), headers={
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "User-Agent": "Cognilode-ChatMode-Rotor/1",
        })
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                result = json.load(response)
            receipt = {"event_id": event["event_id"], "type": event_type, "admitted": bool(result.get("admitted")), "commit": result.get("commit"), "duplicate": result.get("duplicate", False)}
        except urllib.error.HTTPError as error:
            receipt = {"event_id": event["event_id"], "type": event_type, "admitted": False, "status": error.code, "error": error.read(500).decode("utf-8", "replace")}
        except Exception as error:
            receipt = {"event_id": event["event_id"], "type": event_type, "admitted": False, "error": type(error).__name__ + ": " + str(error)[:300]}
        self.receipts.append(receipt)
        return receipt

    def begin(self):
        title = "ChatMode {} work".format(self.lane)
        self.admit("conversation.opened", {"title": title, "lane": self.lane, "model": self.model, "reasoning_level": self.reasoning})
        self.admit("message.committed", {"message_id": stable(self.conversation_id + "-user"), "role": "user", "body": self.assignment, "title": title})

    def activities(self, network_events, native_conversation_id=None):
        for index, observation in enumerate(network_events):
            self.admit("activity.committed", {
                "activity_id": stable("{}-http-{}".format(self.conversation_id, index + 1)),
                "title": "ChatGPT {} {}".format(observation.get("method", "HTTP"), observation.get("response_status", "unknown")),
                "operation": observation.get("operation"),
                "phase": observation.get("phase"),
                "method": observation.get("method"),
                "endpoint": observation.get("url"),
                "response_status": observation.get("response_status"),
                "elapsed_ms": observation.get("elapsed_ms"),
                "network_route": observation.get("network_route"),
                "environment_id": observation.get("environment_id"),
                "credential_ref": observation.get("credential_ref"),
                "content_type": (observation.get("response_headers") or {}).get("content-type"),
            }, native_conversation_id)

    def failure(self, error, network_events, native_conversation_id=None):
        self.activities(network_events, native_conversation_id)
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
        detail = str(error)
        if response is not None:
            try:
                body = response.json()
                detail = body.get("detail") or body.get("error") or detail
            except Exception:
                pass
        self.admit("error.committed", {
            "error_id": stable(self.conversation_id + "-provider-error"),
            "title": "ChatGPT provider request failed",
            "category": "provider_http_rejection" if status else "provider_transport_error",
            "status": status,
            "message": str(detail)[:2000],
            "retry_policy": "account_pause_no_automatic_retry",
            "lane": self.lane,
            "model": self.model,
            "reasoning_level": self.reasoning,
        }, native_conversation_id)
        self.admit("outcome.committed", {"outcome_id": stable(self.conversation_id + "-outcome"), "status": "failed", "terminal": True, "provider_status": status, "retry_policy": "account_pause_no_automatic_retry"}, native_conversation_id)

    def success(self, text, network_events, provider_events, native_conversation_id=None):
        self.activities(network_events, native_conversation_id)
        for index, event in enumerate(provider_events):
            kind = "error.committed" if event.get("type") == "error" else "activity.committed"
            self.admit(kind, {"event_id": stable("{}-stream-{}".format(self.conversation_id, index + 1)), "title": "ChatGPT stream {}".format(event.get("type") or "event"), "provider_event": event}, native_conversation_id)
        self.admit("message.committed", {"message_id": stable(self.conversation_id + "-assistant"), "role": "assistant", "body": text, "title": "ChatMode {} result".format(self.lane)}, native_conversation_id)
        self.admit("outcome.committed", {"outcome_id": stable(self.conversation_id + "-outcome"), "status": "completed", "terminal": True, "response_characters": len(text)}, native_conversation_id)

    def summary(self):
        return {"conversation_id": self.conversation_id, "events": len(self.receipts), "admitted": sum(1 for item in self.receipts if item.get("admitted")), "failed": [item for item in self.receipts if not item.get("admitted")]}
