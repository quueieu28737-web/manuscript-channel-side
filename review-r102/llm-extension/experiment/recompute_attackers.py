"""Refit the fixed LR/RF suite from exported features; make no network calls."""
import os
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import csv,json,sys
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
f=np.load(root/'analysis/features.npz',allow_pickle=False)
selection=json.loads((root/'analysis/validation-selection.json').read_text())
saved=list(csv.DictReader((root/'analysis/predictions.csv').open(newline='',encoding='utf-8')))
report=[]
for model in sorted(set(f['model'])):
    estimators={};chosen={}
    for arm in sorted(set(f['arm'])):
        train=(f['model']==model)&(f['arm']==arm)&(f['split']=='train')
        val=(f['model']==model)&(f['arm']==arm)&(f['split']=='validation')
        scores={}
        for name,est in [('LR',make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=3000,random_state=102))),
                         ('RF',RandomForestClassifier(n_estimators=300,random_state=102,n_jobs=2))]:
            est.fit(f['X'][train],f['y'][train]);prediction=est.predict(f['X'][val])
            scores[name]=float(np.mean(prediction==f['y'][val]));estimators[arm,name]=est
        chosen[arm]='LR' if scores['LR']>=scores['RF'] else 'RF'
        old=next(r for r in selection if r['model']==model and r['arm']==arm)
        assert old['selected']==chosen[arm] and all(abs(old['validation_BA'][n]-scores[n])<1e-12 for n in scores)
    for arm in sorted(set(f['arm'])):
        mask=(f['model']==model)&(f['arm']==arm)&(f['split']=='test')
        ids=f['task'][mask];X=f['X'][mask]
        preds={n:estimators[arm,n].predict(X) for n in ['LR','RF']}
        preds['selected']=preds[chosen[arm]];preds['frozen']=estimators['none',chosen['none']].predict(X)
        for name,v in preds.items():
            old={int(r['task_id']):int(r[name]) for r in saved if r['model']==model and r['arm']==arm}
            assert all(old[int(i)]==int(p) for i,p in zip(ids,v)),(model,arm,name)
        report.append({'model':str(model),'arm':str(arm),'test_rows':len(ids),'selected':chosen[arm]})
print(json.dumps({'status':'PASS','scope':'All LR/RF fits, validation selection and frozen/adapted held-out predictions recomputed from the public feature arrays. No inference requests.','cells':report}))
