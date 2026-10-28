import base64,json,os,time
import requests
h=json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}'))
h.update({'Authorization':'Bearer '+os.environ['CHATGPT_ACCESS_TOKEN'],'ChatGPT-Account-ID':os.environ['CHATGPT_ACCOUNT_ID'],'Cookie':os.environ.get('CHATGPT_COOKIE',''),'Accept':'application/json','Origin':'https://chatgpt.com','Referer':'https://chatgpt.com/'})
r=requests.get('https://chatgpt.com/backend-api/ps/plugins/installed',headers=h,timeout=45)
available_response=requests.get('https://chatgpt.com/backend-api/ps/plugins/list?scope=USER&limit=200',headers=h,timeout=45)
out={'schema':'cognilode.plugin-admin-snapshot.v1','status':r.status_code,'content_type':r.headers.get('content-type',''),'observed_at':time.time(),'installed':r.json() if r.ok and 'json' in r.headers.get('content-type','') else None,'available':available_response.json() if available_response.ok and 'json' in available_response.headers.get('content-type','') else None,'available_status':available_response.status_code}
open('plugin-admin-snapshot.json','w').write(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'application_json':out['installed'] is not None}))
if out['installed'] is None or out['available'] is None:raise SystemExit(1)

# GitHub is the durable free-tier handoff.  One issue is the current readable
# projection; workflow artifacts retain short-lived execution evidence.
gh_token=os.environ['COGNILODE_GITHUB_TOKEN']
repo=os.environ.get('PLUGIN_STATE_REPO','evanbrown3000/cognilode-conversation-corpus')
gh_headers={'Authorization':'Bearer '+gh_token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
label='plugin-admin-current'
title='Current Plugin Admin provider snapshot'
content_path='snapshots/plugin-admin-current.json'
content_url=f'https://api.github.com/repos/{repo}/contents/{content_path}'
prior=requests.get(content_url,headers=gh_headers,timeout=30)
payload={'message':'Update Plugin Admin provider snapshot','content':base64.b64encode((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode()).decode()}
if prior.ok:payload['sha']=prior.json()['sha']
stored=requests.put(content_url,headers=gh_headers,json=payload,timeout=30);stored.raise_for_status()
plugins=(out.get('installed') or {}).get('plugins') or []
compact=[{'id':p.get('id') or p.get('plugin_id'),'name':p.get('name') or p.get('manifest',{}).get('name'),'enabled':p.get('enabled')} for p in plugins]
body='<!-- cognilode.plugin-admin-snapshot.v1 -->\n```json\n'+json.dumps({'schema':out['schema'],'status':out['status'],'observed_at':out['observed_at'],'count':len(plugins),'plugins':compact,'content_path':content_path},ensure_ascii=False,indent=2)+'\n```\n'
requests.post(f'https://api.github.com/repos/{repo}/labels',headers=gh_headers,json={'name':label,'color':'1f6feb','description':'Current Plugin Admin provider projection'},timeout=30)
q=requests.get(f'https://api.github.com/repos/{repo}/issues',headers=gh_headers,params={'state':'open','labels':label,'per_page':10},timeout=30)
q.raise_for_status()
issues=[x for x in q.json() if x.get('title')==title]
if issues:
    u=requests.patch(issues[0]['url'],headers=gh_headers,json={'body':body},timeout=30)
else:
    u=requests.post(f'https://api.github.com/repos/{repo}/issues',headers=gh_headers,json={'title':title,'body':body,'labels':[label]},timeout=30)
u.raise_for_status()
print(json.dumps({'published':True,'repository':repo,'issue':u.json()['number']}))
