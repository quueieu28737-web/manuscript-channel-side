"""Live five-arm TLS record study. One episode at a time; no request retries.

M3 business semantics and planner implementation are vendored unchanged. Service
connection locks define nonoverlapping call windows on each shared connection;
calls to different services and inference remain concurrent.
"""
from __future__ import annotations
import argparse, asyncio, contextlib, copy, hashlib, importlib.util, json, logging
import os, random, signal, subprocess, sys, time, uuid
from pathlib import Path
from common import H, enc, load, save, log, sha, now
import httpx
from environment import SERVICES, SYSTEM, ACTIONS, make_state, destination, admissible, outcomes
from cover_env import make_task
from langgraph.graph import StateGraph, START, END

spec=importlib.util.spec_from_file_location('m3_collect',H/'vendor/m3_collect.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
BASE_PLAN=load(H/'experiment/cohort-plan.json')
ARMS=['none','unmatched','gdm_live','concurrent','shadow']
B.FRONT={s:41120+i for i,s in enumerate(SERVICES)}
B.BACK={s:41220+i for i,s in enumerate(SERVICES)}
B.OLLAMA='http://127.0.0.1:11510'
OUT=None;EVENTS=None;POOLS=None;RUN_ID=None

class RecordWire(B.Wire):
    def __init__(self,service,peer):
        super().__init__(service,peer);self.backend_port=None;self.last_record_end=[None,None]
    def observe(self,side,b):
        t=time.perf_counter_ns();wall=time.time_ns()
        self.counts[side]+=len(b);self.chunks[side]+=1;self.buffers[side].extend(b)
        buf=self.buffers[side]
        while len(buf)>=5:
            n=int.from_bytes(buf[3:5],'big');assert n<=18432
            if len(buf)<n+5:break
            self.records[side].append([buf[0],n+5,t,wall]);self.last_record_end[side]=t
            del buf[:n+5]
    def receipt(self):
        return {**super().receipt(),'backend_client_port':self.backend_port,
                'record_schema':['outer_type','wire_length','completion_perf_ns','completion_epoch_ns']}

async def relay(service,reader,writer):
    peer=writer.get_extra_info('peername');w=RecordWire(service,peer)
    B.CONNECTIONS[(service,peer[1])]=w
    rr,rw=await asyncio.open_connection('127.0.0.1',B.BACK[service])
    w.backend_port=rw.get_extra_info('sockname')[1]
    async def cp(src,dst,side):
        try:
            while b:=await src.read(65536):
                w.observe(side,b);dst.write(b);await dst.drain()
        finally:dst.close()
    await asyncio.gather(cp(reader,rw,0),cp(rr,writer,1),return_exceptions=True)
    w.closed=True;save(OUT/'wire'/f'{w.id}.json',w.receipt())

async def sleep_not_before(seconds):
    deadline=time.perf_counter_ns()+max(0,int(seconds*1e9))
    while True:
        remaining=(deadline-time.perf_counter_ns())/1e9
        if remaining<=0:return
        await asyncio.sleep(remaining)

class HoldPaddedTool:
    """Hold only a cover response, then use the unchanged M3 body padding."""
    def __init__(self,app):self.app=B.PaddedTool(app)
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method']!='POST':
            return await self.app(scope,receive,send)
        pieces=[];more=True
        while more:
            event=await receive()
            if event['type']!='http.request':return
            pieces.append(event.get('body',b''));more=event.get('more_body',False)
        body=b''.join(pieces);meta=None
        try:
            val=json.loads(body);rid=val.get('params',{}).get('arguments',{}).get('request_id')
            meta=B.REQUESTS.get(rid)
        except (ValueError,AttributeError):pass
        origin=time.perf_counter();sent=False
        async def replay():
            nonlocal sent
            if not sent:sent=True;return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        async def held(event):
            if event['type']=='http.response.start' and meta and meta.get('hold_s'):
                delay=max(0.,meta['hold_s']-(time.perf_counter()-origin))
                meta['hold_actual_sleep']=delay
                await sleep_not_before(delay)
            await send(event)
        return await self.app(scope,replay,held)

class Connections(B.ToolConnections):
    def __init__(self,job,out):
        super().__init__(job,out);self.locks={s:asyncio.Lock() for s in SERVICES}
        self.seq=0;self.completed=[];self.cover_tasks=[];self.failure=None
        self.dispatch_queue=asyncio.Queue();self.dispatch_task=None
    async def __aexit__(self,*args):
        if self.dispatch_task is not None and not self.dispatch_task.done():
            self.dispatch_task.cancel()
            await asyncio.gather(self.dispatch_task,return_exceptions=True)
        return await super().__aexit__(*args)

async def cover_dispatcher(tc):
    try:
        while True:
            item=await tc.dispatch_queue.get()
            if item is None:return
            fn,decoy,trigger=item
            await fn(decoy,trigger)
    except BaseException as e:
        tc.failure=e
        raise

async def tool_call(st,job,tc,action,oid,kind,out,role='real',hold_s=0.,schedule=None):
    if tc.failure is not None:raise RuntimeError('A prior tool request requires interruption audit') from tc.failure
    # Assign sequence before the first await; concurrent chains cannot reuse it.
    seq=tc.seq;tc.seq+=1;folder=out/'tools'/f'{seq:03d}';folder.mkdir(parents=True,exist_ok=False)
    service=destination(action);rid=uuid.uuid5(uuid.NAMESPACE_URL,f'{RUN_ID}/{job}/{seq}').hex
    meta={'job':job,'operation':action,'order_id':oid,'kind':kind,'folder':folder,
          'server_seen':False,'hold_s':float(hold_s)}
    B.REQUESTS[rid]=meta
    request={'request_id':rid,'job_id':job,'operation':action,'order_id':oid,'kind':kind,
             'role':role,'service':service,'schedule':schedule,'hold_s':float(hold_s)}
    save(folder/'request.json',request)
    try:
        async with tc.locks[service]:
            sess=tc.sessions[service];w=tc.wires[service];before=w.snapshot()
            begin=time.time();p0=time.perf_counter_ns()
            save(folder/'started.json',{'time':begin,'perf_ns':p0,'wire_id':w.id,'before':before})
            result=await sess.call_tool('execute',{'job_id':job,'request_id':rid,'operation':action,'order_id':oid})
            obj=result.structuredContent
            if obj is None:obj=json.loads(next(c.text for c in result.content if c.type=='text'))
            assert not result.isError,obj
            await asyncio.sleep(.002)
            after=w.snapshot()
            slices=[w.records[i][before['records'][i]:after['records'][i]] for i in range(2)]
            ups=[r for r in slices[0] if r[0]==23];downs=[r for r in slices[1] if r[0]==23]
            assert ups and downs,'missing encrypted TLS records in call window'
            start_ns=ups[0][2];end_ns=downs[-1][2];assert end_ns>=start_ns
            terminal={'start':begin,'end':time.time(),'receipt_perf_start_ns':p0,'receipt_perf_end_ns':time.perf_counter_ns(),
                      'wire_id':w.id,'before':before,'after':after,'result':obj,'is_error':False,
                      'cipher_bytes':[after['bytes'][i]-before['bytes'][i] for i in range(2)],
                      'record_start_ns':start_ns,'record_end_ns':end_ns,
                      'hold_actual_sleep':meta.get('hold_actual_sleep',0.)}
            assert all(x>0 for x in terminal['cipher_bytes'])
            save(folder/'terminal.json',terminal)
        obs={'service':service,'bytes':terminal['cipher_bytes'],'start_ns':start_ns,'end_ns':end_ns,
             'request_id':rid,'kind':kind,'role':role,'operation':action,'folder':str(folder.relative_to(out))}
        tc.completed.append(obs);st['wire_trace'].append(obs)
        return obj,obs
    except BaseException as e:
        tc.failure=e
        name='unknown.json' if (folder/'started.json').exists() else 'not-dispatched.json'
        save(folder/name,{'utc':now(),'type':type(e).__name__,'server_seen':meta['server_seen']})
        raise

async def chain(unit,model,st,job,tc,out,mc,arm,role,ready=None):
    chain_out=out/'chains'/role;chain_out.mkdir(parents=True,exist_ok=False)
    usage=[];start=time.time();rng=random.Random(unit['seed']+1101111)
    ticket,obs=await tool_call(st,job,tc,'get_ticket',unit['target'],'honest',out,role)
    if ready:ready.set()
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':'Process this support ticket.\n'+enc(ticket).decode()}]
    async def one_cover(decoy,trigger):
        gap=hold=0.
        anchor=max(tc.completed,key=lambda c:c['end_ns'])
        if arm in ['gdm_live','concurrent']:
            pool=POOLS['models'][model];gap=rng.choice(pool['gap_seconds'])
            ds=destination(decoy['action']);vs=pool['duration_seconds'].get(ds,[])
            hold=rng.choice(vs if len(vs)>=20 else pool['all_duration_seconds'])
            await sleep_not_before(max(0.,gap-(time.perf_counter_ns()-anchor['end_ns'])/1e9))
        await tool_call(st,job,tc,decoy['action'],decoy['order_id'],'cover',out,role,hold,
                        {'index':decoy['index'],'trigger_request':trigger['request_id'],'anchor_request':anchor['request_id'],'anchor_end_ns':anchor['end_ns'],'target_gap_s':gap,'target_duration_s':hold})
    async def covers(trigger):
        if role!='real' or arm not in ['unmatched','gdm_live','concurrent']:return
        for d in unit['decoys']:
            if d['after_honest_calls']==st['honest_calls'] and d['index'] not in st['executed_decoys']:
                st['executed_decoys'].add(d['index'])
                if arm=='concurrent':tc.dispatch_queue.put_nowait((one_cover,d,trigger))
                else:await one_cover(d,trigger)
    await covers(obs)
    async def planner(s):
        if tc.failure is not None:raise RuntimeError('Stopped after unresolved tool request') from tc.failure
        text,terminal=await B.model_call(st,model,s['messages'],s['steps'],mc,chain_out)
        usage.append({k:terminal['done'].get(k,0) for k in ['prompt_eval_count','eval_count','total_duration','load_duration','prompt_eval_duration','eval_duration']})
        try:
            v=json.loads(text);action=v['action'];oid=v['order_id']
            assert action in admissible(st) and oid in unit['fixture']['orders']
        except (ValueError,KeyError,TypeError,AssertionError):
            return {'steps':s['steps']+1,'status':'invalid_model_output','action':'','order_id':'','messages':s['messages']}
        return {'steps':s['steps']+1,'action':action,'order_id':oid,
                'status':'finished' if action=='finish' else s['status'],
                'messages':s['messages']+[{'role':'assistant','content':text}]}
    async def perform(s):
        result,ob=await tool_call(st,job,tc,s['action'],s['order_id'],'honest',out,role)
        st['honest_calls']+=1
        await covers(ob)
        return {'messages':s['messages']+[{'role':'user','content':'Your tool result: '+enc(result).decode()}]}
    g=StateGraph(B.GraphState);g.add_node('planner',planner);g.add_node('tool',perform);g.add_edge(START,'planner')
    g.add_conditional_edges('planner',lambda s:END if s['status'] in ['invalid_model_output','finished'] else 'tool')
    g.add_conditional_edges('tool',lambda s:END if s['steps']>=BASE_PLAN['max_model_steps'] else 'planner')
    final=await g.compile().ainvoke({'messages':messages,'steps':0,'action':'','order_id':'','status':'step_limit'},config={'recursion_limit':24})
    save(chain_out/'final-messages.json',final['messages'])
    r={'start':start,'end':time.time(),'status':final['status'],'model_steps':final['steps'],
       'model_usage':usage,'calls':st['calls'],'checked':sorted(st['checked']),
       'executed_decoys':sorted(st['executed_decoys']),**outcomes(st)}
    save(chain_out/'result.json',r)
    return r

def shadow_fixture(unit):
    rng=random.Random(unit['seed']+500000)
    a=rng.choice(ACTIONS)
    t=make_task(rng,unit['task_id']+500000,a)
    t.update(seed=unit['seed']+500000,phrase=rng.randrange(10),split=unit['split'],decoys=[])
    first=bool(rng.randrange(2));offset=rng.uniform(.2,1.5)
    return t,{'shadow_first':first,'offset_s':offset,'decoy_action':a,'seed':unit['seed']+500000}

async def episode(unit,model,arm,mc):
    jid=uuid.uuid5(uuid.NAMESPACE_URL,f'{RUN_ID}/{model}/{unit["task_id"]}/{arm}').hex
    out=OUT/'episodes'/jid;out.mkdir(parents=True,exist_ok=False)
    save(out/'job.json',{'id':jid,'model':model,'arm':arm,'task_id':unit['task_id'],'split':unit['split'],'unit':unit})
    save(out/'started.json',{'utc':now(),'time':time.time(),'perf_ns':time.perf_counter_ns()})
    real=make_state(unit,'isolated');real['wire_trace']=[];B.STATE[jid]=real
    async with Connections(jid,out) as tc:
        # AnyIO session cancel scopes are entered and exited in this root task.
        for service in SERVICES:await tc.get(service)
        if arm=='concurrent':tc.dispatch_task=asyncio.create_task(cover_dispatcher(tc))
        admitted_at=time.time()
        shadow=None;meta=None
        if arm=='shadow':
            su,meta=shadow_fixture(unit);sj=jid+'-shadow'
            ss=make_state(su,'isolated');ss['wire_trace']=[];B.STATE[sj]=ss
            save(out/'shadow-unit.json',{'unit':su,'schedule':meta})
            ready=asyncio.Event()
            async def later(u,s,j,role):
                await ready.wait();await sleep_not_before(meta['offset_s'])
                return await chain(u,model,s,j,tc,out,mc,'shadow',role)
            if meta['shadow_first']:
                shadow,primary=await asyncio.gather(chain(su,model,ss,sj,tc,out,mc,'shadow','shadow',ready),later(unit,real,jid,'real'))
            else:
                primary,shadow=await asyncio.gather(chain(unit,model,real,jid,tc,out,mc,'shadow','real',ready),later(su,ss,sj,'shadow'))
        else:primary=await chain(unit,model,real,jid,tc,out,mc,arm,'real')
        # Drain cover while sessions remain alive; never close a pending request.
        if tc.dispatch_task is not None:
            tc.dispatch_queue.put_nowait(None)
            await tc.dispatch_task
        if tc.cover_tasks:await asyncio.gather(*tc.cover_tasks)
        trace=sorted(tc.completed,key=lambda t:(t['start_ns'],SERVICES.index(t['service']),t['end_ns']))
        r={'job_id':jid,'model':model,'arm':arm,'task_id':unit['task_id'],'split':unit['split'],'label':unit['action'],
           'admitted_at':admitted_at,'primary':primary,'shadow':shadow,'shadow_schedule':meta,'wire_trace':trace,'protocol':tc.protocol,
           'transport_total_bytes':sum(sum(w.counts) for w in tc.wires.values()),
           'tool_cipher_bytes':sum(sum(x['bytes']) for x in trace),
           'observation_start_ns':min(t['start_ns'] for t in trace),'observation_end_ns':max(t['end_ns'] for t in trace)}
    deadline=time.perf_counter()+2.
    while not all(w.closed for w in tc.wires.values()):
        if time.perf_counter()>deadline:raise RuntimeError('TLS relay did not close; review capture before proceeding')
        await asyncio.sleep(.002)
    r['transport_total_bytes']=sum(sum(w.counts) for w in tc.wires.values())
    save(out/'result.json',r)
    log(EVENTS,{'event':'episode_terminal','model':model,'arm':arm,'task_id':unit['task_id'],
                'split':unit['split'],'goal':primary['goal_success'],'integrity':primary['state_integrity'],'job_id':jid})
    print(json.dumps({'model':model,'arm':arm,'task':unit['task_id'],'split':unit['split'],
                      'goal':primary['goal_success'],'integrity':primary['state_integrity'],
                      'seconds':round(primary['end']-primary['start'],2),'calls':len(trace)}),flush=True)
    del B.STATE[jid]
    if shadow is not None:del B.STATE[jid+'-shadow']
    return r

def start_capture():
    folder=OUT/'capture';folder.mkdir()
    cmd=[r'C:\Program Files\Wireshark\dumpcap.exe','-i',r'\Device\NPF_Loopback','-f',
         'tcp and (portrange 41120-41126 or portrange 41220-41226)','-s','0','-B','64','-w',str(folder/'traffic.pcapng')]
    err=(folder/'dumpcap.stderr.log').open('wb')
    p=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=err,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                       startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW,wShowWindow=0))
    save(folder/'started.json',{'cmd':cmd,'pid':p.pid,'utc':now()})
    return p,err

