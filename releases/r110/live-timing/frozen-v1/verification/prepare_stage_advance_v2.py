"""Resume post-collection checks using the corrected capture audit only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from common import H,load,save,sha,now
old=H/'verification/advance_to_pools.py';text=old.read_text(encoding='utf-8')
assert load(H/'private-run/stage-advance/verify-formal-none.exit.json')['returncode']==1
assert (H/'private-run/formal-none-v1/finished.json').exists()
text=text.replace("stage-advance'","stage-advance-v2'")
needle="path('experiment/verify_collection.py'),'formal-none-v1'"
assert text.count(needle)==1;text=text.replace(needle,"path('verification/verify_collection_v2.py'),'formal-none-v1'")
target=H/'verification/advance_to_pools_v2.py';assert not target.exists();target.write_text(text,encoding='utf-8',newline='\n')
root=H/'private-run/formal-none-v1/wire'
ids=['0112927890ca4623af16081a48de96b9','96fa3244610e4f81841b80e1ea740ca5']
proof=[]
for i in ids:
    w=load(root/(i+'.json'));proof.append({'wire_id':i,'service':w['service'],'peer':w['peer'],
        'backend_client_port':w['backend_client_port'],'first_record_epoch_ns':w['records'][0][0][3],
        'upstream_records':len(w['records'][0]),'raw_sha256':sha(root/(i+'.json'))})
assert proof[0]['service']==proof[1]['service'] and proof[0]['peer']==proof[1]['peer']
assert proof[0]['first_record_epoch_ns']!=proof[1]['first_record_epoch_ns']
save(H/'verification/none-capture-audit-failure-investigation.json',{'utc':now(),
    'status':'Port-pair collision demonstrated; corrected generation-aware full audit pending',
    'failure_log_sha256':sha(H/'private-run/stage-advance/verify-formal-none.stderr.log'),
    'unchanged_capture_sha256':sha(H/'private-run/formal-none-v1/capture/traffic.pcapng'),
    'collision':proof,'continuation_script_sha256':sha(target),
    'change':'Only saved-data transport reassembly is corrected. No collector, raw datum, fixture, model, hypothesis, terminal outcome or request is retried or replaced.'})
print(sha(target))
