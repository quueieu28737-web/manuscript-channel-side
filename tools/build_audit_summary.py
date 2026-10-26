"""Generate family summaries and bibliography sensitivity from fixed record judgments.

No source recoding or experiment rerun. Each family cell carries its record witnesses.
Run before audit_check.py and compilation. Joint queries remain record-local.
"""
from pathlib import Path
from collections import Counter
import json, re, hashlib
import audit_check as a
M=Path(__file__).resolve().parents[1]
def put(f,t):f.write_text(t,encoding='utf8',newline='\n')
def save(f,x):put(f,json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def h(f):return hashlib.sha256(f.read_bytes()).hexdigest()
cells=a.parse_record_cells();mit={k:v for k,v in cells.items() if not v['contextual']}
assert len(cells)==39 and len(mit)==33
f=M/'tables/family-audit-matrix.tex';old=f.read_text();names={}
for line in old.splitlines():
 if r'\cite{' in line and '&' in line:names[a.cite_key(line)]=line.split('&')[0].strip()
assert len(names)==20
agg={};witness=[]
for family in names:
 recs={k:v for k,v in mit.items() if v['family']==family};assert recs,family
 agg[family]=[]
 for j in range(9):
  col=[v['cells'][j] for v in recs.values()]
  status=next(s for s in a.PRECEDENCE if s in col);agg[family].append(status)
  witness.append({'family':family,'item':f'R{j+1}','status':status,'records':[{'id':k,'status':v['cells'][j],'source_scope':v['rationale']} for k,v in recs.items()]})
save(M/'data/family-record-witnesses.json',{'source':'tables/r19-record-audit.tex','source_sha256':h(M/'tables/r19-record-audit.tex'),'rule':'Existential availability projection B > P > ? > U > A > --; no cross-record configuration join','cells':witness})
text=old[:old.index('Family &')]+r'Family & R1 & R2 & R3 & R4 & R5 & R6 & R7 & R8 & R9\\\midrule'+'\n'
for family,label in names.items():
 formatted=[r'\textbf{'+s+'}' if s in ('B','P') else s for s in agg[family]]
 text+=label+' & '+' & '.join(formatted)+r'\\'+'\n'
bound=[sum(v[j]=='B' for v in agg.values()) for j in range(9)]
app=[sum(v[j]!='--' for v in agg.values()) for j in range(9)]
text+=r'\midrule Bound & '+' & '.join(map(str,bound))+r'\\'+'\nApplicable & '+' & '.join(map(str,app))+r'\\'+'\n'
text+=r'''\bottomrule\end{tabularx}
\par\smallskip\raggedright \textbf{B}: bound; \textbf{P}: partial; U: unreported in inspected scope; ?: unverified binding; --: inapplicable. Table~\ref{tab:audit-rules} defines R1--R9. Each cell is generated from the scoped records: B if any record is B, otherwise P, ?, U, A, then --. This availability summary retains a witness for every B; separate cells can refer to different configurations. NetEcho and Early Bird retain unresolved record-specific R5 bindings. Dangol's B in R5 is supported by stored capture; its live binding remains unresolved. S36 records the projection and its 13 corrections.
\end{table}
'''
text=text.replace('Per-family evidence bindings for all 20 evaluated-mitigation families.','Record-derived evidence availability for all 20 evaluated-mitigation families.')
put(f,text)

# Retain the exact old/new differences and their already archived source locators.
prior=json.loads((M/'data/family-summary-baseline.json').read_text())['cells'];changes=[]
assert set(prior)==set(names)
for family,before in prior.items():
 for j,(x,y) in enumerate(zip(before,agg[family])):
  if x!=y:changes.append({'family':family,'item':f'R{j+1}','old':x,'new':y,'records':next(w['records'] for w in witness if w['family']==family and w['item']==f'R{j+1}')})
assert len(changes)==13
save(M/'data/family-summary-reconciliation.json',{'record_judgments_changed':0,'family_cells_changed':13,'bound_counts':bound,'applicable_counts':app,'changes':changes})
table=r'''\begin{table}[ht]\centering\footnotesize
\caption{Family-summary reconciliation. Record-local judgments and all joint queries are unchanged. The old column is the pre-projection display.}\label{tab:r32-reconciliation}
\begin{tabular}{@{}llccp{.50\textwidth}@{}}\toprule
Family & Item & Old & Current & Record-local evidence retained\\\midrule
'''
for c in changes:
 reason='; '.join(r'\texttt{'+r['id'].replace('-',r'-\allowbreak{}')+'}: '+r['status'] for r in c['records'])
 table+=names[c['family']]+' & '+c['item']+' & '+c['old']+' & '+c['new']+' & '+reason+r'\\'+'\n'
table+=r'\bottomrule\end{tabular}\end{table}'+'\n';put(M/'tables/r32-reconciliation.tex',table)

# Fixed bibliography membership; all strata use the same record-level query rules.
pr=a.peer_reviewed_keys();groups={'all':mit,'venue':{k:v for k,v in mit.items() if v['family'] in pr},'other':{k:v for k,v in mit.items() if v['family'] not in pr}}
q={}
for name,items in a.QUERIES.items():
 q[name]={}
 for group,records in groups.items():
  out,eligible,joined=a.query(records,items)
  q[name][group]={'excluded':out,'eligible':eligible,'bound':len(joined),'bound_ids':joined}
 assert q[name]['all']['eligible']==q[name]['venue']['eligible']+q[name]['other']['eligible']
save(M/'data/publication-query-counts.json',{'group_families':{k:len({v['family'] for v in rs.values()}) for k,rs in groups.items()},'group_records':{k:len(rs) for k,rs in groups.items()},'queries':q})
table=r'''\begin{table}[ht]\centering\footnotesize
\caption{Bibliography-stratified joint queries: bound/eligible records, using identical applicability rules in both strata. Venue-linked: four families/five records; other cited versions: 16 families/28 records.}\label{tab:r32-publication}
\begin{tabular}{@{}lrrr@{}}\toprule
Query & All records & Venue-linked & Other cited versions\\\midrule
'''
for name,v in q.items():table+=name+' & '+' & '.join(f"{v[g]['bound']}/{v[g]['eligible']}" for g in groups)+r'\\'+'\n'
table+=r'\bottomrule\end{tabular}\end{table}'+'\n';put(M/'tables/r32-publication-strata.tex',table)

# Synchronize all current family summaries, including the supplement's reason table.
f=M/'sections/46-r8-sok-audit.tex';t=f.read_text()
t=t.replace('Following the source reconciliation in S34, R4 has 4 B, 5 P, 2 U and 9 inapplicable; R5 has 2 B, 2 P, 7 U and 9 inapplicable.', 'In the record-derived projection, R4 has 4 B, 5 P, 2 U and 9 inapplicable; R5 has 2 B, 2 ?, 7 U and 9 inapplicable.')
t=t.replace('NetEcho & B & P & U','NetEcho & B & ? & U').replace('Early Bird & B & P & U','Early Bird & B & ? & U')
t=t.replace('with 2 B (2/11), 2 P and 7 U','with 2 B (2/11), 2 ? and 7 U').replace('2/10, with 2 P and 6 U','2/10, with 2 ? and 6 U')
start=t.index('Across the 20 audited families,');dist=[]
for j in range(9):
 c=Counter(v[j] for v in agg.values());dist.append('R'+str(j+1)+' '+'/'.join(str(c[s]) for s in ['B','P','U','?','--']))
t=t[:start]+'Across the 20 audited families, the R1--R9 column distributions (B/P/U/?/inapplicable) are: '+'; '.join(dist)+'. Each column sums to 20. S36 documents the record-derived projection and its 13 changes; the earlier source-scope reconciliation remains archived in S34.\n'
put(f,t)
print(json.dumps({'family_changes':len(changes),'bound':bound,'applicable':app,'queries':q},indent=2))
