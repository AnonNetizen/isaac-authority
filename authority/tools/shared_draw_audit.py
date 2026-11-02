"""Bounded, lossless decoder for private CLI draw audit references."""
import copy,hashlib,json
MAX_EXPANDED=16*1024*1024
def _bad_constant(value):raise ValueError('Nonfinite shared audit JSON')
def decode(report):
    if not isinstance(report,dict):raise ValueError('Shared audit report type invalid')
    table=report.pop('shared_draw_audit',None)
    if table is None:return report
    if not isinstance(table,dict)or table.get('schema')!='ia-shared-draw-audit-1'or table.get('self_round_trip_verified')is not True:raise ValueError('Shared draw audit schema invalid')
    states=table.get('states');frames=table.get('frames')
    if not isinstance(states,list)or not isinstance(frames,list)or len(states)>4096 or len(frames)>256:raise ValueError('Shared draw dictionary capacity exceeded')
    total=0
    def entry(record):
        nonlocal total
        if not isinstance(record,dict)or set(record)!={'json','sha256'}or not isinstance(record['json'],str):raise ValueError('Shared draw dictionary entry invalid')
        raw=record['json'].encode('utf-8');total+=len(raw)
        if total>2*1024*1024:raise ValueError('Shared draw dictionary byte quota exceeded')
        if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Shared draw dictionary hash mismatch')
        return json.loads(record['json'],parse_constant=_bad_constant),len(raw)
    decoded_states=[entry(record)for record in states]
    if any(not isinstance(value,dict)for value,_ in decoded_states):raise ValueError('Shared capture state type invalid')
    decoded_frames=[]
    def ref(value,key,items):
        if not isinstance(value,dict)or set(value)!={key}or type(value[key])is not int or not 0<=value[key]<len(items):raise ValueError('Shared draw reference invalid')
        return items[value[key]]
    for record in frames:
        value,size=entry(record)
        if not isinstance(value,list):raise ValueError('Shared draw frame type invalid')
        for command in value:
            if not isinstance(command,dict):raise ValueError('Shared draw command invalid')
            if'capture_state'in command:
                state,added=ref(command['capture_state'],'$ia_capture_state',decoded_states);size+=added
                if size>MAX_EXPANDED:raise ValueError('Shared draw expansion capacity exceeded')
                command['capture_state']=state
        decoded_frames.append((value,size))
    expanded=0
    def frame_at(container,key):
        nonlocal expanded
        frame,size=ref(container[key],'$ia_draw_frame',decoded_frames);expanded+=size
        if expanded>MAX_EXPANDED:raise ValueError('Shared draw expansion capacity exceeded')
        container[key]=copy.deepcopy(frame)
    semantic=report.get('semantic',{})
    if'draws'in semantic:
        if not isinstance(semantic['draws'],list)or len(semantic['draws'])>4:raise ValueError('Shared semantic frame count invalid')
        for i in range(len(semantic['draws'])):frame_at(semantic['draws'],i)
    steps=report.get('steps')
    if not isinstance(steps,list)or len(steps)>512:raise ValueError('Shared audit step capacity exceeded')
    for step in steps:
        if'draws'in step:frame_at(step,'draws')
        if'branch_views'in step:
            for key in ['draws','ordinary_draws']:
                if key in step['branch_views']:frame_at(step['branch_views'],key)
    report['draw_audit_transport']=dict(schema=table['schema'],states=len(states),frames=len(frames),dictionary_bytes=total,expanded_frame_byte_bound=expanded,self_round_trip_verified=True)
    return report
