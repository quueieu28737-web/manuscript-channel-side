"""Recompute scoped applicability, placement and leave-one-family-out checks.

Variants are prospective interpretations of the frozen cells, never source
recodings. Unreviewed broader adaptive-attacker evidence remains unknown.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,sys
import audit_check as a

M=Path(__file__).resolve().parents[1]
inputs=['tables/r19-record-audit.tex','tables/r9-record-index.tex',
        'tables/core-family-map.tex','data/r35-privacy-census.json']
d=json.loads((M/inputs[-1]).read_text(encoding='utf8'))
cells=a.parse_record_cells()
ids=d['variants']['all']['record_ids']
records={k:cells[k] for k in ids}
assert len(records)==31 and len({v['family'] for v in records.values()})==19

def variant(records, broad=False, require_placement=False, spec_partial=False):
 def status(k,i):
  x=records[k]['cells'][i-1]
  if broad and i in (4,5) and x=='--':return '?'
  if spec_partial and k=='SPEC-padding-REST' and i==9:return 'P'
  return x
 queries={}
 for name,items in a.QUERIES.items():
  eligible=sorted(k for k in records if all(status(k,i)!='--' for i in items))
  bound=sorted(k for k in eligible if all(status(k,i)=='B' for i in items)
               and (not require_placement or status(k,3)=='B'))
  queries[name]={'eligible':len(eligible),'bound':len(bound),'eligible_ids':eligible,'bound_ids':bound}
 return queries

variants={
 'historical_fit_scope':variant(records),
 'broad_nonfit_unknown':variant(records,broad=True),
 'placement_required':variant(records,require_placement=True),
 'spec_payload_cost_partial':variant(records,spec_partial=True),
}
loo={}
for family in sorted({v['family'] for v in records.values()}):
 subset={k:v for k,v in records.items() if v['family']!=family}
 loo[family]=variant(subset)
triple=[q['Inference + utility + cost']['bound'] for q in loo.values()]
assert Counter(triple)=={0:1,2:18}
assert variants['broad_nonfit_unknown']['All five bindings']['eligible']==19
assert variants['placement_required']['Inference + cost']['bound']==4

out={'version':'R36-sensitivity','source_sha256':{n:hashlib.sha256((M/n).read_bytes()).hexdigest() for n in inputs},
     'rule':'Historical R4/R5 ask about protected-data fits and a matched clean/protected fit. Broader adaptive strategies require a source review; former -- becomes ? in sensitivity only.',
     'variants':variants,'leave_one_family_out':loo,
     'triple_loo_bound_distribution':dict(Counter(triple)),
     'qualifications':'Bound cost objects are retained separately; payload ratios are not wire bytes. No source cell is recoded.'}
(M/'data/r36-sensitivity.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf8',newline='\n')
table=r'''\begin{table}[t]\centering\footnotesize
\caption{Two fit-applicability and cost-placement interpretations over the same 31 privacy/attribution records. Entries are bound/eligible records. Broadening maps fit-inapplicable records to unknown, not to a verified absence of adaptation.}\label{tab:r36-sensitivity}
\begin{tabularx}{\columnwidth}{@{}Yrr@{}}\toprule
Query & Fit scope & Broader unknown\\\midrule
'''
for key in ('Matched adaptation + inference','All five bindings'):
 vals=[variants[x][key] for x in ('historical_fit_scope','broad_nonfit_unknown')]
 table+=key+' & '+' & '.join(f'{v["bound"]}/{v["eligible"]}' for v in vals)+r'\\'+'\n'
table+=r'''\midrule
Inference + cost & 5/21 & 4/21$^{\dagger}$\\
\bottomrule\end{tabularx}
\par\smallskip\raggedright $^{\dagger}$ Requires explicit R3 placement as well as R7/R9, or treats SPEC's payload-only cost as P for a wire-level query. The same four records remain, with distinct cost objects. Source cells and original query labels remain unchanged.
\end{table}
'''
(M/'tables/r36-sensitivity.tex').write_text(table,encoding='utf8',newline='\n')
print(json.dumps({'variants':variants,'triple_loo_bound_distribution':dict(Counter(triple))},indent=2))
