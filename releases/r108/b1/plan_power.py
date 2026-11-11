"""Paired binary TOST planning sensitivity, not observed-effect power."""
from pathlib import Path
import json,math,datetime
import numpy as np
from scipy.stats import norm,t

H=Path(__file__).resolve().parent
rng=np.random.default_rng(1072026)
rows=[]
R=100000
for q in [.05,.10,.20,.30]:
    for delta in [0.,.04,.08]:
        if abs(delta)>q:continue
        for n in [120,240,402,504,612,1002]:
            # D=+1,-1,0. q is discordance probability, E[D]=delta.
            counts=rng.multinomial(n,[(q+delta)/2,(q-delta)/2,1-q],size=R)
            means=(counts[:,0]-counts[:,1])/n
            variance=(counts[:,0]+counts[:,1]-n*means**2)/(n-1)
            se=np.sqrt(variance/n)
            for alpha in [.05,.025]:
                half=t.ppf(1-alpha,n-1)*se
                equivalent=(means-half>-.08)&(means+half<.08)
                rows.append({'discordance_probability':q,'true_difference':delta,'paired_test_fixtures':n,
                             'one_sided_alpha':alpha,'replicates':R,'probability_tost_rejects_both_nulls':float(equivalent.mean()),
                             'mc_se':float(np.sqrt(equivalent.mean()*(1-equivalent.mean())/R))})
analytic=[]
for q in [.05,.10,.20,.30]:
    for alpha in [.05,.025]:
        analytic.append({'discordance_probability':q,'true_difference':0.,'one_sided_alpha':alpha,
                         'normal_approx_n_for_80pct_marginal_equivalence_power':math.ceil(q*(norm.ppf(1-alpha)+norm.ppf(.9))**2/.08**2)})
result={'purpose':'Planning A/B2 paired recognition equivalence only; no new collected data or test-dependent method selection.',
        'margin':.08,'distribution':'Independent paired fixtures with D in {-1,0,1}; q assumed, not estimated from held-out timing outcomes. Class/fit/workload dependence is omitted.',
        'method':'Paired t TOST via interval inclusion. .025 is a conservative per-model threshold for two-model familywise .05, not exact joint power.',
        'interpretation':'Equivalence of an attained attack accuracy within a fixed margin is not semantic equivalence or equality of information available to all attackers.',
        'seed':1072026,'analytic':analytic,'simulation':rows,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
p=H/'equivalence-power.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'q03_n80': [x for x in analytic if x['discordance_probability']==.30],
                  'q03_n120_240': [x for x in rows if x['discordance_probability']==.30 and x['true_difference']==0 and x['paired_test_fixtures'] in [120,240]]}))
