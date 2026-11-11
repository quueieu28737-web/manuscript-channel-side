from pathlib import Path
import hashlib,json,zipfile
H=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=load(H/'manifest.json')
for n,r in manifest['files'].items():
    p=H/n
    assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],n
source=load(H/'checks/source-export-files.json')
with zipfile.ZipFile(H/'latex-source.zip') as z:
    assert z.testzip() is None and set(z.namelist())==set(source)
    for n,d in source.items():
        assert hashlib.sha256(z.read(n)).hexdigest()==sha(H/'source'/n)==d,n
assert load(H/'b1/verification.json')['status']=='PASS'
assert load(H/'b1/diagnostic/verification.json')['status']=='PASS'
c=load(H/'b1/results/comparisons.json')
assert len(c['primary_timing_size_vs_bytes'])==10
assert sum(x['p_holm']<.05 for x in c['primary_timing_size_vs_bytes'])==0
assert len(c['secondary_stripping_vs_bytes'])==10
assert sum(x['p_holm']<.05 for x in c['secondary_stripping_vs_bytes'])==10
d=load(H/'b1/results/cover-detection.json')
assert sum(x['tp'] for x in d)==1807 and sum(x['fn'] for x in d)==13
assert sum(x['fp'] for x in d)==0 and sum(x['tn'] for x in d)==6741
print(json.dumps(dict(status='PASS',files_verified=len(manifest['files']),source_files=len(source),primary_significant=0,secondary_significant=10,scope='File/arithmetic consistency; not independent human review or new collection.')))
