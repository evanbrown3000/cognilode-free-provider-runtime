import json, os, time
import requests
headers=json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}'))
headers.update({
 'Authorization':'Bearer '+os.environ['CHATGPT_ACCESS_TOKEN'],
 'ChatGPT-Account-ID':os.environ['CHATGPT_ACCOUNT_ID'],
 'Cookie':os.environ['CHATGPT_COOKIE'],
 'Accept':'application/json',
})
start=time.time()
r=requests.get('https://chatgpt.com/backend-api/me',headers=headers,timeout=30)
out={
 'schema':'cognilode.provider-route-qualification.v1',
 'provider':'chatgpt.com','operation':'GET /backend-api/me',
 'http_status':r.status_code,'content_type':r.headers.get('content-type',''),
 'elapsed_ms':round((time.time()-start)*1000),
 'accepted':r.status_code==200 and 'json' in r.headers.get('content-type','').lower(),
 'runner':'github-hosted-ubuntu','repository':os.environ.get('GITHUB_REPOSITORY'),
 'run_id':os.environ.get('GITHUB_RUN_ID'),
}
open('qualification.json','w').write(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
if not out['accepted']: raise SystemExit(1)
