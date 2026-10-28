import json,os,sys,time,urllib.request,urllib.error
import requests
BASE='https://chatgpt.com/backend-api'; REPO=os.environ.get('STATE_REPOSITORY','evanbrown3000/cognilode-agent-turns')
def github(method,path,data=None):
 req=urllib.request.Request('https://api.github.com'+path,method=method,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+os.environ['COGNILODE_GITHUB_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.loads(r.read() or b'{}')
 except urllib.error.HTTPError as e:return e.code,{'error':e.read(1000).decode(errors='replace')}
def main():
 rid=os.environ['REQUEST_ID'];op=os.environ['OPERATION'];args=json.loads(os.environ.get('ARGUMENTS','{}'))
 s=requests.Session();s.headers.update({'Authorization':'Bearer '+os.environ['CHATGPT_ACCESS_TOKEN'],'ChatGPT-Account-ID':os.environ['CHATGPT_ACCOUNT_ID']})
 for k,v in json.loads(os.environ.get('CHATGPT_BROWSER_HEADERS','{}')).items():
  if k.lower() in {'user-agent','accept-language','oai-device-id','oai-did','oai-language','sec-ch-ua','sec-ch-ua-mobile','sec-ch-ua-platform'} and isinstance(v,str):s.headers[k]=v
 if os.environ.get('CHATGPT_COOKIE'):s.headers['Cookie']=os.environ['CHATGPT_COOKIE']
 evidence=[]
 def call(method,path,body=None):
  started=time.time();r=s.request(method,BASE+path,json=body,timeout=(15,45));evidence.append({'method':method,'path':path.split('?')[0],'status':r.status_code,'duration_ms':round((time.time()-started)*1000),'content_type':r.headers.get('content-type')});
  try:data=r.json()
  except Exception:data={'error':'non_json'}
  if not r.ok:raise RuntimeError('provider_http_'+str(r.status_code)+':'+str(data)[:500])
  return data
 app_id=args.get('app_id')
 if op not in {'app_full_access','app_refresh','app_install'} or not isinstance(app_id,str):raise RuntimeError('unsupported_operation')
 app=call('GET','/aip/connectors/'+app_id); links=call('POST','/aip/connectors/links/list_accessible',{'principals':app.get('owners',[]) }).get('links',[]);links=[x for x in links if x.get('connector_id')==app_id]
 if op=='app_install' and not links:
  call('POST','/aip/connectors/links/noauth',{'connector_id':app_id,'name':app.get('name'),'action_names':[x.get('name') for x in app.get('actions',[]) if x.get('name')]});links=call('POST','/aip/connectors/links/list_accessible',{'principals':app.get('owners',[])}).get('links',[]);links=[x for x in links if x.get('connector_id')==app_id]
 if len(links)!=1:raise RuntimeError('one_exact_account_connection_required')
 link=links[0]
 if op=='app_refresh':call('POST','/aip/connectors/mcp/refresh_actions',{'link_id':link['id']})
 if link.get('apps_privacy_control')!='full_access':call('PATCH','/aip/connectors/links/'+link['id'],{'apps_privacy_control':'full_access'})
 after=call('POST','/aip/connectors/links/list_accessible',{'principals':app.get('owners',[])}).get('links',[]);after=[x for x in after if x.get('connector_id')==app_id]
 ok=len(after)==1 and after[0].get('apps_privacy_control')=='full_access'
 result={'schema':'cognilode.plugin-admin-result.v1','request_id':rid,'operation':op,'ok':ok,'app_id':app_id,'link_id':after[0].get('id') if after else None,'apps_privacy_control':after[0].get('apps_privacy_control') if after else None,'provider_http':evidence,'observed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 st,out=github('POST',f'/repos/{REPO}/issues',{'title':'PluginAdmin result: '+rid,'body':json.dumps(result,indent=2)});assert st==201,(st,out)
 print(json.dumps(result))
 if not ok:raise SystemExit(1)
if __name__=='__main__':
 try:main()
 except Exception as e:
  rid=os.environ.get('REQUEST_ID','unknown');result={'schema':'cognilode.plugin-admin-result.v1','request_id':rid,'operation':os.environ.get('OPERATION'),'ok':False,'error':str(e)[:1000],'observed_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())};github('POST',f'/repos/{REPO}/issues',{'title':'PluginAdmin result: '+rid,'body':json.dumps(result,indent=2)});print(json.dumps(result));raise