async def main(args):
    global OUT,EVENTS,POOLS,RUN_ID
    RUN_ID=args.run;OUT=H/'private-run'/RUN_ID;OUT.mkdir(parents=True,exist_ok=False);EVENTS=OUT/'events.jsonl'
    B.OUT=OUT;B.EVENTS=EVENTS
    lock=H/'private-run/collector.lock'
    with lock.open('x') as f:f.write(json.dumps({'pid':os.getpid(),'run':RUN_ID,'phase':args.phase,'utc':now()}))
    stop=asyncio.Event();servers=[];relays=[];capture=None;failed=True
    try:
        if args.phase!='development':
            frozen=load(H/'experiment/freeze.json')
            for p,d in frozen['files'].items():assert sha(H/p)==d,p
            assert load(H/'verification/freeze-pushed.json')['freeze_sha256']==sha(H/'experiment/freeze.json')
        if args.phase=='cover':
            amended=load(H/'experiment/cover-freeze-v3.json')
            assert amended['parent_freeze_sha256']==sha(H/'experiment/freeze.json')
            for p,d in amended['files'].items():assert sha(H/p)==d,p
            assert load(H/'verification/cover-freeze-v3-pushed.json')['freeze_sha256']==sha(H/'experiment/cover-freeze-v3.json')
            POOLS=load(H/'pools/timing-pools.json')
            assert load(H/'verification/pools-pushed.json')['pools_sha256']==sha(H/'pools/timing-pools.json')
        elif args.phase=='development' and (H/'private-run/development-pools.json').exists():
            POOLS=load(H/'private-run/development-pools.json')
        weights=load(H/'verification/weights-before.json')
        root=Path(os.environ['USERPROFILE'])/'.ollama/models/manifests/registry.ollama.ai/library'
        for m in weights['models']:
            n,t=m['model'].split(':');assert sha(root/n/t)==m['manifest_sha256']
        save(OUT/'started.json',{'utc':now(),'time':time.time(),'pid':os.getpid(),'phase':args.phase,
             'perf_ns':time.perf_counter_ns(),'time_ns':time.time_ns(),'models':BASE_PLAN['models'],
             'weights_sha256':sha(H/'verification/weights-before.json'),'workers':1,'ollama_parallel':2})
        B.certificates();capture=start_capture();await asyncio.sleep(1)
        assert capture[0].poll() is None,'packet capture failed'
        for service in SERVICES:
            app=B.server(service);cfg=B.TLS13();cfg.bind=[f'127.0.0.1:{B.BACK[service]}']
            cfg.certfile=str(H/'private-run/tls/cert.pem');cfg.keyfile=str(H/'private-run/tls/key.pem')
            cfg.alpn_protocols=['h2'];cfg.accesslog=None;cfg.errorlog=str(OUT/f'server-{service}.log')
            cfg.loglevel='ERROR';cfg.keep_alive_timeout=3600
            servers.append(asyncio.create_task(B.serve(HoldPaddedTool(app.streamable_http_app()),cfg,shutdown_trigger=stop.wait)))
        await asyncio.sleep(.5)
        for service in SERVICES:
            async def accept(r,w,s=service):await relay(s,r,w)
            relays.append(await asyncio.start_server(accept,'127.0.0.1',B.FRONT[service]))
        async with httpx.AsyncClient(timeout=600,trust_env=False,limits=httpx.Limits(max_connections=4)) as mc:
            for model in BASE_PLAN['models']:
                d=OUT/'loads'/model.replace(':','-');d.mkdir(parents=True)
                save(d/'started.json',{'utc':now()})
                response=await mc.post(B.OLLAMA+'/api/generate',json={'model':model,'prompt':'','keep_alive':'30m','options':{'num_ctx':4096}})
                response.raise_for_status();save(d/'terminal.json',response.json())
                units=BASE_PLAN['development_units'] if args.phase=='development' else BASE_PLAN['units']
                if args.dev_limit:units=units[:args.dev_limit]
                for i,u in enumerate(units):
                    arms=['none'] if args.phase=='none' else ['unmatched','gdm_live','concurrent','shadow']
                    if args.phase=='development':arms=args.dev_arms.split(',')
                    if args.phase=='cover':arms=arms[i%4:]+arms[:i%4]
                    for arm in arms:
                        assert capture[0].poll() is None,'capture stopped'
                        await episode(u,model,arm,mc)
        failed=False
    except BaseException as e:
        save(OUT/'interrupted.json',{'utc':now(),'type':type(e).__name__,'message':str(e)[:500]});raise
    finally:
        for r in relays:r.close();await r.wait_closed()
        stop.set();await asyncio.gather(*servers,return_exceptions=True);await asyncio.sleep(.2)
        if capture:
            p,err=capture;method='CTRL_BREAK'
            try:p.send_signal(signal.CTRL_BREAK_EVENT);await asyncio.to_thread(p.wait,10)
            except (OSError,subprocess.TimeoutExpired):
                method='terminate_after_connections_closed';p.terminate();await asyncio.to_thread(p.wait,10)
            err.close();save(OUT/'capture/stopped.json',{'utc':now(),'returncode':p.returncode,'method':method})
        if not failed:
            save(OUT/'finished.json',{'utc':now(),'episodes':len(list((OUT/'episodes').glob('*/result.json')))})
            lock.unlink()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['development','none','cover'],required=True)
    ap.add_argument('--run',required=True);ap.add_argument('--dev-limit',type=int,default=0)
    ap.add_argument('--dev-arms',default='none');args=ap.parse_args()
    assert args.phase=='development' or not args.dev_limit
    logging.basicConfig(level=logging.ERROR);asyncio.run(main(args))
