"""Run one ordinary signed-in ChatGPT UI turn on an ephemeral GitHub runner."""
import json,os,time,uuid
from pathlib import Path
from playwright.sync_api import sync_playwright

ASSIGNMENTS={
 "provider":"Own implementation of the single ChatGPT.com product adapter and durable stream contract in the supplied clean Cognilode Core. Preserve errors, approvals, tool events, deltas, terminal status, attachments, model, reasoning level, account, network route and request attribution without polling full history. Produce concrete replacement source or a precise patch. Work substantively through completion.",
 "corpus":"Own the off-D1 corpus cutover for Cognilode Core. Implement free cloud persistence for complete recent conversations, summaries, incremental committed provider events, Operator live readback, and generated foreground context. Produce concrete source and migration work that replaces D1 consumers and permits deletion of all databases. Work substantively through completion.",
 "plugins":"Own Plugin Admin cutover. Replace its failed legacy provider lane with clean Cognilode Core while preserving read, write, mutate, delete, search, credential custody and plugin factory operations. Integrate persistent Network/Operator reporting. Produce concrete code or a reviewable patch and exercise a meaningful operation. Work substantively through completion.",
 "organization":"Own the recurring organization rotor. Implement a manager-to-specialist-to-contributor loop over clean Framework/Harness and its single ChatGPT product adapter. Every turn must be provider-accepted, stream into the shared corpus and Operator, return useful work, and alter the manager's next action. Produce concrete implementation artifacts and deployment handoff. Work substantively through completion.",
}
lane=os.environ["LANE"]; prompt=ASSIGNMENTS[lane]
cookies=json.loads(os.environ.get("CHATGPT_COOKIES","[]"))
browser_headers=json.loads(os.environ.get("CHATGPT_BROWSER_HEADERS","{}"))
receipt={"schema":"cognilode.chatmode-browser-turn.v1","lane":lane,"accepted":False,"assistant_activity":False,"terminal":False,"events":[]}
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
user_agent=browser_headers.get("user-agent") or browser_headers.get("User-Agent")
extra={k:v for k,v in browser_headers.items() if k.lower() in {"accept-language","oai-device-id","oai-did","oai-language","originator","sec-ch-ua","sec-ch-ua-mobile","sec-ch-ua-platform","dnt"}}
context=browser.new_context(viewport={"width":1440,"height":900},user_agent=user_agent,extra_http_headers=extra)
 normalized=[]
 for source in cookies:
  item={k:source[k] for k in ("name","value","domain","path","expires","httpOnly","secure") if k in source}
  if str(source.get("sameSite","")).lower() in {"strict","lax","none"}:item["sameSite"]=str(source["sameSite"]).title()
  normalized.append(item)
 context.add_cookies(normalized)
 page=context.new_page()
 def response_seen(response):
  if "/backend-api/f/conversation" not in response.url:return
  event={"path":response.url.split("?",1)[0].replace("https://chatgpt.com",""),"method":response.request.method,"status":response.status,"content_type":response.headers.get("content-type")}
  receipt["events"].append(event)
  if event["method"]=="POST" and event["status"]==200:receipt["accepted"]=True
 page.on("response",response_seen)
 page.goto("https://chatgpt.com/",wait_until="domcontentloaded",timeout=60000)
 editor=page.locator('[role="textbox"][contenteditable="true"]').first
try:
 editor.wait_for(state="visible",timeout=45000)
except Exception:
 receipt.update({"observed_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"conversation_url":page.url.split("?",1)[0],"page_title":page.title(),"page_text":page.locator("body").inner_text()[:500]})
 Path("turn-receipt.json").write_text(json.dumps(receipt,indent=2))
 raise
 editor.fill(prompt)
 page.locator('button[aria-label="Send"]').first.click()
 deadline=time.time()+420
 while time.time()<deadline:
  if page.locator('button[aria-label="Stop"],button[aria-label="Stop streaming"],button[data-testid="stop-button"]').count():receipt["assistant_activity"]=True
  if receipt["accepted"] and receipt["assistant_activity"] and not page.locator('button[aria-label="Stop"],button[aria-label="Stop streaming"],button[data-testid="stop-button"]').count():
   receipt["terminal"]=True;break
  page.wait_for_timeout(1000)
 receipt["conversation_url"]=page.url.split("?",1)[0]
 receipt["observed_at"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
 Path("turn-receipt.json").write_text(json.dumps(receipt,indent=2))
 browser.close()
print(json.dumps({k:receipt[k] for k in ("lane","accepted","assistant_activity","terminal","conversation_url")}))
if not receipt["accepted"] or not receipt["assistant_activity"]:raise SystemExit(1)
