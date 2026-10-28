import json,os,time
from codex_backend_sdk import CodexClient
from codex_backend_sdk.storage import TokenStore
wanted={m for row in json.load(open('accepted-turns.json')) for m in row.get('user_message_ids',[])}
headers=json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}'));headers['Cookie']=os.environ.get('CHATGPT_COOKIE','')
store=TokenStore(access_token=os.environ['CHATGPT_ACCESS_TOKEN'],refresh_token='',id_token_raw='',account_id=os.environ['CHATGPT_ACCOUNT_ID'])
client=CodexClient(store=store,timeout=60,max_retries=0,default_headers=headers)
page=client.chatgpt.conversations.list(offset=0,limit=30,order='updated')
items=page.get('items') or page.get('conversations') or []
matched=[]
for item in items:
 cid=item.get('id') or item.get('conversation_id')
 if not cid:continue
 c=client.chatgpt.conversations.retrieve(cid)
 ids={n.get('message',{}).get('id') for n in (c.get('mapping') or {}).values() if isinstance(n,dict)}
 hit=sorted(wanted & ids)
 if hit:matched.append({'conversation_id':cid,'user_message_ids':hit,'conversation':c})
 if len({m for row in matched for m in row['user_message_ids']})==len(wanted):break
open('matched-conversations.json','w').write(json.dumps({'schema':'cognilode.chatmode-readback.v1','matched':matched,'wanted':sorted(wanted),'observed_at':time.time()},indent=2)+'\n')
print(json.dumps({'wanted':len(wanted),'matched_messages':len({m for row in matched for m in row['user_message_ids']}),'conversations':len(matched)}))
if len({m for row in matched for m in row['user_message_ids']})<len(wanted):raise SystemExit(2)
