"""Separate slice2 oracles; all historical source and manifests remain frozen."""
import copy,json
from pathlib import Path
from suite_scenarios import case,accept,reject,configs
ROOT=Path(__file__).resolve().parents[1]
OPTIONS=[{'Language':'zh','HUDOffset':0.2},{'Language':'en','HUDOffset':0.6}]
CHANGED=[{}, {'triggered':[77]}]

def template():
    old=json.loads((ROOT/'research/slice_suite.template.json').read_text())
    cases=copy.deepcopy(old['cases'])
    for item in cases:
        item['mode']='slice2';item['id']=item['id'].replace('slice-','slice2-',1)
        if item['id']=='slice2-unmatched-query-recovery':
            first=accept(1,templates=['zh|1','en|1'],values={'/world/coins/0':1})
            changed=accept(2,values={'/world/coins/0':2,'/draws/1/2/x':125},inputs=CHANGED)
            changed['expect']['texts']=[['zh|2'],['queued','extra=2','en|2']]
            duplicate=copy.deepcopy(changed);duplicate['expect']['values']['/duplicate']=True
            item['frames']=[first,changed,duplicate]
        elif item['id']=='slice2-unresolved-control-recovery':
            first=accept(1,templates=['zh|1|reward=${/effects/0/amount}','en|1|reward=${/effects/0/amount}'])
            changed=accept(2,templates=['zh|2|reward=${/effects/0/amount}','en|2|reward=${/effects/0/amount}'],values={'/draws/1/1/x':125},inputs=CHANGED)
            changed['expect']['text_templates'][1].insert(0,'queued')
            duplicate=copy.deepcopy(changed);duplicate['expect']['values']['/duplicate']=True
            item['frames']=[first,changed,duplicate]
        elif item['id']=='slice2-multiple-authority-consumers':
            item['frames']=[accept(1,templates=['first=${/effects/0/amount}|second=${/effects/1/amount}']*2)]
    def add(identity,fixture,frames,stores=None,kind='functional',**extra):
        cases.append(case('slice2-'+identity,fixture,'slice2',stores or [{},{}],frames,options=OPTIONS,case_kind=kind,**extra))
    add('new-queries-before-and-after','slice2_extra_queries',[
        accept(1,values={'/world/coins/0':1}),accept(2,values={'/world/coins/0':2})])
    cases[-1]['frames'][0]['expect']['texts']=[[],['before=0','after=1']]
    cases[-1]['frames'][1]['expect']['texts']=[[],['before=1','after=2']]
    add('helper-queries-before-and-after','slice2_helper_queries',[accept(1,values={'/world/coins/0':1})])
    cases[-1]['frames'][0]['expect']['texts']=[[],['before=0','after=1']]
    for identity,fixture,error in (
        ('query-frontier-ambiguity','slice2_query_frontier_ambiguity','query state point crosses unmatched'),
        ('unresolved-paths','slice2_unresolved_paths','Unbound slice world contribution'),
        ('callback-anchor-ambiguity','slice2_callback_ambiguity','callback anchor'),
        ('unproven-heap-instances','slice2_heap_instances','authority heap instance'),
        ('branch-budget','slice2_branch_budget','unresolved branch budget'),
        ('path-budget','slice2_path_budget','exploration path budget'),
        ('instruction-budget','slice2_instruction_budget','budget exceeded')):
        add(identity,fixture,[reject(1,error,gate=True)],kind='safety')
    for key in (77,78,79):
        add('native-deferred-key-'+str(key),'slice2_native_deferred_keys',[
            reject(1,'Unsupported slice2 deferred native selector',[{}, {'pressed':[key]}],gate=True)],kind='safety')
    add('setting-control-ambiguity','slice2_setting_control',[
        reject(1,'Ambiguous slice draw',gate=True)],configs('Slice2 Setting Control',2))
    add('two-rewards-upvalues-helper','slice2_two_rewards_upvalues',[
        accept(1,templates=['first=${/effects/0/amount}|second=${/effects/1/amount}']*2),
        accept(2,templates=['first=${/effects/0/amount}|second=${/effects/1/amount}']*2)])
    add('reversed-consumers','slice2_reversed_consumers',[
        accept(1,templates=['first=${/effects/1/amount}|second=${/effects/0/amount}']*2)])
    add('lua-comparison-semantics','slice2_comparisons',[
        accept(1,texts=['equal|less|le|truth|3']*2)])
    add('two-rewards-fields-cross-frame','slice2_two_rewards_fields',[
        accept(i,values={'/world/frame':i,'/draws/1/0/x':124 if i==1 else 125},inputs=CHANGED if i==2 else [{},{}]) for i in range(1,7)],configs('Slice2 Two Rewards Fields'))
    name='Slice2 Transaction Failure'
    add('failure-after-save-state-draw','slice2_transaction_failure',[
        accept(1,templates=['zh|1|reward=${/effects/0/amount}','en|1|reward=${/effects/0/amount}']),
        reject(2,'slice2 injected after save private state and queued draw',CHANGED),
        accept(2,templates=['zh|2|reward=${/effects/0/amount}','en|2|reward=${/effects/0/amount}']),
        accept(2,values={'/duplicate':True}),
        reject(2,'Duplicate model frame payload changed',CHANGED),
        accept(3,templates=['zh|3|reward=${/effects/0/amount}','en|3|reward=${/effects/0/amount}'])],configs(name),kind='transaction')
    return {'schema':'isaac-runtime-suite-1','purpose':'Slice2 timeline, storage-use projection and deferred-branch coin model; rejection is not compatibility','cases':cases}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with a.output.open('x',encoding='utf-8') as f:json.dump(template(),f,indent=2)
    print(json.dumps({'cases':len(template()['cases']),'template':str(a.output)}))
