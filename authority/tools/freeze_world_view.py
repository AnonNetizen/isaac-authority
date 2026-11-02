"""Freeze small XML-derived metadata and explicit dynamic availability scenarios."""
import copy,hashlib,json,re,struct,sys,xml.etree.ElementTree as ET
from pathlib import Path
sys.dont_write_bytecode=True
import run_menu_environment as m
from packed_resources import Archive,name_hash
from freeze_sprite_state import BoundedPath
ROOT=m.ROOT;DIR=ROOT/'research/world_view';MENU=DIR/'menu-v2.json';PROFILE=DIR/'profile-v2.json'
def freeze():
    base=copy.deepcopy(m.f.load(m.freezer.PROFILE));sdk=m.f.load(ROOT/'research/sprite_state/profile.json');game=Path(sdk['game_root']);p=game/'resources/packed/repentance.a'
    a=Archive(p);a.sha256='range-verified; whole archive deliberately not hashed'
    header=p.open('rb').read(14);_,_,index,count=struct.unpack('<7sBIH',header);ranges={(0,14),(index,count*20)};xml={};members=[]
    for leaf in ['items.xml','items_metadata.xml','wisps.xml']:
        name='resources-dlc3/'+leaf;entry=a.entries[name_hash(name)];offset=entry[2];end=min(x for x in[a.size,index,*[r[2]for r in a.entries.values()]]if x>offset)
        b=copy.copy(a);b.path=BoundedPath(p,offset,end);raw,info=b.read(name);xml[leaf]=ET.fromstring(raw);ranges.add((offset,end-offset));members.append({k:v for k,v in info.items()if k!='archive_sha256'})
    proofs=[]
    for offset,size in sorted(ranges):
        assert 0<size<=4*1024*1024
        with p.open('rb')as f:f.seek(offset);raw=f.read(size)
        assert len(raw)==size;proofs.append(dict(offset=offset,bytes=size,sha256=hashlib.sha256(raw).hexdigest()))
    enums=(ROOT/'research/slice3_ui_inputs/resources/scripts/enums.lua').read_text(encoding='utf-8');flags={}
    for name,bit in re.findall(r'TAG_([A-Z_]+)\s*=\s*1\s*<<\s*(\d+)',enums):flags[name.replace('_','').lower()]=1<<int(bit)
    flags['dead']=1;flags['lazarussharedglobal']=flags['lazsharedglobal'];wisp_ids={int(r.attrib['id'])for r in xml['wisps.xml'].iter('wisp')if r.get('id','').isdecimal()}
    itemrows={int(r.attrib['id']):r for r in xml['items.xml']if r.tag in ['passive','active','familiar']};meta={int(r.attrib['id']):r for r in xml['items_metadata.xml']if r.tag=='item'};items={};basis=[]
    for id in [1,73,78]:
        row=itemrows[id];data=meta[id];tags=0
        for name in data.get('tags','').split():assert name in flags,name;tags|=flags[name]
        if row.tag=='active'and id in wisp_ids:tags|=flags['wisp']
        assert row.get('hidden','false')in['true','false']
        items[str(id)]=dict(ID=id,Name=row.attrib['name'],Description=row.attrib['description'],AchievementID=int(row.get('achievement','-1')),Hidden=row.get('hidden','false')=='true',Tags=tags,Type={'passive':1,'active':3,'familiar':4}[row.tag],Quality=int(data.attrib['quality']),MaxCharges=int(row.get('maxcharges','0')))
        basis.append(dict(id=id,item_attributes=row.attrib,metadata_attributes=data.attrib,wisp_entry_present=id in wisp_ids))
    base['snapshot']['item_availability']={'0':{'1':True,'73':False,'78':True}}
    for player in base['snapshot']['players']:player['controls_enabled']=True
    base['snapshot']['seeds']['effects']={'10':False}
    base['snapshot']['entities'][0]['touched']=False;base['definitions']['entity']['Touched']=dict(mode='field',field='touched',type='boolean')
    base['definitions']['player']['ControlsEnabled']=dict(mode='field',field='controls_enabled',type='boolean')
    for name,op in [('AddSeedEffect','add'),('RemoveSeedEffect','remove'),('HasSeedEffect','query')]:base['definitions']['seeds'][name]=dict(mode='view_seed_'+op)
    DIR.mkdir(parents=True,exist_ok=True);m.f.freeze_json(MENU,base)
    data=dict(schema='frozen-world-view-1',rule='authority-writes-personal-intents-v1',main_sha256=sdk['main_sha256'],menu_sha256=m.f.digest(MENU),hud_effect=10,items=items,resource_proof=dict(storage='packed',range_proofs=[dict(path='resources/packed/repentance.a',ranges=proofs)]),decoded_members=members,xml_field_basis=basis,enums_sha256=m.f.digest(ROOT/'research/slice3_ui_inputs/resources/scripts/enums.lua'),availability_basis='explicit authority query scenario; NOT XML-derived unlock state or current personal save',metadata_basis='XML and frozen enum mapping; active WISP tag inferred from matching wisps.xml entry; absent achievement=-1, hidden=false and maxcharges=0 follow declared XML defaults; native getters not resampled',native_tags_resampled=False,native_equivalence_verified=False,docs=['https://wofsauge.github.io/IsaacDocs/rep/Seeds.html','https://wofsauge.github.io/IsaacDocs/rep/ItemConfig_Item.html'])
    m.f.freeze_json(PROFILE,data);print(json.dumps(dict(frozen=True,items=len(items),range_bytes=sum(r['bytes']for r in proofs),copied_game_asset_bytes=0,native_metadata_equivalence=False)))
if __name__=='__main__':freeze()
