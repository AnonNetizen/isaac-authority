"""Independent record-lz-1 decoder; bounded per-record and streaming expansion."""
import hashlib,struct,zlib
RAW=0x31414349;PACKED=0x32414349
RECORD_LIMIT=8*1024*1024;CODEC_LIMIT=256*1024;STREAM_LIMIT=64*1024*1024
def unpack(data):
    if len(data)<8:raise ValueError('Audit codec prefix truncated')
    expected,crc=struct.unpack_from('<II',data)
    if expected<128 or expected>CODEC_LIMIT or len(data)>=expected:raise ValueError('Audit codec decoded length outside bound')
    at=8;out=bytearray()
    while at<len(data):
        token=data[at];at+=1
        if token<128:
            length=token+1
            if length>len(data)-at or length>expected-len(out):raise ValueError('Audit codec literal overrun')
            out.extend(data[at:at+length]);at+=length
        else:
            length=(token&127)+4
            if len(data)-at<2 or length>expected-len(out):raise ValueError('Audit codec match overrun')
            distance=data[at]|(data[at+1]<<8);at+=2
            if not distance or distance>len(out):raise ValueError('Audit codec invalid distance')
            # Copies overlap exactly as a bytewise LZ recurrence; no history.
            begin=len(out)-distance;seed=bytes(out[begin:begin+min(distance,length)]);out.extend((seed*((length+len(seed)-1)//len(seed)))[:length])
    if len(out)!=expected:raise ValueError('Audit codec decoded length mismatch')
    if zlib.crc32(out)!=crc:raise ValueError('Audit decoded payload checksum mismatch')
    return bytes(out)
def records(path):
    sequence=0;expanded=0
    with path.open('rb') as stream:
        while header:=stream.read(32):
            if len(header)!=32:raise ValueError('partial header after forced termination')
            magic,channel,identity,size,seq,crc,hcrc=struct.unpack('<IIIIQII',header)
            if magic not in (RAW,PACKED) or seq!=sequence+1 or zlib.crc32(header[:28])!=hcrc:raise ValueError('header integrity failure')
            if size>RECORD_LIMIT:raise ValueError('record size exceeds frozen limit')
            stored=stream.read(size)
            if len(stored)!=size:raise ValueError('partial record after forced termination')
            if zlib.crc32(stored)!=crc:raise ValueError('payload integrity failure')
            payload=unpack(stored) if magic==PACKED else stored
            expanded+=32+len(payload)
            if expanded>STREAM_LIMIT:raise ValueError('decoded stream exceeds 64 MiB safety bound')
            sequence=seq;yield channel,identity,payload,header,stored
def prefix(path):
    total=0;sequence=0;counts={};error=None;raw=0;stored=0;packed=0;canonical=hashlib.sha256()
    try:
        for channel,identity,payload,header,encoded in records(path):
            sequence+=1;total+=32+len(encoded);raw+=len(payload);stored+=len(encoded);packed+=struct.unpack_from('<I',header)[0]==PACKED
            key=str(channel);counts[key]=counts.get(key,0)+1
            normalized=struct.pack('<IIIIQI',RAW,channel,identity,len(payload),sequence,zlib.crc32(payload));canonical.update(normalized+struct.pack('<I',zlib.crc32(normalized))+payload)
    except ValueError as e:error=str(e)
    return {'complete_records':sequence,'complete_record_bytes':total,'channels':counts,'tail_error':error,'file_bytes':path.stat().st_size,'raw_payload_bytes':raw,'stored_payload_bytes':stored,'compressed_records':packed,'canonical_sha256':canonical.hexdigest(),'decoded_stream_limit':STREAM_LIMIT}
