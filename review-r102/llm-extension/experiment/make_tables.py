"""Render every held-out cell from the verified analysis, without selection."""
import csv
from common import H, load, save, now, sha

ARMS=['none','transport_drop','read','isolated','live_write','isolated_visible']
NAMES={'none':'No cover','transport_drop':'Proxy discard','read':'Read cover',
       'isolated':'Isolated, hidden','live_write':'Live write','isolated_visible':'Isolated, visible'}
MODELS={'qwen3:8b':'Qwen3:8B','llama3.1:8b':'Llama3.1:8B'}

def main():
    assert load(H/'verification/formal-analysis-verified.json')['status']=='PASS'
    scores={(r['model'],r['arm'],r['attack']):r for r in load(H/'analysis/recognition.json')}
    costs={(r['model'],r['arm'],r['endpoint']):r for r in csv.DictReader((H/'analysis/outcomes-costs.csv').open(newline='',encoding='utf-8'))}
    paths={(r['model'],r['arm']):r for r in load(H/'analysis/planner-paths.json')['cells']}
    rows=[]
    for model in MODELS:
        for arm in ARMS:
            s=scores[model,arm,'selected'];p=paths[model,arm]
            rows.append({'model':model,'arm':arm,'n':s['n'],'selected':s['selected_algorithm'],
              'correct':s['correct'],'balanced_accuracy':s['balanced_accuracy'],'conditional_ci':s['conditional_ci'],
              'attack_correct':{a:scores[model,arm,a]['correct'] for a in ['LR','RF','frozen','position_last','position_penultimate']},
              'goal_success':p['goal_success'],'state_integrity':p['state_integrity'],
              'goal_with_state_error':p['goal_success_with_state_error'],
              'costs':{k:float(costs[model,arm,k]['mean']) for k in ['transport_byte_ratio','tool_byte_ratio','model_calls','prompt_tokens','output_tokens','wall_seconds','honest_calls','cover_calls']},
              'planned_decoys':p['planned_decoys'],'triggered_decoys':p['triggered_decoys'],
              'invalid_model_output':p['invalid_model_output'],'step_limit':p['step_limit']})
    save(H/'analysis/table-values.json',{'utc':now(),'rows':rows,'analysis_receipt_sha256':sha(H/'analysis/analysis-receipt.json')})
    latex=H/'latex';latex.mkdir(exist_ok=True)
    lines=[r'\begin{table*}[t]',r'\centering\small',r'\setlength{\tabcolsep}{4pt}',
      r'\caption{LLM-planned executed cover on 120 paired held-out fixtures per cell. The primary LR/RF attacker is selected on validation data. All attack columns count correct predictions out of 120; chance is 20/120. The interval conditions on the fitted attacker and synthetic fixtures.}',
      r'\label{tab:m3-llm-recognition}',r'\begin{tabular}{llrrrrrl}',r'\toprule',
      r'Model & Cover & Frozen & LR & RF & Last & Penultimate & Selected BA [95\% CI] \\',r'\midrule']
    for r in rows:
        a=r['attack_correct'];lo,hi=r['conditional_ci']
        lines.append(f"{MODELS[r['model']]} & {NAMES[r['arm']]} & {a['frozen']} & {a['LR']} & {a['RF']} & {a['position_last']} & {a['position_penultimate']} & {r['balanced_accuracy']:.3f} [{lo:.3f}, {hi:.3f}] ({r['selected']})" + r' \\')
    lines += [r'\bottomrule',r'\end{tabular}',r'\end{table*}']
    (latex/'m3-llm-recognition.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    lines=[r'\begin{table*}[t]',r'\centering\small',r'\setlength{\tabcolsep}{4pt}',
      r'\caption{Task outcomes and measured costs on the same 120 held-out fixtures. State integrity compares the entire business state with the single intended-action reference. Byte ratios are means of paired ratios; total TLS bytes include all seven MCP initializations, while call bytes exclude initialization.}',
      r'\label{tab:m3-llm-utility}',r'\begin{tabular}{llrrrrrr}',r'\toprule',
      r'Model & Cover & Goal & State & Goal + state error & Call bytes $\times$ & Total bytes $\times$ & Model calls \\',r'\midrule']
    for r in rows:
        c=r['costs']
        lines.append(f"{MODELS[r['model']]} & {NAMES[r['arm']]} & {r['goal_success']}/120 & {r['state_integrity']}/120 & {r['goal_with_state_error']}/120 & {c['tool_byte_ratio']:.2f} & {c['transport_byte_ratio']:.2f} & {c['model_calls']:.2f}" + r' \\')
    lines += [r'\bottomrule',r'\end{tabular}',r'\end{table*}']
    (latex/'m3-llm-utility.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Rendered all 12 held-out cells; no attack or condition excluded.')

if __name__=='__main__':main()
