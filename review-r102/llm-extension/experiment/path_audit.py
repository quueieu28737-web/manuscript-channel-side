"""Descriptive planner-path comparisons on the same verified held-out fixtures.

No hypothesis tests or attacker selection. Reports intervention exposure and
behavior changes, including successful tasks with extra unintended writes.
"""
from collections import Counter
from common import H, load, save, now, sha

assert load(H/'verification/formal-v1-verified.json')['status']=='PASS'
raw=H/'private-run/formal-v1';data={}
for p in (raw/'episodes').glob('*/result.json'):
    r=load(p)
    if r['split']=='test':data[r['model'],r['arm'],r['task_id']]=r
plan=load(H/'experiment/cohort-plan.json');rows=[];pairs=[];trace_pairs=[]
targets={t['task_id']:t['target'] for t in plan['units']}
business={'refund','address_update','escalation','replacement','cancellation','receipt'}
def path(r):return [(c['action'],c['order_id'],c['ok']) for c in r['calls'] if c['kind']=='honest']
def choices(r):return [(c['action'],c['order_id']) for c in r['calls'] if c['kind']=='honest']
def services(r):return [x['service'] for x in r['wire_trace']]
def observed_trace(r):return [(x['service'],x['bytes']) for x in r['wire_trace']]
for model in plan['models']:
    ids=sorted(t for m,a,t in data if m==model and a=='none')
    for arm in plan['arms']:
        c=Counter();c['n']=len(ids)
        for ident in ids:
            r=data[model,arm,ident];base=data[model,'none',ident]
            honest=[x for x in r['calls'] if x['kind']=='honest' and x['action'] in business]
            c['goal_success']+=r['goal_success'];c['state_integrity']+=r['state_integrity']
            c['goal_success_with_state_error']+=r['goal_success'] and not r['state_integrity']
            c['honest_choices_differ_from_none']+=choices(r)!=choices(base)
            c['honest_response_paths_differ_from_none']+=path(r)!=path(base)
            c['multiple_business_attempts']+=len(honest)>1
            c['failed_business_attempts']+=sum(not x['ok'] for x in honest)
            c['successful_off_target_business_actions']+=sum(x['ok'] and (x['action']!=r['label'] or x['order_id']!=targets[ident]) for x in honest)
            c['planned_decoys']+=r['planned_decoys'];c['triggered_decoys']+=len(r['executed_decoys'])
            c['step_limit']+=r['status']=='step_limit';c['invalid_model_output']+=r['status']=='invalid_model_output'
        rows.append({'model':model,'arm':arm,**dict(c)})
        if arm!='isolated':
            d=Counter(n=len(ids))
            for ident in ids:
                a=data[model,arm,ident];b=data[model,'isolated',ident]
                d['same_service_sequence']+=services(a)==services(b)
                d['same_observed_destination_byte_trace']+=observed_trace(a)==observed_trace(b)
                d['same_honest_choices']+=choices(a)==choices(b)
                d['same_honest_result_path']+=path(a)==path(b)
            trace_pairs.append({'model':model,'condition':arm,'reference':'isolated',**dict(d)})
    for ident in ids:
        hidden=data[model,'isolated',ident];shown=data[model,'isolated_visible',ident]
        a=[(x['action'],x['order_id'],x['result']) for x in hidden['calls'] if x['kind']=='cover']
        b=[(x['action'],x['order_id'],x['result']) for x in shown['calls'] if x['kind']=='cover']
        pairs.append({'model':model,'task_id':ident,'same_cover_responses':a==b,
          'same_honest_choices':choices(hidden)==choices(shown),
          'same_honest_response_path':path(hidden)==path(shown),
          'hidden_goal':hidden['goal_success'],'visible_goal':shown['goal_success'],
          'hidden_integrity':hidden['state_integrity'],'visible_integrity':shown['state_integrity']})
save(H/'analysis/planner-paths.json',{'utc':now(),'kind':'Descriptive mechanism audit, no new statistical family',
    'cells':rows,'visibility_pairs':pairs,'paired_trace_comparisons':trace_pairs,
    'collection_receipt':sha(H/'verification/formal-v1-verified.json'),'audit_code_sha256':sha(__file__)})
print('Descriptive planner paths recorded for all 1440 test episodes')
