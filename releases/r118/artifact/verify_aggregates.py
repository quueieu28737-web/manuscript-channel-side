"""Recompute released paired-test arithmetic; no individual observations needed."""
from pathlib import Path
import csv,hashlib,json,math
H=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def rows(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def paired(plus,minus):
    n=plus+minus
    return min(1.,2*sum(math.comb(n,i) for i in range(min(plus,minus)+1))/2**n) if n else 1.
def family(data):
    last=0.
    for rank,r in enumerate(sorted(data,key=lambda r:float(r['p_raw']))):
        plus,minus=int(r['condition_only']),int(r['reference_only'])
        assert plus>=0 and minus>=0 and plus+minus<=int(r['n'])==120
        p=paired(plus,minus);assert abs(p-float(r['p_raw']))<1e-12
        assert abs(100*(plus-minus)/120-float(r['difference_pp']))<1e-10
        last=max(last,min(1.,p*(len(data)-rank)));assert abs(last-float(r['p_holm']))<1e-12
    return len(data)
def main():
    identity=load(H/'portable-code-identity.json')
    for n,d in identity['aggregate_inputs'].items():assert hashlib.sha256((H/'p0'/n).read_bytes()).hexdigest()==d,n
    for n,d in identity['code'].items():assert hashlib.sha256((H/'experiment'/n).read_bytes()).hexdigest()==d,n
    for n,d in identity['dependencies'].items():assert hashlib.sha256((H/'dependencies'/n).read_bytes()).hexdigest()==d,n
    a=rows(H/'p0/p0a-tests.csv');assert len(a)==12
    checks=family([r for r in a if r['family']=='A'])+family([r for r in a if r['family']=='B'])
    c=rows(H/'p0/p0c-tests.csv');assert len(c)==8;checks+=family(c)
    for r in c:assert int(r['strong_correct'])-int(r['baseline_correct'])==int(r['condition_only'])-int(r['reference_only'])
    b=load(H/'p0/p0b-summary.json');checks+=family(b['R1'])
    last=0.
    for rank,r in enumerate(sorted(b['T2_selected'],key=lambda r:r['p_raw'])):
        p=paired(r['real'],r['shadow']);assert abs(p-r['p_raw'])<1e-12
        last=max(last,min(1.,p*(2-rank)));assert abs(last-r['p_holm'])<1e-12;checks+=1
    for n in ['p0a-attacks.csv','p0c-attacks.csv']:
        for r in rows(H/'p0'/n):assert 0<=int(r['validation_correct'])<=60 and 0<=int(r['test_correct'])<=120
    rep=rows(H/'p0/p0a-reproduction.csv');assert len(rep)==60
    assert all(all(r[k]=='True' for k in ['count_match','prediction_match','validation_match','selection_match']) for r in rep)
    sigtime=sum(float(r['p_holm'])<.05 for r in a if r['contrast']=='full_adaptive - no_time_adaptive')
    sigrecord=sum(float(r['p_holm'])<.05 and int(r['strong_correct'])>int(r['baseline_correct']) for r in c)
    assert sigtime==3 and sigrecord==5
    print(json.dumps({'status':'AGGREGATE_ARITHMETIC_VERIFIED','paired_or_conditional_tests':checks,'time_cells_significant':sigtime,'record_cells_improved_significantly':sigrecord,'full_reproduction_rows_reported':60,'scope':'Released aggregate/code identity and arithmetic only; no independent refitting, individual prediction, role-assignment or boundary reconstruction.'},indent=2))
if __name__=='__main__':main()
