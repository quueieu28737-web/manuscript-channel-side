"""Reconstruct the 351 record cells and 133 archived pair labels without recoding."""
from pathlib import Path
from collections import Counter
import csv,hashlib,json
import audit_check as audit
M=Path(__file__).resolve().parents[1]
def rows(name):
 with (M/'data'/name).open(encoding='utf8',newline='') as f:return list(csv.DictReader(f))
records=rows('record-scopes.csv');index=audit.parse_record_index();cells=audit.parse_record_cells()
assert len(records)==39 and [r['record_id'] for r in records]==[r['id'] for r in index]
n={r['record_id']:i+1 for i,r in enumerate(records)}
groups={'traffic-envelope':'T','cache-service':'C','local-memory':'L','behavioral-humanization':'B','generator-fingerprint':'G','fixed-instruction':'F','access-control':'A','contention-noise':'N','filter-created-view':'V'}
assert set(groups)=={r['cohort'] for r in records}
pairs=[r for r in rows('pair-inventory.csv') if r['related_subset']=='true']; assert len(pairs)==133
by={r['record_id']:r for r in records}
for x in pairs: assert by[x['left_unit']]['cohort']==by[x['right_unit']]['cohort']==x['cohort']
def edge(x):return tuple(sorted((n[x['left_unit']],n[x['right_unit']])))
labelmap={'COMPATIBLE':'M','INCOMPATIBLE':'D','UNRESOLVED':'U'}
edges={edge(x):labelmap[x['descriptive']] for x in pairs};assert len(edges)==133 and Counter(edges.values())=={'M':17,'D':105,'U':11}
same=[edge(x) for x in pairs if x['same_family']=='true'];diff=[edge(x) for x in pairs if x['same_family']=='true' and x['descriptive']=='INCOMPATIBLE']; assert len(same)==15 and len(diff)==8
reconstructed={}
for i,a in enumerate(records):
 for b in records[i+1:]:
  if a['cohort']==b['cohort']:
   e=(n[a['record_id']],n[b['record_id']]);reconstructed[e]='M' if edges.get(e)=='M' else 'U' if edges.get(e)=='U' else 'D'
assert reconstructed==edges
assert sum(len(cells[r['record_id']]['cells']) for r in records)==351
out={'record_order':[{'index':n[r['record_id']],'record_id':r['record_id'],'cohort':r['cohort'],'cells':cells[r['record_id']]['cells']} for r in records],'pairs':[{'indices':list(e),'label':edges[e]} for e in sorted(edges)],'same_family_different':[list(e) for e in sorted(diff)],'input_sha256':{f:hashlib.sha256((M/f).read_bytes()).hexdigest() for f in ['data/record-scopes.csv','data/pair-inventory.csv','tables/r19-record-audit.tex','tables/r9-record-index.tex']}}
(M/'data/r37-reconstruction.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf8',newline='\n')
def cell(r):
 vals=cells[r['record_id']]['cells'];return ''.join('-' if x=='--' else x for x in vals)
def nums(lab):return [e for e in sorted(edges) if edges[e]==lab]
def fmt(es):return ', '.join(r'\mbox{%02d/%02d}' % e for e in es)
tex=r"""\begin{table*}[t]\centering\footnotesize
\caption{Complete record-cell and pair index. Numbers follow Appendix~\ref{app:records}, reading the left block (01--20) then the right block (21--39). Each nine-character string gives R1--R9 in order; B/P/U/A/?/-- use Table~\ref{tab:audit-rules}. The single hyphen in a string means inapplicable. Cohorts T traffic, C cache, L local memory, B behavioral, G generator, F fixed instruction, A access gate, N contention, V filter-created view.}\label{tab:r37-reconstruction}
\begin{tabular}{@{}rcl@{\hspace{12pt}}rcl@{\hspace{12pt}}rcl@{\hspace{12pt}}rcl@{}}\toprule
No. & Group & R1--R9 & No. & Group & R1--R9 & No. & Group & R1--R9 & No. & Group & R1--R9\\\midrule
"""
for i in range(10):
 chunks=[]
 for offset in (0,10,20,30):
  j=offset+i
  if j>=len(records):chunks.append(' & & ');continue
  r=records[j];chunks.append(r'%02d & %s & \texttt{%s}'%(j+1,groups[r['cohort']],cell(r)))
 tex+=' & '.join(chunks)+r'\\'+'\n'
tex+=r"""\bottomrule\end{tabular}
\par\smallskip\raggedright R1 target, R2 receiver, R3 intervention, R4 protected fitting, R5 matched fitting, R6 workload, R7 inference, R8 utility, R9 cost; B bound, P partial, U unreported, A unavailable, ? unverified, - inapplicable.\par Within each nonsingleton group, every unordered pair is included. The 17 scoped-match pairs are: """+fmt(nums('M'))+r""". The 11 unresolved pairs are: """+fmt(nums('U'))+r""". The remaining 105 within-group pairs have a different-object witness; the three singleton groups yield no pairs. Match refers to the specified object, not universal equality of costs, populations or contracts.
\par The eight different-object pairs within a family are: """+fmt(sorted(diff))+r""". All 351 cells and 133 within-group labels are recoverable here; individual source rationales remain in Supplement S29 and S34.
\end{table*}
"""
(M/'tables/r37-reconstruction.tex').write_text(tex,encoding='utf8',newline='\n')
print('RECONSTRUCTION_PASS: 39 records, 351 cells, 133 pairs, 17/105/11, 8 within-family')
