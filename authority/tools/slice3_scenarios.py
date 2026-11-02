"""Independent policy oracles. The two original counterexamples are not edited."""
import copy,json,argparse
from pathlib import Path
from suite_scenarios import case,accept,configs,reject
RULE='personal-settings-authority-hud-v1'

def counterexamples():
    cases=[]
    for fixture,name,text in (
        ('slice_setting_ambiguity','Slice Setting Ambiguity',lambda n:f'en|amount={n}'),
        ('slice2_setting_control','Slice2 Setting Control',lambda n:'branch' if n==2 else 'other')):
        for host,personal in ((1,2),(2,1)):
            stores=configs(name,personal);h=json.loads(stores[0][name]);h['amount']=host;stores[0][name]=json.dumps(h,sort_keys=True)
            frame=accept(1,values={'/world/coins/0':host,'/draws/1/0/x':124,'/stores/1/'+name:stores[1][name]})
            frame['expect']['texts']=[['zh|amount='+str(host) if fixture=='slice_setting_ambiguity' else ('branch' if host==2 else 'other')],[text(host)]]
            cases.append(case(f'slice3-{fixture}-{host}-{personal}',fixture,'slice3',stores,[frame],case_kind='functional'))
    return {'schema':'isaac-runtime-suite-1','view_rule':RULE,'purpose':'Original ambiguity cases under the fixed global dual-view rule','cases':cases}

def menus():
    name='Slice3 Menu Config';cases=[]
    for host,personal in ((1,2),(2,1)):
        stores=configs(name,personal);h=json.loads(stores[0][name]);h['amount']=host;stores[0][name]=json.dumps(h,sort_keys=True)
        frames=[]
        for n in range(1,4):
            amount=personal+(n>=2);x=124+(n>=2)
            frame=accept(n,values={'/world/coins/0':n*host,'/draws/1/0/x':x,'/draws/1/1/x':x},inputs=[{}, {'triggered':[77]}] if n==2 else [{},{}])
            frame['expect']['texts']=[[f'zh|amount={host}',f'zh|amount={host}'],[f'en|amount={amount}',f'en|amount={host}']]
            cfg={'amount':amount,'key':77,'language':'en','x':x}
            frame['expect']['values']['/stores/1/'+name]=json.dumps(cfg,separators=(',',':'),sort_keys=True)
            frames.append(frame)
        duplicate=copy.deepcopy(frames[-1]);duplicate['expect']['values']['/duplicate']=True;frames.append(duplicate)
        frames.append(reject(3,'Duplicate model frame payload changed',[{}, {'triggered':[77]}]))
        c=case(f'slice3-menu-settings-{host}-{personal}','slice3_menu_config','slice3',stores,frames,case_kind='functional')
        c['mods'].insert(0,{'base':'research','root':'fixtures/slice3_menu_provider'})
        cases.append(c)
    return {'schema':'isaac-runtime-suite-1','view_rule':RULE,'purpose':'Shared settings framework boundary model; no real MCM acceptance','cases':cases}

