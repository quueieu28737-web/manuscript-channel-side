"""R34: descriptive reporting-pattern census from fixed source judgments.

No inference across differently applicable columns, no source recoding, no
independent coding/participant claims. All numerator/denominator IDs are saved.
"""
from pathlib import Path
from collections import Counter
import csv, hashlib, json, re
import audit_check as a

M = Path(__file__).resolve().parents[1]

def save(name, obj):
    (M/name).write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n', encoding='utf8', newline='\n')

def put(name, text):
    (M/name).write_text(text, encoding='utf8', newline='\n')

def sha(name):
    return hashlib.sha256((M/name).read_bytes()).hexdigest()

idx = {r['id']:r for r in a.parse_record_index()}
cells = a.parse_record_cells()
mit = {k:v for k,v in cells.items() if not v['contextual']}
assert len(idx)==39 and len(mit)==33
core = {}
for line in (M/'tables/core-family-map.tex').read_text().splitlines():
    if r'\cite{' not in line or '&' not in line: continue
    cols = line.split('&')
    layers = re.search(r'\$(.*?)\\,\\to\\,(.*?)\$', cols[1])
    assert layers, line
    core[a.cite_key(cols[0])] = {
        'G':[int(x) for x in layers[1].split(',')],
        'O':[int(x) for x in layers[2].split(',')],
        'types':re.search(r'\\texttt\{([^}]+)\}',cols[2])[1].split(',')}
assert len(core)==58

def project(records):
    return {f:[next(s for s in a.PRECEDENCE if s in
        [r['cells'][j] for r in records.values() if r['family']==f])
        for j in range(9)] for f in sorted({r['family'] for r in records.values()})}

def stats(rows, j, accept=('B',)):
    eligible = sorted(k for k,v in rows.items() if v[j-1]!='--')
    bound = sorted(k for k in eligible if rows[k][j-1] in accept)
    return {'bound':len(bound),'eligible':len(eligible),'bound_ids':bound,
        'eligible_ids':eligible,'states':dict(Counter(rows[k][j-1] for k in eligible))}

def summaries(records):
    rows=project(records)
    return {f'R{j}':{'strict':stats(rows,j),'partial_accepted':stats(rows,j,('B','P'))}
            for j in (4,5,7,8,9)}

fams=project(mit)
variants={'all':mit,
 'without_CachePrune':{k:v for k,v in mit.items() if v['family']!='wu2026cacheprune'},
 'without_final_search':{k:v for k,v in mit.items() if not idx[k]['added']},
 'without_CachePrune_or_final_search':{k:v for k,v in mit.items() if not idx[k]['added'] and v['family']!='wu2026cacheprune'}}
field={n:summaries(rs) for n,rs in variants.items()}
common=[f for f,v in fams.items() if all(v[j-1]!='--' for j in (7,8,9))]
common_stats={f'R{j}':{'strict':stats({f:fams[f] for f in common},j),
 'partial_accepted':stats({f:fams[f] for f in common},j,('B','P'))} for j in (7,8,9)}

agent=[f for f in fams if 5 in core[f]['G'] and set(core[f]['types']) & {'I','II'}]
agent_utility={f:{'R8':fams[f][7], 'record_ids':[k for k,v in mit.items() if v['family']==f],
                  **core[f]} for f in agent}
assert len(agent)==4
agent_by_variant={n:{'families':[f for f in project(rs) if f in agent],
 'strict':stats({f:v for f,v in project(rs).items() if f in agent},8),
 'partial_accepted':stats({f:v for f,v in project(rs).items() if f in agent},8,('B','P'))}
 for n,rs in variants.items()}

def crosswalk(records,accept=('B',)):
    families=project(records);out=[]
    for f in families:
        ri=[k for k,v in records.items() if v['family']==f and v['cells'][6] in accept]
        rc=[k for k,v in records.items() if v['family']==f and v['cells'][8] in accept]
        if ri and rc: out.append({'family':f,'inference':ri,'cost':rc,'joint':sorted(set(ri)&set(rc))})
    return {'families':len(out),'separate_only':sum(not r['joint'] for r in out),'rows':out}

joins={n:{'strict':crosswalk(rs),'partial_accepted':crosswalk(rs,('B','P'))} for n,rs in variants.items()}

def block(row):
    g=set(row['G'])
    if g=={1}:return 'P1 only'
    if g=={1,2}:return 'P1/P2'
    if g=={2}:return 'P2 only'
    if 5 in g and g<={5,6,7,8}:return 'Orchestration/workflow'
    return 'Other cross-layer'

groups={}
for label in ['P1 only','P1/P2','P2 only','Orchestration/workflow','Other cross-layer']:
    all_ids=[f for f,v in core.items() if block(v)==label]
    pos=[f for f in all_ids if f in fams]
    groups[label]={'core':len(all_ids),'mitigation':len(pos),'core_ids':all_ids,'mitigation_ids':pos}
