"""Bounded Lua 5.3.3 backwards recipes. Syntax only; never evaluate/project."""
import argparse,hashlib,json,struct,time
from pathlib import Path
OPS=['MOVE','LOADK','LOADKX','LOADBOOL','LOADNIL','GETUPVAL','GETTABUP','GETTABLE','SETTABUP','SETUPVAL','SETTABLE','NEWTABLE','SELF','ADD','SUB','MUL','MOD','POW','DIV','IDIV','BAND','BOR','BXOR','SHL','SHR','UNM','BNOT','NOT','LEN','CONCAT','JMP','EQ','LT','LE','TEST','TESTSET','CALL','TAILCALL','RETURN','FORLOOP','FORPREP','TFORCALL','TFORLOOP','SETLIST','CLOSURE','VARARG','EXTRAARG']
class Unresolved(Exception):pass
class Budget:
    def __init__(self,available):self.used=0;self.available=available;self.deadline=time.perf_counter()+5;self.nodes=0
    def charge(self,n=1):
        if n<0 or n>self.available-self.used:raise RuntimeError('Draw plan work limit exceeded')
        self.used+=n
        if time.perf_counter()>self.deadline:raise RuntimeError('Draw plan 5-second analysis deadline')
class Reader:
    def __init__(self,data,budget):self.data=data;self.at=0;self.budget=budget;self.functions=0
    def take(self,n):
        if n<0 or n>len(self.data)-self.at:raise RuntimeError('Truncated Lua prototype')
        self.budget.charge(1+(n+63)//64);v=self.data[self.at:self.at+n];self.at+=n;return v
    def uint(self,n=4):return int.from_bytes(self.take(n),'little')
    def count(self,maximum):
        n=int.from_bytes(self.take(4),'little',signed=True)
        if not 0<=n<=maximum:raise RuntimeError('Prototype count exceeds bounded contract')
        return n
    def string(self):
        n=self.uint(1)
        if n==255:n=self.uint(self.size_t)
        return None if n==0 else self.take(n-1)
    def function(self,depth=0):
        self.functions+=1
        if depth>32 or self.functions>1024:raise RuntimeError('Prototype tree capacity exceeded')
        source=self.string();line=self.uint();last=self.uint();params=self.uint(1);vararg=self.uint(1);stack=self.uint(1)
        code=[self.uint()for _ in range(self.count(65536))];constants=[]
        for _ in range(self.count(65536)):
            tag=self.uint(1)
            if tag==0:v={'type':'nil'}
            elif tag==1:v={'type':'boolean','value':bool(self.uint(1))}
            elif tag==19:v={'type':'integer','value':int.from_bytes(self.take(8),'little',signed=True)}
            elif tag==3:v={'type':'number','bits':self.take(8).hex()}
            elif tag in [4,20]:
                raw=self.string()
                if raw is None:raise RuntimeError('Missing constant string')
                v={'type':'string','hex':raw.hex()}
            else:raise RuntimeError('Unknown Lua constant tag')
            constants.append(v)
        upvalues=[(self.uint(1),self.uint(1))for _ in range(self.count(255))]
        children=[self.function(depth+1)for _ in range(self.count(1024))]
        self.take(self.count(65536)*4)
        for _ in range(self.count(65536)):self.string();self.take(8)
        for _ in range(self.count(255)):self.string()
        return dict(params=params,vararg=vararg,stack=stack,code=code,constants=constants,upvalues=upvalues,children=children)
    def load(self):
        if len(self.data)>262144:raise RuntimeError('Prototype image capacity exceeded')
        if self.take(4)!=b'\x1bLua'or self.uint(1)!=0x53 or self.uint(1)!=0 or self.take(6)!=b'\x19\x93\r\n\x1a\n':raise RuntimeError('Lua 5.3 binary header mismatch')
        sizes=self.take(5)
        if sizes[0]!=4 or sizes[1]not in [4,8]or sizes[2:]!=b'\x04\x08\x08':raise RuntimeError('Lua scalar ABI mismatch')
        self.size_t=sizes[1]
        if self.uint(8)!=0x5678 or struct.unpack('<d',self.take(8))[0]!=370.5:raise RuntimeError('Lua endian/number ABI mismatch')
        nup=self.uint(1);fn=self.function()
        if len(fn['upvalues'])!=nup or self.at!=len(self.data):raise RuntimeError('Lua function image boundary mismatch')
        return fn
def instruction(raw):
    op=raw&63
    if op>=len(OPS):raise RuntimeError('Unknown Lua opcode')
    return dict(op=OPS[op],a=(raw>>6)&255,c=(raw>>14)&511,b=(raw>>23)&511,bx=(raw>>14)&262143,ax=raw>>6)
class Planner:
    def __init__(self,fn,budget):
        self.fn=fn;self.budget=budget;self.code=[instruction(v)for v in fn['code']];self.nodes=[];self.memo={};self.active=set()
        self.captured_registers={index for child in fn['children']for instack,index in child['upvalues']if instack}
    def node(self,identity,**v):
        if identity in self.memo:return self.memo[identity]
        if self.budget.nodes>=4096:raise RuntimeError('Draw recipe global node capacity exceeded')
        self.budget.charge();self.budget.nodes+=1;idx=len(self.nodes);self.nodes.append(dict(id=idx,**v));self.memo[identity]=idx;return idx
    def constant(self,k):
        if not 0<=k<len(self.fn['constants']):raise RuntimeError('Invalid constant index')
        return self.node(('k',k),kind='constant',constant_index=k,value=self.fn['constants'][k])
    def upvalue(self,index,pc):
        if not 0<=index<len(self.fn['upvalues']):raise RuntimeError('Invalid upvalue index')
        return self.node(('up',index,pc),kind='upvalue',index=index,read_pc=pc,binding_verified=False)
    def rk(self,k,before,depth):return self.constant(k&255)if k&256 else self.register(k,before,depth+1)
    def register(self,reg,before,depth=0):
        if depth>64:raise RuntimeError('Draw recipe depth exceeded')
        if not 0<=reg<self.fn['stack']:raise RuntimeError('Register outside actual frame')
        query=('reg',reg,before)
        if query in self.memo:return self.memo[query]
        if query in self.active:raise Unresolved('cyclic-register-definition')
        self.active.add(query)
        try:
            result=self.resolve(reg,before,depth);self.memo[query]=result;return result
        finally:self.active.remove(query)
    def resolve(self,reg,before,depth):
        for pc in range(before-1,-1,-1):
            self.budget.charge();i=self.code[pc];op=i['op'];a,b,c=i['a'],i['b'],i['c']
            if op=='CALL'and reg>=a:
                # Compiler temporaries at/above the call base cannot be inferred
                # across a call without a return/stack-effect summary.
                raise Unresolved('call-result-or-temporary-summary-required@'+str(pc))
            if op=='CALL'and reg in self.captured_registers:raise Unresolved('captured-register-write-summary-required@'+str(pc))
            writes=a==reg and op in ['MOVE','LOADK','LOADKX','LOADBOOL','GETUPVAL','GETTABUP','GETTABLE','NEWTABLE','CLOSURE']+OPS[13:30]
            if op=='LOADNIL':writes=a<=reg<=a+b
            if op=='SELF':writes=reg in [a,a+1]
            if op=='VARARG':writes=reg>=a if b==0 else a<=reg<=a+b-2
            if not writes:continue
            if op=='MOVE':return self.register(b,pc,depth+1)
            if op=='LOADK':return self.constant(i['bx'])
            if op=='LOADKX':
                if pc+1>=len(self.code)or self.code[pc+1]['op']!='EXTRAARG':raise RuntimeError('LOADKX missing EXTRAARG')
                return self.constant(self.code[pc+1]['ax'])
            if op=='LOADBOOL':return self.node(('producer',pc,reg),kind='constant',pc=pc,value={'type':'boolean','value':bool(b)})
            if op=='LOADNIL':return self.node(('producer',pc,reg),kind='constant',pc=pc,value={'type':'nil'})
            if op=='GETUPVAL':return self.upvalue(b,pc)
            if op in ['GETTABUP','GETTABLE','SELF']:
                table=self.upvalue(b,pc)if op=='GETTABUP'else self.register(b,pc,depth+1)
                if op=='SELF'and reg==a+1:return table
                key=self.rk(c,pc,depth)
                return self.node(('producer',pc,reg),kind='query',pc=pc,table=table,key=key,result_version_verified=False,metamethod_contract_verified=False)
            if op in OPS[13:25]:return self.node(('producer',pc,reg),kind='binary',pc=pc,operator=op,left=self.rk(b,pc,depth),right=self.rk(c,pc,depth),operand_contract_verified=False)
            if op in ['UNM','BNOT','NOT','LEN']:return self.node(('producer',pc,reg),kind='unary',pc=pc,operator=op,operand=self.register(b,pc,depth+1),operand_contract_verified=False)
            if op=='CONCAT':return self.node(('producer',pc,reg),kind='concat',pc=pc,operands=[self.register(r,pc,depth+1)for r in range(b,c+1)],operand_contract_verified=False)
            raise Unresolved('producer-summary-required:'+op+'@'+str(pc))
        if reg<self.fn['params']:return self.node(('param',reg),kind='parameter',index=reg,caller_binding_verified=False)
        raise Unresolved('register-has-no-proven-definition:'+str(reg))
    def site(self,s):
        pc=s['pc']
        if not 0<=pc<len(self.code):raise RuntimeError('Site outside dumped prototype')
        i=self.code[pc]
        if not 0<=s['opcode']<len(OPS)or i['op']not in ['CALL','TAILCALL']or OPS[s['opcode']]!=i['op']or any(i[k]!=s[k]for k in ['a','b','c']):raise RuntimeError('Actual call site does not match immutable bytecode')
        out=dict(ordinal=s['ordinal'],callback=s['callback'],prototype=s['prototype'],pc=pc,bindings_verified=False,projection_allowed=False)
        try:
            if not s['direct_lua_call']:raise Unresolved('C-trampoline-argument-mapping-required')
            if i['b']==0:raise Unresolved('dynamic-argument-window-required')
            if i['b']<4:raise RuntimeError('Actual RenderText argument window is too small')
            for q in range(pc):
                self.budget.charge();v=self.code[q]
                if v['op']in ['JMP','EQ','LT','LE','TEST','TESTSET','FORLOOP','FORPREP','TFORCALL','TFORLOOP']or(v['op']=='LOADBOOL'and v['c']):raise Unresolved('control-flow-observations-required@'+str(q))
            out['roots']={name:self.register(i['a']+offset,pc)for offset,name in enumerate(['text','x','y'],1)};out['status']='symbolic-only'
        except Unresolved as e:out['status']='unresolved';out['reason']=str(e)
        return out
def inspect(capture,available_work):
    budget=Budget(available_work);images=capture['prototypes'];sites=capture['sites']
    if len(images)>64 or len(sites)>128:raise RuntimeError('Capture pool limits exceeded')
    planners={};total=0
    for fingerprint,raw in images.items():
        data=bytes.fromhex(raw);total+=len(data)
        if total>524288 or hashlib.sha256(data).hexdigest()!=fingerprint:raise RuntimeError('Prototype pool/hash mismatch')
        planners[fingerprint]=Planner(Reader(data,budget).load(),budget)
    output=[planners[s['prototype']].site(s)for s in sites]
    return dict(schema='draw-bytecode-recipes-1',analysis_work=budget.used,bindings_verified=False,projection_allowed=False,sites=output,prototypes={h:dict(nodes=p.nodes,instructions=len(p.code))for h,p in planners.items()})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--available-work',type=int,required=True);a=p.parse_args()
    if not 0<=a.available_work<=10000000:raise RuntimeError('Formal work budget required')
    if a.input.stat().st_size>2*1024**2:raise RuntimeError('Capture input limit')
    a.output.write_text(json.dumps(inspect(json.loads(a.input.read_text(encoding='utf-8')),a.available_work),indent=2)+'\n',encoding='utf-8')
