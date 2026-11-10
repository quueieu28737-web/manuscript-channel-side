"""Verify installed weights against the supplied identity record before rerun."""
import os
from pathlib import Path
from common import H,load,sha,save,now
expected=load(H/'verification/weights-before.json')
models=Path(os.environ['USERPROFILE'])/'.ollama/models'
for row in expected['models']:
    name,tag=row['model'].split(':')
    manifest=models/'manifests/registry.ollama.ai/library'/name/tag
    assert sha(manifest)==row['manifest_sha256'], 'Tag does not resolve to the fixed manifest'
    for layer in row['layers']:
        blob=models/'blobs'/layer['digest'].replace(':','-')
        assert sha(blob)==layer['sha256'] and blob.stat().st_size==layer['bytes']
save(H/'verification/runtime-model-check.json',{'utc':now(),'status':'PASS','models':[r['model'] for r in expected['models']]})
print('Installed models match the fixed source, template and weight identities')
