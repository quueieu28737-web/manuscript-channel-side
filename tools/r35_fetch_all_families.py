"""Retrieve bounded OpenAlex snapshots for the 20 frozen mitigation families."""
import concurrent.futures
import csv
import datetime
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

MANUSCRIPT = pathlib.Path(__file__).resolve().parents[1]
record = json.loads((MANUSCRIPT / 'data/reporting-patterns.json').read_text(encoding='utf-8'))
families = record['broad_adaptation_applicability']['R4']['strict']['eligible_ids']
with (MANUSCRIPT / 'data/family-index.csv').open(encoding='utf-8', newline='') as f:
    index = {row['citation_key']: row for row in csv.DictReader(f)}
overrides = {
    'earlybird2025': '10.1109/TIFS.2025.3622954',
    'gao2025iknow': '10.48550/arXiv.2505.06738',
    'hornetz2026tdxray': '10.1109/SP63933.2026.00170',
    'jeong2026wra': '10.48550/arXiv.2508.20282',
}

def get(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)

def worker(key):
    entry = {'family': key, 'frozen_source': index[key]['source_url']}
    m = re.search(r'arxiv\.org/(?:abs|html)/(\d{4}\.\d+)', entry['frozen_source'])
    doi = overrides.get(key) or ('10.48550/arXiv.' + m.group(1) if m else None)
    if not doi:
        entry['error'] = 'No identifier resolved from frozen source or manually verified override'
        return entry
    entry['doi_requested'] = doi
    entry['work_query'] = 'https://api.openalex.org/works/https://doi.org/' + doi
    try:
        work = get(entry['work_query'])
        entry['work'] = {k: work.get(k) for k in ('id', 'doi', 'display_name', 'cited_by_count', 'ids')}
        wid = work['id'].rsplit('/', 1)[-1]
        entry['citing_query'] = 'https://api.openalex.org/works?' + urllib.parse.urlencode({'filter':'cites:' + wid, 'per-page':'200', 'select':'id,doi,display_name,publication_date,primary_location,ids'})
        result = get(entry['citing_query'])
        entry['meta'] = result.get('meta')
        entry['results'] = result.get('results', [])
        entry['truncated'] = (entry['meta'] or {}).get('count', 0) > len(entry['results'])
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
        entry['error'] = f'{type(exc).__name__}: {exc}'
    return entry

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    entries = list(pool.map(worker, families))
output = {'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source':'OpenAlex; index incompleteness demonstrated by the prior pilot', 'entries':entries}
path = MANUSCRIPT / 'data/r35-openalex-20-families.json'
path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
for e in entries:
    print(e['family'], (e.get('work') or {}).get('id'), (e.get('meta') or {}).get('count'), len(e.get('results', [])), e.get('error', ''))
