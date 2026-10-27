"""R33: reproduce granularity sensitivity and record-level query identities.

Uses fixed historical pair judgments; coarsening never creates new judgments.
Mixed groups retain all underlying statuses instead of majority voting.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv, hashlib, json, re
import audit_check as a

M=Path(__file__).resolve().parents[1]
D=M/'data'; T=M/'tables'
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def write(p,t): p.write_text(t,encoding='utf8',newline='\n')
def rows(p): return list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
def texid(s): return r'\texttt{'+s.replace('-',r'-\allowbreak{}')+'}'
idx={r['id']:r for r in a.parse_record_index()}; cells=a.parse_record_cells()
scopes={r['record_id']:r for r in rows(D/'record-scopes.csv')}
meta={r['record_id']:r for r in json.loads((D/'record-source-metadata.json').read_text())}
pairs=rows(D/'pair-inventory.csv')
related=[r for r in pairs if r['related_subset']=='true']
assert len(idx)==len(scopes)==len(meta)==39 and len(pairs)==741 and len(related)==133
assert set(idx)==set(cells)==set(scopes)==set(meta)
statuses=Counter(r['descriptive'] for r in related)
print('PAIR_STATUSES',dict(statuses))

def coarsen(name,key):
 groups=defaultdict(list); hidden=[]; memberships=defaultdict(list)
 for rid in idx: memberships[str(key(rid))].append(rid)
 for p in related:
  x,y=key(p['left_unit']),key(p['right_unit'])
  if x==y: hidden.append(p['pair_id']); continue
  groups[tuple(sorted((str(x),str(y))))].append(p)
 counts=Counter(); details=[]
 for g,ps in sorted(groups.items()):
  st=sorted({p['descriptive'] for p in ps}); result=st[0] if len(st)==1 else 'MIXED'
  counts[result]+=1
  details.append({'units':g,'judgment':result,'underlying_statuses':st,'pair_ids':[p['pair_id'] for p in ps]})
 return {'rule':name,'units':len(memberships),'projected_pairs':len(groups),'hidden_within_unit_pairs':hidden,'counts':dict(counts),'memberships':dict(memberships),'pairs':details}

variants=[coarsen('Scoped result records',lambda x:x),
 coarsen('Shared configuration package',lambda x:scopes[x]['configuration_package']),
 coarsen('Family and measurement mode',lambda x:(idx[x]['family'],idx[x]['mode'])),
 coarsen('Family only',lambda x:idx[x]['family'])]
save(D/'granularity-sensitivity.json',{'method':'Project fixed pair judgments onto coarser groups. A mixed edge retains conflicting statuses; internal edges become hidden, not corrected. Not a recoding, sampling CI or alternative full-paper evaluation.','input_hashes':{f:hashlib.sha256((D/f).read_bytes()).hexdigest() for f in ['pair-inventory.csv','record-scopes.csv']},'variants':variants})
tab=r'''\begin{table}[t]\centering\footnotesize
\caption{Sensitivity to the comparison unit. M/D/U: unanimous scoped match/different object/unresolved; Mix: constituent judgments differ. Hidden: original within-question pairs absorbed inside a unit. No new pair is adjudicated.}\label{tab:r33-granularity}
\begin{tabularx}{\columnwidth}{@{}Yrrrrrr@{}}\toprule
Unit & Units & M & D & U & Mix & Hidden\\\midrule
'''
for v in variants:
 c=v['counts']; tab+=v['rule']+' & '+str(v['units'])+' & '+' & '.join(str(c.get(k,0)) for k in ['COMPATIBLE','INCOMPATIBLE','UNRESOLVED','MIXED'])+' & '+str(len(v['hidden_within_unit_pairs']))+r'\\'+'\n'
tab+=r'\bottomrule\end{tabularx}\end{table}'+'\n';write(T/'r33-granularity.tex',tab)

bycohort=defaultdict(Counter)
for p in related: bycohort[p['cohort']][p['descriptive']]+=1
tab=r'''\begin{table}[t]\centering\footnotesize
\caption{The 133 within-question index labels; 608 other pairs have no declared comparison. A different-object witness limits a specified comparison, not all comparisons between the studies.}\label{tab:r33-pairs}
\begin{tabularx}{\columnwidth}{@{}Yrrr@{}}\toprule
Question & Scoped match & Different object & Unresolved\\\midrule
'''
for k,v in sorted(bycohort.items()): tab+=k.replace('-',' ')+' & '+' & '.join(str(v.get(s,0)) for s in ['COMPATIBLE','INCOMPATIBLE','UNRESOLVED'])+r'\\'+'\n'
tab+=r'\midrule Total & 17 & 105 & 11\\\bottomrule\end{tabularx}\end{table}'+'\n';write(T/'r33-pair-summary.tex',tab)

mit={k:v for k,v in cells.items() if not v['contextual']}; query_records={};membership=[]
for k,v in mit.items():
 row={'record_id':k,'family':v['family'],'configuration':scopes[k]['configuration_package'],'source_url':meta[k]['source_url'],'source_locator':meta[k]['source_locator']}
 for name,items in a.QUERIES.items():
  row[name]='B' if all(v['cells'][j-1]=='B' for j in items) else ('x' if any(v['cells'][j-1]=='--' for j in items) else 'E')
 membership.append(row)
for name,items in a.QUERIES.items():
 out,n,b=a.query(mit,items);query_records[name]={'excluded':out,'eligible':n,'bound_ids':b,'families':sorted({mit[k]['family'] for k in b}),'configurations':sorted({scopes[k]['configuration_package'] for k in b})}
save(D/'joint-query-identities.json',{'queries':query_records,'memberships':membership})
tab=r'''\begin{table*}[t]\centering\footnotesize
\caption{Positive joint results and exact record identities. All rows start from 33 mitigation records; a required inapplicable item excludes a record. Every outcome retains the source locator in Appendix~\ref{app:records}.}\label{tab:r33-positive}
\begin{tabularx}{\textwidth}{@{}p{.19\textwidth}p{.38\textwidth}Y@{}}\toprule
Requested evidence & Bound record IDs & Interpretation at the source configuration\\\midrule
Inference + utility (4/22) & AHB-online-executed; CACHEPRUNE-selective; CACHEPRUNE-context; SPARLEAK-replacement & Executed task outcomes or component quality; the two CachePrune targets share one package.\\
Inference + cost (5/22) & SPEC-padding-REST; DANGOL-capture; DANGOL-livebinding; both CACHEPRUNE records & Payload overhead, transformed-capture cost, loopback cost and serving cost remain distinct.\\
Adaptation + inference (2/17) & UI-delay-offline; DANGOL-capture & Matched clean/protected fitting on a defended test; no live-utility inference.\\
Inference + utility + cost (2/20) & CACHEPRUNE-selective; CACHEPRUNE-context & One family, one default configuration, two target outcomes.\\
All five items (0/14) & None in this extraction & A specified query has no bound record; no estimate of all published or unpublished evidence.\\
\bottomrule\end{tabularx}\end{table*}
''';write(T/'r33-positive-joins.tex',tab)
tab=r'''\begin{table*}[t]\centering\scriptsize
\caption{All 33 mitigation records: query membership. B: eligible and bound; E: eligible with at least one incomplete binding; x: required item inapplicable. IU=inference/utility; IC=inference/cost; AI=adaptation/inference; IUC=triple; All=R4/R5/R7/R8/R9. Full R1--R9 source rationales remain in S29.}\label{tab:r33-membership}
\begin{tabularx}{\textwidth}{@{}Yccccc@{}}\toprule
Record / cited family & IU & IC & AI & IUC & All\\\midrule
'''
for r in membership: tab+=texid(r['record_id'])+r'~\cite{'+r['family']+'} & '+' & '.join(r[q] for q in a.QUERIES)+r'\\'+'\n'
tab+=r'\bottomrule\end{tabularx}\end{table*}'+'\n';write(T/'r33-query-membership.tex',tab)

fams,_=a.parse_family_matrix();cross=[]
for f,fc in fams.items():
 if fc[6]=='B' and fc[8]=='B':
  rs={k:v for k,v in mit.items() if v['family']==f}
  cross.append({'family':f,'inference':[k for k,v in rs.items() if v['cells'][6]=='B'],'cost':[k for k,v in rs.items() if v['cells'][8]=='B'],'same_record':[k for k,v in rs.items() if v['cells'][6]==v['cells'][8]=='B']})
save(D/'family-to-joint-crosswalk.json',cross)
tab=r'''\begin{table*}[t]\centering\scriptsize
\caption{Every family with B in both inference and cost columns of Table~\ref{tab:family-audit}. Separate column witnesses do not automatically form one row-level result. IDs expand in Appendix~\ref{app:records}.}\label{tab:r33-crosswalk}
\begin{tabularx}{\textwidth}{@{}p{.14\textwidth}YYY@{}}\toprule
Family & Inference record(s) & Cost record(s) & Same-record inference + cost\\\midrule
'''
for r in cross:
 tab+=r'\cite{'+r['family']+'} & '+' & '.join('; '.join(texid(x) for x in r[k]) or '--' for k in ['inference','cost','same_record'])+r'\\'+'\n'
tab+=r'\bottomrule\end{tabularx}\end{table*}'+'\n';write(T/'r33-family-crosswalk.tex',tab)
print(json.dumps({'granularity':[{k:v[k] for k in ['rule','units','projected_pairs','counts']} for v in variants],'family_crosswalk':len(cross),'joint_queries':query_records},indent=2))
