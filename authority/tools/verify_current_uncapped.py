"""Read-only integrity checks; never starts the uncapped executable."""
import gzip, hashlib, json, sys
sys.dont_write_bytecode = True
import measure_current_uncapped as m

def main():
    final = m.load(m.OUT/'final.json')
    for group in ['inputs','binaries']:
        for name,h in final[group].items():
            assert m.old.digest(m.ROOT/name)==h, name
    summary=m.load(m.OUT/'summary.json')
    packed=m.OUT/'result.json.gz'
    assert m.old.digest(packed)==summary['report_sha256']
    data=gzip.decompress(packed.read_bytes())
    assert hashlib.sha256(data).hexdigest()==summary['raw_sha256']
    assert len(data)==summary['raw_bytes'] and len(packed.read_bytes())==summary['stored_bytes']
    result=json.loads(data)
    assert result['binary_sha256']==m.old.digest(m.EXE)
    assert result['manifest_sha256']==m.old.digest(m.MANIFEST)
    assert result['driver_sha256']==m.old.digest(m.Path(m.__file__))
    assert result['derivation_sha256']==m.old.digest(m.BASE/'derivation.json')
    assert len(result['cases'])==73 and sum(c['completed'] for c in result['cases'])==67
    assert all(c['measurement_valid'] and all(x['passed'] for x in c['checks']) for c in result['cases'])
    assert not result['real_initialization_completed'] and not result['automatic_projection_passed']
    assert result['formal_files_unchanged'] and result['save_files_unchanged'] and result['frozen_sources_unchanged']
    assert not result['full_trace_enabled'] and not result['game_started']
    assert result['excluded'][0]['id']=='module-work-cap'
    for row in result['cases']:
        r=row['measurement']['report']
        assert r['budget']['limit'] is None and r['budget']['used']==sum(r['budget']['categories'].values())
        assert not r['resource_quotas_enabled']
        if row['formal_control']:
            assert row['formal_control']['returncode']!=0
            assert row['formal_control']['report']['budget']['limit']==10000000
    byid={c['id']:c for c in result['cases']}
    on=byid['stress--million-reads']['measurement']['report']
    off=byid['stress--million-reads-no-values']['measurement']['report']
    assert on['budget']['used']==23000452 and off['budget']['used']==14000369
    assert on['metadata'][1]['source_capture']['created']==9
    assert on['metadata'][1]['source_capture']['live_records']==9
    assert m.m.compact.b.draws.ordinary(on)==m.m.compact.b.draws.ordinary(off)
    assert m.load(m.BASE/'protected-before.json')==m.protected()
    print(json.dumps(dict(artifact_integrity_verified=True,cases=73,native_execution_completed=67,
        real_initialization_completed=False,authority_projection_passed=False,formal_files_unchanged=True,
        uncapped_executable_started=False,report_bytes=summary['stored_bytes'],cleanup_bytes=final['cleanup_bytes'])))

if __name__=='__main__':main()
