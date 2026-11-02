"""Independent bounded decoder; reconstruct exact graph evidence from its journal."""
import struct,zlib

def cbor(data):
    at=0
    def take(n):
        nonlocal at
        if n<0 or at+n>len(data):raise ValueError('Truncated CBOR metadata')
        out=data[at:at+n];at+=n;return out
    def value(depth=0):
        if depth>256:raise ValueError('CBOR nesting exceeds model bound')
        tag=take(1)[0];major=tag>>5;info=tag&31
        if major==7:
            if info==20:return False
            if info==21:return True
            if info==22:return None
            if info in (25,26,27):return struct.unpack({25:'>e',26:'>f',27:'>d'}[info],take({25:2,26:4,27:8}[info]))[0]
            raise ValueError('Unsupported CBOR simple value')
        n=info if info<24 else int.from_bytes(take({24:1,25:2,26:4,27:8}.get(info,0)),'big')
        if info>=28:raise ValueError('Unsupported indefinite CBOR')
        if major==0:return n
        if major==1:return -1-n
        if major==3:return take(n).decode('utf-8')
        if major==4:return [value(depth+1) for _ in range(n)]
        if major==5:
            result={}
            for _ in range(n):
                key=value(depth+1)
                if not isinstance(key,str) or key in result:raise ValueError('Invalid CBOR metadata key')
                result[key]=value(depth+1)
            return result
        raise ValueError('Unsupported CBOR metadata type')
    result=value()
    if at!=len(data):raise ValueError('Trailing CBOR metadata')
    return result

def typed(payload,identity,operations,sites):
    epoch,op,site,owner,previous,upvalue,kind,bits=struct.unpack_from('<q6IQ',payload);at=40
    def blob():
        nonlocal at
        if at+4>len(payload):raise ValueError('Truncated typed blob length')
        n=struct.unpack_from('<I',payload,at)[0];at+=4
        if at+n>len(payload):raise ValueError('Truncated typed blob')
        result=payload[at:at+n];at+=n;return result
    def ids():
        nonlocal at
        if at+4>len(payload):raise ValueError('Truncated operand length')
        n=struct.unpack_from('<I',payload,at)[0];at+=4
        if n>(len(payload)-at)//4:raise ValueError('Truncated operand list')
        result=list(struct.unpack_from('<'+'I'*n,payload,at));at+=n*4
        if any(x>=identity for x in result):raise ValueError('Producer is not earlier')
        return result
    raw=blob();data=ids();control=ids();detail=cbor(blob())
    if at!=len(payload):raise ValueError('Trailing typed bytes')
    if kind==0:scalar={'type':'nil'}
    elif kind==1:scalar={'type':'boolean','value':bool(bits)}
    elif kind==2:scalar={'type':'integer','value':struct.unpack('<q',struct.pack('<Q',bits))[0]}
    elif kind==3:scalar={'type':'number','value':struct.unpack('<d',struct.pack('<Q',bits))[0]}
    elif kind==4:scalar={'type':'string','hex':raw.hex()}
    elif kind==5:scalar={'type':'nonfinite'}
    elif kind in (6,7,8,9):scalar={'type':{6:'table',7:'function',8:'native_closure',9:'native_function'}[kind],'object':bits}
    elif kind==10:scalar={'type':'deferred','expression':bits}
    elif kind in (11,12,13):scalar={'type':{11:'unresolved',12:'structure',13:'object_source'}[kind]}
    elif kind==14:scalar=cbor(raw)
    else:raise ValueError('Unknown typed scalar')
    return {'id':identity,'epoch':epoch,'operation':operations[op+1],'value':scalar,'data':data,'control':control,'site':sites[site] if site else None,'detail':detail}

def read(path):
    nodes={};operations={};sites={};arrays={2:[],3:[],4:[],8:[],10:[],11:[],14:[],16:[]};codes={};root=None;sequence=0
    with path.open('rb') as stream:
        while header:=stream.read(32):
            if len(header)!=32:raise ValueError('Truncated audit header')
            magic,channel,identity,size,seq,crc,header_crc=struct.unpack('<IIIIQII',header)
            if magic!=0x31414349 or seq!=sequence+1 or zlib.crc32(header[:28])!=header_crc:raise ValueError('Audit header integrity/sequence failure')
            if size>8*1024*1024:raise ValueError('Audit record exceeds bound')
            payload=stream.read(size)
            if len(payload)!=size or zlib.crc32(payload)!=crc:raise ValueError('Audit payload integrity failure')
            sequence=seq
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
            elif channel in (9,12):cbor(payload) # semantic view and GC audit events
            elif channel==15:
                if len(payload)!=76 or struct.unpack_from('<I',payload,8)[0]>=identity:raise ValueError('Invalid descriptor index chain')
            else:raise ValueError('Unknown audit channel')
    if set(nodes)!=set(range(1,len(nodes)+1)):raise ValueError('Audit producer gap')
    return {'nodes':[nodes[i] for i in range(1,len(nodes)+1)],'consumption_records':arrays[2],'storage_versions':arrays[3],
            'static_regions':arrays[4],'purpose_records':arrays[14],'cache_descriptors':arrays[8],'cache_sites':arrays[10],'cache_uses':arrays[11],
            'code':[codes[k] for k in sorted(codes)],'root':root,'records':sequence,'consumer_records':arrays[16]}
