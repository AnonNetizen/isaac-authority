"""Reconstruct semantic evidence from raw or packed records without a disk copy."""
import struct
from audit_wire import records
from read_compact_audit import cbor,typed
def read(path):
    nodes={};operations={};sites={};arrays={2:[],3:[],4:[],8:[],10:[],11:[],14:[],16:[]};codes={};root=None;sequence=0
    for channel,identity,payload,header,stored in records(path):
        sequence+=1
        if channel==5:operations[identity]=payload.decode('utf-8')
        elif channel==6:sites[identity]=cbor(payload)
        elif channel==1:nodes[identity]=typed(payload,identity,operations,sites)
        elif channel in arrays:
            if identity!=len(arrays[channel])+1:raise ValueError('Audit array identity changed')
            if channel==11:
                descriptor,site,before,after,epoch=struct.unpack('<IIIIq',payload)
                arrays[channel].append([descriptor,epoch,site,-1 if before==0xffffffff else before,-1 if after==0xffffffff else after])
            else:arrays[channel].append(cbor(payload))
        elif channel==7:root=cbor(payload)
        elif channel==13:
            code=cbor(payload);codes[(code['source_sha256'],code['prototype'])]=code
        elif channel in (9,12):cbor(payload)
        elif channel==15:
            if len(payload)!=76 or struct.unpack_from('<I',payload,8)[0]>=identity:raise ValueError('Invalid descriptor index chain')
        else:raise ValueError('Unknown audit channel')
    if set(nodes)!=set(range(1,len(nodes)+1)):raise ValueError('Audit producer gap')
    return {'nodes':[nodes[i] for i in range(1,len(nodes)+1)],'consumption_records':arrays[2],'storage_versions':arrays[3],'static_regions':arrays[4],'purpose_records':arrays[14],'cache_descriptors':arrays[8],'cache_sites':arrays[10],'cache_uses':arrays[11],'code':[codes[k] for k in sorted(codes)],'root':root,'records':sequence,'consumer_records':arrays[16]}