types={t:{'core_ids':[f for f,v in core.items() if t in v['types']],
 'mitigation_ids':[f for f,v in core.items() if t in v['types'] and f in fams]} for t in ['I','II','III','IV']}
coverage_sensitivity={n:{label:{'mitigation_ids':[f for f in g['core_ids'] if f in project(rs)],
                              'fixed_core_denominator':g['core']}
                         for label,g in groups.items()} for n,rs in variants.items()}

def modes(records):
    return {'records':len(records),'counts':dict(Counter(idx[k]['mode'] for k in records)),
            'ids':{mode:[k for k in records if idx[k]['mode']==mode] for mode in ['Ex','Tr','Si','Co','Un']}}

network={k:v for k,v in mit.items() if 3 in core[v['family']]['O']}
mode_stats={'all_records':modes(cells),'mitigation':modes(mit),'network_receiver_mitigation':modes(network),
            'without_final_search':modes(variants['without_final_search'])}

# A deliberately broader applicability convention: add the nine formerly
# inapplicable families to each denominator as U. This is a sensitivity model,
# not revised coding or a requirement imposed on proof/non-learning studies.
broad={f'R{j}':{'strict':stats({f:[('U' if x=='--' and i==j-1 else x)
 for i,x in enumerate(v)] for f,v in fams.items()},j),
 'partial_accepted':stats({f:[('U' if x=='--' and i==j-1 else x)
 for i,x in enumerate(v)] for f,v in fams.items()},j,('B','P'))} for j in (4,5)}
holdout=list(csv.DictReader((M/'data/family-index.csv').open(encoding='utf-8-sig')))
h={axis:[{'family':r['citation_key'],'mitigation_family':r['citation_key'] in fams,
          'locator':r['source_locators'],'interpretation':r['interpretation']}
          for r in holdout if r[axis]=='H'] for axis in ['task_input_user','model','harness_topology','hardware','network_load','time']}

sources=['tables/r19-record-audit.tex','tables/r9-record-index.tex','tables/core-family-map.tex',
         'data/family-index.csv','data/record-scopes.csv','tables/r26-h-objects.tex']
out={'revision':'R34-reporting-patterns','source_sha256':{n:sha(n) for n in sources},
 'definitions':{'unit':'Family availability unless explicitly record mode or record conjunction',
 'B':'Explicit source-scoped binding','P':'Partial binding; permissive sensitivity only',
 'denominator':'All applicable families for the requested item; U/?/P stay eligible',
 'dagger':'Six final-search records in record index; double dagger marks six contextual records, already excluded',
 'scope':'Inspected sources in frozen corpus; descriptive reporting census, not effectiveness or population prevalence'},
 'field_patterns':field,'common_R7_R8_R9_families':common_stats,'broad_adaptation_applicability':broad,
 'agent_privacy_attribution_utility':agent_utility,'agent_sensitivity':agent_by_variant,
 'inference_cost_conjunction':joins,'source_layer_coverage':groups,'coverage_sensitivity':coverage_sensitivity,'threat_type_coverage':types,
 'measurement_modes':mode_stats,'holdout_entries':h,'new_source_judgments':0,'new_model_calls':0}
save('data/reporting-patterns.json',out)

labels={4:'Protected fitting',5:'Matched adaptation',7:'Inference outcome',8:'Utility',9:'Cost'}
t=r'''\begin{table}[t]\centering\footnotesize
\caption{Reporting asymmetry across the 20 mitigation families. Each denominator contains families to which that item applies; B is explicit, P partial. The common-population row removes denominator differences.}\label{tab:r34-reporting}
\begin{tabularx}{\columnwidth}{@{}Yrr@{}}\toprule
Reported binding & B / applicable & (B+P) / applicable\\\midrule
'''
for j in (7,9,8,4,5):
    d=field['all'][f'R{j}'];s,p=d['strict'],d['partial_accepted']
    t+=f'{labels[j]} (R{j}) & {s["bound"]}/{s["eligible"]} & {p["bound"]}/{p["eligible"]}'+r'\\'+'\n'
t+=r'''\midrule
\multicolumn{3}{@{}l}{Same 14 families, inference / cost / utility:}\\
'''
for key,label in [('strict','Explicit B'),('partial_accepted','B or P')]:
    values=[f'{common_stats[f"R{j}"][key]["bound"]}/{common_stats[f"R{j}"][key]["eligible"]}' for j in (7,9,8)]
    t+=label+r' & \multicolumn{2}{l}{'+r'\quad '.join(values)+r'}\\'+'\n'
