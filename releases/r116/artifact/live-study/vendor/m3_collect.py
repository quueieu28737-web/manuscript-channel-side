"""R102 actual LLM -> LangGraph -> seven TLS1.3/HTTP2 MCP endpoints.

Only synthetic fixtures. No request retries. The opaque wire relay counts the
bytes of actual TCP sockets; it cannot see HTTP, MCP, tool results, or labels.
"""
from __future__ import annotations
import asyncio, contextlib, copy, hashlib, importlib.metadata, ipaddress, json
import logging, os, random, ssl, sys, time, uuid
from pathlib import Path
from typing import TypedDict
from common import H, PR, enc, load, save, log, sha, now, canonical
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.server.fastmcp import FastMCP
from hypercorn.asyncio import serve
from hypercorn.config import Config
from langgraph.graph import StateGraph, START, END
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import datetime
from environment import SERVICES, SYSTEM, ACTIONS, READ_ENDPOINT, make_state, destination, admissible, dispatch, outcomes

PLAN=load(H/'experiment/cohort-plan.json')
FRONT={s:40120+i for i,s in enumerate(SERVICES)}
BACK={s:40220+i for i,s in enumerate(SERVICES)}
OLLAMA='http://127.0.0.1:11502'
STATE={}; REQUESTS={}; CONNECTIONS={}; OUT=None; EVENTS=None

class TLS13(Config):
    def create_ssl_context(self):
        ctx=super().create_ssl_context()
        ctx.minimum_version=ctx.maximum_version=ssl.TLSVersion.TLSv1_3
        return ctx

