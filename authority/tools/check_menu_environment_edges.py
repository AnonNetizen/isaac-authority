"""Exercise receipt eviction and retired snapshot roots in short bounded children."""
import argparse,copy,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_menu_environment as m
ROOT=m.ROOT;MANIFEST=ROOT/'research/menu_environment_edges_v2.json'
def freeze():
    template=copy.deepcopy(m.f.load(m.MANIFEST)['cases'][0]);cases=[]
    def add(id,steps,**kw):
        c=copy.deepcopy(template);c.pop('values',None);c.update(id=id,steps=steps,kind='functional',**kw);cases.append(c)
    add('receipt-eviction-never-reexecutes',[m.dispatch(i)for i in range(1,131)]+[m.dispatch(1,expect_error='Menu frame receipt expired or frame out of order'),m.dispatch(131)],frames=[['zh|coins=0|private=0|data=nil']]*131,audio=[0]*131)
    snap=copy.deepcopy(m.f.load(m.freezer.PROFILE)['snapshot']);snap['revision']=2;snap['room']['id']=2
    add('retired-room-handle',[dict(op='set_menu_snapshot',snapshot=snap),m.ev('R:IsClear()',expect_error='Stale menu object identity'),m.ev('return Game():GetRoom():IsClear()')],values=m.values(True))
    bad=copy.deepcopy(snap);bad['players'][0]['parent']=999
    add('dangling-scene-relation-rejected',[dict(op='set_menu_snapshot',snapshot=bad,expect_error='Dangling actor relation'),m.ev('return P.Parent,P:GetPlayerType()')],values=m.values(None,0))
    add('private-entity-data-independent',[m.ev('P:GetData().changed=9',role='host'),m.dispatch(role='host'),m.dispatch()],frames=[['en|coins=0|private=0|data=9'],['zh|coins=0|private=0|data=nil']],audio=[0,0])
    huge=copy.deepcopy(m.f.load(m.freezer.PROFILE)['snapshot']);huge['revision']=2;huge['players'][0]['player_type']=2**63
    add('reject-value-outside-lua-integer',[dict(op='set_menu_snapshot',snapshot=huge),m.ev('P:GetPlayerType()',expect_error='Integer snapshot required')])
    m.f.freeze_json(MANIFEST,dict(schema='menu-environment-edge-tests-1',work_limit=10000000,timeout_seconds=5,cases=cases))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();freeze();sys.exit(0 if m.run(MANIFEST,a.output)else 1)
