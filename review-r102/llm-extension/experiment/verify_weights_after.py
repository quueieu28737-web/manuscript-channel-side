"""Re-hash every model manifest/config/template/weight at collection completion."""
import os
from pathlib import Path
from common import H, load, sha, save, now

assert (H/'private-run/formal-v1/finished.json').exists()
root=Path(os.environ['USERPROFILE'])/'.ollama/models'
before=load(H/'verification/weights-before.json');after=[]
for m in before['models']:
    name,tag=m['model'].split(':');p=root/'manifests/registry.ollama.ai/library'/name/tag
    manifest=load(p);layers=[]
    for layer in [manifest['config']]+manifest['layers']:
        blob=root/'blobs'/layer['digest'].replace(':','-');value=sha(blob)
        assert 'sha256:'+value==layer['digest']
        layers.append({'digest':layer['digest'],'sha256':value,'bytes':blob.stat().st_size,'mediaType':layer['mediaType']})
    item={'model':m['model'],'manifest_sha256':sha(p),'layers':layers};assert item==m;after.append(item)
target=H/'verification/weights-after.json';assert not target.exists()
save(target,{'utc':now(),'status':'PASS','models':after,'before_equals_after':True})
print('Both fixed local models and all supporting blobs unchanged')
