"""Predeclared live timing attacks, validation selection, paired tests and costs.

Only the observation whitelist enters inference. Role labels are used for
training call detectors and training chain-role selectors, never test inputs.
"""
import os
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import collections,csv,itertools,json,math,sys,time,warnings
from pathlib import Path
from common import H,load,save,sha,now
import numpy as np
from scipy.stats import binomtest
from scipy.special import gammaln
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score,precision_score,roc_auc_score
warnings.filterwarnings('ignore',category=UserWarning)
SERVICES=['helpdesk','crm','policy','orders','payments','billing','shipping']
LABELS=['refund','address_update','escalation','replacement','cancellation','receipt']
MODELS=['qwen3:8b','llama3.1:8b'];ARMS=['none','unmatched','gdm_live','concurrent','shadow']
POSITION={'payments':0,'crm':1,'helpdesk':2,'shipping':3,'orders':4,'billing':5}
SIZE=['byte_LR','byte_RF','frozen','position_last','position_penultimate']
TIMING=['timing_size','gap_detector_strip','label_free_gmm_strip','context_strip','joint_decoding','chain_separation']
SEED=1071111

def observe(r):
    tr=r['wire_trace'];s=np.array([v['start_ns']/1e9 for v in tr]);e=np.array([v['end_ns']/1e9 for v in tr])
    gap=np.r_[0.,np.maximum(0.,s[1:]-e[:-1])]
    return {'trace':[{'service':v['service'],'bytes':v['bytes']} for v in tr],
            'start':s,'end':e,'timing':np.stack([s-s[0],e-s,gap],axis=1),
            'cover':np.array([int(v['kind']=='cover' or v['role']=='shadow') for v in tr]),
            'first_known_honest':r['arm']!='shadow','wall_seconds':e.max()-s.min()}

def byte(o):
    x=np.zeros(153);tr=o['trace']
    for i,w in enumerate(tr):
        j=SERVICES.index(w['service']);x[112+j]+=1
        if i<16:x[i*7+j]=1;x[119+2*i:121+2*i]=w['bytes']
    x[-2:]=[len(tr),sum(sum(w['bytes']) for w in tr)];return x

def view(o,timing=False):
    b=byte(o)
    if not timing:return b
    t=np.zeros(49);n=min(16,len(o['trace']));t[:n*3]=o['timing'][:n].ravel();t[-1]=o['wall_seconds']
    return np.r_[b,t]

def estimators(balanced=False):
    kw={'class_weight':'balanced'} if balanced else {}
    return {'LR':make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=3000,random_state=102,**kw)),
            'RF':RandomForestClassifier(n_estimators=300,n_jobs=2,random_state=102,**kw)}

def fit_task(tr,va,ytr,yv,timing=False):
    fitted=estimators();scores={}
    for k,est in fitted.items():
        est.fit(np.stack([view(o,timing) for o in tr]),ytr)
        scores[k]=int(sum(est.predict(np.stack([view(o,timing) for o in va]))==yv))
    name=max(fitted,key=lambda n:(scores[n],n=='LR'))
    return fitted[name],fitted,{'selected':name,'validation_correct':scores}

def call_features(o,context=False,med=None):
    n=len(o['trace']);x=np.zeros((n,34 if context else 10));t=o['timing'];x[:,:2]=np.log1p(t[:,[2,1]]*1000);x[0,2]=1
    for i,w in enumerate(o['trace']):x[i,3+SERVICES.index(w['service'])]=1
    if context:
        egap=max(float(np.median(t[1:,2])) if n>1 else 1.,1e-3)
        for i,w in enumerate(o['trace']):
            x[i,10+min(i,7)]=1;x[i,18]=np.log1p(t[i,0]*1000)
            x[i,19]=np.log(max(t[i,2],1e-3)/egap) if i else 0.
            x[i,20]=np.log(max(t[i-1,2],1e-3)) if i>1 else 0.
            x[i,21]=np.log(max(t[i+1,2],1e-3)) if i+1<n else 0.
            x[i,22]=np.log(max(t[i,1],1e-3)/max(med.get(w['service'],med['__all__']),1e-3))
            x[i,23:25]=np.log1p(w['bytes'])
            if i:x[i,25+SERVICES.index(o['trace'][i-1]['service'])]=1
            x[i,32:]=[i==n-1,n]
    return x

