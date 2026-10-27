"""Project frozen audit records to the Type I/II privacy/attribution cohort.

All judgments remain unchanged. AHB and contextual records are excluded;
the resulting data include the member IDs of every denominator and numerator.
"""
from pathlib import Path
from collections import Counter
import csv, hashlib, json, re
import audit_check as a

M = Path(__file__).resolve().parents[1]
sources = ['tables/r19-record-audit.tex', 'tables/r9-record-index.tex',
           'tables/core-family-map.tex', 'data/record-scopes.csv',
           'tables/family-audit-matrix.tex']
idx = {r['id']: r for r in a.parse_record_index()}
cells = a.parse_record_cells()
with (M / 'data/record-scopes.csv').open(encoding='utf-8-sig', newline='') as f:
    scopes = {r['record_id']: r for r in csv.DictReader(f)}
core = {}
for line in (M / sources[2]).read_text(encoding='utf8').splitlines():
    if r'\cite{' not in line or '&' not in line:
        continue
    cols = line.split('&')
    layer = re.search(r'\$(.*?)\\,\\to\\,(.*?)\$', cols[1])
    core[a.cite_key(cols[0])] = {
        'G': [int(x) for x in layer[1].split(',')],
        'O': [int(x) for x in layer[2].split(',')],
        'types': re.search(r'\\texttt\{([^}]+)\}', cols[2])[1].split(',')}
assert len(idx) == len(cells) == 39 and len(core) == 58
assert set(idx) == set(cells) == set(scopes)
privacy_core = {f: v for f, v in core.items() if set(v['types']) & {'I', 'II'}}
mit = {k: v for k, v in cells.items() if not v['contextual'] and v['family'] in privacy_core}
assert len(privacy_core) == 52 and len(mit) == 31
assert {v['family'] for v in mit.values()} == {v['family'] for v in cells.values() if not v['contextual']} - {'zhu2026turing'}

def project(records):
    return {f: [next(s for s in a.PRECEDENCE if s in
             [r['cells'][j] for r in records.values() if r['family'] == f])
             for j in range(9)] for f in sorted({r['family'] for r in records.values()})}

def stats(rows, j, accepted):
    eligible = sorted(f for f, v in rows.items() if v[j - 1] != '--')
    bound = sorted(f for f in eligible if rows[f][j - 1] in accepted)
    return {'eligible': len(eligible), 'bound': len(bound), 'eligible_ids': eligible,
            'bound_ids': bound, 'states': dict(Counter(rows[f][j - 1] for f in eligible))}

variants = {'all': mit,
 'without_CachePrune': {k:v for k,v in mit.items() if v['family'] != 'wu2026cacheprune'},
 'without_final_search': {k:v for k,v in mit.items() if not idx[k]['added']},
 'without_CachePrune_or_final_search': {k:v for k,v in mit.items() if not idx[k]['added'] and v['family'] != 'wu2026cacheprune'}}
out = {'revision':'R35-privacy-census',
       'source_sha256': {p: hashlib.sha256((M/p).read_bytes()).hexdigest() for p in sources},
       'scope': 'Frozen core Type I/II union; 6 contextual and 2 AHB records excluded; no recoding',
       'core_ids': sorted(privacy_core), 'no_linked_qualifying_record_ids': sorted(set(privacy_core)-{v['family'] for v in mit.values()}),
       'variants': {}}
for name, records in variants.items():
    rows = project(records)
    q = {}
    for label, items in a.QUERIES.items():
        eligible = sorted(k for k,v in records.items() if all(v['cells'][i-1] != '--' for i in items))
        bound = sorted(k for k in eligible if all(records[k]['cells'][i-1] == 'B' for i in items))
        partial = sorted(k for k in eligible if all(records[k]['cells'][i-1] in ('B','P') for i in items))
        q[label] = {'eligible':len(eligible), 'bound':len(bound), 'partial_accepted':len(partial),
                    'eligible_ids':eligible, 'bound_ids':bound, 'partial_accepted_ids':partial,
                    'bound_family_ids':sorted({records[k]['family'] for k in bound}),
                    'bound_configurations':sorted({scopes[k]['configuration_package'] for k in bound}),
                    'excluded_ids':sorted(set(records)-set(eligible))}
    common = sorted(f for f,v in rows.items() if all(v[j-1]!='--' for j in (7,8,9)))
    out['variants'][name] = {'record_ids': sorted(records), 'family_ids': sorted(rows),
      'projected_cells':rows, 'fields':{f'R{j}':{'strict':stats(rows,j,('B',)),
              'partial_accepted':stats(rows,j,('B','P'))} for j in (4,5,7,8,9)},
      'common_R7_R8_R9':{'family_ids':common, 'fields':{f'R{j}':{
              'strict':stats({f:rows[f] for f in common},j,('B',)),
              'partial_accepted':stats({f:rows[f] for f in common},j,('B','P'))} for j in (7,8,9)}},
      'joint_queries':q, 'modes':{m:sorted(k for k in records if idx[k]['mode']==m)
                                   for m in ('Ex','Tr','Si','Co','Un')}}
