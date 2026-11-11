"""Independent saved-request, state, wire and Npcap TCP/TLS reconstruction audit."""
import argparse, collections, csv, json, math, subprocess, sys
from pathlib import Path
from common import H,load,save,sha,now,canonical
from environment import make_state,dispatch,outcomes,destination
import numpy as np

def capture_records(raw):
    dst=raw/'capture/tcp-fields.tsv'
    if not dst.exists():
        with dst.open('wb') as f:
            subprocess.run([r'C:\Program Files\Wireshark\tshark.exe','-n','-r',str(raw/'capture/traffic.pcapng'),
              '-o','tcp.relative_sequence_numbers:FALSE','-T','fields','-e','frame.time_epoch','-e','tcp.srcport',
              '-e','tcp.dstport','-e','tcp.seq_raw','-e','tcp.payload'],stdout=f,stderr=(raw/'capture/tshark.stderr.log').open('wb'),check=True)
    streams={}
    for line in dst.open(encoding='utf-8'):
        cols=line.rstrip('\n').split('\t')
        if len(cols)<5 or not cols[4]:continue
        epoch,src,dstp,seq,payload=cols[:5]
        key=(int(src),int(dstp));seq=int(seq);b=bytes.fromhex(payload.replace(':',''));t=float(epoch)
        if key not in streams:streams[key]={'expected':seq,'pending':{},'buf':bytearray(),'times':[],'records':[]}
        s=streams[key];end=seq+len(b)
        if end<=s['expected']:continue
        if seq<s['expected']:b=b[s['expected']-seq:];seq=s['expected']
        s['pending'][seq]=(b,t)
        while s['expected'] in s['pending']:
            b,t=s['pending'].pop(s['expected']);s['expected']+=len(b);s['buf'].extend(b);s['times'].extend([t]*len(b))
            while len(s['buf'])>=5:
                size=5+int.from_bytes(s['buf'][3:5],'big');assert size<=18437
                if len(s['buf'])<size:break
                s['records'].append([s['buf'][0],size,max(s['times'][:size])])
                del s['buf'][:size];del s['times'][:size]
    return streams

def verify(run,development=False):
    raw=H/'private-run'/run;assert (raw/'finished.json').exists()
    results=[load(p) for p in sorted((raw/'episodes').glob('*/result.json'))]
    checks=0;unknown=list(raw.rglob('unknown.json'));assert not unknown,unknown
    phase=load(raw/'started.json')['phase']
    expected=None if development else (600 if phase=='none' else 2400)
    assert expected is None or len(results)==expected
    seen=set();counts=collections.Counter();overlaps=0;windows=0;all_wires=set();errors=[]
    streams=capture_records(raw)
    for r in results:
        key=(r['model'],r['arm'],r['task_id']);assert key not in seen;seen.add(key);counts[r['model'],r['arm'],r['split']]+=1
        d=raw/'episodes'/r['job_id'];job=load(d/'job.json');unit=job['unit']
        all_wires.update(load(p)['id'] for p in (d/'connections').glob('*.json'))
        states={r['job_id']:make_state(unit,'isolated')}
        if r['arm']=='shadow':states[r['job_id']+'-shadow']=make_state(load(d/'shadow-unit.json')['unit'],'isolated')
        server_receipts=sorted((d/'tools').glob('*/server-receipt.json'),key=lambda p:load(p)['utc'])
        for p in server_receipts:
            req=load(p.parent/'request.json');t=load(p.parent/'terminal.json');sr=load(p)
            st=states[req['job_id']]
            actual,expected_receipt=dispatch(st,req['operation'],req['order_id'],req['kind'])
            for name in ['kind','action','order_id','ok','result','state_before','state_after','shadow_before','shadow_after']:
                assert canonical(sr[name])==canonical(expected_receipt[name]),(key,p,name)
            assert canonical(actual)==canonical(t['result']);checks+=10
            w=load(raw/'wire'/f'{t["wire_id"]}.json');all_wires.add(w['id'])
            slices=[w['records'][i][t['before']['records'][i]:t['after']['records'][i]] for i in range(2)]
            assert t['record_start_ns']==next(x[2] for x in slices[0] if x[0]==23)
            assert t['record_end_ns']==[x[2] for x in slices[1] if x[0]==23][-1]
            assert [sum(x[1] for x in v) for v in slices]==t['cipher_bytes']
            checks+=3;windows+=1
        assert len(server_receipts)==len(r['wire_trace'])==len(list((d/'tools').glob('*/request.json')))
        for role,j in [('primary',r['job_id']),('shadow',r['job_id']+'-shadow')]:
            if role=='shadow' and r['shadow'] is None:continue
            got=outcomes(states[j]);primary=r[role]
            for k,v in got.items():assert canonical(v)==canonical(primary[k]),(key,k)
            mdir=d/'chains'/('real' if role=='primary' else 'shadow')/'model'
            for p in mdir.glob('*/request.json'):
                assert (p.parent/'terminal.json').exists(),p
                z=load(p);assert z['options']['temperature']==0 and z['options']['num_predict']==96
                assert z['model']==r['model'];checks+=3
        for p in r['protocol']:
            if 'tls' in p:assert p['tls']=='TLSv1.3' and p['alpn']=='h2' and p['http']=='HTTP/2'
        tr=r['wire_trace']
        by_wire=collections.defaultdict(list)
        for c in tr:
            t=load(d/c['folder']/'terminal.json');by_wire[t['wire_id']].append(t)
        for ts in by_wire.values():
            ts.sort(key=lambda t:t['record_start_ns'])
            assert all(a['after']['records'][i]<=b['before']['records'][i] for a,b in zip(ts,ts[1:]) for i in range(2))
        overlaps+=sum(a['end_ns']>b['start_ns'] for a,b in zip(tr,tr[1:]))
    for wid in all_wires:
        w=load(raw/'wire'/f'{wid}.json');assert w['closed'] and not any(w['trailing_bytes'])
        idx=['helpdesk','crm','policy','orders','payments','billing','shipping'].index(w['service'])
        keys=[(int(w['peer'][1]),41120+idx),(41220+idx,w['backend_client_port'])]
        for i,k in enumerate(keys):
            cap=streams[k]['records'];recs=w['records'][i]
            assert [(x[0],x[1]) for x in cap]==[(x[0],x[1]) for x in recs],(wid,i,len(cap),len(recs))
            errors.extend((x[3]/1e9-c[2])*1000 for x,c in zip(recs,cap));checks+=len(recs)
    out={'status':'PASS','utc':now(),'run':run,'phase':phase,'episodes':len(results),'unknown':0,
         'checks':checks,'call_windows':windows,'cross_connection_overlaps':overlaps,'wire_connections':len(all_wires),
         'counts':{'/'.join(k):v for k,v in counts.items()},
         'capture_sha256':sha(raw/'capture/traffic.pcapng'),
         'timing_error_ms':{'n':len(errors),'signed_median':float(np.median(errors)),
             'absolute_median':float(np.median(np.abs(errors))),'absolute_p99':float(np.quantile(np.abs(errors),.99)),
             'absolute_max':float(np.max(np.abs(errors)))},
         'record_match':'All reconstructed ingress TCP/TLS types, lengths and counts equal relay records.'}
    p=H/'verification'/f'{run}-verified.json'
    if p.exists():p=H/'verification'/f'{run}-full-connections-verified.json'
    assert not p.exists();save(p,out);print(json.dumps(out))

if __name__=='__main__':verify(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='development')