def medians(obs):
    by=collections.defaultdict(list)
    for o in obs:
        for w,t in zip(o['trace'],o['timing']):by[w['service']].append(t[1])
    ans={k:float(np.median(v)) for k,v in by.items()};ans['__all__']=float(np.median([z for v in by.values() for z in v]));return ans

def fit_detector(tr,va,context,med):
    xt=np.concatenate([call_features(o,context,med) for o in tr]);yt=np.concatenate([o['cover'] for o in tr])
    xv=np.concatenate([call_features(o,context,med) for o in va]);yv=np.concatenate([o['cover'] for o in va])
    fitted=estimators(True);candidates=[]
    for name,est in fitted.items():
        est.fit(xt,yt);p=est.predict_proba(xv)[:,1]
        for th in np.arange(.05,.951,.05):
            pred=p>=th;k=0
            for o in va:
                if o['first_known_honest']:pred[k]=False
                k+=len(o['trace'])
            candidates.append((f1_score(yv,pred,zero_division=0),precision_score(yv,pred,zero_division=0),2 if name=='LR' else 0,float(th),name))
    if not context:
        gaps=np.concatenate([o['timing'][:,2] for o in va])
        first=np.zeros(len(gaps),bool);k=0
        for o in va:
            first[k]=o['first_known_honest'];k+=len(o['trace'])
        for th in [.025,.05,.10,.20,.35,.50,1.]:
            pred=(gaps<th)&~first
            candidates.append((f1_score(yv,pred,zero_division=0),precision_score(yv,pred,zero_division=0),1,th,'gap_rule'))
    sel=max(candidates);return fitted,{'name':sel[4],'threshold':sel[3],'validation_f1':sel[0],'context':context}

def probs(o,fitted,sel,med,name=None):
    method=name or sel['name']
    if method=='gap_rule':p=(o['timing'][:,2]<sel['threshold']).astype(float)
    else:p=fitted[method].predict_proba(call_features(o,sel['context'],med))[:,1]
    if o['first_known_honest']:p[0]=0.
    return p

def subset(o,ids):
    return {'trace':[o['trace'][i] for i in ids],'start':o['start'][ids],'end':o['end'][ids],
            'timing':o['timing'][ids],'wall_seconds':o['wall_seconds'],'first_known_honest':True}

def strip_prediction(obs,masks,clf):
    return clf.predict(np.stack([byte(subset(o,[i for i in range(len(o['trace'])) if not mask[i]])) for o,mask in zip(obs,masks)]))

def gmm_threshold(tr):
    gap=np.concatenate([o['timing'][1:,2] for o in tr]);x=np.log10(np.maximum(gap,1e-4)).reshape(-1,1)
    g=GaussianMixture(2,random_state=102,n_init=5).fit(x);lo,hi=sorted(g.means_.ravel());small=int(np.argmin(g.means_))
    for _ in range(100):
        mid=(lo+hi)/2
        if g.predict_proba([[mid]])[0,small]>.5:lo=mid
        else:hi=mid
    return float(10**((lo+hi)/2)),{'means_log10':g.means_.ravel().tolist(),'weights':g.weights_.tolist()}

