"""Sequential foreground queue with journaled starts, logs and no automatic retry."""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from common_local import now, save

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--record-only-dir',type=Path,required=True);ap.add_argument('--published',type=Path,required=True);a=ap.parse_args()
    with (a.out/'queue.lock').open('x',encoding='utf-8') as f:f.write(json.dumps({'pid':os.getpid(),'utc':now()}))
    here=Path(__file__).resolve().parent
    env=dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE']='1'
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[k]='2'
    common=['--live-dir',str(a.live_dir.resolve()),'--out',str(a.out.resolve())]
    tasks=[('p0t','p0_terminal_coverage.py',[]),('p0b','p0b_shadow_roles.py',[]),('p0a','p0a_feature_ablation.py',['--published',str(a.published.resolve())]),('p0c','p0c_record_only_strong.py',['--record-only-dir',str(a.record_only_dir.resolve())])]
    state={'status':'RUNNING','started_utc':now(),'completed':[],'experiments':'P0 only; no model calls or collection'}
    for name,script,extra in tasks:
        cmd=[sys.executable,'-X','utf8',str(here/script),*common,*extra]
        state.update(current=name,current_started_utc=now(),command=cmd);save(a.out/'state.json',state)
        print('START',name,now(),flush=True);t=time.monotonic()
        with (a.out/(name+'.stdout.log')).open('xb') as out,(a.out/(name+'.stderr.log')).open('xb') as err:
            proc=subprocess.run(cmd,cwd=here,env=env,stdout=out,stderr=err)
        row={'module':name,'exit_code':proc.returncode,'wall_seconds':time.monotonic()-t,'finished_utc':now()}
        state['completed'].append(row);save(a.out/'state.json',state)
        print('END',name,row['exit_code'],round(row['wall_seconds'],1),'s',flush=True)
        if proc.returncode:
            state.update(status='STOPPED_ON_FAILURE',finished_utc=now());save(a.out/'state.json',state)
            sys.exit(proc.returncode)
    state.update(status='P0_EXECUTED_PENDING_SEPARATE_VERIFICATION',current=None,finished_utc=now());save(a.out/'state.json',state)
if __name__=='__main__':main()
