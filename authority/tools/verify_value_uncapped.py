"""Read-only verification of a completed one-off uncapped measurement."""
import gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import measure_value_uncapped as m

def main():
    s=m.load(m.OUT/'summary.json');d=m.load(m.BASE/'derivation.json')
    assert s['cases']==49 and s['measurement_valid'] and not s['real_initialization_completed']
    assert m.digest(m.EXE)==s['binary_sha256'] and m.digest(m.MANIFEST)==s['manifest_sha256']
    assert m.digest(Path(m.__file__))==s['driver_sha256'] and m.digest(m.BASE/'derivation.json')==s['derivation_sha256']
    assert m.digest(m.GEN/'CMakeLists.txt')==d['cmake_sha256']
    assert m.digest(m.ROOT/'build-read-set/Release/read_lua.lib')==d['lua_sha256']
    for name,x in d['changes'].items():
        assert m.digest(m.GEN/name)==x['sha256'] and m.digest(m.ROOT/x['source'])==x['source_sha256']
    assert m.load(m.BASE/'protected-before.json')==m.protected()
    raw=gzip.decompress((m.OUT/'result.json.gz').read_bytes())
    assert hashlib.sha256(raw).hexdigest()==s['raw_sha256'] and m.digest(m.OUT/'result.json.gz')==s['result_sha256']
    r=json.loads(raw);assert r['complete'] and len(r['cases'])==49
    for c in r['cases']:
        p=c['measurement']['report'];assert c['measurement_valid'] and all(x['passed']for x in c['checks'])
        assert p['budget']['limit']is None and not p['resource_quotas_enabled'] and not p['full_trace_enabled'] and not p['game_started']
        assert p['budget']['used']==sum(p['budget']['categories'].values())
        if c['group']=='real':
            assert not c['completed'] and ('GetItemConfig'if c['id']=='real--eid'else'DebugString')in p['first_unsupported_entry']
    control=m.load(m.OUT/'separation-controls.json');assert all(x['verified']for x in control['cases'])
    print(json.dumps(dict(artifact_integrity_verified=True,measurement_valid=True,cases=49,completed=45,real_initialization_completed=False,formal_files_unchanged=True,game_started=False)))
if __name__=='__main__':main()
