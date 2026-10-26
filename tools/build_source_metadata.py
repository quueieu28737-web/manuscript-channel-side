"""Separate cited publication metadata, inspected version and evidence scope.

Metadata are not a quality score. Existing source judgments are unchanged.
Run offline; no claim of a new exhaustive venue search.
"""
from pathlib import Path
import csv, json, re, hashlib
from collections import Counter
import audit_check as a
M=Path(__file__).resolve().parents[1]; D=M/'data'
def save(n,x): (D/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def bibparse(t):
 out={}
 for match in re.finditer(r'@(\w+)\s*\{\s*([^,]+),',t):
  pos=match.end();depth=1;j=pos
  while j<len(t) and depth:
   if t[j]=='{' and (j==0 or t[j-1]!='\\'):depth+=1
   if t[j]=='}' and (j==0 or t[j-1]!='\\'):depth-=1
   j+=1
  assert depth==0
  fields={};body=t[pos:j-1];k=0
  while k<len(body):
   f=re.search(r'(\w+)\s*=\s*',body[k:])
   if not f:break
   name=f[1].lower();k+=f.end();start=k
   if body[k]=='{':
    d=1;k+=1;start=k
    while k<len(body) and d:
     if body[k]=='{' and body[k-1]!='\\':d+=1
     if body[k]=='}' and body[k-1]!='\\':d-=1
     k+=1
    value=body[start:k-1]
   elif body[k]=='"':
    k+=1;start=k
    while k<len(body) and (body[k]!='"' or body[k-1]=='\\'):k+=1
    value=body[start:k];k+=1
   else:
    end=body.find(',',k);end=len(body) if end<0 else end;value=body[k:end];k=end
   fields[name]=value.strip()
  out[match[2].strip()]={'entry_type':match[1].lower(),**fields}
 return out
entries={};hashes={}
for p in sorted(M.glob('refs*.bib')):
 part=bibparse(p.read_text());assert not (entries.keys()&part.keys()),'duplicate keys';entries.update(part)
 hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
known={r['family']:r for r in json.loads((D/'publication-strata.json').read_text())['families']}
families=list(csv.DictReader((D/'family-index.csv').open(encoding='utf-8-sig',newline='')))
assert len(families)==82
fmeta=[]
for r in families:
 b=entries[r['citation_key']];venue=b.get('booktitle',b.get('journal',''))
 if b['entry_type']=='inproceedings' or (venue and not re.search(r'arxiv|preprint',venue,re.I)):
  kind='venue_publication_listed'
 elif re.search(r'arxiv|preprint',venue+' '+b.get('url',''),re.I):kind='preprint_cited'
 else:kind='web_or_other'
 fmeta.append({'family':r['citation_key'],'classification':r['classification'],'cited_publication_status':kind,'bibliography_year':b.get('year'),'venue':venue,'cited_url':b.get('url'),'doi':b.get('doi'),'inspected_source_url':r['source_url'],'source_locators':r['source_locators'],'exact_version_review_status':'not inferred from family venue metadata','verification':known.get(r['citation_key'],{}).get('basis','Bibliographic metadata retained from the cited source; no new venue-level certification.'),'verification_url':known.get(r['citation_key'],{}).get('verification_url')})
byfamily={r['family']:r for r in fmeta};idx={r['id']:r for r in a.parse_record_index()};cells=a.parse_record_cells()
sources=json.loads((D/'record-source-metadata.json').read_text());ledger=[]
for r in sources:
 rid=r['record_id'];c=cells[rid];f=byfamily[r['family']]
 ledger.append({'record_id':rid,'family':r['family'],'scope':r['scope'],'cited_publication_status':f['cited_publication_status'],'venue':f['venue'],'bibliography_year':f['bibliography_year'],'inspected_source_url':r['source_url'],'source_locator':r['source_locator'],'archived_source_sha256':r['source_sha256_as_archived'],'measurement_mode':idx[rid]['mode'],'inference_binding':c['cells'][6],'utility_binding':c['cells'][7],'cost_binding':c['cells'][8],'protected_fit':c['cells'][3],'matched_adaptation':c['cells'][4],'incomplete_items':{f'R{j+1}':s for j,s in enumerate(c['cells']) if s in ('P','U','A','?')},'source_rationale':c['rationale'],'source_result_replication':'not assessed by publication metadata or this computational audit'})
save('source-status-ledger.json',{'scope':'Publication metadata for all 82 indexed families; exact-version source and multidimensional evidential limits for all 39 records. Publication metadata is not a paper-quality or replication score.','bibliography_hashes':hashes,'family_counts':dict(Counter(r['cited_publication_status'] for r in fmeta)),'record_counts':dict(Counter(r['cited_publication_status'] for r in ledger)),'families':fmeta,'records':ledger})
future=[{'key':k,'year':b.get('year'),'note':b.get('note'),'url':b.get('url')} for k,b in entries.items() if b.get('year','').isdigit() and int(b['year'])>2026]
assert [x['key'] for x in future]==['inputsnatch2024']
assert 'publisher citation year 2027' in future[0]['note']
save('bibliography-date-check.json',{'entries':len(entries),'future_citation_years':future,'inputsnatch_verification':{'checked':'2026-10-26','url':'https://link.springer.com/chapter/10.1007/978-981-92-4805-6_32','first_online':'2026-08-24','publisher_citation_year':2027,'action':'retain publisher year and explicit first-online note'},'scope':'Brace/key/URL-field/year check of bibliography plus primary-source check of the future-year exception; not live metadata verification of every existing entry.'})
def tx(s):return s.replace('&',r'\&').replace('_',r'\_')
t=r'''\begin{longtable}{@{}p{.30\textwidth}p{.17\textwidth}p{.09\textwidth}p{.29\textwidth}@{}}
\caption{All record-level publication and evidence-scope entries. Venue means a venue-linked family in the cited bibliography; the inspected version may remain an author preprint. Modes are defined in the record index. I/U/C are inference/utility/cost bindings, not quality grades.}\label{tab:r33-source-status}\\
\toprule Record & Cited publication & Mode; I/U/C & Inspected version / source locator\\\midrule\endfirsthead
\toprule Record & Cited publication & Mode; I/U/C & Inspected version / source locator\\\midrule\endhead
\bottomrule\endfoot
'''
for r in ledger:
 ver=re.search(r'\d{4}\.\d{4,5}(?:v\d+)?',r['inspected_source_url'])
 version=ver[0] if ver else 'Source URL in ledger'
 stat={'venue_publication_listed':'Venue-linked','preprint_cited':'Preprint','web_or_other':'Web/other'}[r['cited_publication_status']]
 t+=tx(r['record_id']).replace('-',r'-\allowbreak{}')+r'~\cite{'+r['family']+'} & '+stat+' & '+r['measurement_mode']+'; '+ '/'.join(r[k] for k in ['inference_binding','utility_binding','cost_binding'])+' & '+tx(version+'; '+r['source_locator'])+r'\\'+'\n'
t+=r'\end{longtable}'+'\n';(M/'tables/r33-source-status.tex').write_text(t,encoding='utf8',newline='\n')
print(json.dumps({'families':len(fmeta),'records':len(ledger),'family_counts':dict(Counter(r['cited_publication_status'] for r in fmeta)),'future_year_exception':future},indent=2))
