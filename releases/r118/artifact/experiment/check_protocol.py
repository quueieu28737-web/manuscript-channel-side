"""Small synthetic/metamorphic checks of changed paths, never scientific data."""
import argparse, importlib.util, sys
from pathlib import Path
import numpy as np

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live-dir',type=Path,required=True);ap.add_argument('--record-only-dir',type=Path);a=ap.parse_args()
    import p0a_feature_ablation as P
    import p0c_record_only_strong as C
    import p0_terminal_coverage as T
    A=P.import_frozen(a.live_dir)
    tr=[]
    for i,(svc,op,kind) in enumerate([('helpdesk','get_ticket','honest'),('crm','account','honest'),('shipping','replacement','cover'),('payments','refund','honest')]):
        tr.append({'service':svc,'operation':op,'kind':kind,'role':'real','start_ns':int((10+i)*1e9),'end_ns':int((10+i+.2)*1e9),'bytes':[4096+i,16384+i]})
    r={'arm':'unmatched','wire_trace':tr}
    r2={'arm':'unmatched','wire_trace':[dict(c,start_ns=c['start_ns']*7+12345,end_ns=c['end_ns']*9+55555) for c in tr]}
    obs,byte,calls=P.make_variant(A,'no_time')
    x,y=obs(r),obs(r2)
    assert np.array_equal(byte(x),byte(y))
    assert np.array_equal(calls(x,True,{'__all__':0.}),calls(y,True,{'__all__':0.}))
    obs,byte,calls=P.make_variant(A,'no_position');o=obs(r);v=calls(o,True,A.medians([o]))
    assert np.all(v[:,2]==0) and np.all(v[:,10:18]==0) and np.all(v[:,25:33]==0)
    assert np.array_equal(byte(o),byte({**o,'trace':list(reversed(o['trace']))}))
    events=[[0.,.2,0,100,200,2],[.3,.6,1,150,250,3]]
    assert C.event_features(events).shape==(2,32)
    C.PREDICTIONS_SEALED=False
    try:C.call_truth({'split':'test'},{});raise AssertionError('TEST truth firewall failed')
    except RuntimeError:pass
    b=C.boundary_audit([[0.,1.,0,1,1,1]],[[0.,.4,0,0],[.6,1.,0,1]])
    assert b['mixed_events']==1 and b['boundary_tp']==0
    assert T.strata(r)['real_action_last']==1 and T.strata(r)['covered_after']==0
    assert T.strata({'arm':'unmatched','wire_trace':tr[:2]})['covered_after'] is None
    if a.record_only_dir:
        ro,_=C.import_record_only(a.record_only_dir)
        ev={};truth={};labels={}
        for split,repeats in [('train',2),('validation',1)]:
            ev[split]=[];truth[split]=[];labels[split]=[]
            for rep in range(repeats):
                for lab in range(6):
                    z=[[0.,.1,0,100.,200.,2.],[.4,.5,lab+1,110.,210.,2.],[.51,.61,(lab+2)%7,120.,220.,2.]]
                    ev[split].append(z);truth[split].append(np.array([0,0,1]));labels[split].append(lab)
        fitted,best=C.fit_detector(ro,ev,truth)
        assert best is not None and set(fitted)=={'LR','RF'}
        clean=ro.make_estimator('LR').fit(np.stack([ro.vector(z[:2],False) for z in ev['train']]),labels['train'])
        z=ev['validation'][0];prob=C.probs(fitted,best[-1],z)
        cache=C.joint_scores(ro,clean,False,z,prob)
        assert C.joint_pred([cache],clean.classes_,'MAP',1).shape==(1,)
        assert C.joint_pred([cache],clean.classes_,'marginal',1).shape==(1,)
    print('PASS: synthetic No-time invariance, explicit-position removal, event features, TEST-truth firewall, mixed-event audit and terminal definitions. No scientific outcomes.',flush=True)
if __name__=='__main__':main()