t+=r'''
\bottomrule\end{tabularx}
\par\smallskip\raggedright Expanding R4/R5 applicability to all 20 gives 4/20 and 2/20 (B), or 9/20 and 2/20 (B+P). Source judgments stay fixed. Removal checks and member identities accompany the census (main Appendix F; S38).
\end{table}
'''
put('tables/r34-reporting-patterns.tex',t)
t=r'''\begin{table}[t]\centering\footnotesize
\caption{Core-map coverage by source-layer block. Numerators are families with an evaluated mitigation record; denominators are the empirical core map, not all defense research.}\label{tab:r34-coverage}
\begin{tabularx}{\columnwidth}{@{}Yrr@{}}\toprule
Generating-layer block & Mitigation & Core\\\midrule
'''
for label,g in groups.items():t+=f'{label} & {g["mitigation"]} & {g["core"]}'+r'\\'+'\n'
t+=r'''\bottomrule\end{tabularx}
\par\smallskip\raggedright Across overlapping purpose labels, Type II has 2/13 mitigation families (UI Traces and the cloud benchmark). C5 and the scoped evaluation rule define this coverage frame.
\end{table}
'''
put('tables/r34-map-coverage.tex',t)

t=r'''\begin{table*}[t]\centering\footnotesize
\caption{Sensitivity of reporting patterns. Fractions give explicit / applicable family counts; bracketed numerators also accept P. Removing final-search additions excludes six records from four families; contextual controls are excluded in every row. IC separate means no single record carries both explicit inference and cost.}\label{tab:r34-removal}
\begin{tabularx}{\textwidth}{@{}Yccccccl@{}}\toprule
Inventory & R7 & R9 & R8 & R4 & R5 & Agent R8 & IC separate\\\midrule
'''
for key,name in [('all','All mitigation'),('without_CachePrune','Without CachePrune'),('without_final_search','Without final-search records')]:
    s=field[key];vals=[f'{s[f"R{j}"]["strict"]["bound"]}/{s[f"R{j}"]["strict"]["eligible"]} [{s[f"R{j}"]["partial_accepted"]["bound"]}]' for j in (7,9,8,4,5)]
    ag=agent_by_variant[key];c=joins[key]['strict']
    vals += [f'{ag["strict"]["bound"]}/{ag["strict"]["eligible"]} [{ag["partial_accepted"]["bound"]}]',f'{c["separate_only"]}/{c["families"]}']
    t+=name+' & '+' & '.join(vals)+r'\\'+'\n'
t+=r'\bottomrule\end{tabularx}\end{table*}'+'\n'
put('tables/r34-removal-sensitivity.tex',t)

t=r'''\begin{table}[ht]\centering\footnotesize
\caption{Agent privacy/attribution subset: P5 generation and Type I or II. Every applicable family is listed.}\label{tab:r34-agent}
\begin{tabularx}{\linewidth}{@{}lclY@{}}\toprule
Family & R8 & Objective & Located utility evidence\\\midrule
UI Traces~\cite{uitraces2026} & U & Attribution & Offline delay; task outcome unbound.\\
WRA~\cite{jeong2026wra} & P & Privacy & Separately judged usefulness; no same-condition task pair.\\
Dangol~\cite{dangol2026workflow} & U & Privacy & Capture/loopback outcome; workflow utility unbound.\\
Cloud benchmark~\cite{pouryousef2026traffic} & P & Privacy/attribution & Semantic preservation asserted; task score unbound.\\
\bottomrule\end{tabularx}\end{table}
'''
put('tables/r34-agent-utility.tex',t)
t=r'''\begin{table}[ht]\centering\footnotesize
\caption{Sensitivity to accepting partial inference and cost evidence. A family is counted only if it has both requested items under the specified rule.}\label{tab:r34-cost-relaxation}
\begin{tabular}{@{}lrrrr@{}}\toprule
Inventory & Both B & Separate & Both B/P & Separate\\\midrule
'''
for key,label in [('all','All mitigation'),('without_CachePrune','Without CachePrune'),('without_final_search','Without final-search records')]:
    s,p=joins[key]['strict'],joins[key]['partial_accepted']
    t+=f'{label} & {s["families"]} & {s["separate_only"]} & {p["families"]} & {p["separate_only"]}'+r'\\'+'\n'
t+=r'\bottomrule\end{tabular}\end{table}'+'\n'
put('tables/r34-cost-sensitivity.tex',t)
# Pair tables are supporting material. A shared wide float prevents isolated
# single-column float pages behind the larger appendix matrices.
parts=[]
for name in ['r33-pair-summary.tex','r33-granularity.tex']:
    body=(M/'tables'/name).read_text().replace(r'\begin{table}[t]','',1)
    body=body.rsplit(r'\end{table}',1)[0]
    parts.append(r'\begin{minipage}[t]{.49\textwidth}'+body+r'\end{minipage}')
cross=(M/'tables/r33-family-crosswalk.tex').read_text().replace(r'\begin{table*}[t]','',1)
cross=cross.rsplit(r'\end{table*}',1)[0]
put('tables/r34-comparison-index.tex',r'\begin{table*}[t]'+'\n'+cross+r'\par\bigskip'+
    '\n'+r'\hfill'.join(parts)+'\n'+r'\end{table*}'+'\n')
print(json.dumps({k:out[k] for k in ['field_patterns','common_R7_R8_R9_families','measurement_modes']},indent=2))
