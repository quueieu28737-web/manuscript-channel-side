"""Version the saved-data auditor without changing frozen collection or tests."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from common import H,load,save,sha,now
p=H/'experiment/verify_collection.py'
assert sha(p)==load(H/'experiment/freeze.json')['files']['experiment/verify_collection.py']
text=p.read_text(encoding='utf-8')
a=text.index('def capture_records(raw):');b=text.index('def verify(',a)
text=text[:a]+'from capture_tcp_generation import capture_records\n\n'+text[b:]
old="            cap=streams[k]['records'];recs=w['records'][i]"
new="""            recs=w['records'][i]
            candidates=streams[k]
            assert candidates and recs
            chosen=min(candidates,key=lambda z:abs(z['records'][0][2]-recs[0][3]/1e9))
            cap=chosen['records']
            assert abs(cap[0][2]-recs[0][3]/1e9)<2.,'ambiguous TCP generation match'"""
assert text.count(old)==1;text=text.replace(old,new)
old="out={'status':'PASS','utc':now(),'run':run,'phase':phase,'episodes':len(results),'unknown':0,"
new="out={'status':'PASS','auditor_version':'v2: TCP-generation-aware independent reassembly','auditor_sha256':sha(__file__),'utc':now(),'run':run,'phase':phase,'episodes':len(results),'unknown':0,"
assert text.count(old)==1;text=text.replace(old,new)
text="import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))\n"+text
target=H/'verification/verify_collection_v2.py';assert not target.exists();target.write_text(text,encoding='utf-8',newline='\n')
save(H/'verification/capture-auditor-amendment.json',{'utc':now(),'stage':'Before formal cover collection; none auditing is in progress',
    'reason':'The long cover capture can reuse ephemeral port pairs. The original mapping by two ports can merge distinct TCP generations. Preserve the original auditor and use tcp.stream solely for independent evaluator reassembly.',
    'unchanged':'Every request/state/model/record check, every attack input, and every primary statistical rule. No packets, model outcomes or requests are replaced.',
    'old_auditor_sha256':sha(p),'new_auditor_sha256':sha(target),'decoder_sha256':sha(H/'verification/capture_tcp_generation.py')})
print(sha(target))
