"""Pre-cover engineering amendment. Never edit the original frozen collector."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from common import H,load,save,sha,now

source=H/'experiment/collect.py'
assert sha(source)==load(H/'experiment/freeze.json')['files']['experiment/collect.py']
text=source.read_text(encoding='utf-8')
def replace(a,b):
    global text
    assert text.count(a)==1,a
    text=text.replace(a,b)

replace("self.seq=0;self.completed=[];self.cover_tasks=[];self.failure=None",
        "self.seq=0;self.completed=[];self.cover_tasks=[];self.failure=None\n        self.dispatch_queue=asyncio.Queue();self.dispatch_task=None\n    async def __aexit__(self,*args):\n        if self.dispatch_task is not None and not self.dispatch_task.done():\n            self.dispatch_task.cancel()\n            await asyncio.gather(self.dispatch_task,return_exceptions=True)\n        return await super().__aexit__(*args)")
replace("async def tool_call(st,job,tc,action,oid,kind,out,role='real',hold_s=0.,schedule=None):",
        "async def cover_dispatcher(tc):\n    try:\n        while True:\n            item=await tc.dispatch_queue.get()\n            if item is None:return\n            fn,decoy,trigger=item\n            await fn(decoy,trigger)\n    except BaseException as e:\n        tc.failure=e\n        raise\n\nasync def tool_call(st,job,tc,action,oid,kind,out,role='real',hold_s=0.,schedule=None):")
replace("        gap=hold=0.\n        if arm in ['gdm_live','concurrent']:",
        "        gap=hold=0.\n        anchor=max(tc.completed,key=lambda c:c['end_ns'])\n        if arm in ['gdm_live','concurrent']:")
replace("await asyncio.sleep(max(0.,gap-(time.perf_counter_ns()-trigger['end_ns'])/1e9))",
        "await asyncio.sleep(max(0.,gap-(time.perf_counter_ns()-anchor['end_ns'])/1e9))")
replace("{'index':decoy['index'],'trigger_request':trigger['request_id'],'target_gap_s':gap,'target_duration_s':hold}",
        "{'index':decoy['index'],'trigger_request':trigger['request_id'],'anchor_request':anchor['request_id'],'anchor_end_ns':anchor['end_ns'],'target_gap_s':gap,'target_duration_s':hold}")
replace("if arm=='concurrent':tc.cover_tasks.append(asyncio.create_task(one_cover(d,trigger)))",
        "if arm=='concurrent':tc.dispatch_queue.put_nowait((one_cover,d,trigger))")
replace("        admitted_at=time.time()",
        "        if arm=='concurrent':tc.dispatch_task=asyncio.create_task(cover_dispatcher(tc))\n        admitted_at=time.time()")
replace("        if tc.cover_tasks:await asyncio.gather(*tc.cover_tasks)",
        "        if tc.dispatch_task is not None:\n            tc.dispatch_queue.put_nowait(None)\n            await tc.dispatch_task\n        if tc.cover_tasks:await asyncio.gather(*tc.cover_tasks)")
replace("        if args.phase=='cover':\n            POOLS=load(H/'pools/timing-pools.json')",
        "        if args.phase=='cover':\n            amended=load(H/'experiment/cover-freeze-v2.json')\n            assert amended['parent_freeze_sha256']==sha(H/'experiment/freeze.json')\n            for p,d in amended['files'].items():assert sha(H/p)==d,p\n            assert load(H/'verification/cover-freeze-pushed.json')['freeze_sha256']==sha(H/'experiment/cover-freeze-v2.json')\n            POOLS=load(H/'pools/timing-pools.json')")
target=H/'experiment/collect_cover_v2.py';assert not target.exists();target.write_text(text,encoding='utf-8',newline='\n')
save(H/'verification/cover-amendment-v2.json',{
    'utc':now(),'stage':'Before any formal cover collection; formal none is already running under unchanged freeze v1',
    'original_collector_sha256':sha(source),'cover_collector_sha256':sha(target),
    'reason':'Two decoys may share a trigger. Referencing that trigger for both can skip the second sampled gap. Also replace per-cover detached tasks by the proposal\'s persistent episode-scoped sequential cover dispatcher.',
    'change':'In sequential matching, each cover waits relative to the latest completed call. Concurrent matching uses one persistent queue worker and anchors each queued cover at its dispatch-planning time; honest calls can overlap during its wait, so achieved global gaps need not match target draws.',
    'unchanged':'Fixtures, models, none arm, tool and state semantics, relay record timing, attack analysis and all statistical families. No existing request is replayed or replaced.',
    'gates':'Exercise the changed paths on development fixtures only, without competing with formal none on the GPU; freeze and push/read back v2 before formal cover.'})
print(sha(target))
