import base64,json,os,re,subprocess,time,urllib.request
from pathlib import Path
from nacl import encoding,public
EXPORT=Path('/run/user/1000/cognilode-core/credential-export.json')
x=json.loads(EXPORT.read_text())
def cred(cid):
 for c in x['credentials']:
  if c.get('id')==cid:return c['value']
 raise KeyError(cid)
token=cred('github.cli.evanbrown3000')
sess=cred('chatgpt.product-session.owner-personal')
repo='cognilode-free-provider-runtime'
base='https://api.github.com'
def api(method,path,data=None):
 req=urllib.request.Request(base+path,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
 if data is not None:req.data=json.dumps(data).encode();req.add_header('Content-Type','application/json')
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.loads(r.read() or b'{}')
 except urllib.error.HTTPError as e:
  body=e.read(); return e.code,json.loads(body or b'{}')
st,obj=api('GET',f'/repos/evanbrown3000/{repo}')
if st==404:
 st,obj=api('POST','/user/repos',{'name':repo,'description':'Ephemeral zero-paid provider execution for Cognilode Operator','private':False,'has_issues':False,'has_projects':False,'has_wiki':False,'auto_init':False})
 assert st==201,(st,obj)
root=Path(__file__).parent
ask=Path('/tmp/cognilode-git-askpass.sh');ask.write_text('#!/bin/sh\ncase "$1" in *Username*) echo x-access-token;; *) echo "$GITHUB_TOKEN";; esac\n');ask.chmod(0o700)
env={**os.environ,'GITHUB_TOKEN':token,'GIT_ASKPASS':str(ask),'GIT_TERMINAL_PROMPT':'0'}
if not (root/'.git').exists():subprocess.run(['git','init'],cwd=root,check=True,env=env,stdout=subprocess.DEVNULL); subprocess.run(['git','checkout','-b','main'],cwd=root,check=True,env=env,stdout=subprocess.DEVNULL)
subprocess.run(['git','config','user.name','Cognilode Release'],cwd=root,check=True)
subprocess.run(['git','config','user.email','release@cognilode.com'],cwd=root,check=True)
subprocess.run(['git','add','.'],cwd=root,check=True)
subprocess.run(['git','commit','-m','Deploy zero-paid provider route qualification'],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
url=f'https://github.com/evanbrown3000/{repo}.git'
subprocess.run(['git','remote','remove','origin'],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['git','remote','add','origin',url],cwd=root,check=True)
subprocess.run(['git','push','-u','origin','main'],cwd=root,check=True,env=env,stdout=subprocess.DEVNULL)
st,key=api('GET',f'/repos/evanbrown3000/{repo}/actions/secrets/public-key'); assert st==200,(st,key)
pk=public.PublicKey(key['key'].encode(),encoding.Base64Encoder())
def put_secret(name,value):
 box=public.SealedBox(pk); enc=base64.b64encode(box.encrypt(value.encode())).decode()
 st,_=api('PUT',f'/repos/evanbrown3000/{repo}/actions/secrets/{name}',{'encrypted_value':enc,'key_id':key['key_id']}); assert st in (201,204),st
put_secret('CHATGPT_ACCESS_TOKEN',sess['access_token'])
put_secret('CHATGPT_ACCOUNT_ID',sess['account_id'])
put_secret('CHATGPT_COOKIE',sess.get('cookie') or '')
put_secret('CHATGPT_BROWSER_HEADERS',json.dumps(sess.get('browser_headers') or {}))
put_secret('CHATGPT_COOKIES',json.dumps(sess.get('cookies') or []))
put_secret('COGNILODE_GITHUB_TOKEN',token)
put_secret('CORE_REPO_TOKEN',token)
put_secret('OPERATOR_TOKEN',Path('/home/evan/.config/cognilode/operator-token').read_text().strip())

st2,_sink=api('GET','/repos/evanbrown3000/cognilode-conversation-corpus')
if st2==404:
 st2,_sink=api('POST','/user/repos',{'name':'cognilode-conversation-corpus','description':'Private original Chat-mode conversations and corpus projections','private':True,'has_issues':True,'has_projects':False,'has_wiki':False,'auto_init':True})
 assert st2==201,(st2,_sink)
st,_=api('POST',f'/repos/evanbrown3000/{repo}/actions/workflows/browser-turns.yml/dispatches',{'ref':'main'});assert st==204,st
print(json.dumps({'ok':True,'repository':f'evanbrown3000/{repo}','workflow_dispatched':True}))