assert len(out['variants']['all']['family_ids'])==19
assert out['variants']['all']['fields']['R7']['strict']['bound']==15
(M/'data/r35-privacy-census.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
tab = r'''\begin{table*}[t]\centering\footnotesize
\caption{Privacy/attribution cohort and sensitivity to record removal. Fractions are explicit B / applicable families; bracketed numerators also accept P. AHB and contextual records are excluded throughout.}\label{tab:r35-census}
\begin{tabularx}{\textwidth}{@{}Yccccc@{}}\toprule
Inventory & Inference R7 & Cost R9 & Utility R8 & Protected fit R4 & Matched adaptation R5\\\midrule
'''
for name,label in [('all','All 19 families'),('without_CachePrune','Without CachePrune'),('without_final_search','Without final-search records')]:
    fields=out['variants'][name]['fields']; vals=[]
    for j in (7,9,8,4,5):
        s=fields[f'R{j}']['strict']; p=fields[f'R{j}']['partial_accepted']
        vals.append(f'{s["bound"]}/{s["eligible"]} [{p["bound"]}]')
    tab+=label+' & '+' & '.join(vals)+r'\\'+'\n'
tab+=r'\bottomrule\end{tabularx}\end{table*}'+'\n'
(M/'tables/r35-removal-sensitivity.tex').write_text(tab,encoding='utf8',newline='\n')
base=out['variants']['all']['fields']
table = r'''\begin{table}[t]\centering\footnotesize
\caption{Evidence reporting in the 19 privacy/attribution mitigation families. B denotes explicit source-scoped binding; P denotes partial binding. Denominators differ by item applicability.}\label{tab:r35-reporting}
\begin{tabularx}{\columnwidth}{@{}Yrr@{}}\toprule
Reported item & B / applicable & B+P / applicable\\\midrule
'''
for j,label in [(7,'Inference outcome'),(9,'Cost'),(8,'Utility'),(4,'Protected fitting'),(5,'Matched adaptation')]:
    s,p=base[f'R{j}']['strict'],base[f'R{j}']['partial_accepted']
    table+=f'{label} (R{j}) & {s["bound"]}/{s["eligible"]} & {p["bound"]}/{p["eligible"]}'+r'\\'+'\n'
table+=r'\bottomrule\end{tabularx}\end{table}'+'\n'
(M/'tables/r35-reporting-patterns.tex').write_text(table,encoding='utf8',newline='\n')
# Preserve the original family display as a historical output; render the
# primary privacy/attribution matrix separately from the frozen projections.
family_display = (M/'tables/family-audit-matrix.tex').read_text(encoding='utf8')
family_lines = [line for line in family_display.splitlines()
                if r'\cite{' in line and '&' in line]
family_labels = {a.cite_key(line):line.split('&')[0].strip() for line in family_lines}
rows = out['variants']['all']['projected_cells']
assert len(family_labels) == 20 and set(rows) == set(family_labels)-{'zhu2026turing'}
f = r'''\begin{table}[t]\centering\footnotesize
\caption{Evidence availability in the 19 privacy/attribution mitigation families. Rows are record-derived projections; columns may refer to different configurations.}\label{tab:family-audit}
\setlength{\tabcolsep}{2.2pt}
\begin{tabularx}{\columnwidth}{@{}Y*{9}{c}@{}}\toprule
Family & R1 & R2 & R3 & R4 & R5 & R6 & R7 & R8 & R9\\\midrule
'''
for family,label in family_labels.items():
    if family not in rows: continue
    formatted = [r'\textbf{'+s+'}' if s in ('B','P') else s for s in rows[family]]
    f += label+' & '+' & '.join(formatted)+r'\\'+'\n'
bound=[sum(v[j]=='B' for v in rows.values()) for j in range(9)]
app=[sum(v[j]!='--' for v in rows.values()) for j in range(9)]
f += r'\midrule Bound & '+' & '.join(map(str,bound))+r'\\'+'\nApplicable & '+' & '.join(map(str,app))+r'\\'+'\n'
f += r'''\bottomrule\end{tabularx}
\par\smallskip\raggedright B: bound; P: partial; U: unreported in inspected scope; ?: unverified; --: inapplicable. Table~\ref{tab:audit-rules} defines R1--R9. The crosswalk in Appendix~\ref{app:reconstruction} locates inference/cost witnesses.
\end{table}
'''
(M/'tables/r35-family-audit.tex').write_text(f,encoding='utf8',newline='\n')
print(json.dumps({k:{'records':len(v['record_ids']),'families':len(v['family_ids']),
 'fields':v['fields'],'joint_queries':v['joint_queries'],'modes':{m:len(ids) for m,ids in v['modes'].items()}}
 for k,v in out['variants'].items()},indent=2))
