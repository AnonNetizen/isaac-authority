"""New projection oracles; historical fixtures and manifests are not rewritten."""
import copy
import json
from pathlib import Path
from suite_scenarios import case,accept,reject,configs
ROOT=Path(__file__).resolve().parents[1]
OPTIONS=[{'Language':'zh','HUDOffset':0.2},{'Language':'en','HUDOffset':0.6}]
def random_frame(frame,inputs=None,changed=False,duplicate=False):
    time=1000+(frame-1)*16
    templates=[[f'zh|v=${{/transcript/0/result}}|t={time}|clock={time/1000}|count={frame}'],[f'en|v=${{/transcript/0/result}}|t={time}|clock={time/1000}|count={frame}']]
    if changed:templates[1].insert(0,'queued before failure')
    values={'/draws/1/'+('1' if changed else '0')+'/x':125 if changed else 124,'/personal_options/1/Language':'fr' if changed else 'en'}
    if duplicate:values['/duplicate']=True
    action=accept(frame,values=values,inputs=inputs or [{},{}]);action['expect']['text_templates']=templates;return action
def template():
    trace=json.loads((ROOT/'research/trace_suite.template.json').read_text())
    cases=[]
    special={'trace-presentation-return-mutation-mismatch-recovery','trace-presentation-extra-return-mutation-no-reuse','trace-personal-loop-cardinality','trace-generic-loop-unresolved','trace-tail-loop-context'}
    for source in trace['cases']:
        if source['mode']!='trace' or source['id'] in special:continue
        item=copy.deepcopy(source);item['mode']='slice';item['id']=source['id'].replace('trace-','slice-',1);cases.append(item)
    name='Random Gate Fixture';changed=[{}, {'triggered':[77]}];extra=[{}, {'pressed':[99]}]
    cases.append(case('slice-personal-new-range-keeps-ui','presentation_random','slice',configs(name),[random_frame(1),random_frame(2,changed,True),random_frame(2,changed,True,True)]))
    cases.append(case('slice-personal-extra-random-no-execution','presentation_random','slice',configs(name),[random_frame(1),random_frame(2,extra),random_frame(2,extra,duplicate=True)]))
    for fixture in ('trace_loop','trace_generic_loop','trace_loop_tail'):
        suffix='|coins=${/world/coins/0}' if fixture!='trace_generic_loop' else ''
        cases.append(case('slice-'+fixture.replace('_','-'),fixture,'slice',[{},{}],[accept(1,templates=['award=${/effects/0/amount}'+suffix]*2)],options=OPTIONS))
    name='Slice Mixed Fields';frames=[]
    for frame in (1,2):
        previous='0' if frame==1 else '${/transcript/0/result}' # Frame 1/2 seeded awards are equal in this model.
        frames.append(accept(frame,templates=[f'zh|award=${{/effects/0/amount}}|previous={previous}|count={frame}',f'en|award=${{/effects/0/amount}}|previous={previous}|count={frame}'],values={'/draws/1/0/x':124 if frame==1 else 125},inputs=[{},{}] if frame==1 else changed))
    cases.append(case('slice-mixed-fields-alias-closure-save','slice_mixed_fields','slice',configs(name),frames))
    for identity,fixture,name,error in (
        ('slice-unresolved-control-recovery','slice_unresolved_control','Slice Control Gate','Ambiguous slice control'),
        ('slice-unmatched-query-recovery','slice_unmatched_query','Slice Query Gate','Unmatched slice state point')):
        # Rejection is diagnostic success, never compatibility success.
        cases.append(case(identity,fixture,'slice',configs(name),[
            accept(1,values={'/world/frame':1}),reject(2,error,changed,gate=True),accept(2,values={'/world/frame':2}),accept(2,values={'/duplicate':True})]))
    cases.append(case('slice-multiple-authority-consumers','slice_multiple_consumers','slice',[{},{}],[reject(1,'Ambiguous slice contribution',gate=True)],options=OPTIONS))
    cases.append(case('slice-setting-versus-game-result-ambiguity','slice_setting_ambiguity','slice',configs('Slice Setting Ambiguity',2),[reject(1,'Ambiguous slice draw',gate=True)]))
    action=accept(1,values={'/world/coins/0':1});action['expect']['texts']=[['zh|world=0','zh|literal=0|17|literal'],['en|world=0','en|literal=0|17|literal']]
    cases.append(case('slice-identical-json-distinct-producers','slice_json_versions','slice',configs('Slice JSON Versions'),[action]))
    return {'schema':'isaac-runtime-suite-1','purpose':'Execution projection coin-model candidate; expected refusals remain incompatibilities','cases':cases}
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with a.output.open('x',encoding='utf-8') as f:json.dump(template(),f,indent=2)
    print(json.dumps({'cases':len(template()['cases']),'template':str(a.output)}))
