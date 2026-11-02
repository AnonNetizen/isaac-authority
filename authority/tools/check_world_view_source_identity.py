"""Check physical source ownership without an active SDK root hiding the issue."""
import argparse,copy,gzip,hashlib,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_world_view as w
ROOT=w.ROOT;DIR=ROOT/'research/world_view/source_identity';MANIFEST=ROOT/'research/world_view_source_identity_v1.json'
def freeze():
    files={'a/main.lua':"RegisterMod('Physical Source Owner Fixture',1)\nF=dofile('mods/source-owner-b/main.lua')\n",'a/pick.lua':"return 'primary'\n",'b/main.lua':"error('Unused alternate provider placeholder')\n",'b/pick.lua':"return 'secondary'\n",'alternate.lua':"return function()return require('pick')end\n"}
    for name,code in files.items():w.parent.f.parent.frozen(DIR/name,code.encode())
    roots=[dict(root=(DIR/'a').relative_to(ROOT).as_posix(),display='mods/source-owner-a',sha256={n:w.parent.f.digest(DIR/'a'/n)for n in ['main.lua','pick.lua']}),dict(root=(DIR/'b').relative_to(ROOT).as_posix(),display='mods/source-owner-b',sha256={'main.lua':w.parent.f.digest(DIR/'alternate.lua'),'pick.lua':w.parent.f.digest(DIR/'b/pick.lua')},source_paths={'main.lua':(DIR/'alternate.lua').relative_to(ROOT).as_posix()})]
    c=dict(id='physical-alternate-resolves-own-module',source=(DIR/'a/main.lua').relative_to(ROOT).as_posix(),source_sha256=w.parent.f.digest(DIR/'a/main.lua'),modules=dict(entry=0,roots=roots),stores=['{}','{}'],steps=[w.ev('return F()')])
    w.parent.f.freeze_json(MANIFEST,dict(schema='world-source-identity-1',work_limit=10000000,timeout_seconds=5,cases=[c]));return c
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();c=freeze();a.output.mkdir(parents=True,exist_ok=False);artifacts=[];reports=[]
    for ref in [True,False,False]:
        artifact,result=w.invoke(MANIFEST,c,ref);artifacts.append(artifact);reports.append(result)
        assert artifact['returncode']==0 and not artifact['timed_out']and not artifact['output_limit_exceeded']and result['steps'][0]['values']==w.values('secondary')
        assert result['budget']['limit']==10000000 and not result['game_started']and not result['full_trace_enabled']
    assert reports[0]['semantic']==reports[1]['semantic']==reports[2]['semantic']and reports[0]['steps']==reports[1]['steps']==reports[2]['steps']
    result=dict(schema='world-source-identity-result-1',passed=True,reports=reports,artifacts=artifacts,manifest_sha256=w.parent.f.digest(MANIFEST),driver_sha256=w.parent.f.digest(Path(__file__)),binaries={p.relative_to(ROOT).as_posix():w.parent.f.digest(p)for p in[w.EXE,w.REF]})
    raw=json.dumps(result,separators=(',',':')).encode();(a.output/'result.json.gz').write_bytes(gzip.compress(raw,mtime=0));print(json.dumps(dict(passed=True,physical_source_owner='secondary',game_started=False)))
if __name__=='__main__':main()
