"""Reuse completed none audits; test corrected timers and stop for Git gate."""
import json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from common import H,load,save,sha,now

def main():
    stage=H/'private-run/stage-advance-v3';stage.mkdir(exist_ok=False)
    save(stage/'started.json',{'pid':os.getpid(),'utc':now()})
    def run(file,args,name):
        with (stage/(name+'.stdout.log')).open('xb') as out,(stage/(name+'.stderr.log')).open('xb') as err:
            t=time.time();p=subprocess.run([sys.executable,str(H/file),*args],stdout=out,stderr=err,cwd=H.parent.parent)
        save(stage/(name+'.exit.json'),{'returncode':p.returncode,'start':t,'end':time.time(),'utc':now()})
        if p.returncode:raise RuntimeError('Preserved failed stage, no retry: '+name)
    try:
        a=load(H/'verification/formal-none-v1-verified.json');b=load(H/'verification/formal-none-v1-protocol-audit.json')
        assert a['status']==b['status']=='PASS' and a['episodes']==b['episodes']==600
        assert a['capture_sha256']==sha(H/'private-run/formal-none-v1/capture/traffic.pcapng')
        assert not (H/'private-run/collector.lock').exists()
        run('experiment/collect_cover_v3.py',['--phase','development','--run','development-cover-v3','--dev-limit','1','--dev-arms','gdm_live,concurrent'],'development-cover-v3')
        run('verification/verify_collection_v2.py',['development-cover-v3','development'],'verify-development-cover-v3')
        run('verification/check_dispatcher_v3.py',[],'check-deadlines-and-dispatch')
        run('experiment/manage.py',['pools','formal-none-v1'],'extract-training-pools')
        files=['experiment/collect_cover_v3.py','verification/prepare_cover_v3.py','verification/cover-amendment-v2.json',
               'verification/cover-amendment-v3.json','verification/check_dispatcher_v3.py','verification/cover-v3-readiness.json',
               'pools/timing-pools.json','verification/formal-none-v1-verified.json','verification/formal-none-v1-protocol-audit.json',
               'verification/verify_collection_v2.py','verification/capture_tcp_generation.py','verification/capture-auditor-amendment.json',
               'verification/test_tcp_generations.py','verification/tcp-generation-parser-readiness.json',
               'verification/none-capture-audit-failure-investigation.json','verification/audit_protocol.py']
        dst=H/'experiment/cover-freeze-v3.json';assert not dst.exists()
        save(dst,{'utc':now(),'status':'FROZEN_AFTER_NONE_BEFORE_ANY_FORMAL_COVER',
            'parent_freeze_sha256':sha(H/'experiment/freeze.json'),'files':{p:sha(H/p) for p in files},
            'unchanged':'Original none data, original freeze and all attack/statistical definitions; engineering timing and TCP-audit corrections are separately versioned.'})
        save(H/'task-state.json',{'stage':'pools_and_cover_v3_ready_for_git','utc':now(),
            'next':'Push/read back cover-freeze-v3 and all bound files, save cover-freeze-v3-pushed.json and pools-pushed.json; launch collect_cover_v3.py --phase cover --run formal-cover-v1 once.',
            'pools_sha256':sha(H/'pools/timing-pools.json'),'cover_freeze_sha256':sha(dst)})
        save(stage/'finished.json',{'utc':now(),'status':'READY_FOR_GIT_NOT_STARTED_FORMAL_COVER'});print('READY_FOR_GIT',flush=True)
    except BaseException as e:
        save(stage/'interrupted.json',{'utc':now(),'type':type(e).__name__,'message':str(e)});raise

if __name__=='__main__':main()
