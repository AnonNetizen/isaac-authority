"""Freeze small font contracts and signatures; leave bytes in the installation."""
import hashlib,json,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_callback_framework as c
ROOT=c.ROOT;OUT=ROOT/'research/font_metrics/profile.json'

def metrics(raw):
    assert raw[:4]==b'BMF\x03';at=4;blocks={}
    while at<len(raw):
        kind,size=struct.unpack_from('<BI',raw,at);at+=5;assert kind in [1,2,3,4,5]and kind not in blocks and at+size<=len(raw);blocks[kind]=raw[at:at+size];at+=size
    assert set([1,2,3,4])<=blocks.keys()and len(blocks[2])==15 and len(blocks[4])%20==0 and len(blocks.get(5,b''))%10==0
    line,base,width,height,pages=struct.unpack_from('<HHHHH',blocks[2]);names=[p.decode('utf-8')for p in blocks[3].rstrip(b'\0').split(b'\0')];assert len(names)==pages
    glyphs={}
    for row in struct.iter_unpack('<IHHHHhhhBB',blocks[4]):
        char,x,y,w,h,ox,oy,advance,page,channel=row;assert char not in glyphs and page<pages;glyphs[char]=advance
    kern={}
    for a,b,n in struct.iter_unpack('<IIh',blocks.get(5,b'')):assert(a,b)not in kern;kern[a,b]=n
    assert 0<len(glyphs)<=65536 and line>0 and base<=line and not kern,'Current candidate only admits fonts without kerning records'
    wire=struct.pack('<HH',line,base)+b''.join(struct.pack('<Ih',i,n)for i,n in sorted(glyphs.items()))
    return dict(line_height=line,baseline=base,glyphs=len(glyphs),metrics_sha256=hashlib.sha256(wire).hexdigest(),pages=names),glyphs

def freeze():
    catalog_path=ROOT/'research/resource_catalog.json';catalog=c.t.s.e.v.s.o.load(catalog_path);game=Path(c.t.s.e.v.s.o.load(ROOT/'research/model_objects/resources.json')['game_root']);evidence=ROOT/'runs/runtime-suite-final-j460-20261010/mod-runtime.json';probe=c.t.s.e.v.s.o.load(evidence)['engine_api_preflight'];native={a['path']:a['widths'][0]for a in probe['font_roundtrips']};fonts=[]
    assert probe['probe_passed']and probe['checks']['canonical_and_two_private_legacy_font_load_missing_character']
    for a in catalog['resources']:
        if a['kind']!='font':continue
        files=[]
        for item in a['files']:
            p=game/item['path'];assert p.resolve().is_relative_to(game.resolve())and not p.is_symlink()and not p.is_junction();raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==item['sha256'];assert not p.name.endswith('.png')or raw[:8]==b'\x89PNG\r\n\x1a\n';files.append(dict(item,bytes=len(raw)))
        raw=(game/a['path']).read_bytes();m,glyphs=metrics(raw);pages=[(Path(a['path']).parent/p).as_posix()for p in m['pages']];assert {p.casefold()for p in pages}=={p['path'].casefold()for p in files if p['path']!=a['path']},dict(font=a['path'],pages=pages,files=files)
        calculated=sum(glyphs[ord(ch)]for ch in 'native bridge')
        if a['path']in native:assert calculated==native[a['path']]
        fonts.append(dict(path=a['path'],aliases=a['aliases'],files=files,metrics=m,canonical_width=calculated,native_canonical_width=native.get(a['path'])))
    main=c.t.s.e.v.s.MAIN;lines=main.read_bytes().splitlines(keepends=True)
    result=dict(schema='frozen-font-metrics-1',game_root=game.as_posix(),main_sha256=c.old.digest(main),width_wrapper=dict(first=308,last=310,sha256=hashlib.sha256(b''.join(lines[307:310])).hexdigest()),fonts=fonts,evidence=[dict(path=p.relative_to(ROOT).as_posix(),sha256=c.old.digest(p))for p in [catalog_path,evidence,ROOT/'native/engine_api.cpp',Path(__file__)]],default_missing_behavior_verified=False,complete_native_equivalence_verified=False,rendering_verified=False)
    c.t.s.e.v.s.o.freeze_json(OUT,result);print(json.dumps(dict(frozen=True,fonts=len(fonts),native_width_controls=len(native),asset_bytes_copied=0)))
if __name__=='__main__':freeze()
