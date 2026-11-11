"""Fix an observed early-wakeup dev failure without relaxing its check."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from common import H,load,save,sha,now
old=H/'experiment/collect_cover_v2.py';text=old.read_text(encoding='utf-8')
helper='''async def sleep_not_before(seconds):
    deadline=time.perf_counter_ns()+max(0,int(seconds*1e9))
    while True:
        remaining=(deadline-time.perf_counter_ns())/1e9
        if remaining<=0:return
        await asyncio.sleep(remaining)

'''
needle='class HoldPaddedTool:';assert text.count(needle)==1;text=text.replace(needle,helper+needle)
needle='await asyncio.sleep(delay)';assert text.count(needle)==1;text=text.replace(needle,'await sleep_not_before(delay)')
needle="await asyncio.sleep(max(0.,gap-(time.perf_counter_ns()-anchor['end_ns'])/1e9))"
assert text.count(needle)==1;text=text.replace(needle,"await sleep_not_before(max(0.,gap-(time.perf_counter_ns()-anchor['end_ns'])/1e9))")
needle="await asyncio.sleep(meta['offset_s'])";assert text.count(needle)==1;text=text.replace(needle,"await sleep_not_before(meta['offset_s'])")
text=text.replace('cover-freeze-v2.json','cover-freeze-v3.json').replace('cover-freeze-pushed.json','cover-freeze-v3-pushed.json')
dst=H/'experiment/collect_cover_v3.py';assert not dst.exists();dst.write_text(text,encoding='utf-8',newline='\n')
checker=(H/'verification/check_dispatcher_v2.py').read_text(encoding='utf-8')
checker=checker.replace('development-cover-v2','development-cover-v3').replace('cover-v2-readiness','cover-v3-readiness').replace('collect_cover_v2','collect_cover_v3').replace('COVER_V2','COVER_V3')
(H/'verification/check_dispatcher_v3.py').write_text(checker,encoding='utf-8',newline='\n')
save(H/'verification/cover-amendment-v3.json',{'utc':now(),'stage':'Before any formal cover; only development fixtures used',
    'observed_failure':'One development concurrent wait dispatched 7.5843 ms before the sampled perf-counter deadline after asyncio.sleep returned. The one-millisecond readiness tolerance is retained.',
    'failure_log_sha256':sha(H/'private-run/stage-advance-v2/check-cover-dispatcher-v2.stderr.log'),
    'fix':'Use a perf_counter_ns not-before loop around asyncio.sleep for sampled gaps, server holds and shadow start offsets. This corrects timer early wakeups rather than widening acceptance tolerance.',
    'previous_collector_sha256':sha(old),'collector_sha256':sha(dst),
    'unchanged':'No formal episode, fixture, model, attack or statistical rule changed. The four terminal development v2 episodes remain preserved and excluded from scientific denominators.'})
print(sha(dst))