def joint_cache(obs,context,sel,med,clean,prior):
    output=[]
    for o in obs:
        n=len(o['trace']);cand=list(range(1 if o['first_known_honest'] else 0,n))
        masks=[()]+[m for k in (1,2) for m in itertools.combinations(cand,k)]
        post=clean.predict_proba(np.stack([byte(subset(o,[i for i in range(n) if i not in m])) for m in masks]))
        scores={}
        for name in ['LR','RF']:
            pc=np.clip(probs(o,context,sel,med,name),1e-4,1-1e-4)
            scores[name]=np.array([math.log(prior[len(m)])+sum(math.log(pc[i] if i in m else 1-pc[i]) for i in cand) for m in masks])
        output.append((scores,post))
    return output

def joint_pred(cache,classes,spec):
    name,variant,lam=spec;pred=[]
    for scores,post in cache:
        s=scores[name]
        if variant=='MAP':p=post[np.argmax(s+lam*np.log(np.maximum(post.max(axis=1),1e-4)))]
        else:
            w=np.exp(s-s.max());w/=w.sum();p=w@post
        pred.append(classes[np.argmax(p)])
    return np.array(pred)

def chain_summary(o,ids,clean):
    z=subset(o,ids);p=clean.predict_proba(byte(z)[None])[0];s=o['start'][ids];e=o['end'][ids]
    return np.r_[len(ids),s[0]-o['start'][0],e[-1]-o['start'][0],np.log1p(sum(sum(w['bytes']) for w in z['trace'])),
                 np.mean(e-s),np.median(np.maximum(s[1:]-e[:-1],0)) if len(ids)>1 else 0.,p]

def partition(o,gap_mu,gap_sd,clean):
    # Symmetry broken only by chronological first call, not by its private role.
    beams=[([0],[],0.)]
    for i in range(1,len(o['trace'])):
        nxt=[]
        for a,b,score in beams:
            for target in [0,1]:
                c=a if target==0 else b
                if c and o['start'][i]<o['end'][c[-1]]-.002:continue
                if not c and o['trace'][i]['service']!='helpdesk':continue
                if len(c)>=11:continue
                cost=0.
                if c:
                    gap=max(1e-4,o['start'][i]-o['end'][c[-1]])
                    cost=-.5*((np.log(gap)-gap_mu)/gap_sd)**2-np.log(gap_sd)
                nxt.append((a+[i] if target==0 else a,b+[i] if target==1 else b,score+cost))
        if not nxt:break
        beams=sorted(nxt,key=lambda v:v[2],reverse=True)[:64]
    valid=[v for v in beams if v[1] and len(v[0])+len(v[1])==len(o['trace'])]
    if not valid:
        # Public deterministic fallback; no true role/chain is consulted.
        a=list(range(0,len(o['trace']),2));b=list(range(1,len(o['trace']),2)) or a
        return a,b
    return max(valid,key=lambda v:v[2]+np.log(max(clean.predict_proba(byte(subset(o,v[0]))[None])[0]))+
                                np.log(max(clean.predict_proba(byte(subset(o,v[1]))[None])[0])))[:2]

def train_chain(tr,none,clean):
    gs=np.concatenate([np.maximum(o['timing'][1:,2],1e-4) for o in none]);mu=float(np.log(gs).mean());sd=max(.2,float(np.log(gs).std()))
    x=[];y=[]
    for o in tr:
        a=np.flatnonzero(o['cover']==0).tolist();b=np.flatnonzero(o['cover']==1).tolist()
        if not a or not b:continue
        if o['start'][a[0]]<o['start'][b[0]]:first,second,role=a,b,1
        else:first,second,role=b,a,0
        x.append(chain_summary(o,first,clean)-chain_summary(o,second,clean));y.append(role)
    est=estimators(True)['LR'];est.fit(np.stack(x),y);return est,mu,sd

