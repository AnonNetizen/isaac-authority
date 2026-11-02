"""Preserve Slice3 and freeze the exact installed framework inputs, without game use."""
import argparse, hashlib, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def digest(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def start(game):
    target=ROOT/'slice3_ui_runtime'
    if target.exists(): raise ValueError('UI candidate already exists; refusing to replace frozen inputs')
    preserved={}
    for folder in ('slice3_runtime', 'research'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts: preserved[p.relative_to(ROOT).as_posix()]=digest(p)
    for name in ('artifacts/isaac-authority-slice3-0.1.0-verified.zip',
                 'build-slice3-release/Release/ia_lua533_slice3.dll',
                 'build-slice3-release/Release/authority-slice3-research.exe'):
        preserved[name]=digest(ROOT/name)
    (ROOT/'reports/slice3-ui-baseline.json').write_text(json.dumps({'schema':'slice3-ui-baseline-1','files':preserved},indent=2)+'\n')
    target.mkdir()
    for name in ('ia_graph.h','ia_graph.cpp','views.inc','prepare_lua.py','CMakeLists.txt'):
        shutil.copyfile(ROOT/'slice3_runtime'/name,target/name)
    p=target/'ia_graph.cpp';p.write_text(p.read_text().replace('return "ia-lua533-slice-3"','return "ia-lua533-slice3-ui-1"'),encoding='utf-8')
    p=target/'CMakeLists.txt';p.write_text(p.read_text().replace('SLICE3','SLICE3_UI').replace('ia_lua533_slice3','ia_lua533_slice3_ui').replace('authority-slice3-research ../trace_runtime/runner.cpp','authority-slice3-ui-research runner.cpp').replace('authority-slice3-research','authority-slice3-ui-research'),encoding='utf-8')
    p=target/'prepare_lua.py';p.write_text(p.read_text().replace('ia-lua533-slice-3','ia-lua533-slice3-ui-1'),encoding='utf-8')
    frozen=ROOT/'research/slice3_ui_inputs'
    mods=[]
    for relative in ('mods/mod_config_menu_cn_2494192799','mods/external item descriptions_836319872'):
        hashes={}
        for p in sorted((game/relative).rglob('*.lua')):
            rel=p.relative_to(game).as_posix();out=frozen/rel;out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,out);hashes[p.relative_to(game/relative).as_posix()]=digest(out)
        mods.append({'root':relative,'sha256':hashes})
    scripts={}
    for name in ('enums.lua','main.lua'):
        rel='resources/scripts/'+name;out=frozen/rel;out.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(game/rel,out);scripts[rel]=digest(out)
    catalog=json.loads((ROOT/'research/resource_catalog.json').read_text())
    manifest={'schema':'isaac-slice3-ui-inputs-1','private_abi':'ia-lua533-slice3-ui-1',
              'view_rule':'personal-settings-authority-hud-v1','original_game_root':str(game.resolve()),
              'mods':mods,'scripts':scripts,'resource_catalog':catalog,
              'resource_catalog_sha256':digest(ROOT/'research/resource_catalog.json'),
              'game_process_used':False,'modifications_to_installed_sources':False}
    out=ROOT/'research/slice3_ui_inputs.json';out.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'preserved_files':len(preserved),'lua_files':sum(len(m['sha256']) for m in mods),'inputs':str(out)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--game',type=Path,required=True)
    print(json.dumps(start(p.parse_args().game),indent=2))
