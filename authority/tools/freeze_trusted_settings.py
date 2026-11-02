"""Compile the actual frozen MCM with stock/private Lua and freeze exact consumer sites."""
import copy,gzip,hashlib,json,struct,sys
from pathlib import Path
sys.dont_write_bytecode=True
import check_menu_capture as parent
ROOT=parent.ROOT;DIR=ROOT/'research/trusted_settings'
class Chunk:
    def __init__(self,data):
        self.data=data;self.at=0;assert self.take(4)==b'\x1bLua'and self.byte()==0x53 and self.byte()==0 and self.take(6)==b'\x19\x93\r\n\x1a\n'
        self.sizes=[self.byte()for _ in range(5)];assert self.sizes==[4,4,4,8,8];assert self.take(8)==struct.pack('<q',0x5678)and self.take(8)==struct.pack('<d',370.5);self.byte();self.root=self.function();assert self.at==len(data)
    def take(self,n):r=self.data[self.at:self.at+n];assert len(r)==n;self.at+=n;return r
    def byte(self):return self.take(1)[0]
    def integer(self):return struct.unpack('<i',self.take(4))[0]
    def string(self):
        size=self.byte()
        if size==0:return None
        if size==255:size=struct.unpack('<I',self.take(4))[0]
        return self.take(size-1).decode('utf-8',errors='surrogateescape')
    def function(self):
        source=self.string();first,last=self.integer(),self.integer();params,vararg,stack=self.byte(),self.byte(),self.byte();code=[struct.unpack('<I',self.take(4))[0]for _ in range(self.integer())]
        for _ in range(self.integer()):
            kind=self.byte()
            if kind==0:pass
            elif kind==1:self.byte()
            elif kind in [3,19]:self.take(8)
            elif kind in [4,20]:self.string()
            else:raise AssertionError(kind)
        for _ in range(self.integer()):self.take(2)
        children=[self.function()for _ in range(self.integer())];lines=[self.integer()for _ in range(self.integer())];locals=[dict(name=self.string(),start=self.integer(),end=self.integer())for _ in range(self.integer())];upvalues=[self.string()for _ in range(self.integer())]
        return dict(source=source,first=first,last=last,params=params,vararg=vararg,stack=stack,code=code,lines=lines,locals=locals,upvalues=upvalues,children=children)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    DIR.mkdir(exist_ok=True);base=copy.deepcopy(parent.world.parent.f.load(ROOT/'research/sparse_value/real-init-v1.json')['cases'][0]);base['id']='mcm-trusted-prototype-catalog';names=['AddSetting','PostRender','ConvertDisplayToTextTable'];base['steps']=[parent.world.ev('return '+','.join('string.dump(ModConfigMenu.'+name+','+flag+')'for name in names for flag in ['false','true']))]
    manifest=DIR/'catalog-input-v1.json';parent.world.parent.f.freeze_json(manifest,dict(schema='mcm-prototype-catalog-1',work_limit=10000000,timeout_seconds=5,cases=[base]))
    pairs=[parent.invoke(manifest,base,reference)for reference in [True,False,False]]
    for a,r in pairs:assert a['returncode']==0 and not a['timed_out']and not a['output_limit_exceeded']and r and'semantic'in r
    results=[[bytes.fromhex(v['hex'])for v in r['steps'][0]['values']]for _,r in pairs];assert results[1]==results[2]
    for i in range(1,6,2):assert results[0][i]==results[1][i]
    contract=parent.world.parent.f.load(ROOT/'research/menu_capture/mcm-contract-v1.json');functions={}
    for i,name in enumerate(names):
        proto=Chunk(results[1][2*i]).root;functions[name]=dict(sha256=sha(results[1][2*i+1]),first=proto['first'],last=proto['last'],instructions=len(proto['code']))
    specs=[('PostRender','optionCurrent()','CurrentSetting','currentMenuOption'),('PostRender','optionOnChange(','OnChange','currentMenuOption'),('PostRender','textToDraw = optionDisplay(','Display','thisOption'),('PostRender','numberToShow = optionDisplay(','Display','thisOption'),('ConvertDisplayToTextTable','displayValue = displayValue()','Info',None)]
    sites=[]
    for name,needle,role,receiver in specs:
        proto=Chunk(results[1][2*names.index(name)]).root;locations={r['line']for r in contract['source_sites'][needle]}
        selected=[(pc,word)for pc,word in enumerate(proto['code'])if word&63==36 and proto['lines'][pc]in locations]
        assert selected,(name,needle)
        for pc,word in selected:
            active=[v for v in proto['locals']if v['start']<=pc<v['end']];matches=[i+1 for i,v in enumerate(active)if v['name']==receiver]if receiver else[]
            upvalues=[i+1 for i,v in enumerate(proto['upvalues'])if v==receiver]if receiver and not matches else[]
            assert not receiver or len(matches)+len(upvalues)==1,(name,pc,receiver,matches,upvalues)
            sites.append(dict(caller=name,caller_sha256=functions[name]['sha256'],pc=pc,instruction=word,line=proto['lines'][pc],role=role,receiver_index=(matches or upvalues or[0])[0],receiver_kind='local'if matches else'upvalue'if upvalues else'ancestor',receiver_name=receiver or'',args=((word>>23)&511)-1,results=((word>>14)&511)-1))
    proto=Chunk(results[1][2]).root;raw_source=(ROOT/contract['source']).read_text(encoding='utf-8').splitlines();renderers=[]
    for pc,word in enumerate(proto['code']):
        line=proto['lines'][pc]
        if word&63!=36:continue
        source_line=raw_source[line-1]
        if ':DrawString'in source_line or ':Render('in source_line:renderers.append(dict(pc=pc,instruction=word,line=line,kind='font'if':DrawString'in source_line else'sprite'))
    info_index=proto['upvalues'].index('currentMenuOption')+1
    profile=dict(schema='trusted-mcm-sites-1',source=contract['source'],source_sha256=contract['source_sha256'],functions=functions,sites=sites,renderer_sites=renderers,info_receiver_upvalue=info_index,settings_limit=256,proof_count_limit=512,proof_byte_limit=262144,personal_result_forwarding_implemented=False)
    parent.world.parent.f.freeze_json(DIR/'profile-v2.json',profile)
    proof=DIR/'catalog-proof-v2.json.gz';raw=json.dumps(dict(schema='trusted-settings-catalog-proof-1',pairs=[dict(artifact=a,report=r)for a,r in pairs],private_repeat_equal=True,stock_stripped_bytecode_equal=True,profile_sha256=sha((DIR/'profile-v2.json').read_bytes())),separators=(',',':')).encode();assert not proof.exists();proof.write_bytes(gzip.compress(raw,mtime=0));print(json.dumps(dict(catalogue_frozen=True,functions=functions,consumer_sites=len(sites),renderer_sites=len(renderers))))
if __name__=='__main__':main()
