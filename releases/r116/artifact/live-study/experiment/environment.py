"""PR business semantics with a real LLM controller and six execution policies."""
import copy, importlib.util
from common import H, canonical
from cover_env import ACTIONS, CHECKS, ACTION_SERVICE, READ_ENDPOINT, apply_action, reference_final_state

# Reuse the already inspected natural-language workload; no new source search.
spec=importlib.util.spec_from_file_location('r98_workload',H/'inputs/workload.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
PHRASES={a:old.PHRASES[b] for a,b in zip(ACTIONS,['refund','address','escalate','reship','cancel','receipt'])}
SERVICES=['helpdesk','crm','policy','orders','payments','billing','shipping']
SYSTEM=('You are a customer-support planner. Choose one tool action at a time. '
 'Follow the customer request and target order in the ticket. Finish every required check before a business action. '
 'Actions: refund reimburses payment; address_update changes the shipping address; escalation routes a complaint to a specialist; '
 'replacement sends a replacement; cancellation stops a pending order; receipt sends an invoice. '
 'Choose finish when the request has been completed or cannot be completed. Do not repeat successful writes. '
 'The gateway may perform background cover work. If its responses are shown, they are explicitly labeled gateway_cover; '
 'they are context, not new customer requests or evidence that your requested action succeeded. '
 'Return JSON with action and order_id, without explanation.')

def ticket(t):
    return {'customer_request':PHRASES[t['action']][t['phrase']], 'target_order':t['target'],
            'required_checks':t['checks'],'orders':copy.deepcopy(t['fixture']['orders'])}

def make_state(t,arm):
    return {'unit':t,'arm':arm,'business':copy.deepcopy(t['fixture']),
            'shadow':copy.deepcopy(t['fixture']),'checked':set(),'opened':False,
            'attempts':0,'honest_calls':0,'executed_decoys':set(),'calls':[]}

def destination(action):
    if action=='get_ticket':return 'helpdesk'
    if action in CHECKS:return CHECKS[action]
    if action in ACTION_SERVICE:return ACTION_SERVICE[action]
    return next(s for s,a in READ_ENDPOINT.items() if a==action)

def admissible(st):
    remaining=[x for x in st['unit']['checks'] if x not in st['checked']]
    if remaining:return remaining
    return ACTIONS+(['finish'] if st['attempts'] else [])

def dispatch(st,action,order_id,kind):
    before=canonical(st['business']);shadow_before=canonical(st['shadow']);ok=True
    if kind=='honest':
        if action=='get_ticket':st['opened']=True;result=ticket(st['unit'])
        elif action in CHECKS:
            st['checked'].add(action);result={'checked':action,'ok':True}
        elif action in ACTIONS:
            st['attempts']+=1
            missing=[x for x in st['unit']['checks'] if x not in st['checked']]
            if missing:ok=False;result={'error':'missing_prerequisites','missing':missing}
            else:ok,result=apply_action(st['business'],action,order_id)
            result={'action':action,'order_id':order_id,'ok':ok,**result}
        else:raise ValueError(action)
    elif kind=='cover':
        arm=st['arm']
        if arm=='transport_drop':
            # No real business call. Response shape follows the submitted PR model.
            _,result=apply_action(copy.deepcopy(st['unit']['fixture']),action,order_id)
        elif arm=='read':
            result={'lookup':action,'order_id':order_id,'ok':True}
        elif arm in ['isolated','isolated_visible']:
            ok,result=apply_action(st['shadow'],action,order_id)
        elif arm=='live_write':ok,result=apply_action(st['business'],action,order_id)
        else:raise ValueError(arm)
        result={'action':action,'order_id':order_id,'ok':ok,**result}
    else:raise ValueError(kind)
    receipt={'kind':kind,'action':action,'order_id':order_id,'ok':ok,'result':result,
             'state_before':before,'state_after':canonical(st['business']),
             'shadow_before':shadow_before,'shadow_after':canonical(st['shadow'])}
    st['calls'].append(receipt)
    return result,receipt

def outcomes(st):
    t=st['unit'];s=st['business'];ref=reference_final_state(t);target=t['target'];a=t['action']
    checked=set(t['checks']) <= st['checked']
    intended_ok=any(r['kind']=='honest' and r['action']==a and r['order_id']==target and r['ok'] for r in st['calls'])
    goal=checked and intended_ok and s['orders'][target]==ref['orders'][target]
    if a=='address_update':goal=goal and s['customer']['address']=='new' and all(v['address']=='new' for v in s['orders'].values() if v['status']=='pending')
    elif a=='escalation':goal=goal and s['customer']['escalated']
    elif a=='replacement':goal=goal and any(x[0]=='replacement' and x[1]==target and x[2]=='home' for x in s['ledger'])
    return {'goal_success':bool(goal),'state_integrity':canonical(s)==canonical(ref),
            'intended_action_succeeded':intended_ok,'checks_satisfied':checked,
            'reference_state':canonical(ref),'state_after':canonical(s)}
