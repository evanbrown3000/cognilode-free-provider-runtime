"""Queue adapter for the recovered SDK; credentials remain in process memory."""
import base64
import datetime as dt
import json
import os
import random
import subprocess
import sys
import tempfile
import time
import uuid

from curl_cffi import requests


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


config = json.loads(sys.stdin.readline())
job = config['job']
tokens = config['auth'].get('tokens', config['auth'])
web = config.get('web_session') or {}
cookies = web.get('cookie') or '; '.join(c['name'] + '=' + c['value'] for c in web.get('cookies', []))
headers = {
    'Authorization': 'Bearer ' + tokens['access_token'],
    'ChatGPT-Account-ID': tokens['account_id'],
    'Origin': 'https://chatgpt.com',
    'Referer': 'https://chatgpt.com/',
    'Content-Type': 'application/json',
    'OAI-Language': 'en-US',
    'originator': 'Codex Browser',
    'X-OpenAI-Codex-Window-Type': 'browser',
    'X-OpenAI-Web-Frontend': 'codex_webview',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36',
}
if cookies:
    headers['Cookie'] = cookies
for cookie in web.get('cookies', []):
    if cookie['name'] == 'oai-did':
        headers['OAI-Device-ID'] = cookie['value']
session = requests.Session(impersonate='chrome')
session.headers.update(headers)
request = {'id': str(uuid.uuid4()), 'operation': 'prompt_post', 'method': 'POST', 'url': 'https://chatgpt.com/backend-api/f/conversation'}
attachments = (job.get('attachments') or []) + [x for x in job.get('reusable_attachments', []) if x.get('id') and x.get('sha256')]
message_id = job['user_message_id']
payload = {'action':'next','messages':[{'id':message_id,'author':{'role':'user'},'content':{'content_type':'text','parts':[job['prompt']]},'metadata':{'attachments':attachments}}], 'parent_message_id':job.get('parent_message_id') or str(uuid.uuid4()), 'model':job.get('model') or 'auto','conversation_mode':{'kind':'primary_assistant'},'history_and_training_disabled':False}
if job.get('conversation_id'):
    payload['conversation_id'] = job['conversation_id']
emit({'type': 'attachments_uploaded', 'attachments': job.get('reusable_attachments', [])})


def b64(value):
    return base64.b64encode(json.dumps(value, separators=(',', ':')).encode()).decode()


def mix(value):
    number = 2166136261
    for char in value:
        number = ((number ^ ord(char)) * 16777619) & 0xFFFFFFFF
    number ^= number >> 16; number = (number * 2246822507) & 0xFFFFFFFF
    number ^= number >> 13; number = (number * 3266489909) & 0xFFFFFFFF
    number ^= number >> 16
    return f'{number & 0xFFFFFFFF:08x}'


def sentinel_headers():
    device = headers.get('OAI-Device-ID') or headers.get('oai-did') or str(uuid.uuid4())
    values = [3840, str(dt.datetime.now().astimezone()), None, 1, headers['User-Agent'], None,
              None, 'en-US', 'en-US,en', random.random(), None, None, None, 0, device, '', 8,
              time.time() * 1000, 0, 0, 0, 0, 0, 0, 0]
    key = 'gAAAAAC' + b64(values)
    prepared = session.post('https://chatgpt.com/backend-api/sentinel/chat-requirements/prepare',
                            json={'p': key}, timeout=60)
    prepared.raise_for_status(); requirements = prepared.json()
    turn = requirements.get('turnstile') or {}; proof = requirements.get('proofofwork') or {}
    turn_token = ''
    if turn.get('required'):
        vm = os.environ.get('COGNILODE_SENTINEL_VM', '/opt/cognilode-chatmode-sdk/chatgpt_sentinel_vm.mjs')
        turn_token = subprocess.check_output(['node', vm, turn['dx'], key], text=True, timeout=30).strip()
    proof_token = ''
    if proof.get('required'):
        started = time.perf_counter(); template = list(values); difficulty = str(proof['difficulty'])
        for counter in range(500_000):
            template[3] = counter; template[9] = round((time.perf_counter() - started) * 1000)
            candidate = b64(template)
            if mix(str(proof['seed']) + candidate)[:len(difficulty)] <= difficulty:
                proof_token = 'gAAAAAB' + candidate + '~S'; break
        if not proof_token: raise RuntimeError('Sentinel proof-of-work was not solved')
    finalized = session.post('https://chatgpt.com/backend-api/sentinel/chat-requirements/finalize',
                             json={'prepare_token': requirements['prepare_token'],
                                   'proofofwork': proof_token, 'turnstile': turn_token}, timeout=60)
    finalized.raise_for_status(); final = finalized.json()
    return {'OpenAI-Sentinel-Proof-Token': proof_token,
            'OpenAI-Sentinel-Turnstile-Token': turn_token,
            'OpenAI-Sentinel-Chat-Requirements-Token': final['token']}


