"""Read-only binding of the exact preexisting inputs; individual paths stay local."""
import argparse, hashlib, json
from pathlib import Path
from common_local import sha, save, now

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    out=a.out/'LOCAL-ONLY-input-manifest.json'
    assert not out.exists(),'Preserve original input seal'
    files={}
    for run in ['formal-none-v1','formal-cover-v1']:
        root=a.live_dir/'private-run'/run
        results=sorted((root/'episodes').glob('*/result.json'))
        assert len(results)==(600 if run=='formal-none-v1' else 2400)
        for p in results:
            files[p.relative_to(a.live_dir).as_posix()]=sha(p)
            conns=sorted((p.parent/'connections').glob('*.json'));assert len(conns)==7
            for c in conns:
                w=root/'wire'/c.name
                files[c.relative_to(a.live_dir).as_posix()]=sha(c)
                files[w.relative_to(a.live_dir).as_posix()]=sha(w)
    for n in ['results.json','predictions.csv','validation-selection.json']:
        p=a.live_dir/'analysis'/n;files[p.relative_to(a.live_dir).as_posix()]=sha(p)
    save(out,{'utc':now(),'live_root':str(a.live_dir.resolve()),'files':files,'scope':'LOCAL ONLY; source bytes bound before new diagnostic scores'})
    print('Sealed',len(files),'input files;',sha(out),flush=True)
if __name__=='__main__':main()
