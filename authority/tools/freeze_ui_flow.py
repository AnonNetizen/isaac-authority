"""Freeze ANM2 clock metadata using existing bounded resource proofs."""
import copy,hashlib,json,struct,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.dont_write_bytecode=True
import run_font_capture as f
from packed_resources import Archive,name_hash
from freeze_sprite_state import BoundedPath
ROOT=f.ROOT;OUT=ROOT/'research/ui_flow/profile.json'

def freeze():
    profile_path=ROOT/'research/sprite_state/profile.json';profile=f.load(profile_path);game=Path(profile['game_root']);catalog=f.load(ROOT/'research/resource_catalog.json');by_path={x['path']:x for x in catalog['resources']};archives={};sprites=[];checked=set()
    for a in profile['sprites']:
        source=by_path[a['path']]
        if a['storage']=='loose':
            p=game/a['path'];assert not p.is_symlink()and p.resolve().is_relative_to(game.resolve());raw=p.read_bytes();proof=next(x for x in source['files']if x['path']==a['path']);assert hashlib.sha256(raw).hexdigest()==proof['sha256']
        else:
            target=next(x for x in source['packed_entries']if x['entry']=='resources/'+source['engine_path']);path=game/'resources/packed'/target['archive'];assert not path.is_symlink()and path.resolve().is_relative_to(game.resolve())
            for proof in a['range_proofs']:
                provider=game/proof['path']
                for r in proof['ranges']:
                    key=(str(provider),r['offset'],r['bytes'])
                    if key in checked:continue
                    assert 0<r['bytes']<=4*1024*1024
                    with provider.open('rb')as stream:stream.seek(r['offset']);data=stream.read(r['bytes'])
                    assert hashlib.sha256(data).hexdigest()==r['sha256'];checked.add(key)
            if path not in archives:archives[path]=Archive(path)
            archive=archives[path];archive.sha256=target['archive_sha256'] # Historical label only; all current reads were checked against bounded proofs above.
            row=archive.entries[name_hash(target['entry'])];offset=row[2]
            proof=next(p for p in a['range_proofs']if p['path']=='resources/packed/'+path.name);region=next(r for r in proof['ranges']if r['offset']==offset);bounded=copy.copy(archive);bounded.path=BoundedPath(path,offset,offset+region['bytes']);raw,info=bounded.read(target['entry']);assert hashlib.sha256(raw).hexdigest()==target['sha256']
        root=ET.fromstring(raw);animations={}
        for clip in root.findall('./Animations/Animation'):
            name=clip.attrib['Name'];frames=int(clip.attrib['FrameNum']);loop=clip.attrib['Loop'];assert loop in ['true','false']and name in a['animations']and frames==a['animations'][name]['declared'];animations[name]=dict(frames=frames,loop=loop=='true')
        assert set(animations)==set(a['animations']);sprites.append(dict(path=a['path'],animations=animations,anm2_sha256=hashlib.sha256(raw).hexdigest()))
    result=dict(schema='frozen-ui-flow-1',rule='explicit-play-anm2-loop-clock-v1',main_sha256=profile['main_sha256'],animation_sha256=f.digest(profile_path),sprites=sprites,source_catalog_sha256=f.digest(ROOT/'research/resource_catalog.json'),freezer_sha256=f.digest(Path(__file__)),native_update_equivalence_verified=False,non_loop_terminal_verified=False,docs=['https://wofsauge.github.io/IsaacDocs/rep/Sprite.html','https://wofsauge.github.io/IsaacDocs/rep/Game.html'])
    f.freeze_json(OUT,result);print(json.dumps(dict(frozen=True,sprites=len(sprites),animations=sum(len(x['animations'])for x in sprites),whole_archive_hashing=False,copied_asset_bytes=0)))
if __name__=='__main__':freeze()
