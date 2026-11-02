"""The functional acceptance scenarios; write a template, then freeze_suite.py pins its sources."""
import json
from pathlib import Path

EMPTY=[{},{}]
def configs(name,amount=1):
    return [{name:json.dumps({'language':'zh','key':76,'x':24,'amount':1},sort_keys=True)},
            {name:json.dumps({'language':'en','key':77,'x':124,'amount':amount},sort_keys=True)}]
def case(identity,fixture,mode,stores,frames,**extra):
    return dict(id=identity,mode=mode,mods=[{'base':'research','root':'fixtures/'+fixture}],stores=stores,frames=frames,**extra)
def accept(frame,texts=None,values=None,inputs=EMPTY,templates=None):
    expected={'outcome':'accept'}
    if texts is not None: expected['texts']=[[texts[0]],[texts[1]]]
    if values is not None: expected['values']=values
    if templates is not None: expected['text_templates']=[[templates[0]],[templates[1]]]
    return {'frame':frame,'time_ms':1000+(frame-1)*16,'inputs':inputs,'expect':expected}
def reject(frame,error,inputs=EMPTY,gate=False,texts=None):
    result={'frame':frame,'time_ms':1000+(frame-1)*16,'inputs':inputs,'gate_required':gate,
            'expect':{'outcome':'reject','error_contains':error}}
    if texts is not None:result['expect']['texts']=[[texts[0]],[texts[1]]]
    return result
def template():
    cases=[]
    name='Authority Research Legacy Chaos Fixture'
    for mode in ('strict','presentation'):
        cases.append(case('original-mixed-'+mode,'legacy_chaos',mode,configs(name),[
            accept(1,values={'/effects/1/amount':1,'/draws/0/0/x':24,'/draws/1/0/x':124},
                   templates=['zh|1|1000|${/effects/0/amount}','en|1|1000|${/effects/0/amount}'])]))
    name='Config Drives World Fixture'
    frames=[accept(1,['zh|1','en|1'],{'/world/coins/0':1}),
            reject(2,'divergent authority world call',[{}, {'triggered':[77]}]),
            accept(2,['zh|2','en|2'],{'/world/coins/0':2})]
    cases.append(case('strict-personal-config-boundary','config_drives_world','strict',configs(name),frames))
    frames=[accept(1,['zh|1','en|1'],{'/world/coins/0':1}),
            accept(2,['zh|2','en|2'],{'/world/coins/0':2},[{}, {'triggered':[77]}])]
    cases.append(case('presentation-original-config-counterexample','config_drives_world','presentation',configs(name),frames))
    name='Presentation Gate Fixture'
    changed=[{}, {'triggered':[77]}]
    extra=[{}, {'pressed':[88]}]
    frames=[accept(1,['zh|coins=1|count=1','en|coins=1|count=1'],{'/world/coins/0':1}),
            accept(2,['zh|coins=2|count=2','en|coins=2|count=2'],{'/world/coins/0':2,'/draws/1/0/x':125,'/personal_options/1/Language':'fr','/suppressed/0/args/1':2},changed),
            accept(3,['zh|coins=3|count=3','en|coins=3|count=3'],{'/world/coins/0':3,'/suppressed/1/args/1':2},extra),
            accept(3,['zh|coins=3|count=3','en|coins=3|count=3'],{'/world/coins/0':3,'/duplicate':True},extra),
            reject(3,'Duplicate model frame payload changed',changed),
            accept(4,['zh|coins=4|count=4','en|coins=4|count=4'],{'/world/coins/0':4,'/personal_options/1/Language':'fr'})]
    cases.append(case('presentation-config-extra-writes-cached-query-dedup','presentation_gate','presentation',configs(name),frames))
    # Fresh contexts use the saved configuration, while the authoritative world starts fresh.
    restored=configs(name,2)
    config=json.loads(restored[1][name]);config['x']=125;restored[1][name]=json.dumps(config,sort_keys=True)
    cases.append(case('presentation-fresh-context-personal-config','presentation_gate','presentation',restored,[
        accept(1,['zh|coins=1|count=1','en|coins=1|count=1'],{'/world/coins/0':1,'/draws/1/0/x':125,'/suppressed/0/args/1':2})]))
    cases.append(case('strict-read-write-read','presentation_transition','strict',[{},{}],[
        accept(1,['0->1|count=1','0->1|count=1'],{'/world/coins/0':1})]))
    cases.append(case('presentation-read-write-read-semantic-boundary','presentation_transition','presentation',[{},{}],[
        reject(1,'Semantic oracle mismatch',gate=True,texts=['0->1|count=1','0->1|count=1']),
        reject(1,'Semantic oracle mismatch',gate=True,texts=['0->1|count=1','0->1|count=1'])]))
    name='Random Gate Fixture'
    def random_accept(frame,duplicate=False):
        values={'/world/frame':frame,'/world/time_ms':1000+(frame-1)*16,'/personal_options/1/Language':'en','/draws/1/0/x':124}
        if duplicate:values['/duplicate']=True
        now=1000+(frame-1)*16
        return accept(frame,values=values,templates=[
            f'zh|v=${{/transcript/0/result}}|t={now}|clock={now/1000}|count={frame}',
            f'en|v=${{/transcript/0/result}}|t={now}|clock={now/1000}|count={frame}'])
    cases.append(case('presentation-random-time-cached-functions','presentation_random','presentation',configs(name),[random_accept(1),random_accept(2),random_accept(2,True)]))
    cases.append(case('presentation-return-mutation-mismatch-recovery','presentation_random','presentation',configs(name),[
        random_accept(1),reject(2,'Unmatched return-bearing world mutation',[{}, {'triggered':[77]}],gate=True),random_accept(2),random_accept(2,True)]))
    cases.append(case('presentation-extra-return-mutation-no-reuse','presentation_random','presentation',configs(name),[
        random_accept(1),reject(2,'Unmatched return-bearing world mutation',[{}, {'pressed':[99]}],gate=True),random_accept(2)]))
    alias=reject(1,'Semantic oracle mismatch',gate=True)
    alias['expect']['text_templates']=[['award=${/effects/0/amount}|coins=${/world/coins/0}'],['award=${/effects/0/amount}|coins=${/world/coins/0}']]
    cases.append(case('presentation-identical-return-arguments-ambiguous','presentation_random_alias','presentation',[{},{}],[alias],
        options=[{'Language':'zh','HUDOffset':0.2},{'Language':'en','HUDOffset':0.6}]))
    # This is initialization only. Real MCM callbacks/HUD are explicitly outside the passed evidence.
    cases.append(dict(id='unchanged-mcm-eid-two-language-initialization',mode='strict',native_roots=True,load_enums=True,
        mods=[{'base':'game','root':'mods/mod_config_menu_cn_2494192799'},
              {'base':'game','root':'mods/external item descriptions_836319872'}],stores=[{},{}],frames=[],
        options=[{'Language':'zh','HUDOffset':0.2},{'Language':'en','HUDOffset':0.6}],
        inspect=[{'slot':0,'code':"assert(EID:getLanguage()=='zh_cn');return true",'expected':[{'t':'boolean','v':True}]},
                 {'slot':1,'code':"assert(EID:getLanguage()=='en_us');return true",'expected':[{'t':'boolean','v':True}]}]))
    return {'schema':'isaac-runtime-suite-1','purpose':'Coin-model isolation gate; real menus/world/network unverified','cases':cases}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with args.output.open('x',encoding='utf-8') as target:json.dump(template(),target,indent=2)
    print(json.dumps({'template':str(args.output),'cases':len(template()['cases'])}))
