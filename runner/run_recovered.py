import json,os,subprocess,sys,uuid
assignments=[
'Take continuing responsibility for the ChatGPT.com provider execution lane of the Cognilode free-tier cutover. Use installed Cognilode Operator and Plugin Admin tools. Produce and publish a concrete implementation that makes one-owner Chat-mode submission, SSE/readback, steering and recovery work without Cloudflare Containers, D1, KV, paid Cloudflare, AWS or a laptop host. Consume the existing B4PT0R Framework/Harness/SDK composition and do not create a second sender.',
'Take continuing responsibility for the conversation corpus and foreground lane of the Cognilode free-tier cutover. Use the installed Cognilode Operator tools. Implement a zero-paid path that collects actual Chat-mode conversations, stores semantically useful original messages and hierarchical summaries outside D1/KV, supports search/read, and generates an overlapping current foreground.md for later turns. Publish a concrete artifact and drive it to its next consumer.',
'Take continuing responsibility for the Cognilode Operator shared conversation experience during free-tier cutover. Use installed Operator and Plugin Admin tools. Build on B4PT0R Harness/Framework so humans and agents see the same ChatGPT-quality stream, errors, approvals, navigation, model/effort and attachments while the upstream turn has exactly one owner. Preserve incumbent windows and publish a concrete usable implementation.',
'Take continuing responsibility for cutting the organization and TaskFlow Employee loop off D1 and Cloudflare paid services. Use current Operator state and existing source. Implement a free-tier durable dispatch/result-consumption path that actually triggers provider Employees, returns useful work to managers, preserves Company/Employee/Office/Episode semantics, and allows dependent D1 databases to be deleted. Publish concrete source and a migration handoff with exact consumers.'
]
i=int(os.environ.get('ASSIGNMENT_INDEX','0'))
web={'cookie':os.environ['CHATGPT_COOKIE'],'browser_headers':json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}'))}
config={'job':{'id':str(uuid.uuid4()),'user_message_id':str(uuid.uuid4()),'prompt':assignments[i],'model':'auto'},'auth':{'tokens':{'access_token':os.environ['CHATGPT_ACCESS_TOKEN'],'account_id':os.environ['CHATGPT_ACCOUNT_ID']}},'web_session':web}
p=subprocess.Popen([sys.executable,'runner/recovered_chatmode.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
p.stdin.write(json.dumps(config)+'\n');p.stdin.flush()
accepted=False
with open('conversation-events.jsonl','w') as out:
 for line in p.stdout:
  out.write(line);out.flush()
  try:e=json.loads(line)
  except:continue
  if e.get('type')=='ready_to_send':p.stdin.write('send\n');p.stdin.flush()
  if e.get('type')=='provider_accepted':accepted=True
p.stdin.close();err=p.stderr.read();code=p.wait()
result={'provider_accepted':accepted,'assignment_index':i,'exit_code':code,'stderr_tail':err[-500:] if not accepted else ''}
open('result.json','w').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if not accepted:raise SystemExit(1)
