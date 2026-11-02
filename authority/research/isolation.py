"""Host-side shadow Lua VMs with checked API replay and atomic MODEL commits.

All VMs run on this computer. Guest rendering/input transport and J460 native world adapters
are deliberately absent. Unsupported boundaries stop the experiment, including inside pcall.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / '.tools'))
from lupa.lua53 import LuaRuntime, lua_type

class IsolationFailure(RuntimeError): pass
class TranscriptMismatch(IsolationFailure): pass
class UnsupportedBoundary(IsolationFailure): pass

def sha(data): return hashlib.sha256(data).hexdigest()

def wire(value):
    if isinstance(value, bytes): return {'bytes_hex':value.hex()}
    if value is None or isinstance(value,(bool,int,str)): return value
    if isinstance(value,float) and math.isfinite(value): return value
    if isinstance(value,(list,tuple)): return [wire(v) for v in value]
    if isinstance(value,dict): return {str(k):wire(v) for k,v in value.items()}
    raise UnsupportedBoundary('non-scalar API argument/result')

@dataclass(frozen=True)
class ModSource:
    name: str
    files: dict[str,bytes]
    entry: str = 'main.lua'
    definitions: bytes | None = None

    def __post_init__(self):
        object.__setattr__(self,'files',MappingProxyType({name:bytes(data) for name,data in self.files.items()}))

    @classmethod
    def directory(cls, root: Path, definitions=None):
        root=root.resolve(strict=True)
        files={}
        for path in sorted(root.rglob('*.lua')):
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise UnsupportedBoundary('module symlink outside selected root')
            content=path.read_bytes()
            if len(content)>4*1024*1024: raise UnsupportedBoundary('module source limit')
            files[path.relative_to(root).as_posix()]=content
        if 'main.lua' not in files: raise ValueError('Selected mod has no main.lua')
        return cls(root.name,files,definitions=definitions)

    def manifest(self):
        result={name:sha(data) for name,data in sorted(self.files.items())}
        if self.definitions is not None: result['@sdk/enums.lua']=sha(self.definitions)
        return result

    def module(self, requested: bytes):
        name=requested.decode('utf-8')
        if ':' in name or name.startswith(('/', '\\')) or '..' in name:
            raise UnsupportedBoundary('module path outside selected root')
        if name.endswith('.lua'): name=name[:-4]
        name=name.replace('\\','/').replace('.','/')+'.lua'
        for candidate in (name,'resources/'+name):
            if candidate in self.files: return self.files[candidate],('@'+self.name+'/'+candidate).encode()
        raise UnsupportedBoundary('module not in frozen source: '+name)

class WorldModel:
    def __init__(self, seed, coins):
        self.coins=list(coins); self.rng=random.Random(seed); self.frame=0; self.time_ms=0
        self.effects=[]

    def call(self, op, args):
        if op=='Isaac.GetTime': return self.time_ms
        if op=='Game.GetFrameCount': return self.frame
        if op=='os.clock': return self.time_ms/1000
        if op=='os.time': return self.time_ms//1000
        if op=='math.random':
            if not args: return self.rng.random()
            if len(args)==1: return self.rng.randint(1,self.integer(args[0]))
            if len(args)==2: return self.rng.randint(self.integer(args[0]),self.integer(args[1]))
        if op=='math.randomseed' and len(args)==1:
            self.rng.seed(self.integer(args[0])); return None
        if op=='Player.GetNumCoins' and len(args)==1: return self.coins[self.player(args[0])]
        if op=='Player.AddCoins' and len(args)==2:
            index,amount=self.player(args[0]),self.integer(args[1])
            self.coins[index]=max(0,min(99,self.coins[index]+amount))
            self.effects.append({'op':op,'player':index,'amount':amount})
            return None
        raise UnsupportedBoundary('unmapped world operation: '+op)

    @staticmethod
    def integer(value):
        if isinstance(value,bool) or not isinstance(value,int): raise UnsupportedBoundary('integer API argument required')
        return value

    def player(self,index):
        index=self.integer(index)
        if index not in (0,1): raise UnsupportedBoundary('unmapped player')
        return index

    def snapshot(self): return {'coins':list(self.coins),'frame':self.frame,'time_ms':self.time_ms}

class Context:
    def __init__(self, owner, slot):
        self.owner,self.slot=owner,slot
        self.mode='record' if slot==0 else 'replay'; self.tape=[]; self.cursor=0
        self.phase='load'; self.fault=None; self.draws=[]; self.logs=[]; self.instructions=0
        self.lua=LuaRuntime(encoding=None,unpack_returned_tuples=True,register_eval=False,
            register_builtins=False,attribute_filter=self.deny_attribute,max_memory=64*1024*1024)
        for key,method in {'__api':self.api,'__data':self.data,'__draw':self.draw,
            '__unsupported':self.unsupported,'__json_encode':self.json_encode,
            '__json_decode':self.json_decode,'__module_source':self.module_source,'__budget':self.budget}.items():
            self.lua.globals()[key.encode()]=method
        self.lua.execute((ROOT/'research'/'context.lua').read_bytes())
        self.execute=self.lua.globals()[b'__execute']; self.dispatch=self.lua.globals()[b'__dispatch']

    def deny_attribute(self,*args): return self.unsupported(b'python_attribute_access')

    def unsupported(self,name):
        self.fault='slot '+str(self.slot)+': unsupported '+(name.decode('utf-8','replace') if isinstance(name,bytes) else str(name))
        raise UnsupportedBoundary(self.fault)

    def budget(self):
        self.instructions+=1000
        if self.instructions>2_000_000: self.unsupported(b'instruction_budget')

    def begin(self,phase,tape=None):
        self.phase,self.cursor,self.fault,self.instructions=phase,0,None,0
        self.tape=[] if tape is None else deepcopy(tape)

    def check(self):
        if self.fault: raise IsolationFailure(self.fault)
        if self.mode=='replay' and self.cursor!=len(self.tape):
            raise TranscriptMismatch(f'slot {self.slot} {self.phase}: missing {len(self.tape)-self.cursor} authority calls')

    def api(self,operation,*args):
        op=operation.decode('ascii')
        try: actual={'op':op,'args':wire(args)}
        except Exception as error:
            self.fault=str(error); raise
        if self.mode=='record':
            try: result=self.owner._tx_world.call(op,args)
            except Exception as error:
                self.fault=str(error); raise
            self.tape.append({**actual,'result':wire(result)})
            return result
        if self.cursor>=len(self.tape):
            self.fault=f'slot {self.slot} {self.phase}: extra authority call {op}'
            raise TranscriptMismatch(self.fault)
        expected=self.tape[self.cursor]; self.cursor+=1
        if actual!={k:expected[k] for k in ('op','args')}:
            self.fault=f'slot {self.slot} {self.phase}: divergent world call: {op}'
            raise TranscriptMismatch(self.fault)
        return deepcopy(expected['result'])

    def data(self,operation,key,value=None):
        op=operation.decode('ascii'); store=self.owner._tx_stores[str(self.slot)]
        if op=='log':
            if not isinstance(key,bytes): return self.unsupported(b'log_bytes')
            self.logs.append(key.hex()); return None
        if op in ('has','load','save','remove'):
            if not isinstance(key,bytes): return self.unsupported(b'mod_data_name')
            name=key.hex()
            if op=='has': return bool(store.get(name,b''))
            if op=='load': return store.get(name,b'')
            if op=='save':
                if not isinstance(value,bytes) or len(value)>1024*1024: return self.unsupported(b'mod_data_value')
                store[name]=value; return None
            store.pop(name,None); return None
        controller=0 if value is None else value
        if not isinstance(key,int) or controller not in (0,1): return self.unsupported(b'input_argument')
        slot=self.slot if controller==0 else controller
        controls=self.owner._tx_inputs.get(str(slot),{})
        if op in ('triggered','pressed'): return key in controls.get(op,[])
        if op=='action': return controls.get('actions',{}).get(str(key),0.0)
        return self.unsupported(b'data_operation')

    def draw(self,text,x,y,r,g,b,a):
        if not isinstance(text,bytes) or len(text)>65536: return self.unsupported(b'text_bytes')
        numbers=(x,y,r,g,b,a)
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in numbers):
            return self.unsupported(b'draw_numbers')
        if len(self.draws)>=8192: return self.unsupported(b'draw_command_limit')
        self.draws.append({'op':'text','text_hex':text.hex(),'x':x,'y':y,
                           'color':{'r':r,'g':g,'b':b,'a':a}})

    def from_lua(self,value,depth=0):
        if depth>24: return self.unsupported(b'json_depth_or_cycle')
        if lua_type(value)=='table':
            items=list(value.items())
            if len(items)>8192: return self.unsupported(b'json_size')
            if items and all(isinstance(k,int) and not isinstance(k,bool) for k,v in items) and set(k for k,v in items)==set(range(1,len(items)+1)):
                return [self.from_lua(value[i],depth+1) for i in range(1,len(items)+1)]
            result={}
            for k,v in items:
                if not isinstance(k,bytes): return self.unsupported(b'json_object_key')
                result[k.decode('utf-8')]=self.from_lua(v,depth+1)
            return result
        if isinstance(value,bytes): return value.decode('utf-8')
        if value is None or isinstance(value,(bool,int,float)): return value
        return self.unsupported(b'json_userdata_or_function')

    def to_lua(self,value):
        if isinstance(value,dict): return self.lua.table_from({k.encode():self.to_lua(v) for k,v in value.items()})
        if isinstance(value,list): return self.lua.table_from([self.to_lua(v) for v in value])
        if isinstance(value,str): return value.encode()
        return value

    def json_encode(self,value):
        # Lua table iteration order changes between VMs; canonical JSON stabilizes this MODEL codec.
        return json.dumps(self.from_lua(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

    def json_decode(self,value):
        if not isinstance(value,bytes) or len(value)>1024*1024: return self.unsupported(b'json_input')
        return self.to_lua(json.loads(value))

    def module_source(self,name):
        try: return self.owner.source.module(name)
        except Exception as error: return self.unsupported(str(error))

class HostIsolation:
    """Two host-owned Lua VMs; one MODEL transaction may commit after checked replay."""
    def __init__(self, source: ModSource, configs=None, seed=12345, coins=(0,0), journal=None):
        self.source,self.seed,self.initial_coins=source,seed,list(coins)
        configs=configs or {'0':{},'1':{}}
        self.initial_configs={str(slot):{name:bytes(value) for name,value in store.items()} for slot,store in configs.items()}
        if set(self.initial_configs)!={'0','1'}: raise ValueError('Exactly two config contexts required')
        self.history=[]; self.journal=Path(journal) if journal else None
        self.failed_closed=False; self.last_failure=None
        self._build()

    def _build(self):
        self.world=WorldModel(self.seed,self.initial_coins); self.stores=deepcopy(self.initial_configs)
        self._tx_world=deepcopy(self.world); self._tx_stores=deepcopy(self.stores); self._tx_inputs={}
        self.contexts=[Context(self,slot) for slot in (0,1)]
        host,shadow=self.contexts
        try:
            self.load_stage='authority_sdk_definitions' if self.source.definitions else 'authority_mod'
            host.begin('load')
            if self.source.definitions: host.execute(self.source.definitions,b'@sdk/enums.lua')
            self.load_stage='authority_mod'
            host.execute(self.source.files[self.source.entry],('@'+self.source.name+'/'+self.source.entry).encode()); host.check()
            self.load_stage='shadow_sdk_definitions' if self.source.definitions else 'shadow_mod'
            shadow.begin('load',host.tape)
            if self.source.definitions: shadow.execute(self.source.definitions,b'@sdk/enums.lua')
            self.load_stage='shadow_mod'
            shadow.execute(self.source.files[self.source.entry],('@'+self.source.name+'/'+self.source.entry).encode()); shadow.check()
        except Exception as error: raise IsolationFailure(self.load_stage+': '+str(error)) from error
        self.load_stage='complete'
        self.initial_tape=deepcopy(host.tape)
        self.world,self.stores=self._tx_world,self._tx_stores

    def _run(self,request):
        self._tx_world=deepcopy(self.world); self._tx_stores=deepcopy(self.stores)
        self._tx_inputs=deepcopy(request['inputs']); self._tx_world.frame=request['frame']; self._tx_world.time_ms=request['time_ms']
        self._tx_world.effects=[]
        host,shadow=self.contexts
        for context in self.contexts: context.draws=[]; context.logs=[]
        transcripts,returns={},{}
        for phase,callback in (('update',1),('render',2)):
            host.begin(phase); canonical=wire(host.dispatch(callback)); host.check()
            transcripts[phase]=deepcopy(host.tape)
            shadow.begin(phase,host.tape); replayed=wire(shadow.dispatch(callback)); shadow.check()
            if canonical!=replayed: raise TranscriptMismatch('callback return differs in '+phase)
            returns[phase]=canonical
        return {'request':deepcopy(request),'transcripts':transcripts,'returns':returns,'world':self._tx_world.snapshot(),
                'effects':deepcopy(self._tx_world.effects),'draws':{str(c.slot):deepcopy(c.draws) for c in self.contexts},
                'logs':{str(c.slot):deepcopy(c.logs) for c in self.contexts},
                'stores':wire(self._tx_stores),'research_only':True,'native_game_adapter':False}

    def _restore(self,history):
        self._build()
        for record in history:
            regenerated=self._run(record['request'])
            if regenerated!=record: raise IsolationFailure('accepted history could not reconstruct private VM state')
            self.world,self.stores=self._tx_world,self._tx_stores

    def step(self,frame,time_ms,inputs=None):
        if self.failed_closed: raise IsolationFailure('session failed closed after reconstruction failure')
        if isinstance(frame,bool) or not isinstance(frame,int) or frame<=0: raise ValueError('Positive integer frame required')
        if isinstance(time_ms,bool) or not isinstance(time_ms,int) or time_ms<0: raise ValueError('Nonnegative integer time required')
        request={'frame':frame,'time_ms':time_ms,'inputs':deepcopy(inputs or {})}
        for record in self.history:
            if record['request']['frame']==frame:
                if record['request']!=request: raise IsolationFailure('duplicate frame has different input/time')
                return deepcopy(record)
        if self.history and frame<=self.history[-1]['request']['frame']: raise IsolationFailure('stale frame')
        if len(self.history)>=1024: raise IsolationFailure('experimental reconstruction history limit')
        try:
            result=self._run(request)
            candidate=self.history+[result]
            if self.journal: self._persist(candidate)
        except Exception as error:
            self.last_failure=str(error)
            try: self._restore(self.history)
            except Exception as recovery:
                self.failed_closed=True
                raise IsolationFailure('rollback reconstruction failed: '+str(recovery)) from error
            raise IsolationFailure(self.last_failure) from error
        self.world,self.stores=self._tx_world,self._tx_stores
        self.history=candidate
        return deepcopy(result)

    def checkpoint(self,history=None):
        return {'schema':1,'model_only':True,'source_manifest':self.source.manifest(),'context_sha256':sha((ROOT/'research'/'context.lua').read_bytes()),
                'model_adapter_sha256':sha(Path(__file__).read_bytes()),
                'seed':self.seed,'initial_coins':self.initial_coins,'initial_configs':wire(self.initial_configs),
                'initial_tape':self.initial_tape,'history':self.history if history is None else history}

    def _persist(self,history):
        body=json.dumps(self.checkpoint(history),sort_keys=True,separators=(',',':')).encode()
        envelope={'body_sha256':sha(body),'checkpoint':json.loads(body)}
        self.journal.parent.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=self.journal.parent,prefix='.isolation-',delete=False) as output:
                temporary=Path(output.name); output.write(json.dumps(envelope,separators=(',',':')).encode()); output.flush(); os.fsync(output.fileno())
            os.replace(temporary,self.journal); temporary=None
        finally:
            if temporary is not None: temporary.unlink(missing_ok=True)

    @classmethod
    def resume(cls,source,journal):
        envelope=json.loads(Path(journal).read_bytes()); body=envelope['checkpoint']
        expected=sha(json.dumps(body,sort_keys=True,separators=(',',':')).encode())
        if envelope['body_sha256']!=expected: raise IsolationFailure('checkpoint hash mismatch')
        if body['schema']!=1 or not body['model_only'] or body['source_manifest']!=source.manifest(): raise IsolationFailure('checkpoint code/schema mismatch')
        if body['context_sha256']!=sha((ROOT/'research'/'context.lua').read_bytes()): raise IsolationFailure('checkpoint adapter changed')
        if body.get('model_adapter_sha256')!=sha(Path(__file__).read_bytes()): raise IsolationFailure('checkpoint model adapter changed')
        configs={slot:{name:bytes.fromhex(value['bytes_hex']) for name,value in store.items()} for slot,store in body['initial_configs'].items()}
        instance=cls(source,configs,body['seed'],body['initial_coins'],journal)
        if instance.initial_tape!=body['initial_tape']: raise IsolationFailure('initialization replay mismatch')
        instance._restore(body['history']); instance.history=deepcopy(body['history'])
        return instance

def config_store(mod_name,first,second):
    key=mod_name.encode().hex()
    return {str(slot):{key:json.dumps(config,ensure_ascii=False,separators=(',',':')).encode()} for slot,config in enumerate((first,second))}
