"""Review the uncapped measurement without hiding its strict-repeat failures."""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import measure_font_uncapped as m


def review():
    s = m.load(m.OUT / 'summary.json')
    packed = m.OUT / 'result.json.gz'
    raw = gzip.decompress(packed.read_bytes())
    assert m.digest(packed) == s['result_sha256']
    assert hashlib.sha256(raw).hexdigest() == s['raw_sha256']
    assert m.digest(m.EXE) == s['binary_sha256']
    assert m.digest(m.MANIFEST) == s['manifest_sha256']
    assert m.digest(Path(m.__file__)) == s['driver_sha256']
    assert m.digest(m.BASE / 'derivation.json') == s['derivation_sha256']
    assert m.protection() == m.load(m.BASE / 'protected-before.json')
    d = m.load(m.BASE / 'derivation.json')
    for name, item in d['changes'].items():
        assert m.digest(m.GEN / name) == item['sha256']
        assert m.digest(m.ROOT / item['source']) == item['source_sha256']
    assert all(m.digest(m.ROOT / p) == h for p, h in d['shared_libraries'].items())
    assert m.digest(m.GEN / 'CMakeLists.txt') == d['cmake_sha256']
    result = json.loads(raw)
    assert result['complete'] and len(result['cases']) == 113
    first = [x for x in result['cases'] if x['repeat'] == 1]
    repeats = [x for x in result['cases'] if x['repeat'] == 2]
    assert len(first) == 110 and all(x['measurement_valid'] for x in first)
    assert [x['id'] for x in first] == [x['id'] for x in m.load(m.MANIFEST)['cases']]
    assert len(repeats) == 3 and {x['group'] for x in repeats} == {'real'}
    for row in result['cases']:
        p = row['measurement']['report']
        assert p['measurement_only'] and not p['resource_quotas_enabled']
        assert not p['full_trace_enabled'] and not p['game_started']
        assert p['budget']['limit'] is None
        assert p['budget']['used'] == sum(p['budget']['categories'].values())
    exact = {}
    for row in repeats:
        prior = next(x for x in first if x['id'] == row['id'])
        a, b = [x['measurement']['report'] for x in [prior, row]]
        assert a['semantic'] == b['semantic'] and a['steps'] == b['steps']
        assert all(c['passed'] or c['check'] == 'repeat-same-state-steps-work' for c in row['checks'])
        exact[row['id']] = a['budget'] == b['budget']
        different = {k for k in a['budget']['categories'] if a['budget']['categories'][k] != b['budget']['categories'][k]}
        assert different <= {'vm_prepaid_instructions', 'consumer_reads'}
    measurements = []
    for case in first:
        if case['group'] not in ['real', 'stress']:
            continue
        group = [x for x in result['cases'] if x['id'] == case['id']]
        reports = [x['measurement']['report'] for x in group]
        measurements.append(dict(id=case['id'], executions=len(group),
            seconds=[min(p['seconds'] for p in reports), max(p['seconds'] for p in reports)],
            work=[min(p['budget']['used'] for p in reports), max(p['budget']['used'] for p in reports)],
            observed_peak_private_bytes=max(max(x['measurement']['sampled_peak_private_bytes'],
                x['measurement']['report']['peak_private_commit_bytes']) for x in group)))
    return dict(schema='font-uncapped-review-1', original_summary_sha256=m.digest(m.OUT / 'summary.json'),
                original_strict_verdict=s['measurement_valid'], original_strict_failures_preserved=True,
                first_pass_classified_checks=110, first_pass_all_checks_satisfied=True,
                repeated_real_states_equal=True, repeated_real_work_identical=exact,
                work_variation_categories=['vm_prepaid_instructions', 'consumer_reads'],
                exact_work_reproducibility_passed=all(exact.values()),
                measurements_valid=True, observations=measurements,
                memory_method='maximum of pre-report native peak and external 10ms samples; not a lifetime bound',
                formal_files_unchanged=True, game_started=False, full_trace_enabled=False,
                actual_menu_navigation_verified=False, drawing_capture_verified=False,
                arbitrary_mod_compatibility_verified=False, long_session_stability_verified=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-review', action='store_true')
    args = parser.parse_args()
    value = review()
    path = m.OUT / 'review.json'
    if args.write_review and not path.exists():
        m.save(path, value)
    else:
        assert m.load(path) == value
    print(json.dumps(value))
