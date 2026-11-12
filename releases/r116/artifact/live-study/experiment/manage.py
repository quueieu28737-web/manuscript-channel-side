"""Preflight, immutable freeze and TRAIN-only historical timing pools."""
import argparse, collections, importlib.metadata, json, os, subprocess, sys, time
from pathlib import Path
from common import H,load,save,sha,now

def weights():
    ref=load(H/'verification/weights-reference.json');root=Path(os.environ['USERPROFILE'])/'.ollama/models'
    out={'utc':now(),'models':[]}
    for m in ref['models']:
        name,tag=m['model'].split(':');manifest=root/'manifests/registry.ollama.ai/library'/name/tag
        assert sha(manifest)==m['manifest_sha256'],m['model']
        checked=[]
        for layer in m['layers']:
            p=root/'blobs'/('sha256-'+layer['sha256'])
            assert p.stat().st_size==layer['bytes'] and sha(p)==layer['sha256'],layer
            checked.append(layer)
        out['models'].append({'model':m['model'],'manifest_sha256':sha(manifest),'layers':checked})
    out['status']='PASS'
    path=H/'verification'/sys.argv[2];assert not path.exists();save(path,out)
    print(json.dumps({'status':'PASS','path':str(path),'models':[m['model'] for m in out['models']]}))

def freeze():
    path=H/'experiment/freeze.json';assert not path.exists()
    files={}
    for folder in ['experiment','inputs','vendor']:
        for p in (H/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:files[p.relative_to(H).as_posix()]=sha(p)
    for p in [H/'verification/weights-before.json',H/'verification/weights-reference.json',H/'verification/readiness.json',H/'verification/design-power.json',H/'requirements.txt',H/'README.md']:
        files[p.relative_to(H).as_posix()]=sha(p)
    save(path,{'utc':now(),'status':'FROZEN_BEFORE_FORMAL_COLLECTION','source_proposal':'74e2e8294b10dc2c0ba208924cd8abb58a9cf7ec',
               'files':files,'dependencies':{n:importlib.metadata.version(n) for n in ['numpy','scipy','scikit-learn','httpx','mcp','langgraph','h2','hypercorn']}})
    print(json.dumps({'freeze_sha256':sha(path),'files':len(files)}))

def pools(run,dev=False):
    raw=H/'private-run'/run;assert (raw/'finished.json').exists()
    records=[load(p) for p in sorted((raw/'episodes').glob('*/result.json'))]
    if not dev:
        receipt=load(H/'verification'/f'{run}-verified.json');assert receipt['status']=='PASS'
        assert len(records)==600
    result={'version':'L-live-timing-pools-v1','utc':now(),'source_run':run,'source_split':'development' if dev else 'train','models':{},'inputs':{}}
    for model in ['qwen3:8b','llama3.1:8b']:
        selected=[r for r in records if r['model']==model and r['arm']=='none' and (dev or r['split']=='train')]
        assert len(selected)==(len(records)//2 if dev else 120)
        gaps=[];durations=collections.defaultdict(list);all_durations=[]
        for r in selected:
            tr=r['wire_trace']
            for i,c in enumerate(tr):
                assert c['kind']=='honest' and c['role']=='real'
                d=(c['end_ns']-c['start_ns'])/1e9;durations[c['service']].append(d);all_durations.append(d)
                if i:gaps.append(max(0.,(c['start_ns']-tr[i-1]['end_ns'])/1e9))
            p=raw/'episodes'/r['job_id']/'result.json';result['inputs'][p.relative_to(H).as_posix()]=sha(p)
        assert gaps and all_durations
        result['models'][model]={'episodes':len(selected),'gap_seconds':gaps,
                                 'duration_seconds':dict(durations),'all_duration_seconds':all_durations}
    dst=H/'private-run/development-pools.json' if dev else H/'pools/timing-pools.json'
    assert not dst.exists();save(dst,result);print(json.dumps({'path':str(dst),'sha256':sha(dst)}))

if __name__=='__main__':
    if sys.argv[1]=='weights':weights()
    elif sys.argv[1]=='freeze':freeze()
    elif sys.argv[1]=='pools':pools(sys.argv[2],len(sys.argv)>3 and sys.argv[3]=='development')
    else:raise ValueError(sys.argv[1])
