"""Check the published R101 evidence subset without network access or model fits."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json

H = Path(__file__).resolve().parent
read = lambda p: list(csv.DictReader(p.open(encoding='utf-8-sig', newline='')))
load = lambda p: json.loads(p.read_text(encoding='utf8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
release = H.parent
for name, record in load(release / 'manifest.json')['files'].items():
    p = (release / name).resolve()
    assert p.is_relative_to(release.resolve()) and sha(p) == record['sha256'], name
source_path = H / 'field-map/evidence-matrix.csv'
source = {r['setting_id']: r for r in read(source_path)}
rows = read(H / 'transfer-synthesis/setting-availability.csv')
summary = load(H / 'transfer-synthesis/availability-summary.json')
assert sha(source_path) == summary['input_sha256']
assert len(source) == len(rows) == 44
assert len({r['source_key'] for r in rows}) == 15
assert {r['setting_id'] for r in rows} == set(source)
for r in rows:
    s = source[r['setting_id']]
    for a, b in [('source_key', 'source_key'), ('source_version', 'source_version'),
                 ('access_basis', 'observer_access'), ('adaptation_basis', 'protected_attacker_adaptation'),
                 ('utility_basis', 'utility_cost_link'), ('locator', 'locator'), ('primary_url', 'primary_url')]:
        assert r[a] == s[b], (r['setting_id'], a)
for field, key in [('access_class', 'access'), ('intervention_purpose', 'purposes')]:
    counts = Counter(r[field] for r in rows)
    assert set(counts) == set(summary[key])
    for category, n in counts.items():
        assert summary[key][category] == {'settings': n, 'sources': len({r['source_key'] for r in rows if r[field] == category})}
q = [r for r in rows if r['intervention_purpose'] == 'query_workflow_privacy']
assert {r['setting_id'] for r in q} == {'WRA-decoy', 'WRA-visibility', 'CG-transform', 'CG-live'}
a = {r['setting_id'] for r in q if r['adaptation_status'] == 'located'}
u = {r['setting_id'] for r in q if r['original_task_utility_status'] == 'located'}
assert a == {'CG-transform', 'CG-live'} and u == {'WRA-visibility'} and not (a & u)
assert summary['query_workflow_privacy']['adaptation_located'] == sorted(a)
assert summary['query_workflow_privacy']['original_task_utility_located'] == sorted(u)
assert summary['query_workflow_privacy']['both_located'] == []
for r in rows:
    if r not in q:
        assert r['adaptation_status'] == r['original_task_utility_status'] == 'outside_selected_denominator'
matrix = read(H / 'transfer-synthesis/transfer-matrix.csv')
assert len(matrix) == 6
for r in matrix:
    assert set(r['agent_settings'].split(';')) <= set(source)
    assert r['relation'] in {'retained', 'extended', 'access_mismatch', 'untested_generalization'}
    assert all(r[k] for k in ['classical_condition', 'anchors', 'mapping', 'evidence', 'unresolved'])
print(json.dumps({'status': 'PASS', 'scope': 'Published-file integrity and descriptive evidence arithmetic; not semantic source verification or experimental rerunning.',
                  'settings': 44, 'sources': 15, 'transfer_rows': 6,
                  'eligible_privacy_settings': len(q), 'adaptation': len(a),
                  'original_task_utility': len(u), 'both': len(a & u)}, indent=2))