def evidence(response):
    return {'request': request, 'response': {'url': response.url, 'status': response.status_code,
        'content_type': response.headers.get('content-type'), 'server': response.headers.get('server'),
        'challenge': response.headers.get('cf-mitigated'), 'request_id': response.headers.get('x-request-id'),
        'edge_trace': response.headers.get('cf-ray')}, 'application_origin_confirmed': False}


try:
    generation_headers = sentinel_headers()
    request['operation'] = 'prepare_post'
    request['url'] = 'https://chatgpt.com/backend-api/f/conversation/prepare'
    emit({'type':'prepare_post_started','request':dict(request)})
    prepare_response = session.post('https://chatgpt.com/backend-api/f/conversation/prepare', json=payload, timeout=120)
    prepare_response.raise_for_status()
    preparation = prepare_response.json()
    for field in ('headers','request_headers','generation_headers'):
        if isinstance(preparation.get(field),dict):
            generation_headers.update({k:str(v) for k,v in preparation[field].items() if isinstance(v,(str,int,float))})
    if preparation.get('conduit_token'):
        generation_headers['X-Conduit-Token'] = preparation['conduit_token']
    emit({'type': 'ready_to_send', 'user_message_id': message_id})
    if sys.stdin.readline().strip() != 'send':
        raise RuntimeError('Queue did not commit this send')
    request['operation'] = 'prompt_post'
    request['url'] = 'https://chatgpt.com/backend-api/f/conversation'
    emit({'type':'prompt_post_started','request':dict(request)})
    response = session.post('https://chatgpt.com/backend-api/f/conversation', json=payload,
                            headers={**generation_headers, 'Accept': 'text/event-stream'},
                            timeout=900, stream=True)
    response.raise_for_status()
except Exception as exc:
    response = getattr(exc, 'response', None)
    if response is None:
        raise
    rejection = None
    response_text = None
    try:
        response_text = response.text
    except Exception:
        pass
    if 'application/json' in response.headers.get('content-type', ''):
        try:
            rejection = response.json()
        except ValueError:
            pass
    emit({'type': 'provider_rejected_before_send' if request['operation']=='prepare_post' else 'provider_rejected', 'status': response.status_code, 'rejection': rejection,
        'response_text': response_text[:8000] if isinstance(response_text, str) else None,
        'evidence': evidence(response), 'operation': request['operation'], 'path': '/backend-api/f/conversation/prepare' if request['operation']=='prepare_post' else '/backend-api/f/conversation',
        'content_type': response.headers.get('content-type'), 'network_server': response.headers.get('server'),
        'network_challenge': response.headers.get('cf-mitigated')})
    sys.exit(0)

emit({'type': 'provider_accepted', 'status': response.status_code, 'evidence': evidence(response),
    'content_type': response.headers.get('content-type')})
frame = []
for line in response.iter_lines(chunk_size=1, decode_unicode=True):
    if isinstance(line, bytes):
        line = line.decode('utf-8')
    if line:
        if line.startswith('data:'):
            frame.append(line[5:].lstrip())
        continue
    data = '\n'.join(frame)
    frame = []
    if data == '[DONE]':
        emit({'type': 'stream_done'})
    elif data:
        try:
            emit({'type': 'provider_event', 'event': json.loads(data)})
        except ValueError:
            emit({'type': 'provider_event_unparsed', 'data': data})
session.close()