def chain_predict(obs,trained,clean):
    est,mu,sd=trained;pred=[];roles=[]
    for o in obs:
        a,b=partition(o,mu,sd,clean);x=chain_summary(o,a,clean)-chain_summary(o,b,clean)
        p=float(est.predict_proba(x[None])[0,list(est.classes_).index(1)])
        ids=a if p>=.5 else b;pred.append(clean.predict(byte(subset(o,ids))[None])[0])
        # Evaluation only, after partition and selection are final.
        real=np.flatnonzero(o['cover']==0).tolist();cover=np.flatnonzero(o['cover']==1).tolist()
        roles.append({'first_chain_real_probability':p,'selected_chain_purity':float(np.mean(o['cover'][ids]==0)),
                      'exact_partition':int((a==real and b==cover) or (b==real and a==cover)),
                      'exact_real_chain':int(ids==real),
                      'call_role_correct':int(sum((i in ids)==(o['cover'][i]==0) for i in range(len(o['trace'])))),
                      'calls':len(o['trace'])})
    return np.array(pred),roles

def paired_tost(plus,minus,n=120,margin=.1):
    """Paired t-TOST with df=n-1 and a conservative zero-variance fallback.

    The fixture-level differences are {-1,0,1}. Report as a finite-sample
    approximate test, alongside exact McNemar superiority and discordant counts.
    No normal approximation claims a universal all-attacker equivalence.
    """
    from scipy.stats import t as student_t
    d=(plus-minus)/n;q=(plus+minus)/n;se=math.sqrt(max(0.,q-d*d)/(n-1))
    if se==0:
        # At all ties, P(no discordance) under either boundary <=(1-margin)^n.
        return (1-margin)**n if d==0 else 1.
    return float(max(student_t.sf((d+margin)/se,n-1),student_t.cdf((d-margin)/se,n-1)))

def holm(rows):
    last=0.
    for rank,i in enumerate(sorted(range(len(rows)),key=lambda j:rows[j]['p_raw'])):
        last=max(last,min(1.,rows[i]['p_raw']*(len(rows)-rank)));rows[i]['p_holm']=last

def comparison(a,b,model,arm,family,boot,eq=None):
    d=a.astype(int)-b.astype(int);plus=int(sum(d==1));minus=int(sum(d==-1));D=plus-minus;n=len(d)
    p=float(binomtest(plus,plus+minus,.5).pvalue) if plus+minus else 1.
    if family=='E':p=paired_tost(plus,minus,n)
    return {'model':model,'arm':arm,'family':family,'condition_only':plus,'reference_only':minus,
            'difference_pp':float(100*d.mean()),'conditional_ci_pp':(100*np.quantile(d[boot].mean(axis=1),[.025,.975])).tolist(),'p_raw':p,'n':n}

