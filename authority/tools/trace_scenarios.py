"""New acceptance manifest; keeps the historical 13 cases unchanged as controls."""
import copy
import json
from pathlib import Path
from suite_scenarios import accept,reject,case,configs

ROOT=Path(__file__).resolve().parents[1]
OPTIONS=[{'Language':'zh','HUDOffset':0.2},{'Language':'en','HUDOffset':0.6}]
def template():
    original=json.loads((ROOT/'research/runtime_suite.template.json').read_text())
    cases=copy.deepcopy(original['cases'])
    wanted={'original-mixed-presentation','presentation-original-config-counterexample',
        'presentation-config-extra-writes-cached-query-dedup','presentation-fresh-context-personal-config',
        'presentation-random-time-cached-functions','presentation-return-mutation-mismatch-recovery',
        'presentation-extra-return-mutation-no-reuse'}
    for source in original['cases']:
        if source['id'] not in wanted:continue
        item=copy.deepcopy(source);item['id']='trace-'+source['id'];item['mode']='trace'
        for frame in item['frames']:
            if 'Unmatched return-bearing' in frame['expect'].get('error_contains',''):
                frame['expect']['error_contains']='Unmatched trace return/query'
        cases.append(item)
    cases.append(case('trace-read-write-read','presentation_transition','trace',[{},{}],[
        accept(1,['0->1|count=1','0->1|count=1'],{'/world/coins/0':1}),
        accept(1,['0->1|count=1','0->1|count=1'],{'/duplicate':True})]))
    for fixture in ('presentation_random_alias','trace_same_line','trace_helper','trace_cached','trace_tail','trace_dynamic'):
        cases.append(case('trace-authority-award-'+fixture.replace('_','-'),fixture,'trace',[{},{}],[
            accept(1,templates=['award=${/effects/0/amount}|coins=${/world/coins/0}']*2)
        ],options=OPTIONS))
    cases.append(case('trace-personal-loop-cardinality','trace_loop','trace',[{},{}],[
        reject(1,'Unmatched trace return/query',gate=True),reject(1,'Unmatched trace return/query',gate=True)
    ],options=OPTIONS))
    cases.append(case('trace-generic-loop-unresolved','trace_generic_loop','trace',[{},{}],[
        reject(1,'Ambiguous trace dynamic context',gate=True)
    ],options=OPTIONS))
    cases.append(case('trace-tail-loop-context','trace_loop_tail','trace',[{},{}],[
        reject(1,'Unmatched trace return/query',gate=True)
    ],options=OPTIONS))
    name='Trace Serialization Fixture'
    cases.append(case('trace-config-save-roundtrip','trace_serialization','trace',configs(name,2),[
        accept(1,['zh|previous=0|0->1|count=1','en|previous=0|0->1|count=1'],{'/world/coins/0':1}),
        accept(2,['zh|previous=1|1->2|count=2','en|previous=1|1->2|count=2'],{'/world/coins/0':2,'/draws/1/0/x':125},[{}, {'triggered':[77]}]),
        accept(2,['zh|previous=1|1->2|count=2','en|previous=1|1->2|count=2'],{'/duplicate':True,'/world/coins/0':2},[{}, {'triggered':[77]}])
    ]))
    return {'schema':'isaac-runtime-suite-1','purpose':'Standalone execution-dependency coin-model research; no game integration','cases':cases}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with args.output.open('x',encoding='utf-8') as out:json.dump(template(),out,indent=2)
    print(json.dumps({'cases':len(template()['cases']),'template':str(args.output)}))
