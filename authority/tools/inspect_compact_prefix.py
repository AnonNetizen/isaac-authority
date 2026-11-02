"""Stream-check an audit, including failed-run tails, without decoding the graph."""
import argparse,collections,json,struct,zlib
from pathlib import Path

def inspect(path,published=None):
    at=0;sequence=0;channels=collections.Counter();error=None
    with path.open('rb') as stream:
        while True:
            header=stream.read(32)
            if not header:break
            if len(header)!=32:error='truncated header';break
            magic,channel,identity,size,seq,payload_crc,header_crc=struct.unpack('<IIIIQII',header)
            if magic!=0x31414349 or zlib.crc32(header[:28])!=header_crc or seq!=sequence+1 or size>8*1024*1024:error='invalid header/sequence';break
            remaining=size;crc=0
            while remaining:
                chunk=stream.read(min(remaining,65536))
                if not chunk:error='truncated payload';break
                crc=zlib.crc32(chunk,crc);remaining-=len(chunk)
            if error:break
            if crc!=payload_crc:error='payload checksum';break
            at+=32+size;sequence=seq;channels[channel]+=1
    physical=path.stat().st_size
    return {'file':path.name,'complete_record_prefix_bytes':at,'physical_bytes':physical,'published_bytes':published,'prefix_matches_published':published is None or at==published,'whole_file_valid':error is None and at==physical,'tail_error':error,'records':sequence,'channels':dict(channels),'final_root_present':channels[7]>0}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('path',type=Path);a=p.parse_args();print(json.dumps(inspect(a.path)))
