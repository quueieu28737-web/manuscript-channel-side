"""Exploratory public-protocol eventization after the idle-gap results.

Fixed padding quanta and two MCP setup requests per connection are public
implementation knowledge. No true call endpoints, operations or roles are read.
"""
import collections, json, sys
from pathlib import Path
import numpy as np
from sklearn.metrics import accuracy_score
import no_call_windows as A

H=Path(__file__).resolve().parents[1]


def events(records):
    out=[]
    for service in range(7):
        rr=[r for r in records if r[1]==service]
        triggers=[i for i,r in enumerate(rr) if r[2]==0 and r[3]>=4096]
        assert len(triggers)>=2,'Missing public MCP setup requests; preserve for investigation.'
        # First initialize/initialized transactions are protocol setup, not roles.
        for k,i in enumerate(triggers[2:],start=2):
            end=triggers[k+1] if k+1<len(triggers) else len(rr)
            segment=rr[i:end]
            down=[r for r in segment if r[2]==1 and r[3]>=4096]
            stop=down[-1][0] if down else rr[i][0]
            out.append([rr[i][0],stop,service,
                        sum(r[3] for r in segment if r[2]==0 and r[3]>=4096),
                        sum(r[3] for r in down),sum(r[3]>=4096 for r in segment)])
    return sorted(out,key=lambda z:(z[0],z[2]))


def main():
    frozen=A.load(H/'experiment/protocol-freeze.json')
    assert frozen['files']['experiment/protocol_record_events.py']==A.sha(__file__)
    assert not (H/'analysis/protocol-event-results.json').exists()
    rows=[json.loads(s) for s in (H/'inputs/record-only.jsonl').read_text().splitlines()]
    results=[];choices=[];predictions=[]
    for model in A.MODELS:
        data={a:{s:sorted([r for r in rows if r['model']==model and r['arm']==a and r['split']==s],key=lambda z:z['unit'])
                 for s in ['train','validation','test']} for a in A.ARMS}
        obs={a:{s:[events(r['records']) for r in data[a][s]] for s in data[a]} for a in A.ARMS}
        yy={s:np.array([r['label'] for r in data['none'][s]]) for s in data['none']}
        clean={}
        for timing in [False,True]:
            for kind in ['LR','RF']:
                e=A.make_estimator(kind);e.fit(np.stack([A.vector(z,timing) for z in obs['none']['train']]),yy['train'])
                clean[timing,kind]=e
        for arm in A.ARMS:
            z=obs[arm];threshold=A.fit_gmm(z['train']);models={};val={};testx={}
            for timing in [False,True]:
                X={s:np.stack([A.vector(v,timing) for v in z[s]]) for s in z}
                SX={s:np.stack([A.vector(A.strip(v,threshold),timing) for v in z[s]]) for s in ['validation','test']}
                for kind in ['LR','RF']:
                    name=f'protocol_{"time" if timing else "size"}_{kind}'
                    e=A.make_estimator(kind);e.fit(X['train'],yy['train']);models[name]=e
                    val[name]=e.predict(X['validation']);testx[name]=X['test']
                    name=f'protocol_strip_{"time" if timing else "size"}_{kind}';e=clean[timing,kind];models[name]=e
                    val[name]=e.predict(SX['validation']);testx[name]=SX['test']
            names=list(val);scores={n:int(sum(v==yy['validation'])) for n,v in val.items()}
            baseline=max([n for n in names if 'strip' not in n],key=lambda n:(scores[n],-names.index(n)))
            removal=max([n for n in names if 'strip' in n],key=lambda n:(scores[n],-names.index(n)))
            choice={'model':model,'arm':arm,'baseline':baseline,'removal':removal,'validation_correct':scores,'gmm_threshold_s':threshold}
            A.save(H/f'analysis/protocol-selection-{model.replace(":","-")}-{arm}.json',choice);choices.append(choice)
            pp={n:models[n].predict(testx[n]) for n in names}
            for n,v in pp.items():
                results.append({'model':model,'arm':arm,'attack':n,'n':120,'correct':int(sum(v==yy['test']))})
                for unit,p,t in zip(data[arm]['test'],v,yy['test']):predictions.append({'model':model,'arm':arm,'unit':unit['unit'],'attack':n,'prediction':int(p),'truth':int(t)})
            print(model,arm,'protocol baseline/removal/max',sum(pp[baseline]==yy['test']),sum(pp[removal]==yy['test']),max(sum(v==yy['test']) for v in pp.values()),flush=True)
    A.save(H/'analysis/protocol-event-results.json',{'scope':'Exploratory public-protocol eventizer; episode association retained; declared after Qwen idle-gap test counts were known.',
                                                  'attacks':results,'selections':choices,'primary_p_values':None})
    A.csvout(H/'analysis/protocol-event-predictions.csv',predictions)


if __name__=='__main__':main()
