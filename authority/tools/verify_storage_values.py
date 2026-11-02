"""Seal component evidence without promoting the failed playable/UI gates."""
import argparse,contextlib,gzip,hashlib,io,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];FINAL=ROOT/'reports/storage-values-final.json'
import verify_sparse_values
REPORTS={
 'storage':ROOT/'reports/storage-values-v5/result.json.gz',
 'regressions':ROOT/'reports/storage-values-world-regressions-v3/result.json.gz',
 'init':ROOT/'reports/storage-values-real-init-v3/result.json.gz',
 'required_hud':ROOT/'reports/storage-values-required-v2/projection/result.json.gz',
 'required_mixed':ROOT/'reports/storage-values-required-v2/mixed/result.json.gz',
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(gzip.decompress(p.read_bytes()))
def inputs():
    d=ROOT/'build-storage-value/generated/derived_sha256.json';m=json.loads(d.read_text())
    paths={d,ROOT/'reports/sparse-values-final.json',ROOT/'docs/STORAGE_VALUE_RESULTS.md',ROOT/'tools/check_storage_values.py',Path(__file__)}
    paths.update(ROOT/p for p in m['inputs']);paths.update(ROOT/p for p in m['outputs'])
    paths.update(p for p in (ROOT/'storage_value_runtime').iterdir()if p.is_file())
    paths.update(p for p in (ROOT/'research/storage_value').iterdir()if p.is_file())
    paths.update((ROOT/'build-storage-value/Release')/p for p in ['authority-storage-value.exe','authority-storage-value-reference.exe'])
    paths.update(REPORTS.values());return sorted(paths)
def verify():
    with contextlib.redirect_stdout(io.StringIO()):verify_sparse_values.verify()
    seal=json.loads(FINAL.read_text())
    for p,h in seal['files'].items():assert sha(ROOT/p)==h,('Changed sealed input',p)
    d={k:load(p)for k,p in REPORTS.items()}
    assert [len(d[k]['cases'])for k in ['storage','regressions','init']]==[28,35,3]
    assert all(d[k]['passed']for k in ['storage','regressions','init'])
    suite=json.loads((ROOT/'research/storage_value/suite-v5.json').read_text());spec={c['id']:c for c in suite['cases']}
    maxima=dict(seconds=0,work=0,private_commit_bytes=0)
    for name,r in d.items():
        for p,h in r['binaries'].items():assert sha(ROOT/p)==h
        for c in r['cases']:
            for p,a in zip(c['reports'],c['artifacts']):
                assert p and not a['timed_out']and not a['output_limit_exceeded']and not a['reader_failures']
                assert p['abi']=='ia-lua533-storage-value-1'and p['budget']['limit']==10000000 and p['budget']['used']<=10000000
                assert not p['game_started']and not p['full_trace_enabled']
                if'semantic'not in p:continue
                assert p['seconds']<5 and p['private_commit_bytes']<1024**3
                assert not p['automatic_projection_implemented']and not p['personal_draws_publishable']
                maxima['seconds']=max(maxima['seconds'],p['seconds']);maxima['work']=max(maxima['work'],p['budget']['used']);maxima['private_commit_bytes']=max(maxima['private_commit_bytes'],p['private_commit_bytes'])
                for g in p['sparse_provenance']:
                    if g is None:continue
                    s=g['storage_versions'];assert s['registered_write_versions']and not s['all_lua_storage_covered']and not s['consumer_cache_reuse_enabled']
                    assert s['tables']<=256 and s['fields']<=1024 and s['cells']<=256 and len(s['read_scopes'])<=128
                    assert len(g['nodes'])<=4096 and g['bytes']<=1024**2 and g['audit_files_read']==0
                    for scope in s['read_scopes']:assert not scope['all_inputs_captured']and not scope['cache_reuse_allowed']and len(scope['dependencies'])<=1024
                    for n in g['nodes']:assert all(a['tag']<n['id']for a in n.get('args',[]))
            if name in ['storage','regressions','init']:
                assert c['passed'];left,right=c['reports'][-2:];assert left['semantic']==right['semantic']and left['sparse_provenance']==right['sparse_provenance']
            if name=='storage':
                p=c['reports'][1];actual=[[bytes.fromhex(x['text_hex']).decode()for x in s['draws']]for s in p['steps']if'draws'in s]
                assert actual==[[]if x is None else[x]for x in spec[c['id']]['texts']]
                if not spec[c['id']].get('private_only'):assert c['reports'][0]['semantic']==p['semantic']and c['reports'][0]['steps']==p['steps']
    assert not d['required_hud']['passed']and not d['required_mixed']['passed']
    hud=d['required_hud']['cases'][0];assert[c['check']for c in hud['checks']if not c['passed']]==['exact-hud']
    assert d['required_mixed']['cases'][0]['reports'][1]['first_unsupported_entry']=='World write requires authority phase'
    found={c['id']:c for c in d['storage']['cases']}
    for id in ['lua-pcall-cannot-hide-evidence-exhaustion','expired-storage-receipt-is-not-reused','saved-scalar-does-not-read-original-field-again']:
        assert found[id]['passed']and all(found[id]['checks'].values())
    print(json.dumps(dict(integrity_verified=True,storage_and_read_cases=28,unchanged_world_api_cases=35,real_initialization_cases=3,required_functional_failures=2,maximum_completed_child=maxima,world_projection_gate_passed=False,all_lua_storage_covered=False,long_session_memory_bounded=False,playable=False)))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seal',action='store_true');a=p.parse_args()
    if a.seal:
        if FINAL.exists():raise RuntimeError('Preserved seal already exists')
        FINAL.write_text(json.dumps(dict(schema='storage-values-seal-1',abi='ia-lua533-storage-value-1',files={p.relative_to(ROOT).as_posix():sha(p)for p in inputs()},world_projection_gate_passed=False,playable=False),indent=2)+'\n')
    verify()
