import json,os,time,uuid
from codex_backend_sdk import CodexClient
from codex_backend_sdk.storage import TokenStore
idx=int(os.environ['ASSIGNMENT_INDEX'])
assignments=[
'''Take continuing responsibility for the ChatGPT.com provider execution lane of the Cognilode free-tier cutover. Use the installed Cognilode Operator and Plugin Admin tools. Inspect the current shared state, then produce and publish a concrete implementation or patch that makes one-owner Chat-mode submission, SSE/readback, steering, and recovery work without Cloudflare Containers, D1, KV, paid Cloudflare, AWS, or a laptop host. Work as an implementation owner, consume existing B4PT0R Framework/Harness/SDK work, and do not create a second sender.''',
'''Take continuing responsibility for the conversation corpus and foreground lane of the Cognilode free-tier cutover. Use the installed Cognilode Operator tools to inspect current state. Implement a zero-paid path that collects actual Chat-mode conversations, stores semantically useful original messages and hierarchical summaries outside D1/KV, supports search/read, and generates an overlapping current foreground.md for subsequent agent turns. Publish a concrete artifact and drive it to its next consumer.''',
'''Take continuing responsibility for the Cognilode Operator shared conversation experience during the free-tier cutover. Use the installed Operator and Plugin Admin tools. Build on B4PT0R Harness/Framework so humans and agents see the same ChatGPT-quality conversation stream, errors, approvals, navigation, model/effort and attachments while the upstream turn has exactly one owner. Preserve the 14 incumbent windows and publish a concrete usable implementation, not another report.''',
'''Take continuing responsibility for cutting the organization and TaskFlow employee loop off D1 and Cloudflare paid services. Use current Operator state and existing source. Implement a free-tier durable dispatch/result-consumption path that actually triggers provider Employees, returns useful work to managers, preserves Company/Employee/Office/Episode semantics, and allows dependent D1 databases to be deleted. Publish concrete source and a migration handoff with exact consumers.'''
]
access=os.environ['CHATGPT_ACCESS_TOKEN']; account=os.environ['CHATGPT_ACCOUNT_ID']
headers=json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}'))
headers['Cookie']=os.environ.get('CHATGPT_COOKIE','')
headers['Origin']='https://chatgpt.com';headers['Referer']='https://chatgpt.com/'
store=TokenStore(access_token=access,refresh_token='',id_token_raw='',account_id=account)
client=CodexClient(store=store,timeout=180,max_retries=0,default_headers=headers)
mid=str(uuid.uuid4())
payload={'turn_attribution':{'turn_trigger':'composer'},'action':'next','is_do_not_remember':False,
'messages':[{'id':mid,'author':{'role':'user'},'channel':None,'content':{'content_type':'text','parts':[assignments[idx]]},'metadata':{},'recipient':'all','status':'finished_successfully','weight':1}],
'parent_message_id':str(uuid.uuid4()),'model':'auto','timezone':'America/Matamoros','timezone_offset_min':-300,
'supported_encodings':['v1'],'genui_state_snapshots':[],'client_prepare_state':'sent','conversation_mode':{'kind':'primary_assistant'},'history_and_training_disabled':False}
started=time.time()
msg=payload['messages'][0]
prepare={k:payload[k] for k in ('action','parent_message_id','model','timezone_offset_min','timezone','is_do_not_remember') if k in payload}
prepare.update({'client_prepare_state':'success','partial_query':{'id':msg['id'],'author':msg['author'],'content':msg['content']}})
preparation=client.chatgpt.conversations.prepare(prepare)
for field in ('headers','request_headers','generation_headers'):
 for key,value in (preparation.get(field) or {}).items():
  if key.lower() not in ('authorization','cookie','host','content-length','chatgpt-account-id','oai-device-id') and isinstance(value,(str,int,float,bool)):
   client._session.headers[key]=str(value)
conduit=preparation.get('conduit_token') or preparation.get('conduitToken')
if conduit:client._session.headers['X-Conduit-Token']=str(conduit)
client._session.headers['X-Oai-Turn-Trace-Id']=str(uuid.uuid4())
payload['client_prepare_state']='sent'
resp=client.chatgpt.conversations.create_stream(payload)
result={'schema':'cognilode.chatmode-turn.v1','assignment_index':idx,'user_message_id':mid,'http_status':resp.status_code,'content_type':resp.headers.get('content-type',''),'provider_accepted':resp.status_code==200 and 'text/event-stream' in resp.headers.get('content-type',''),'conversation_id':None,'assistant_completion_observed':False,'events':0,'runner':'github-hosted-ubuntu','run_id':os.environ.get('GITHUB_RUN_ID'),'elapsed_ms':None}
with open('conversation.jsonl','w') as f:
 for raw in resp.iter_lines(decode_unicode=True):
  if not raw or not raw.startswith('data:'):continue
  data=raw[5:].lstrip()
  if data=='[DONE]':break
  try:e=json.loads(data)
  except Exception:continue
  f.write(json.dumps(e,separators=(',',':'))+'\n');result['events']+=1
  cid=e.get('conversation_id') or (e.get('v') or {}).get('conversation_id')
  if cid:result['conversation_id']=cid
  m=e.get('message') or (e.get('v') or {}).get('message')
  if isinstance(m,dict) and m.get('author',{}).get('role')=='assistant' and m.get('end_turn') is True:result['assistant_completion_observed']=True
result['elapsed_ms']=round((time.time()-started)*1000)
open('result.json','w').write(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
if not result['provider_accepted']:raise SystemExit(1)
