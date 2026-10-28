"""Own four ChatGPT web turns in one zero-paid cloud browser session."""

import asyncio
import json
import os
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

from playwright.async_api import async_playwright


ASSIGNMENTS = (
    "Own the single ChatGPT product adapter cutover in the attached Cognilode Core source. Produce concrete replacement source for provider-owned submission, streaming, approvals, errors, attachments, recovery and request attribution. Use the existing B4PT0R Framework, Harness and SDK composition. Do not design another sender or queue. Work substantively through a reviewable artifact.",
    "Own the off-D1 corpus cutover in the attached Cognilode Core source. Implement free cloud persistence for complete recent conversations, summaries, committed events, Operator readback and generated foreground context. Produce concrete source and migration work that permits deletion of every D1 database. Work substantively through a reviewable artifact.",
    "Own the Plugin Admin free-tier cutover in the attached Cognilode Core source. Preserve meaningful read, write, mutate, delete, search, credential custody and plugin factory operations through the one provider owner, with Network/Operator request reporting. Produce concrete code and exercise a meaningful operation.",
    "Own the recurring organization rotor in the attached Cognilode Core source. Implement a manager-to-specialist-to-contributor loop where provider-accepted results stream into the shared corpus and Operator, return to the manager and change its next action. Produce concrete implementation artifacts and deployment handoff.",
)


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
        raw = response.read()
        return json.loads(raw) if raw else {}


def publish(index, receipt, text):
    repo = "evanbrown3000/cognilode-agent-turns"
    title = "ChatMode browser lane {}".format(index)
    issues = github("GET", "/repos/{}/issues?state=open&per_page=100".format(repo))
    issue = next((item for item in issues if item.get("title") == title), None)
    if issue is None:
        issue = github("POST", "/repos/{}/issues".format(repo), {
            "title": title,
            "body": "Provider-owned ChatGPT web conversation lane.",
        })
    body = "```json\n{}\n```\n\n{}".format(json.dumps(receipt, indent=2), text[:55000])
    github("POST", "/repos/{}/issues/{}/comments".format(repo, issue["number"]), {"body": body})
    return issue["number"]


def cookie_set():
    value = json.loads(os.environ.get("CHATGPT_COOKIES", "[]"))
    cookies = []
    for source in value:
        cookie = {key: source[key] for key in ("name", "value", "domain", "path", "expires", "httpOnly", "secure") if key in source}
        cookie.setdefault("domain", ".chatgpt.com")
        cookie.setdefault("path", "/")
        cookie["secure"] = True
        same_site = str(source.get("sameSite", "Lax")).title()
        if same_site in ("Strict", "Lax", "None"):
            cookie["sameSite"] = same_site
        cookies.append(cookie)
    return cookies


async def run_lane(context, index, assignment):
    page = await context.new_page()
    provider = None
    async def observe(response):
        nonlocal provider
        if "/backend-api/f/conversation" in response.url and response.request.method == "POST":
            provider = {
                "method": "POST",
                "path": "/backend-api/f/conversation",
                "status": response.status,
                "content_type": response.headers.get("content-type"),
                "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "network_route": "github-actions-free-browser",
            }
    page.on("response", observe)
    await page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=60000)
    editor = page.locator('[role="textbox"][contenteditable="true"]').first
    try:
        await editor.wait_for(state="visible", timeout=45000)
    except Exception as error:
        body = await page.locator("body").inner_text(timeout=5000)
        raise RuntimeError("composer unavailable at {}: {}".format(page.url.split("?", 1)[0], body[:700])) from error
    attachment = page.locator('input[type="file"]').first
    if await attachment.count() and Path("cognilode-core-input.zip").exists():
        await attachment.set_input_files("cognilode-core-input.zip")
        await page.wait_for_timeout(1000)
    await editor.fill(assignment)
    send = page.locator('button[aria-label*="Send" i]').first
    await send.wait_for(state="visible", timeout=20000)
    await send.click()
    for _ in range(60):
        if provider:
            break
        await page.wait_for_timeout(250)
    accepted = bool(provider and provider["status"] == 200)
    provisional = {
        "schema": "cognilode.chatmode-browser-turn.v1",
        "lane": index,
        "accepted": accepted,
        "terminal": False,
        "provider_http": provider,
        "conversation_url": page.url.split("?", 1)[0],
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }
    if accepted:
        provisional["state_issue"] = await asyncio.to_thread(
            publish, index, provisional, "Provider accepted this turn; response streaming is active."
        )
    stop = page.locator('button[aria-label*="Stop" i],button[data-testid="stop-button"]')
    in_turn = False
    for _ in range(60):
        in_turn = bool(await stop.count())
        if in_turn:
            break
        await page.wait_for_timeout(500)
    conversation_url = page.url.split("?", 1)[0]
    # Keep ownership until the provider turn is terminal or the bounded cloud
    # job approaches its own timeout. Capture semantic visible content only.
    deadline = time.time() + 1200
    while in_turn and time.time() < deadline:
        await page.wait_for_timeout(5000)
        in_turn = bool(await stop.count())
    messages = await page.locator("main").inner_text(timeout=30000)
    receipt = {
        "schema": "cognilode.chatmode-browser-turn.v1",
        "lane": index,
        "accepted": accepted,
        "terminal": not in_turn,
        "provider_http": provider,
        "conversation_url": conversation_url,
        "response_characters": len(messages),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }
    receipt["state_issue"] = await asyncio.to_thread(publish, index, receipt, messages)
    return receipt


