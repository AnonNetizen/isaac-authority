"""Fixed-size Windows sampler page; no simulation or historical audit reads."""
import mmap,struct,uuid
SIZE=32768
TAGS=['other','source_mark','aggregate','field_index','invalidation','value_graph','graph_read','graph_pack','evidence','audit_pack','audit_io','cfg','ledger','presence','trace','presence_graph_read','origin_merge']
class ProfilePage:
    def __init__(self):
        self.name='Local\\IsaacInitProfile-'+uuid.uuid4().hex
        self.mapping=mmap.mmap(-1,SIZE,tagname=self.name);self.mapping[:]=bytes(SIZE)
    def close(self):self.mapping.close()
    def read(self):
        for _ in range(4):
            first=self.mapping[:];header=struct.unpack_from('<4I8Q4I',first)
            magic,version,owner_seq,sample_seq=header[:4]
            if magic!=0x31465049:return None
            if version!=1:raise RuntimeError('Unexpected profile page version')
            if owner_seq&1 or sample_seq&1:continue
            second=struct.unpack_from('<2I',self.mapping,8)
            if second!=(owner_seq,sample_seq):continue
            frequency,started,checkpoint,last_sample,used,limit,rejected,checkpoints=header[4:12]
            rows,current,flags,phase=header[12:16]
            if rows>256:raise RuntimeError('Profile work rows exceed fixed page')
            categories={}
            for index in range(rows):
                label,value=struct.unpack_from('<64sQ',first,368+index*72);label=label.split(b'\0',1)[0].decode('utf-8')
                if label in categories:raise RuntimeError('Duplicate profile work category')
                categories[label]=value
            calls=dict(zip(TAGS,struct.unpack_from('<17Q',first,96)));samples=dict(zip(TAGS,struct.unpack_from('<17Q',first,232)))
            n=sum(samples.values());seconds=max(0,last_sample-started)/frequency if frequency else 0
            return {'used':used,'limit':limit,'rejected_charge':rejected,'checkpoints':checkpoints,'categories':categories,'calls':calls,'samples':samples,'sample_count':n,'profile_seconds':seconds,'mean_sample_interval_ms':seconds*1000/n if n else None,'checkpoint_age_ms':max(0,last_sample-checkpoint)*1000/frequency if frequency else None,'sampled_wall_fractions':{k:v/n for k,v in samples.items()} if n else {},'phase':phase,'flags':flags,'work_accounting_valid':used==sum(categories.values()) and limit==10000000 and used<=limit and not(flags&2)}
        return None
