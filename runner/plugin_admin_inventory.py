import json,os,time
import requests
h=json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}'))
h.update({'Authorization':'Bearer '+os.environ['CHATGPT_ACCESS_TOKEN'],'ChatGPT-Account-ID':os.environ['CHATGPT_ACCOUNT_ID'],'Cookie':os.environ.get('CHATGPT_COOKIE',''),'Accept':'application/json','Origin':'https://chatgpt.com','Referer':'https://chatgpt.com/'})
r=requests.get('https://chatgpt.com/backend-api/ps/plugins/installed',headers=h,timeout=45)
out={'schema':'cognilode.plugin-admin-snapshot.v1','status':r.status_code,'content_type':r.headers.get('content-type',''),'observed_at':time.time(),'installed':r.json() if r.ok and 'json' in r.headers.get('content-type','') else None}
open('plugin-admin-snapshot.json','w').write(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'application_json':out['installed'] is not None}))
if out['installed'] is None:raise SystemExit(1)
