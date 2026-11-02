"""Freeze metadata and bounded encoded ranges; never copy game assets."""
import copy,hashlib,json,struct,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.dont_write_bytecode=True
import run_engine_services as e
from packed_resources import Archive,name_hash
from catalog_resources import sprite_metadata
ROOT=e.ROOT;OUT=ROOT/'research/sprite_state/profile.json'
def digest(p):return e.old.digest(p)
def load(p):return e.v.s.o.load(p)
class BoundedReader:
 def __init__(self,path,start,end):self.file=path.open('rb');self.start=start;self.end=end
 def __enter__(self):return self
 def __exit__(self,*args):self.file.close()
 def seek(self,at):
  if not self.start<=at<=self.end:raise RuntimeError('Packed decoder seeks outside witnessed member')
  return self.file.seek(at)
 def read(self,n):
  if n<0 or self.file.tell()+n>self.end:raise RuntimeError('Packed decoder crosses member range')
  return self.file.read(n)
class BoundedPath:
 def __init__(self,path,start,end):self.path=path;self.start=start;self.end=end;self.name=path.name
 def open(self,mode):assert mode=='rb';return BoundedReader(self.path,self.start,self.end)
def freeze():
 report=ROOT/'runs/packed-resources-j460-20261010-final/mod-runtime.json';source=ROOT/'native/engine_api.cpp';j=load(report)['engine_api_preflight'];assert j['probe_passed']
 catalog=j['resource_inventory'];original=load(ROOT/'research/resource_catalog.json');game=Path(load(ROOT/'research/model_objects/resources.json')['game_root'])
 bypath={x['path']:x for x in original['resources']};measure={x['path']:x for x in j['sprite_roundtrips']};archives={};sprites=[]
 def arc(name,expected):
  p=game/'resources/packed'/name
  if name not in archives:
   assert p.resolve().is_relative_to(game.resolve())and not p.is_symlink()and not p.is_junction();assert digest(p)==expected
   a=Archive(p);a.sha256=expected;archives[name]=a
  assert archives[name].sha256==expected;return archives[name]
 for entry in catalog['resources']:
  if entry['kind']!='sprite':continue
  assert entry==bypath[entry['path']]
  ranges={};metadata_bytes=None
  if entry.get('storage')=='packed':
   for member in entry['packed_entries']:
    a=arc(member['archive'],member['archive_sha256']);row=a.entries[name_hash(member['entry'])];at=row[2];assert row[3]==member['bytes']and row[4]==member['checksum']
    p=a.path;header=p.open('rb').read(14);magic,mode,index,count=struct.unpack('<7sBIH',header);assert magic==b'ARCH000'
    end=min(n for n in [a.size,index,*[x[2]for x in a.entries.values()]]if n>at)
    bounded=copy.copy(a);bounded.path=BoundedPath(p,at,end);data,info=bounded.read(member['entry']);assert hashlib.sha256(data).hexdigest()==member['sha256']and info==member
    if member['entry']=='resources/'+entry['engine_path']:metadata_bytes=data
    proofs=ranges.setdefault(p.name,{})
    for offset,size in [(0,14),(index,count*20),(at,end-at)]:
     assert 0<size<=4*1024*1024
     with p.open('rb')as f:f.seek(offset);raw=f.read(size)
     assert len(raw)==size;proofs[(offset,size)]=dict(offset=offset,bytes=size,sha256=hashlib.sha256(raw).hexdigest())
  else:
   metadata_bytes=(game/entry['path']).read_bytes()
   for f in entry['files']:assert digest(game/f['path'])==f['sha256']
  metadata,pages=sprite_metadata(metadata_bytes);assert all(metadata[k]==entry[k]for k in ['animations','declared_frames','default_animation','layers'])
  measured={x['animation']:x for x in measure[entry['path']]['animations']};animations={}
  for name,selectable in metadata['animations'].items():
   m=measured[name];declared=metadata['declared_frames'][name];root=max(0,declared-1)
   assert m['canonical_frames']==[root,root]and m['first_named_frame']==root and m['first_numeric_frame']==root and m['second_frame']==0
   animations[name]=dict(declared=declared,selectable=selectable,native_last_root=root,native_zero_root=0)
  sprites.append(dict(path=entry['path'],aliases=entry['aliases'],storage=entry.get('storage','loose'),default_animation=metadata['default_animation'],layers=metadata['layers'],animations=animations,
    range_proofs=[dict(path='resources/packed/'+name,archive_sha256_at_freeze=archives[name].sha256,ranges=list(proofs.values()))for name,proofs in ranges.items()]))
 main=e.v.s.MAIN;lines=main.read_bytes().splitlines(keepends=True)
 profile=dict(schema='frozen-sprite-state-1',game_root=game.as_posix(),main_sha256=digest(main),evidence=[dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p))for p in [report,source,ROOT/'tools/packed_resources.py',ROOT/'tools/catalog_resources.py']],sprites=sprites,
  wrappers=[dict(first=a,last=b,sha256=hashlib.sha256(b''.join(lines[a-1:b])).hexdigest())for a,b in [(639,649),(687,691)]])
 e.v.s.o.freeze_json(OUT,profile);print(json.dumps(dict(frozen=True,sprites=len(sprites),animations=sum(len(s['animations'])for s in sprites),archive_bytes_copied=0,range_bytes=sum(x['bytes']for s in sprites for p in s['range_proofs']for x in p['ranges']))))
if __name__=='__main__':freeze()
