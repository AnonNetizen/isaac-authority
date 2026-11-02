"""Freeze layer/image identities with bounded providers; copy no game assets."""
import copy,hashlib,json,posixpath,struct,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.dont_write_bytecode=True
import run_sprite_state as s
from freeze_sprite_state import BoundedPath
from packed_resources import Archive,name_hash
ROOT=s.ROOT;OUT=ROOT/'research/texture_state/profile.json'

def freeze():
    original=s.e.v.s.o.load(ROOT/'research/resource_catalog.json');animation=s.e.v.s.o.load(s.PROFILE);game=Path(animation['game_root'])
    native=ROOT/'runs/packed-resources-j460-20261010-final/mod-runtime.json';evidence=s.e.v.s.o.load(native)['engine_api_preflight']
    assert evidence['probe_passed']and evidence['checks']['packed_replacement_cached_calls_two_contexts_and_canonical_control']and evidence['checks']['unverified_layer_and_image_refused']
    inventory={a['path']:a for a in evidence['resource_inventory']['resources']}
    for a in original['resources']:
        if a['kind']in ['sprite','image']:assert inventory[a['path']]==a
    known={};providers={};decoded={};images={};sprites=[]
    for a in animation['sprites']:
        for p in a['range_proofs']:
            for r in p['ranges']:known[(p['path'],r['offset'],r['bytes'])]=r['sha256']
    def packed(member):
        key=(member['archive'],member['entry'])
        if key in decoded:return decoded[key]
        path='resources/packed/'+member['archive'];p=game/path
        if path not in providers:
            a=Archive(p)
            with p.open('rb')as f:header=f.read(14)
            _,_,index,count=struct.unpack('<7sBIH',header)
            for at,size in [(0,14),(index,count*20)]:
                with p.open('rb')as f:f.seek(at);raw=f.read(size)
                assert len(raw)==size and hashlib.sha256(raw).hexdigest()==known[(path,at,size)]
            providers[path]=(a,index,count)
        a,index,count=providers[path];a.sha256=member['archive_sha256'];row=a.entries[name_hash(member['entry'])];at=row[2];end=min(n for n in [a.size,index,*[x[2]for x in a.entries.values()]]if n>at)
        assert row[3]==member['bytes']and row[4]==member['checksum']and 0<end-at<=4*1024**2
        bounded=copy.copy(a);bounded.path=BoundedPath(p,at,end);raw,_=bounded.read(member['entry']);assert hashlib.sha256(raw).hexdigest()==member['sha256']
        ranges=[]
        for offset,size in [(0,14),(index,count*20),(at,end-at)]:
            with p.open('rb')as f:f.seek(offset);data=f.read(size)
            assert len(data)==size;ranges.append(dict(offset=offset,bytes=size,sha256=hashlib.sha256(data).hexdigest()))
        proof=dict(path=path,archive_sha256_at_freeze=member['archive_sha256'],ranges=ranges)
        decoded[key]=(raw,proof);return raw,proof
    def add_image(path,raw,expected,proof=None):
        assert raw[:8]==b'\x89PNG\r\n\x1a\n'and raw[12:16]==b'IHDR'and hashlib.sha256(raw).hexdigest()==expected
        width,height=struct.unpack('>II',raw[16:24]);assert 0<width<=65535 and 0<height<=65535
        alias=path.split('/resources/',1)[1]if'/resources/'in path else path.removeprefix('resources/')
        image=dict(path=path,aliases=[alias],storage='packed'if proof else'loose',sha256=expected,bytes=len(raw),width=width,height=height,range_proofs=[proof]if proof else[])
        if path in images:assert images[path]==image
        else:images[path]=image
    for entry in original['resources']:
        if entry['kind']not in ['sprite','image']:continue
        members={m['entry']:m for m in entry.get('packed_entries',[])}
        if entry.get('storage')=='packed':
            for path,m in members.items():
                if path.endswith('.png'):
                    raw,proof=packed(m);add_image(path,raw,m['sha256'],proof)
            raw,_=packed(members[entry['path']])
        else:
            for item in entry['files']:
                data=(game/item['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==item['sha256']
                if item['path'].endswith('.png'):add_image(item['path'],data,item['sha256'])
            raw=(game/entry['path']).read_bytes()
        if entry['kind']=='sprite':
            xml=ET.fromstring(raw);sheets={int(x.attrib['Id']):posixpath.normpath(posixpath.join(posixpath.dirname(entry['path']),x.attrib['Path'].replace('\\','/')))for x in xml.findall('./Content/Spritesheets/Spritesheet')}
            layers=[dict(layer=int(x.attrib['Id']),image=sheets[int(x.attrib['SpritesheetId'])])for x in xml.findall('./Content/Layers/Layer')]
            canonical={p.casefold():p for p in images}
            for layer in layers:layer['image']=canonical[layer['image'].casefold()]
            assert all(x['image']in images for x in layers)and [x['layer']for x in layers]==entry['layers'],dict(sprite=entry['path'],missing=[x['image']for x in layers if x['image']not in images],layers=layers,expected=entry['layers'])
            sprites.append(dict(path=entry['path'],layers=layers))
    profile=dict(schema='frozen-texture-state-1',animation_profile_sha256=s.old.digest(s.PROFILE),evidence=[dict(path=p.relative_to(ROOT).as_posix(),sha256=s.old.digest(p))for p in [native,ROOT/'native/engine_api.cpp',ROOT/'research/resource_catalog.json',ROOT/'tools/packed_resources.py',Path(__file__)]],images=list(images.values()),sprites=sprites,
      api_contract=dict(source='https://wofsauge.github.io/IsaacDocs/rep/Sprite.html#replacespritesheet',checked='2026-10-16',replace_return='Repentance+ boolean: selected canonical image identity changed',native_return_equivalence_verified=False,rendering_verified=False))
    s.e.v.s.o.freeze_json(OUT,profile)
    print(json.dumps(dict(frozen=True,images=len(images),sprites=len(sprites),layers=sum(len(x['layers'])for x in sprites),copied_asset_bytes=0,whole_archives_rehashed=False)))
if __name__=='__main__':freeze()
