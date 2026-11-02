"""Export actual source-anchor intersections; never equate them to semantic proof."""
import gzip,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]

def anchors(graph,tag):
    pending=[tag];seen=set();found={}
    while pending:
        tag=pending.pop()
        if not tag or tag in seen:continue
        if len(seen)>=4096:raise RuntimeError('Sparse graph traversal capacity exceeded')
        if not 0<tag<=len(graph['nodes']):raise RuntimeError('Invalid sparse reference')
        seen.add(tag);n=graph['nodes'][tag-1]
        if n['id']!=tag:raise RuntimeError('Noncanonical sparse node identity')
        if n['op']=='config-field':
            root=graph['nodes'][n['root']-1]
            if root['op']!='store-root':raise RuntimeError('Unproven configuration root')
            identity=dict(root['identity'],json_pointer=n['path'])
            key=json.dumps(identity,sort_keys=True,separators=(',',':'))
            found[key]=dict(source=identity,value_version=tag,actual=n['actual'])
        for a in n.get('args',[]):
            if a['tag']>=tag:raise RuntimeError('Sparse graph is not an immutable DAG')
            pending.append(a['tag'])
    return found

def analyze(report):
    host,personal=report['sparse_provenance'];bindings=[]
    for contribution in host['sinks']:
        if not contribution['api'].startswith('world.'):continue
        supplied=anchors(host,contribution['tag'])
        for display in personal['sinks']:
            if display['api']!='hud.text':continue
            used=anchors(personal,display['tag'])
            for key in sorted(supplied.keys()&used.keys()):
                bindings.append(dict(authority_api=contribution['api'],authority_argument=contribution['actual'],authority_source=supplied[key],personal_source=used[key],display_value=display['actual'],source_anchor_correspondence=True,semantic_correspondence_proven=False,projection_applied=False))
    return dict(schema='sparse-source-anchor-observation-1',candidates=bindings,field_write_identity_complete=False,control_dependency_complete=False,world_query_timeline_resolved=False,world_projection_gate_passed=False)

if __name__=='__main__':
    d=json.loads(gzip.decompress(Path(sys.argv[1]).read_bytes()))
    row=next(c for c in d['cases']if c['id']=='authority-reward-personal-config')
    result=analyze(row['reports'][1]);p=Path(sys.argv[2]);p.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(source_anchor_candidates=len(result['candidates']),semantic_correspondence_proven=False)))