def write_csv(p,rows):
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main(development=False):
    out=H/('private-run/analysis-development' if development else 'analysis');out.mkdir(exist_ok=False)
    if not development:
        for name,d in load(H/'experiment/freeze.json')['files'].items():assert sha(H/name)==d,name
        for run in ['formal-none-v1','formal-cover-v1']:assert load(H/'verification'/f'{run}-verified.json')['status']=='PASS'
    runs=['development-none-v1','development-cover-v1'] if development else ['formal-none-v1','formal-cover-v1']
    records=[load(p) for run in runs for p in (H/'private-run'/run/'episodes').glob('*/result.json')]
    data={(r['model'],r['arm'],r['task_id']):r for r in records}
    if not development:assert len(data)==3000
    eq=None;allrows=[];selections=[];predrows=[];costrows=[];chainrows=[];families={k:[] for k in ['P','E','R','C']}
    for model in MODELS:
        ids={s:sorted(r['task_id'] for r in records if r['model']==model and r['arm']=='none' and r['split']==s) for s in ['train','validation','test']}
        if development:
            dev=sorted(r['task_id'] for r in records if r['model']==model and r['arm']=='none')
            ids={'train':dev,'validation':dev,'test':dev}
        yy={s:np.array([LABELS.index(data[model,'none',i]['label']) for i in ids[s]]) for s in ids}
        obs={a:{s:[observe(data[model,a,i]) for i in ids[s]] for s in ids} for a in ARMS}
        clean,_,clean_sel=fit_task(obs['none']['train'],obs['none']['validation'],yy['train'],yy['validation'])
        med=medians(obs['none']['train']);preds={};best={};bestsize={}
        rng=np.random.default_rng(SEED)
        boot=np.concatenate([rng.choice(np.flatnonzero(yy['test']==k),(10000,sum(yy['test']==k)),replace=True) for k in range(6)],axis=1)
        for arm in ARMS:
            tr,va,te=[obs[arm][s] for s in ['train','validation','test']]
            bclf,bs,bsel=fit_task(tr,va,yy['train'],yy['validation']);tclf,_,tsel=fit_task(tr,va,yy['train'],yy['validation'],True)
            pp={s:{} for s in ['validation','test']}
            for split,oset in [('validation',va),('test',te)]:
                X=np.stack([byte(o) for o in oset]);pp[split]['byte_LR']=bs['LR'].predict(X);pp[split]['byte_RF']=bs['RF'].predict(X)
                pp[split]['frozen']=clean.predict(X)
                for name,offset in [('position_last',-1),('position_penultimate',-2)]:
                    pp[split][name]=np.array([POSITION.get(o['trace'][offset]['service'],0) if len(o['trace'])>=abs(offset) else 0 for o in oset])
                pp[split]['timing_size']=tclf.predict(np.stack([view(o,True) for o in oset]))
            selection={'model':model,'arm':arm,'byte':bsel,'timing':tsel}
            if arm!='none':
                fd,ds=fit_detector(tr,va,False,med);ctx,cs=fit_detector(tr,va,True,med);gth,ginfo=gmm_threshold(tr)
                vc=joint_cache(va,ctx,cs,med,clean,[.02,.49,.49]);tc=joint_cache(te,ctx,cs,med,clean,[.02,.49,.49])
                grid=[(name,'MAP',lam) for name in ['LR','RF'] for lam in [0,.5,1,2,4]]+[(name,'marginal',1) for name in ['LR','RF']]
                js=max(grid,key=lambda sp:(sum(joint_pred(vc,clean.classes_,sp)==yy['validation']),-grid.index(sp)))
                selection.update(detector=ds,context=cs,gmm={'threshold_s':gth,**ginfo},joint=js)
                for split,oset,cache in [('validation',va,vc),('test',te,tc)]:
                    masks=[probs(o,fd,ds,med)>=ds['threshold'] for o in oset]
                    pp[split]['gap_detector_strip']=strip_prediction(oset,masks,clean)
                    masks=[probs(o,ctx,cs,med)>=cs['threshold'] for o in oset]
                    pp[split]['context_strip']=strip_prediction(oset,masks,clean)
                    masks=[]
                    for o in oset:
                        m=o['timing'][:,2]<gth;m[0]=False;masks.append(m)
                    pp[split]['label_free_gmm_strip']=strip_prediction(oset,masks,clean)
                    pp[split]['joint_decoding']=joint_pred(cache,clean.classes_,js)
                if arm=='shadow':
                    chain=train_chain(tr,obs['none']['train'],clean)
                    for split,oset in [('validation',va),('test',te)]:
                        pp[split]['chain_separation'],role_metrics=chain_predict(oset,chain,clean)
                        if split=='test':
                            for i,v in zip(ids['test'],role_metrics):chainrows.append({'model':model,'task_id':i,**v})
            names=SIZE+[n for n in TIMING if n in pp['validation']]
            sn=max(SIZE,key=lambda n:(sum(pp['validation'][n]==yy['validation']),-SIZE.index(n)))
            an=max(names,key=lambda n:(sum(pp['validation'][n]==yy['validation']),-names.index(n)))
            selection.update(size_selected=sn,adaptive_selected=an,validation={n:int(sum(pp['validation'][n]==yy['validation'])) for n in names})
            selections.append(selection);preds[arm]=pp['test'];bestsize[arm]=pp['test'][sn]==yy['test'];best[arm]=pp['test'][an]==yy['test']
            for name,p in pp['test'].items():
                allrows.append({'model':model,'arm':arm,'attack':name,'correct':int(sum(p==yy['test'])),'n':len(p),
                                'selected_size':name==sn,'selected_adaptive':name==an,
                                'conditional_ci':np.quantile((p==yy['test'])[boot].mean(axis=1),[.025,.975]).tolist()})
                for i,v,y in zip(ids['test'],p,yy['test']):predrows.append({'model':model,'arm':arm,'task_id':i,'attack':name,'prediction':int(v),'truth':int(y)})
            for i in ids['test']:
                r=data[model,arm,i];r0=data[model,'none',i];p=r['primary'];p0=r0['primary'];shadow=r['shadow']
                usage=p['model_usage']+(shadow['model_usage'] if shadow else [])
                latency=p['end']-r.get('admitted_at',p['start']);latency0=p0['end']-r0.get('admitted_at',p0['start'])
                costrows.append({'model':model,'arm':arm,'task_id':i,'goal_success':int(p['goal_success']),
                    'state_integrity':int(p['state_integrity']),'real_latency_s':latency,
                    'added_real_latency_s':latency-latency0,
                    'transport_bytes':r['transport_total_bytes'],'byte_ratio':r['transport_total_bytes']/r0['transport_total_bytes'],
                    'tool_calls':len(r['wire_trace']),'model_calls':len(usage),'model_tokens':sum(u['prompt_eval_count']+u['eval_count'] for u in usage),
                    'honest_path_equal':int([(x['action'],x['order_id']) for x in p['calls'] if x['kind']=='honest']==
                                             [(x['action'],x['order_id']) for x in p0['calls'] if x['kind']=='honest'])})
            print(json.dumps({'model':model,'arm':arm,'size':int(sum(bestsize[arm])),'adaptive':int(sum(best[arm]))}),flush=True)
        if not development:
            for arm in ['gdm_live','concurrent','shadow']:
                for family in ['P','E']:families[family].append(comparison(best[arm],bestsize[arm],model,arm,family,boot,eq))
            families['R'].append(comparison(preds['unmatched']['label_free_gmm_strip']==yy['test'],bestsize['unmatched'],model,'unmatched','R',boot,eq))
            for arm in ARMS[1:]:families['C'].append(comparison(bestsize[arm],bestsize['none'],model,arm,'C',boot,eq))
    for rows in families.values():holm(rows)
    decisions={}
    if not development:
        for arm in ['gdm_live','concurrent','shadow']:
            ps=[v for v in families['P'] if v['arm']==arm];es=[v for v in families['E'] if v['arm']==arm]
            decisions[arm]={'timing_increment_at_least_10pp_detected':any(v['difference_pp']>=10-1e-9 and v['p_holm']<.05 for v in ps),
                            'tested_suite_increment_equivalent_within_10pp_both_models':all(v['p_holm']<.05 for v in es),
                            'caution':'Attack-suite accuracy increment only; report remaining task recognition and shadow pair ambiguity separately.'}
        decisions['unmatched_removal_replication']=all(v['difference_pp']>=20-1e-9 and v['p_holm']<.05 for v in families['R'])
    save(out/'results.json',{'utc':now(),'development':development,'attacks':allrows,'families':families,
         'decisions':decisions,
         'equivalence_method':'Paired t-TOST +/-0.1 on fixture accuracy differences, df=119; finite-sample approximation; all-tie boundary safeguard',
         'shadow_chain_diagnostics':chainrows,'shadow_baselines':{'six_class_prior':1/6,'perfect_unordered_chain_pair_prior':7/12},
         'uncertainty':'Paired action-stratified fixture bootstrap conditional on fitted attacks; same old M3 fixtures.'})
    save(out/'validation-selection.json',selections);write_csv(out/'predictions.csv',predrows);write_csv(out/'costs.csv',costrows)

if __name__=='__main__':main('--development' in sys.argv)
