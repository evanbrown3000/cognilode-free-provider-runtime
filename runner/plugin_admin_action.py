import base64,json,os,time,urllib.error,urllib.parse,urllib.request
from codex_backend_sdk import CodexClient
from codex_backend_sdk.storage import TokenStore

op=os.environ['PLUGIN_OPERATION']; target=os.environ['PLUGIN_TARGET']; request_id=os.environ['PLUGIN_REQUEST_ID']
client=CodexClient(store=TokenStore(access_token=os.environ['CHATGPT_ACCESS_TOKEN'],account_id=os.environ['CHATGPT_ACCOUNT_ID'],refresh_token='',id_token_raw=''),timeout=(15,90),max_retries=0)
client._session.headers.pop('OpenAI-Beta',None);client._session.headers.pop('originator',None)
for k,v in json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}')).items():
 if k.lower() in {'user-agent','accept-language','oai-device-id','oai-did','oai-language','sec-ch-ua','sec-ch-ua-mobile','sec-ch-ua-platform'} and isinstance(v,str):client._session.headers[k]=v
if os.environ.get('CHATGPT_COOKIE'):client._session.headers['Cookie']=os.environ['CHATGPT_COOKIE']

if op=='plugin_install':
 before=client.chatgpt.plugins.retrieve(target)
 result=client.chatgpt.plugins.installation.install(target)
 page=client.chatgpt.plugins.installed(scope=before.get('scope') if before.get('scope') in {'GLOBAL','USER','WORKSPACE'} else None)
 matches=[p for p in page['plugins'] if p.get('id')==target and p.get('enabled') is not False]
 if len(matches)!=1:raise RuntimeError('plugin_install_readback_failed')
 receipt={'operation':op,'target':target,'changed':before.get('enabled') is not True,'provider_result':result,'readback':matches[0]}
elif op=='app_full_access':
 app=client.chatgpt.connectors.retrieve(target,include_actions=True)
 links=client.chatgpt.connectors.links.list_accessible(principals=app.get('owners') or [])['links']
 matches=[v for v in links if v.get('connector_id')==target]
 if len(matches)!=1:raise RuntimeError('one_exact_account_connection_required')
 link=matches[0];changed=link.get('apps_privacy_control')!='full_access'
 if changed:
  response=client._request_chatgpt('PATCH','/aip/connectors/links/'+urllib.parse.quote(link['id'],safe=''),body={'apps_privacy_control':'full_access'})
  response.raise_for_status()
 after=[v for v in client.chatgpt.connectors.links.list_accessible(principals=app.get('owners') or [])['links'] if v.get('connector_id')==target]
 if len(after)!=1 or after[0].get('apps_privacy_control')!='full_access':raise RuntimeError('app_full_access_readback_failed')
 receipt={'operation':op,'target':target,'changed':changed,'readback':after[0]}
else:raise RuntimeError('unsupported_plugin_operation')

receipt={'schema':'cognilode.plugin-admin-operation.v1','ok':True,'request_id':request_id,'observed_at':time.time(),**receipt}
raw=(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode();token=os.environ['COGNILODE_GITHUB_TOKEN'];repo='evanbrown3000/cognilode-conversation-corpus';headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json'}
for path in ('snapshots/plugin-admin-operation-'+request_id+'.json','snapshots/plugin-admin-operation-current.json'):
 url='https://api.github.com/repos/'+repo+'/contents/'+path;req=urllib.request.Request(url,headers=headers)
 try:
  with urllib.request.urlopen(req) as r:prior=json.load(r);sha=prior.get('sha')
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
  sha=None
 body={'message':'Record Plugin Admin provider operation','content':base64.b64encode(raw).decode()};
 if sha:body['sha']=sha
 with urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method='PUT')) as r:json.load(r)
open('plugin-operation-receipt.json','wb').write(raw);print(json.dumps({'ok':True,'operation':op,'target':target,'changed':receipt['changed'],'request_id':request_id}))
