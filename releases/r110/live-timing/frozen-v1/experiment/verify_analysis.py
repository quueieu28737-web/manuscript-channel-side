"""Independent CSV arithmetic and paired-null reconstruction, not attack retraining."""
import collections,csv,json,math,sys
from common import H,load,save,sha,now
from scipy.stats import binomtest
import numpy as np

def main():
    root=H/'analysis';r=load(root/'results.json');sel=load(root/'validation-selection.json')
    rows=list(csv.DictReader((root/'predictions.csv').open(encoding='utf-8')))
    data=collections.defaultdict(dict)
    for v in rows:
        key=(v['model'],v['arm'],v['attack']);i=int(v['task_id']);assert i not in data[key]
        data[key][i]=(int(v['prediction']),int(v['truth']))
    checks=0
    for cell in r['attacks']:
        a=data[cell['model'],cell['arm'],cell['attack']];assert len(a)==cell['n']==120
        assert sum(p==y for p,y in a.values())==cell['correct'];checks+=2
    chosen={(s['model'],s['arm']):s for s in sel}
    def correct(model,arm,attack):
        d=data[model,arm,attack];return np.array([d[i][0]==d[i][1] for i in sorted(d)])
    for family,items in r['families'].items():
        adjusted=[]
        for c in items:
            m,a=c['model'],c['arm'];s=chosen[m,a]
            if family in ['P','E']:
                x=correct(m,a,s['adaptive_selected']);y=correct(m,a,s['size_selected'])
            elif family=='R':x=correct(m,a,'label_free_gmm_strip');y=correct(m,a,s['size_selected'])
            else:x=correct(m,a,s['size_selected']);y=correct(m,'none',chosen[m,'none']['size_selected'])
            plus=int(sum(x&~y));minus=int(sum(y&~x))
            assert plus==c['condition_only'] and minus==c['reference_only']
            assert abs(c['difference_pp']-100*(plus-minus)/120)<1e-10;checks+=3
            if family!='E':
                p=binomtest(plus,plus+minus,.5).pvalue if plus+minus else 1.
                assert abs(p-c['p_raw'])<1e-12;checks+=1
            else:
                from scipy.stats import t as student_t
                d=x.astype(float)-y.astype(float);se=float(d.std(ddof=1)/math.sqrt(len(d)))
                p=(.9**120 if not d.any() else 1.) if se==0 else max(student_t.sf((d.mean()+.1)/se,119),student_t.cdf((d.mean()-.1)/se,119))
                assert abs(p-c['p_raw'])<1e-12;checks+=1
            adjusted.append(c)
        running=0.
        for rank,c in enumerate(sorted(adjusted,key=lambda c:c['p_raw'])):
            running=max(running,min(1.,c['p_raw']*(len(adjusted)-rank)))
            assert abs(running-c['p_holm'])<1e-12;checks+=1
    costs=list(csv.DictReader((root/'costs.csv').open(encoding='utf-8')));assert len(costs)==1200
    assert len({(v['model'],v['arm'],v['task_id']) for v in costs})==1200
    save(H/'verification/analysis-verified.json',{'status':'PASS','utc':now(),'checks':checks,
        'limits':'Independent saved CSV arithmetic and raw-paired-vector TOST reconstruction; not independent human coding or attack implementation.',
        'inputs':{p.name:sha(p) for p in [root/'results.json',root/'predictions.csv',root/'costs.csv',root/'validation-selection.json']}})
    print(json.dumps({'status':'PASS','checks':checks}))

if __name__=='__main__':main()