def full():
    root=Path(__file__).resolve().parents[1]
    result=copy.deepcopy(json.loads((root/'research/slice2_suite.template.json').read_text()))
    result.update(view_rule=RULE,purpose='Slice3 fixed global use policy, function compatibility separate from safe refusal')
    originals=counterexamples()['cases']
    for c in result['cases']:
        c['id']=c['id'].replace('slice2-','slice3-',1);c['mode']='slice3'
        if c['id']=='slice3-setting-versus-game-result-ambiguity':c['frames']=copy.deepcopy(originals[0]['frames'])
        if c['id']=='slice3-setting-control-ambiguity':c['frames']=copy.deepcopy(originals[2]['frames'])
    result['cases']+=copy.deepcopy([originals[1],originals[3]])+menus()['cases']
    def add(identity,fixture,name,frames,kind='functional',stores=None):
        result['cases'].append(case('slice3-'+identity,fixture,'slice3',stores or configs(name,2),frames,case_kind=kind))
    name='Slice3 Cross Frame'
    for change in ('host','personal'):
        frames=[];total=0
        for n in range(1,4):
            h=1+(n>=2 and change=='host');p=2+(n>=2 and change=='personal');total+=h
            inputs=[{'triggered':[76]},{}] if n==2 and change=='host' else ([{}, {'triggered':[77]}] if n==2 else [{},{}])
            f=accept(n,values={'/world/coins/0':total},inputs=inputs)
            previous=1 if n==2 else h
            ht=([f'zh|amount={previous}'] if n>1 else [])+[f'zh|amount={h}',f'native={h}']
            pt=([f'en|amount={previous}'] if n>1 else [])+[f'en|amount={h}',f'native={h}']
            f['expect']['texts']=[ht,pt]
            f['expect']['values']['/stores/1/'+name]=json.dumps({'amount':p,'key':77,'language':'en','x':124+(change=='personal' and n>=2)},sort_keys=True,separators=(',',':'))
            frames.append(f)
        add('cross-frame-'+change,'slice3_cross_frame',name,frames)
    name='Slice3 Transaction'
    first=accept(1,texts=['zh|amount=1|private=1','en|amount=1|private=1'])
    retry=accept(2,texts=['zh|amount=1|private=2','en|amount=1|private=2'])
    dup=copy.deepcopy(retry);dup['expect']['values']={'/duplicate':True}
    add('dual-view-transaction','slice3_transaction',name,[first,reject(2,'slice3 injected after save state draw',[{}, {'triggered':[77],'pressed':[88]}]),retry,dup,reject(2,'Duplicate model frame payload changed',[{}, {'pressed':[88]}]),accept(3,texts=['zh|amount=1|private=3','en|amount=1|private=3'])],kind='transaction')
    add('ambiguous-producer-refusal','slice3_multiple_views','Slice3 Multiple Views',[reject(1,'Ambiguous slice3 multiple authority producers',gate=True)],kind='safety')
    add('unknown-projection-refusal','slice3_unknown_projection','Slice3 Unknown Projection',[reject(1,'Unsupported slice3 projected native contract: string.rep',gate=True)],kind='safety')
    add('fake-menu-default-hud','slice3_fake_menu','Slice3 Fake Menu',[accept(1,texts=['zh|amount=1','en|amount=1'])])
    for host,personal in ((1,2),(2,1)):
        name='Slice3 Display State';stores=configs(name,personal);h=json.loads(stores[0][name]);h['amount']=host;stores[0][name]=json.dumps(h,sort_keys=True)
        frames=[]
        for n in range(1,3):
            x=124+n*(5 if host==2 else 0)+(n>=2)
            f=accept(n,texts=[f'zh|amount={host}',f'en|amount={host}'],values={'/draws/1/0/x':x},inputs=[{}, {'triggered':[77]}] if n==2 else [{},{}])
            f['expect']['values']['/stores/1/'+name]=json.dumps({'amount':personal,'key':77,'language':'en','x':x},sort_keys=True,separators=(',',':'))
            frames.append(f)
        add(f'reward-controls-display-{host}-{personal}','slice3_display_state',name,frames,stores=stores)
    add('ordered-operands','slice3_operands','Slice3 Operands',[accept(1,texts=['zh|7,9,-9','en|7,9,-9'])])
    add('lost-serialization-refusal','slice3_lost_serialization','Slice3 Lost Serialization',[reject(1,'Slice3 lost serialized field provenance',gate=True)],kind='safety')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--stage',choices=['counterexamples','menus','full'],default='counterexamples');a=p.parse_args()
    with a.output.open('x',encoding='utf-8') as f:json.dump({'counterexamples':counterexamples,'menus':menus,'full':full}[a.stage](),f,indent=2)
