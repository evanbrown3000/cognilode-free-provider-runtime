import json,os,time,urllib.request,urllib.error
from codex_backend_sdk import CodexClient
from codex_backend_sdk.storage import TokenStore
wanted={m for row in json.load(open('accepted-turns.json')) for m in row.get('user_message_ids',[])}
headers=json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}'));headers['Cookie']=os.environ.get('CHATGPT_COOKIE','')
store=TokenStore(access_token=os.environ['CHATGPT_ACCESS_TOKEN'],refresh_token='',id_token_raw='',account_id=os.environ['CHATGPT_ACCOUNT_ID'])
client=CodexClient(store=store,timeout=60,max_retries=0,default_headers=headers)
matched=[];deferred=None
try:
 page=client.chatgpt.conversations.list(offset=0,limit=12,order='updated')
 for item in page.get('items') or page.get('conversations') or []:
  cid=item.get('id') or item.get('conversation_id')
  if not cid:continue
  try:c=client.chatgpt.conversations.retrieve(cid)
  except Exception as e:
   status=getattr(getattr(e,'response',None),'status_code',None)
   if status==429:deferred='provider_429';break
   continue
  ids={n.get('message',{}).get('id') for n in (c.get('mapping') or {}).values() if isinstance(n,dict)}
  hit=sorted(wanted & ids)
  if hit:matched.append({'conversation_id':cid,'user_message_ids':hit,'conversation':c})
  if len({m for row in matched for m in row['user_message_ids']})==len(wanted):break
  time.sleep(3)
except Exception as e:
 deferred='provider_'+str(getattr(getattr(e,'response',None),'status_code','error'))
body={'schema':'cognilode.chatmode-readback.v1','matched':matched,'wanted':sorted(wanted),'observed_at':time.time(),'deferred':deferred}
open('matched-conversations.json','w').write(json.dumps(body,indent=2)+'\n')
# Private GitHub corpus sink: one current issue, updated in place.
token=os.environ['COGNILODE_GITHUB_TOKEN']; repo='evanbrown3000/cognilode-conversation-corpus'
def api(method,path,data=None):
 req=urllib.request.Request('https://api.github.com'+path,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
 if data is not None:req.data=json.dumps(data).encode();req.add_header('Content-Type','application/json')
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.loads(r.read() or b'{}')
 except urllib.error.HTTPError as e:return e.code,json.loads(e.read() or b'{}')
st,issues=api('GET','/repos/'+repo+'/issues?state=open&labels=chatmode-current&per_page=1')
payload={'title':'Current accepted Chat-mode conversation readback','body':'```json\n'+json.dumps(body,separators=(',',':'))+'\n```','labels':['chatmode-current']}
if st==200 and issues:api('PATCH','/repos/'+repo+'/issues/'+str(issues[0]['number']),payload)
else:api('POST','/repos/'+repo+'/issues',payload)
hits=len({m for row in matched for m in row['user_message_ids']})
print(json.dumps({'wanted':len(wanted),'matched_messages':hits,'conversations':len(matched),'deferred':deferred,'private_sink':True}))