def certificates():
    d=H/'private-run/tls'; d.mkdir(parents=True,exist_ok=True)
    if (d/'cert.pem').exists():return
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    t=datetime.datetime.now(datetime.timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(t-datetime.timedelta(minutes=5))
          .not_valid_after(t+datetime.timedelta(days=30)).add_extension(x509.SubjectAlternativeName([
          x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),False)
          .sign(key,hashes.SHA256()))
    (d/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (d/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))

class Wire:
    def __init__(self,service,peer):
        self.service=service;self.peer=peer;self.id=uuid.uuid4().hex
        self.counts=[0,0];self.chunks=[0,0];self.buffers=[bytearray(),bytearray()];self.records=[[],[]]
        self.closed=False
    def observe(self,side,b):
        self.counts[side]+=len(b);self.chunks[side]+=1;self.buffers[side].extend(b)
        buf=self.buffers[side]
        while len(buf)>=5:
            n=int.from_bytes(buf[3:5],'big')
            assert n<=18432, 'unexpected TLS record length'
            if len(buf)<n+5:break
            self.records[side].append([buf[0],n+5]);del buf[:n+5]
    def snapshot(self):
        return {'bytes':list(self.counts),'records':[len(x) for x in self.records]}
    def receipt(self):
        return {'id':self.id,'service':self.service,'peer':self.peer,'bytes':self.counts,
                'chunks':self.chunks,'records':self.records,'trailing_bytes':[len(x) for x in self.buffers],
                'closed':self.closed}

async def relay(service,reader,writer):
    peer=writer.get_extra_info('peername');w=Wire(service,peer)
    CONNECTIONS[(service,peer[1])]=w
    remote_reader,remote_writer=await asyncio.open_connection('127.0.0.1',BACK[service])
    async def copy_stream(src,dst,side):
        try:
            while True:
                b=await src.read(65536)
                if not b:break
                w.observe(side,b);dst.write(b);await dst.drain()
        finally:
            dst.close()
    await asyncio.gather(copy_stream(reader,remote_writer,0),copy_stream(remote_reader,writer,1),return_exceptions=True)
    w.closed=True
    save(OUT/'wire'/f'{w.id}.json',w.receipt())

class PaddedTool:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method']!='POST':return await self.app(scope,receive,send)
        start=None;pieces=[]
        async def output(event):
            nonlocal start
            if event['type']=='http.response.start':start=event;return
            if event['type']=='http.response.body':
                pieces.append(event.get('body',b''))
                if event.get('more_body'):return
                body=b''.join(pieces);ctype=dict(start.get('headers',[])).get(b'content-type',b'')
                if body and b'text/event-stream' in ctype:
                    n=((len(body)+3+16383)//16384)*16384
                    body+=b':'+b' '*(n-len(body)-3)+b'\n\n'
                elif body and b'application/json' in ctype:body+=b' '*((-len(body))%16384)
                start['headers']=[(k,v) for k,v in start.get('headers',[]) if k.lower()!=b'content-length']+[(b'content-length',str(len(body)).encode())]
                await send(start);await send({'type':'http.response.body','body':body,'more_body':False})
        await self.app(scope,receive,output)

def server(service):
    mcp=FastMCP('Support '+service,stateless_http=True,json_response=False,host='127.0.0.1',port=BACK[service],log_level='ERROR')
    @mcp.tool()
    async def execute(job_id:str,request_id:str,operation:str,order_id:str)->dict:
        """Execute a customer service operation and return its result."""
        meta=REQUESTS[request_id];st=STATE[job_id]
        assert meta['job']==job_id and meta['operation']==operation and meta['order_id']==order_id
        assert destination(operation)==service
        assert not meta['server_seen'], 'duplicate execution is prohibited'
        meta['server_seen']=True
        result,receipt=dispatch(st,operation,order_id,meta['kind'])
        receipt.update(request_id=request_id,service=service,utc=now())
        save(meta['folder']/'server-receipt.json',receipt)
        return result
    return mcp

class ToolConnections:
    def __init__(self,job,out):self.job=job;self.out=out;self.stack=contextlib.AsyncExitStack();self.sessions={};self.wires={};self.protocol=[]
    async def __aenter__(self):await self.stack.__aenter__();return self
    async def __aexit__(self,*args):
        await self.stack.__aexit__(*args)
        for w in self.wires.values():save(self.out/'connections'/f'{w.id}.json',w.receipt())
    async def get(self,service):
        if service in self.sessions:return self.sessions[service]
        async def request_hook(r):
            if r.method=='POST':
                b=await r.aread();b+=b' '*((-len(b))%4096)
                r._content=b;r.stream=httpx.ByteStream(b);r.headers['content-length']=str(len(b))
        async def response_hook(r):
            ns=r.extensions['network_stream'];s=ns.get_extra_info('ssl_object');peer=ns.get_extra_info('client_addr')
            info={'service':service,'tls':s.version(),'alpn':s.selected_alpn_protocol(),'http':r.http_version,
                  'method':r.request.method,'path':r.request.url.path,'status':r.status_code,
                  'stream_id':r.extensions.get('stream_id'),'client':peer}
            assert info['tls']=='TLSv1.3' and info['alpn']=='h2' and info['http']=='HTTP/2',info
            self.protocol.append(info)
            w=CONNECTIONS[(service,peer[1])]
            if service in self.wires:assert self.wires[service].id==w.id, 'unexpected reconnect'
            self.wires[service]=w
        def factory(**kwargs):
            ctx=ssl.create_default_context(cafile=str(H/'private-run/tls/cert.pem'))
            ctx.minimum_version=ctx.maximum_version=ssl.TLSVersion.TLSv1_3
            kwargs['timeout']=180
            return httpx.AsyncClient(http2=True,verify=ctx,trust_env=False,
               limits=httpx.Limits(max_connections=1,max_keepalive_connections=1,keepalive_expiry=None),
               event_hooks={'request':[request_hook],'response':[response_hook]},**kwargs)
        streams=await self.stack.enter_async_context(streamablehttp_client(f'https://127.0.0.1:{FRONT[service]}/mcp',httpx_client_factory=factory,timeout=180))
        sess=await self.stack.enter_async_context(ClientSession(streams[0],streams[1]));init=await sess.initialize()
        self.protocol.append({'service':service,'mcp_version':init.protocolVersion})
        self.sessions[service]=sess
        return sess

async def tool_call(st,job,tc,action,order_id,kind,out):
    seq=len(st['calls']);folder=out/'tools'/f'{seq:02d}'
    assert not folder.exists();folder.mkdir(parents=True)
    service=destination(action)
    request_id=uuid.uuid5(uuid.NAMESPACE_URL,f'r102/{job}/{seq}').hex
    REQUESTS[request_id]={'job':job,'operation':action,'order_id':order_id,'kind':kind,'folder':folder,'server_seen':False}
    save(folder/'request.json',{'request_id':request_id,'job_id':job,'operation':action,'order_id':order_id,'kind':kind,'service':service})
    try:
        sess=await tc.get(service);w=tc.wires[service];before=w.snapshot();begin=time.time()
        save(folder/'started.json',{'time':begin,'wire_id':w.id,'before':before})
        result=await sess.call_tool('execute',{'job_id':job,'request_id':request_id,'operation':action,'order_id':order_id})
        obj=result.structuredContent
        if obj is None:obj=json.loads(next(c.text for c in result.content if c.type=='text'))
        assert not result.isError, obj
        # Let the already-sent final HTTP2 frame reach the local counting relay.
        await asyncio.sleep(.002)
        after=w.snapshot()
        terminal={'start':begin,'end':time.time(),'result':obj,'is_error':result.isError,'wire_id':w.id,
                  'before':before,'after':after,'cipher_bytes':[after['bytes'][i]-before['bytes'][i] for i in range(2)]}
        assert all(v>0 for v in terminal['cipher_bytes'])
        save(folder/'terminal.json',terminal)
        st['wire_trace'].append({'service':service,'bytes':terminal['cipher_bytes'],'kind':kind,'operation':action,'request_id':request_id})
        return obj
    except BaseException as e:
        save(folder/'unknown.json',{'utc':now(),'type':type(e).__name__,'server_seen':REQUESTS[request_id]['server_seen']})
        raise

async def model_call(st,model,messages,k,client,out):
    d=out/'model'/f'{k:02d}';assert not d.exists();d.mkdir(parents=True)
    allowed=admissible(st)
    schema={'type':'object','properties':{'action':{'type':'string','enum':allowed},
             'order_id':{'type':'string','enum':list(st['unit']['fixture']['orders'])}},
             'required':['action','order_id'],'additionalProperties':False}
    sent=messages+[{'role':'user','content':'Available actions: '+', '.join(allowed)+'. Return one JSON action and order_id.'}]
    opts={**PLAN['options'],'seed':st['unit']['seed']}
    payload={'model':model,'messages':sent,'format':schema,'think':False,'stream':True,'options':opts,'keep_alive':'30m'}
    save(d/'request.json',payload);begin=time.time();save(d/'started.json',{'time':begin,'request_sha256':sha(d/'request.json')})
    text='';done=None
    try:
        async with client.stream('POST',OLLAMA+'/api/chat',json=payload) as r:
            if r.status_code!=200:
                b=await r.aread();save(d/'http-terminal.json',{'time':time.time(),'status':r.status_code,'body_sha256':hashlib.sha256(b).hexdigest()})
                raise RuntimeError('Model HTTP rejection; review before continuing')
            async for line in r.aiter_lines():
                if not line:continue
                value=json.loads(line);log(d/'chunks.jsonl',{'time':time.time(),'response':value})
                text+=value.get('message',{}).get('content','')
                if value.get('done'):done=value
        if done is None:raise RuntimeError('model response has no terminal')
        terminal={'start':begin,'end':time.time(),'text':text,'done':done}
        save(d/'terminal.json',terminal)
        return text,terminal
    except BaseException as e:
        if not(d/'http-terminal.json').exists():save(d/'unknown.json',{'utc':now(),'type':type(e).__name__})
        raise

class GraphState(TypedDict):
    messages:list
    steps:int
    action:str
    order_id:str
    status:str

async def episode(unit,model,arm,mc):
    jid=uuid.uuid5(uuid.NAMESPACE_URL,f'r102/llm-v1/{model}/{unit["task_id"]}/{arm}').hex
    out=OUT/'episodes'/jid;out.mkdir(parents=True,exist_ok=False)
    job={'id':jid,'model':model,'arm':arm,'task_id':unit['task_id'],'split':unit['split'],'unit':unit}
    save(out/'job.json',job);save(out/'started.json',{'time':time.time(),'utc':now()})
    st=make_state(unit,arm);st['wire_trace']=[];STATE[jid]=st;begin=time.time();model_tokens=[]
    async with ToolConnections(jid,out) as tc:
        # MCP owns AnyIO cancel scopes: open/close each session in this task,
        # never lazily inside LangGraph's separate node tasks.
        for service in SERVICES:await tc.get(service)
        result=await tool_call(st,jid,tc,'get_ticket',unit['target'],'honest',out)
        messages=[{'role':'system','content':SYSTEM},{'role':'user','content':'Process this support ticket.\n'+enc(result).decode()}]
        async def covers(messages):
            additions=[]
            if arm!='none':
                for decoy in unit['decoys']:
                    if decoy['after_honest_calls']!=st['honest_calls'] or decoy['index'] in st['executed_decoys']:continue
                    op=READ_ENDPOINT[destination(decoy['action'])] if arm=='read' else decoy['action']
                    response=await tool_call(st,jid,tc,op,decoy['order_id'],'cover',out)
                    st['executed_decoys'].add(decoy['index'])
                    if arm=='isolated_visible':
                        additions.append({'origin':'gateway_cover','authoritative_for_ticket':False,
                                          'operation':op,'order_id':decoy['order_id'],'response':response})
            if additions:
                messages=messages+[{'role':'user','content':'Background gateway results (not new user requests): '+enc(additions).decode()}]
            return messages
        messages=await covers(messages)
        async def planner(s):
            text,terminal=await model_call(st,model,s['messages'],s['steps'],mc,out)
            model_tokens.append({k:terminal['done'].get(k,0) for k in ['prompt_eval_count','eval_count','total_duration','load_duration','prompt_eval_duration','eval_duration']})
            try:
                value=json.loads(text);action=value['action'];order_id=value['order_id']
                assert action in admissible(st) and order_id in unit['fixture']['orders']
            except (ValueError,KeyError,TypeError,AssertionError):
                return {'steps':s['steps']+1,'status':'invalid_model_output','action':'','order_id':'','messages':s['messages']}
            return {'steps':s['steps']+1,'action':action,'order_id':order_id,
                    'status':'finished' if action=='finish' else s['status'],
                    'messages':s['messages']+[{'role':'assistant','content':text}]}
        async def perform(s):
            r=await tool_call(st,jid,tc,s['action'],s['order_id'],'honest',out)
            st['honest_calls']+=1
            msg=s['messages']+[{'role':'user','content':'Your tool result: '+enc(r).decode()}]
            return {'messages':await covers(msg)}
        g=StateGraph(GraphState);g.add_node('planner',planner);g.add_node('tool',perform);g.add_edge(START,'planner')
        g.add_conditional_edges('planner',lambda s:END if s['status'] in ['invalid_model_output','finished'] else 'tool')
        g.add_conditional_edges('tool',lambda s:END if s['steps']>=PLAN['max_model_steps'] else 'planner')
        final=await g.compile().ainvoke({'messages':messages,'steps':0,'action':'','order_id':'','status':'step_limit'},config={'recursion_limit':24})
        save(out/'final-messages.json',final['messages'])
        result={'job_id':jid,'model':model,'arm':arm,'task_id':unit['task_id'],'split':unit['split'],'label':unit['action'],
                'start':begin,'end':time.time(),'status':final['status'],'model_steps':final['steps'],
                'model_usage':model_tokens,'calls':st['calls'],'wire_trace':st['wire_trace'],
                'checked':sorted(st['checked']),'executed_decoys':sorted(st['executed_decoys']),
                'planned_decoys':len(unit['decoys']) if arm!='none' else 0,**outcomes(st)}
    result['transport_total_bytes']=sum(sum(w.counts) for w in tc.wires.values())
    result['tool_cipher_bytes']=sum(sum(x['bytes']) for x in st['wire_trace'])
    result['protocol']=tc.protocol
    save(out/'result.json',result)
    log(EVENTS,{'event':'episode_terminal',**{k:result[k] for k in ['job_id','model','arm','task_id','split','goal_success','state_integrity','status','start','end']}})
    print(json.dumps({'model':model,'arm':arm,'task':unit['task_id'],'split':unit['split'],
        'goal':result['goal_success'],'integrity':result['state_integrity'],'steps':final['steps'],'seconds':round(result['end']-begin,2)}),flush=True)
    del STATE[jid]
    return result

async def main(mode):
    global OUT,EVENTS
    assert mode in ['development-v1','development-v2','formal-v1']
    OUT=H/'private-run'/mode;OUT.mkdir(parents=True,exist_ok=False);EVENTS=OUT/'events.jsonl'
    lock=H/'private-run/collector.lock'
    with lock.open('x') as f:f.write(json.dumps({'pid':os.getpid(),'mode':mode,'utc':now()}))
    stop=asyncio.Event();servers=[];relays=[];failed=True
    try:
        if mode=='formal-v1':
            for name,digest in load(H/'experiment/freeze.json')['files'].items():assert sha(H/name)==digest,name
        weights=load(H/'verification/weights-before.json')
        # A tag change between the full preflight hash and this start is fatal.
        model_root=Path(os.environ['USERPROFILE'])/'.ollama/models'
        for m in weights['models']:
            name,tag=m['model'].split(':')
            assert sha(model_root/'manifests/registry.ollama.ai/library'/name/tag)==m['manifest_sha256']
        save(OUT/'started.json',{'utc':now(),'time':time.time(),'pid':os.getpid(),'mode':mode,'weights':weights,
             'dependencies':{x:importlib.metadata.version(x) for x in ['langgraph','langchain-core','mcp','hypercorn','httpx','h2','cryptography']}})
        for p in (H/'experiment').glob('*.py'):
            (OUT/'source').mkdir(exist_ok=True);(OUT/'source'/p.name).write_bytes(p.read_bytes())
        certificates()
        for service in SERVICES:
            app=server(service);cfg=TLS13();cfg.bind=[f'127.0.0.1:{BACK[service]}']
            cfg.certfile=str(H/'private-run/tls/cert.pem');cfg.keyfile=str(H/'private-run/tls/key.pem')
            cfg.alpn_protocols=['h2'];cfg.accesslog=None;cfg.errorlog=str(OUT/f'server-{service}.log');cfg.loglevel='ERROR';cfg.keep_alive_timeout=3600
            servers.append(asyncio.create_task(serve(PaddedTool(app.streamable_http_app()),cfg,shutdown_trigger=stop.wait)))
        await asyncio.sleep(.5)
        for service in SERVICES:
            async def accept(reader,writer,s=service):await relay(s,reader,writer)
            relays.append(await asyncio.start_server(accept,'127.0.0.1',FRONT[service]))
        async with httpx.AsyncClient(timeout=240,trust_env=False,limits=httpx.Limits(max_connections=4)) as mc:
            for model in PLAN['models']:
                # Empty generation loads weights only and is separately recorded.
                load_dir=OUT/'loads'/model.replace(':','-');load_dir.mkdir(parents=True)
                save(load_dir/'started.json',{'utc':now(),'model':model})
                r=await mc.post(OLLAMA+'/api/generate',json={'model':model,'prompt':'','keep_alive':'30m','options':{'num_ctx':4096}})
                r.raise_for_status();save(load_dir/'terminal.json',r.json())
                units=(load(H/'experiment/development-v2-plan.json') if mode=='development-v2' else
                       PLAN['development_units'] if mode.startswith('development') else PLAN['units'])
                queue=asyncio.Queue()
                for t in units:queue.put_nowait(t)
                async def worker():
                    while not queue.empty():
                        t=queue.get_nowait()
                        arms=t['arm_order'] if mode=='formal-v1' or t['action']=='refund' else ['none']
                        for arm in arms:await episode(t,model,arm,mc)
                        queue.task_done()
                tasks=[asyncio.create_task(worker()) for _ in range(PLAN['workers'])]
                done,pending=await asyncio.wait(tasks,return_when=asyncio.FIRST_EXCEPTION)
                error=next((t.exception() for t in done if t.exception() is not None),None)
                if error:
                    for t in pending:t.cancel()
                    await asyncio.gather(*pending,return_exceptions=True)
                    raise error
                await asyncio.gather(*pending)
        save(OUT/'finished.json',{'utc':now(),'time':time.time(),'episodes':len(list((OUT/'episodes').glob('*/result.json')))})
        failed=False
    except BaseException as e:
        save(OUT/'interrupted.json',{'utc':now(),'type':type(e).__name__,'message':str(e)[:500]});raise
    finally:
        for r in relays:r.close();await r.wait_closed()
        stop.set();await asyncio.gather(*servers,return_exceptions=True)
        # A stopped collection keeps its lock for explicit unknown-request audit.
        if not failed:lock.unlink()

if __name__=='__main__':
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(main(sys.argv[1]))
