"""Local R102 paths and deterministic serialization; no remote credentials."""
from pathlib import Path
import datetime, hashlib, json, os, site, sys

H = Path(__file__).resolve().parents[1]
ROOT = H.parent.parent
PR = H / 'pr4'
for p in [H.parent/'r98-feedback-interventions/private-runtime',
          H.parent/'r97-concurrent-mcp/private-runtime']:
    site.addsitedir(str(p))
sys.path.insert(0, str(H/'inputs'))
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'

def enc(x):
    return json.dumps(x, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def save(p, x):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    with tmp.open('wb') as f:
        f.write(enc(x) + b'\n'); f.flush(); os.fsync(f.fileno())
    tmp.replace(p)

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def log(p, x):
    with Path(p).open('ab') as f:
        f.write(enc(x)+b'\n'); f.flush()

def canonical(x):
    return json.loads(enc(x))
