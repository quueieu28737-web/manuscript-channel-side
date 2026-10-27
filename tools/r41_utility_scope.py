"""Recompute R8 and joint queries for the outcome named by the reuse claim.

Archived record cells remain unchanged. The source-linked R41 applicability
overlay separates content/behavior changes from narrow preservation witnesses.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,re
import audit_check as a
M=Path(__file__).resolve().parents[1]
load=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf8',newline='\n')
source=load(M/'data/r41-utility-scopes.json')
for rel,h in source['input_sha256'].items():assert sha(M/rel)==h,rel
old=a.parse_record_cells();scope={r['record_id']:r for r in source['rows']}
assert len(scope)==31 and set(scope)==set(load(M/'data/r35-privacy-census.json')['variants']['all']['record_ids'])
cells={k:{**old[k],'cells':old[k]['cells'].copy()} for k in scope}
for k,v in scope.items():
 assert v['archived_R8']==old[k]['cells'][7]
 assert v['quality_applicable']==(v['category']=='may_change_function')
 cells[k]['cells'][7]=v['current_R8']
families={f:[next(s for s in a.PRECEDENCE if s in [v['cells'][j] for v in cells.values() if v['family']==f]) for j in range(9)] for f in sorted({v['family'] for v in cells.values()})}
fields={}
for j in (4,5,7,8,9):
 eligible=sorted(f for f,v in families.items() if v[j-1]!='--')
 fields[f'R{j}']={'eligible':len(eligible),'eligible_ids':eligible,
                'bound_ids':[f for f in eligible if families[f][j-1]=='B'],
                'partial_accepted_ids':[f for f in eligible if families[f][j-1] in ('B','P')]}
queries={}
for label,items in a.QUERIES.items():
 eligible=sorted(k for k,v in cells.items() if all(v['cells'][j-1]!='--' for j in items))
 queries[label]={'eligible':len(eligible),'eligible_ids':eligible,
                 'bound_ids':[k for k in eligible if all(cells[k]['cells'][j-1]=='B' for j in items)],
                 'partial_accepted_ids':[k for k in eligible if all(cells[k]['cells'][j-1] in ('B','P') for j in items)]}
preservation_packages=sorted(k for k,v in cells.items() if scope[k]['category']=='preserves_scoped_object' and v['cells'][6]=='B' and v['cells'][8]=='B')
agent_families=['uitraces2026','jeong2026wra','dangol2026workflow','pouryousef2026traffic']
agent_rows={f:{'record_ids':sorted(k for k,v in cells.items() if v['family']==f),
               'quality_record_ids':sorted(k for k,v in cells.items() if v['family']==f and scope[k]['quality_applicable']),
               'current_R8':families[f][7]} for f in agent_families}
assert Counter(r['category'] for r in scope.values())=={'may_change_function':11,'preserves_scoped_object':18,'component_only':2}
assert fields['R8']['eligible']==8 and len(fields['R8']['bound_ids'])==3 and len(fields['R8']['partial_accepted_ids'])==4
assert len(families)==19
assert preservation_packages==['DANGOL-capture','DANGOL-livebinding','SPEC-padding-REST']
assert [f for f,v in agent_rows.items() if v['quality_record_ids']]==['pouryousef2026traffic']
out={'revision':'R41','selection_scope':source['selection_scope'],'input_sha256':{'data/r41-utility-scopes.json':sha(M/'data/r41-utility-scopes.json')},
     'families':families,'fields':fields,'joint_queries':queries,
     'category_record_ids':{c:sorted(k for k,v in scope.items() if v['category']==c) for c in ('may_change_function','preserves_scoped_object','component_only')},
     'quality_exempt_family_ids':sorted(f for f,v in families.items() if v[7]=='--'),
     'preservation_function_packages':preservation_packages,'agent_subset':agent_rows,
     'agent_task_score':'No explicit same-condition end-to-end task score in the inspected scope of these four mapped families; only WRA clearly adds executed decoy research calls.'}
index={v['id']:v for v in a.parse_record_index()}
out['removal_sensitivity']={}
for variant,keep in [('All source families',lambda k:True),('Without CachePrune',lambda k:cells[k]['family']!='wu2026cacheprune'),('Without final-search records',lambda k:not index[k]['added'])]:
 subset={k:v for k,v in cells.items() if keep(k)}
 grouped={f:[v['cells'][7] for v in subset.values() if v['family']==f] for f in sorted({v['family'] for v in subset.values()})}
 states={f:next(s for s in a.PRECEDENCE if s in vals) for f,vals in grouped.items()}
 eligible=[f for f,s in states.items() if s!='--']
 out['removal_sensitivity'][variant]={'family_ids':list(states),'quality_eligible_ids':eligible,
      'bound_ids':[f for f in eligible if states[f]=='B'],'partial_accepted_ids':[f for f in eligible if states[f] in ('B','P')]}
write(M/'data/r41-current-census.json',json.dumps(out,ensure_ascii=False,indent=2)+'\n')

t=r'''\begin{table}[t]\centering\footnotesize
\caption{Reporting in the C1--C5 attack-evaluated source frame. R8 counts only families with a potentially changed generation, computation or component outcome; eleven families are exempt from that narrow quality query.}\label{tab:r35-reporting}
\begin{tabularx}{\columnwidth}{@{}Yrr@{}}\toprule
Requested evidence & B / applicable & B+P / applicable\\\midrule
'''
for j,label in [(7,'Inference outcome'),(9,'Cost'),(8,'Functional quality'),(4,'Protected fitting'),(5,'Matched adaptation')]:
 v=fields[f'R{j}'];t+=f"{label} (R{j}) & {len(v['bound_ids'])}/{v['eligible']} & {len(v['partial_accepted_ids'])}/{v['eligible']}"+r'\\'+'\n'
t+=r'\bottomrule\end{tabularx}\end{table}'+'\n';write(M/'tables/r41-reporting-patterns.tex',t)

t=r'''\begin{table}[ht]\centering\small
\caption{Functional-quality denominator after applicability and source-removal checks. Preservation and component-only units are exempt.}\label{tab:r41-removal}
\begin{tabularx}{\linewidth}{@{}Yrrr@{}}\toprule
Source inventory & Families & Quality B/applicable & Quality B+P/applicable\\\midrule
'''
for name,v in out['removal_sensitivity'].items():
 n=len(v['quality_eligible_ids']);t+=name+f" & {len(v['family_ids'])} & {len(v['bound_ids'])}/{n} & {len(v['partial_accepted_ids'])}/{n}"+r'\\'+'\n'
t+=r'\bottomrule\end{tabularx}\end{table}'+'\n';write(M/'tables/r41-removal.tex',t)

original=(M/'tables/family-audit-matrix.tex').read_text(encoding='utf8')
labels={a.cite_key(l):l.split('&')[0].strip() for l in original.splitlines() if r'\cite{' in l and '&' in l}
t=r'''\begin{table}[t]\centering\footnotesize
\caption{Mitigation-source bindings in the attack-evaluation frame. R8 exempts scoped preservation; columns can refer to different records.}\label{tab:family-audit}
\setlength{\tabcolsep}{2.2pt}
\begin{tabularx}{\columnwidth}{@{}Y*{9}{c}@{}}\toprule
Family & R1 & R2 & R3 & R4 & R5 & R6 & R7 & R8 & R9\\\midrule
'''
for f,l in labels.items():
 if f not in families:continue
 vals=[r'\textbf{'+v+'}' if v in ('B','P') else v for v in families[f]]
 t+=l+' & '+' & '.join(vals)+r'\\'+'\n'
t+=r'\midrule Bound & '+' & '.join(str(sum(v[j]=='B' for v in families.values())) for j in range(9))+r'\\'+'\n'
t+='Applicable & '+' & '.join(str(sum(v[j]!='--' for v in families.values())) for j in range(9))+r'\\'+'\n'
t+=r'''\bottomrule\end{tabularx}
\par\smallskip\raggedright B: bound; P: partial; U: unreported; ?: unverified; --: inapplicable to the named outcome. For R8, -- supports only the stated functional object, not timeliness or task completion. Current record codes: Appendix~\ref{app:reconstruction}; source rationales: S44.
\end{table}
''';write(M/'tables/r41-family-audit.tex',t)

def ratio(q):return f"{len(queries[q]['bound_ids'])}/{queries[q]['eligible']}"
t=r'''\begin{table*}[t]\centering\footnotesize
\caption{Joint results in the same 31-record source frame after R8 applicability is resolved. Quality queries include only potentially quality-changing records; a scoped preservation witness supplies a separate functional route.}\label{tab:r35-positive}
\begin{tabularx}{\textwidth}{@{}p{.23\textwidth}p{.35\textwidth}Y@{}}\toprule
Requested evidence & Bound records & Interpretation\\\midrule
'''
for q,short,desc in [
 ('Inference + utility','Inference + measured quality','CachePrune shares one default package; SparLeak binds quality by intensity.'),
 ('Inference + cost','Inference + cost','Payload, capture, loopback and serving costs remain distinct.'),
 ('Matched adaptation + inference','Adaptation + inference','Matched clean/protected fitting on defended tests.'),
 ('Inference + utility + cost','Inference + measured quality + cost','Two CachePrune outcomes, one configuration.'),
 ('All five bindings','All five applicable checks','No bound record for this scoped query.')]:
 ids=queries[q]['bound_ids'];names='; '.join(x.replace('-','-\\allowbreak{}') for x in ids) or 'None'
 t+=short+' ('+ratio(q)+') & '+names+' & '+desc+r'\\'+'\n'
t+=r'\midrule Narrow preservation + inference/cost & DANGOL-capture; DANGOL-livebinding; SPEC-padding-REST & Fixed message/token content; no implied deadline or end-to-end task guarantee.\\'+'\n'
t+=r'''\bottomrule\end{tabularx}
\par\smallskip\raggedright SPEC binds a payload-size ratio, not live wire cost; requiring explicit placement still leaves four of the 21 inference/cost-eligible records. A structural function witness and an empirical quality score are separate evidence types.
\end{table*}
''';write(M/'tables/r41-positive-joins.tex',t)

def query_variant(broad):
 ans={}
 for q,items in a.QUERIES.items():
  def status(k,i):
   s=cells[k]['cells'][i-1]
   return '?' if broad and i in (4,5) and s=='--' else s
  ids=[k for k in cells if all(status(k,i)!='--' for i in items)]
  ans[q]={'eligible':len(ids),'bound':sum(all(status(k,i)=='B' for i in items) for k in ids)}
 return ans
variants={k:query_variant(v) for k,v in [('fit_scope',False),('broad_nonfit_unknown',True)]}
t=r'''\begin{table}[t]\centering\footnotesize
\caption{Fit-scope sensitivity with the current R8 quality applicability. Broadening fit-inapplicable cells gives unknown evidence.}\label{tab:r36-sensitivity}
\begin{tabularx}{\columnwidth}{@{}Yrr@{}}\toprule
Query & Fit scope & Broader unknown\\\midrule
'''
for q in ('Matched adaptation + inference','All five bindings'):
 t+=q+' & '+' & '.join(f"{v[q]['bound']}/{v[q]['eligible']}" for v in variants.values())+r'\\'+'\n'
t+=r'\midrule Inference + cost & 5/21 & 4/21$^\dagger$\\'+'\n'
t+=r'''\bottomrule\end{tabularx}
\par\smallskip\raggedright $^\dagger$ Requires explicit R3 placement, or a wire-level cost rather than SPEC's payload ratio. R8 exemptions do not change this inference/cost query.
\end{table}
''';write(M/'tables/r41-fit-sensitivity.tex',t)

t=r'''\begingroup\footnotesize\setlength{\tabcolsep}{3pt}
\begin{longtable}{@{}p{.23\textwidth}p{.12\textwidth}p{.08\textwidth}p{.18\textwidth}p{.33\textwidth}@{}}
\caption{Complete R8 applicability overlay for all 31 Type I/II records. Relevant = functional quality applies; preserved = scoped content/action/function witness; component = no output-quality unit. Archived source statuses remain available.}\label{tab:r41-utility-records}\\
\toprule Record & Scope & Old/new R8 & Source locator & Outcome-specific reason\\\midrule\endfirsthead
\toprule Record & Scope & Old/new R8 & Source locator & Outcome-specific reason\\\midrule\endhead
'''
for k,v in scope.items():
 kind={'may_change_function':'Relevant','preserves_scoped_object':'Preserved','component_only':'Component'}[v['category']]
 t+=k.replace('-','-\\allowbreak{}')+r'~\cite{'+v['family']+'} & '+kind+' & '+v['archived_R8']+'/'+v['current_R8']+' & '+v['source_locator'].replace(';','; ')+' & '+v['reason'].replace('%',r'\%')+r'\\'+'\n'
t+=r'\bottomrule\end{longtable}\endgroup'+'\n';write(M/'tables/r41-utility-records.tex',t)
print(json.dumps({'status':'R41_SCOPE_PROJECTION_PASS','families':len(families),'R8':fields['R8'],'queries':queries,
                  'preserved_function_packages':preservation_packages},ensure_ascii=False))

original=(M/'tables/r37-reconstruction.tex').read_text(encoding='utf8')
for record in a.parse_record_index():
 k=record['id']
 if k not in scope:continue
 previous=''.join('-' if x=='--' else x for x in old[k]['cells'])
 current=''.join('-' if x=='--' else x for x in cells[k]['cells'])
 # Replace by position, not globally: identical strings can occur on different records.
 position=next(i for i,r in enumerate(a.parse_record_index()) if r['id']==k)
 lines=original.splitlines()
 lineindex=next(i for i,l in enumerate(lines) if f"{position+1:02d} & " in l)
 line=lines[lineindex];start=line.index(f"{position+1:02d} & ");end=line.index('}',start)+1
 fragment=line[start:end];assert r'\texttt{'+previous+'}' in fragment
 lines[lineindex]=line[:start]+fragment.replace(r'\texttt{'+previous+'}',r'\texttt{'+current+'}')+line[end:]
 original='\n'.join(lines)+'\n'
original=original.replace('Complete record-cell and pair index.','Complete current record-cell and pair index. R8 uses the outcome-specific applicability rule; the original 351 cells remain archived.')
write(M/'tables/r41-reconstruction.tex',original)
