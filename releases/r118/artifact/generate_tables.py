"""Generate paper tables from released aggregates; no individual inputs or fits."""
from pathlib import Path
import argparse,csv,json,math,re
H=Path(__file__).resolve().parent
O=H/'p0'
S=H.parent/'source'
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def rows(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')
def esc(s):return str(s).replace('_',r'\_')
def pv(p):
    p=float(p)
    if p<.001:
        e=math.floor(math.log10(p));return rf'${p/10**e:.2g}\!\times\!10^{{{e}}}$'
    return f'{p:.4f}'.rstrip('0').rstrip('.')
def tab(name,caption,label,spec,header,body,wide=True,size='footnotesize'):
    env='table*' if wide else 'table';width=r'\textwidth' if wide else r'\columnwidth'
    text='\\begin{'+env+'}[t]\\centering\\'+size+'\n\\caption{'+caption+'}\\label{'+label+'}\n'
    text+='\\setlength{\\tabcolsep}{3pt}\n\\begin{tabularx}{'+width+'}{'+spec+'}\\toprule\n'
    text+=header+r' \\\midrule'+'\n'
    text+='\n'.join(' & '.join(map(str,r))+r' \\' for r in body)
    text+='\n\\bottomrule\\end{tabularx}\\end{'+env+'}\n'
    write(S/'tables'/name,text)


def main():
    global S
    ap=argparse.ArgumentParser();ap.add_argument("--source",required=True,type=Path);a=ap.parse_args();S=a.source.resolve()
    assert (S/"tables/decision.tex").is_file()
    aa=rows(O/'p0a-attacks.csv');ss=load(O/'p0a-summary.json')['selections'];tt=rows(O/'p0a-tests.csv')
    lookup={(r['variant'],r['model'],r['arm'],r['attack']):r for r in aa}
    pick={(r['variant'],r['model'],r['arm']):r['adaptive_selected'] for r in ss}
    arm_short={'Immediate':'Immediate','History, sequential':'History, seq.','History, concurrent':'History, conc.','Planner shadow':'Shadow'}
    mod={'qwen3:8b':'Qwen','llama3.1:8b':'Llama'}
    body=[]
    for m in mod:
        for ar in ['History, sequential','History, concurrent']:
            vals=[int(lookup[v,m,ar,pick[v,m,ar]]['test_correct']) for v in ['full','no_time','no_position']]
            t=next(r for r in tt if r['model']==m and r['arm']==ar and r['contrast']=='full_adaptive - no_time_adaptive')
            p=next(r for r in tt if r['model']==m and r['arm']==ar and r['family']=='B')
            body.append([mod[m],arm_short[ar],*vals,f"{float(t['difference_pp']):+.1f}",pv(t['p_holm']),pv(p['p_holm'])])
    tab('feature-ablation-main.tex',
        'Exploratory feature ablations on the same test fixtures. Full, No-time and No-position are validation-selected task-recognition counts /120. No-time retains destinations, order, ciphertext bytes and the candidate suite. No-position changes the explicit-position representation and omits position-only rules; timing order remains. $p_T$: Full minus No-time, Holm within eight timing contrasts; $p_P$: Full minus No-position, Holm within four contrasts. All tests are two-sided.',
        'tab:feature-ablation','@{}llrrrrrr@{}','Planner & Policy & Full & No-time & No-position & Time gain (pp) & $p_T$ & $p_P$',body)
    testbody=[]
    for r in tt:
        c={'full_adaptive - no_time_adaptive':'Full $-$ No-time','no_time_adaptive - full_size_selected':'No-time $-$ Full size','full_adaptive - no_position_adaptive':'Full $-$ No-position'}[r['contrast']]
        testbody.append([r['family'],mod[r['model']],arm_short[r['arm']],c,r['condition_only'],r['reference_only'],f"{float(r['difference_pp']):+.1f}",pv(r['p_raw']),pv(r['p_holm'])])
    tab('feature-ablation-tests.tex','All exploratory ablation tests. Discordant counts are condition-only ($+$) and reference-only ($-$), with 120 paired fixtures. Timing family A contains eight contrasts; position family B contains four. Full size denotes its original validation-selected size attack.','tab:supp-ablation-tests','@{}lllYrrrrr@{}','Family & Planner & Policy & Contrast & $+$ & $-$ & Difference (pp) & Raw $p$ & Holm $p$',testbody)
    cs=load(O/'p0c-summary.json');ca=rows(O/'p0c-attacks.csv');ct=rows(O/'p0c-tests.csv');audit=rows(O/'p0c-event-audit.csv')
    cb=[];tb=[];eb=[];maxima={}
    for s in cs['selections']:
        m,ar=s['model'],s['arm'];d={r['attack']:r for r in ca if r['model']==m and r['arm']==ar}
        t=next(r for r in ct if r['model']==m and r['arm']==ar)
        mx=max(int(r['test_correct']) for r in d.values());maxima[m,ar]=mx
        cb.append([mod[m],arm_short[ar],t['baseline_correct'],t['strong_correct'],d[s['overall']]['test_correct'],mx,f"{float(t['difference_pp']):+.1f}",pv(t['p_holm'])])
        tb.append([mod[m],arm_short[ar],t['condition_only'],t['reference_only'],f"{float(t['difference_pp']):+.1f}",pv(t['p_raw']),pv(t['p_holm'])])
        seg=re.fullmatch(r'(ctx|joint)_(.+)_(size|time)_(LR|RF)',s['strong']).group(2)
        e=next(r for r in audit if r['model']==m and r['arm']==ar and r['segmentation']==seg)
        segname='Protocol' if seg=='protocol' else str(int(1000*float(seg.split('_')[1])))+' ms'
        f=lambda key:f"{float(e[key]):.3f}"
        role='/'.join(f('test_cover_label_'+key) for key in ['precision','recall','f1'])
        bound='/'.join(f('segmentation_'+key+'_iou50') for key in ['precision','recall','f1'])
        eb.append([mod[m],arm_short[ar],segname,role,bound,e['mixed_events'],e['test_events']])
    tab('record-context-main.tex',
        'Exploratory attacks without test call windows; episode association remains supplied. Counts /120. B: validation-selected baseline, including all raw-record candidates. J: validation-selected context-removal/joint-decoding candidate. All: validation selection across all 76 candidates. Max: descriptive test maximum. Difference and Holm $p$ compare J with B in one eight-test family. Both shadow cells select the baseline in All.',
        'tab:record-context','@{}llrrrrrr@{}','Planner & Policy & B & J & All & Max & J$-$B (pp) & Holm $p$',cb)
    tab('record-context-tests.tex','All eight exploratory context/joint minus baseline tests on record-only observations. Discordances and denominators are paired fixture counts; $n=120$ in each cell. Holm correction covers all eight rows.','tab:supp-record-tests','@{}llrrrrr@{}','Planner & Policy & J-only & B-only & Difference (pp) & Raw $p$ & Holm $p$',tb)
    tab('record-event-audit.tex',
        'Test audits for the eventization used by the validation-selected strong attack. Role P/R/F1 labels an event as cover if it overlaps any cover call; boundary P/R/F1 matches events to calls at IoU .5. Mixed events overlap real and cover calls. All test predictions were saved before these private-truth audits. The complete six-eventizer audit is in the aggregate artifact.',
        'tab:supp-record-audit','@{}llrYYrr@{}','Planner & Policy & Event gap & Role P/R/F1 & Boundary P/R/F1 & Mixed & Events',eb)
    ts=load(O/'p0t-summary.json')['cells'];ta=rows(O/'p0t-attack-strata.csv');b=[]
    for c in ts:
        r=next(r for r in ta if r['model']==c['model'] and r['arm']==c['arm'] and 'adaptive' in r['selected'])
        b.append([mod[c['model']],arm_short[c['arm']],c['no_real_business_call'],c['uncovered_terminal'],c['covered_terminal'],r['uncovered_correct']+'/'+r['uncovered_n'],r['covered_correct']+'/'+r['covered_n']])
    tab('terminal-coverage.tex','Exploratory stratification by the last issued honest business call. After means later start time; for shadow, coverage requires a later shadow business call. Requested-goal correctness is not part of this definition. Scores are the saved validation-selected adaptive attack; strata are observational, not randomized position interventions.','tab:supp-terminal','@{}llrrrYY@{}','Planner & Policy & No business call & Uncovered & Covered & Uncovered correct/$n$ & Covered correct/$n$',b)
    bs=load(O/'p0b-summary.json');bl=rows(O/'p0b-task-labels.csv');b=[]
    for r in bs['R1']:
        m=r['model'];st=[z for z in bs['R2'] if z['model']==m];rf=next(z for z in bl if z['model']==m and z['attack']=='byte_RF')
        b.append([mod[m],r['selector_correct'],r['baseline_correct'],pv(r['p_holm']),sum(z['exact_partition'] for z in st),sum(z['exact_real_chain'] for z in st),rf['different_correct']+'/99'])
    tab('shadow-role-diagnostics.tex',r'Exploratory shadow diagnostics. First-role prediction uses the frozen $p\ge.5$ selector and is compared with the TRAIN-majority start-order baseline by exact paired testing, Holm across two models. Counts /120 except RF task recognition on the 99 different-label pairs. First-role prediction, exact partition and exact real-chain recovery are distinct endpoints.','tab:supp-shadow-role','@{}lrrrrrY@{}','Planner & First role & Order baseline & Holm $p$ & Exact partition & Exact real chain & RF different-label correct/$n$',b)
    # Update only the record-only columns of the current worksheet; all costs/state/CW values remain.
    p=S/'tables/decision.tex';text=p.read_text(encoding='utf-8')
    lines=[]
    for line in text.splitlines():
        if line.startswith(('Qwen3:8B &','Llama3.1:8B &')):
            parts=line.split(' & ');m='qwen3:8b' if parts[0]=='Qwen3:8B' else 'llama3.1:8b';ar=parts[1]
            parts[3]=str(maxima[m,ar])
            if ar!='Planner shadow':parts[-1]=r'Above: inference \\'
            line=' & '.join(parts)
        lines.append(line)
    text='\n'.join(lines)+'\n';text=text.replace('RO history uses a weaker suite.','RO Max uses the 76-candidate exploratory record-only suite; the observation representations and attack suites differ.')
    write(p,text)
    print("Generated seven aggregate-linked tables and worksheet record maxima")

if __name__=="__main__":main()