async def ensure_authenticated(context):
    """Restore the owner session through ChatGPT's ordinary browser login flow."""
    page = await context.new_page()
    await page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=60000)
    editor = page.locator('[role="textbox"][contenteditable="true"]').first
    if await editor.count():
        try:
            await editor.wait_for(state="visible", timeout=10000)
            await page.close()
            return
        except Exception:
            pass

    email_choice = page.get_by_role("button", name="Continue with email").first
    if not await email_choice.is_visible():
        login = page.get_by_role("button", name="Log in").or_(page.get_by_role("link", name="Log in")).first
        await login.wait_for(state="visible", timeout=30000)
        await login.click(force=True)
    await email_choice.wait_for(state="visible", timeout=30000)
    await email_choice.click(force=True)
    email = page.locator('input[type="email"],input[name="email"],input[name="username"]').first
    await email.wait_for(state="visible", timeout=45000)
    await email.fill(os.environ["CHATGPT_LOGIN_USERNAME"])
    await page.get_by_role("button", name="Continue").first.click(force=True)
    password = page.locator('input[type="password"],input[name="password"]').first
    try:
        await password.wait_for(state="visible", timeout=45000)
    except Exception:
        body = await page.locator("body").inner_text(timeout=5000)
        body = body.replace(os.environ["CHATGPT_LOGIN_USERNAME"], "[account]")
        Path("login-stage.json").write_text(json.dumps({"url": page.url.split("?", 1)[0], "body": body[:4000]}, indent=2))
        raise
    await password.fill(os.environ["CHATGPT_LOGIN_PASSWORD"])
    await page.get_by_role("button", name="Continue").first.click()
    await editor.wait_for(state="visible", timeout=90000)
    await page.close()


async def main():
    bundle = Path("cognilode-core-input.zip")
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        for source in [Path("core/ARCHITECTURE_PLAN.md"), *sorted(Path("core/application").rglob("*.py")), *sorted(Path("core/tests").rglob("*.py"))]:
            if source.exists():
                archive.write(source, source.relative_to("core"))
    stored_headers = json.loads(os.environ.get("CHATGPT_BROWSER_HEADERS", "{}"))
    extra_headers = {}
    for key, value in stored_headers.items():
        if key.lower() in {"accept-language", "oai-device-id", "oai-did", "oai-language", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform"} and isinstance(value, str):
            extra_headers[key] = value
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir="browser-profile",
            executable_path="/usr/bin/google-chrome",
            headless=False,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
            viewport={"width": 1440, "height": 1000},
            extra_http_headers=extra_headers,
        )
        await context.add_cookies(cookie_set())
        await ensure_authenticated(context)
        results = await asyncio.gather(*[
            run_lane(context, index, assignment)
            for index, assignment in enumerate(ASSIGNMENTS, 1)
        ], return_exceptions=True)
        normalized = []
        for index, result in enumerate(results, 1):
            if isinstance(result, Exception):
                normalized.append({"lane": index, "accepted": False, "error": type(result).__name__ + ": " + str(result)[:500]})
            else:
                normalized.append(result)
        Path("browser-turns-receipt.json").write_text(json.dumps({"results": normalized}, indent=2) + "\n")
        print(json.dumps({"accepted": sum(bool(item.get("accepted")) for item in normalized), "lanes": len(normalized)}))
        await context.close()
        if sum(bool(item.get("accepted")) for item in normalized) != 4:
            raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
