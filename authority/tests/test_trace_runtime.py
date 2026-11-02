"""VM dependency propagation and semantic comparison; never opens or attaches Isaac."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

class TraceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bin=Path(os.environ['IA_TRACE_BINARY_DIR']).resolve()
        cls.runner=cls.bin/'authority-trace-research.exe'
        cls.trace=cls.bin/'ia_lua533_trace.dll';cls.reference=cls.bin/'ia_lua533_reference.dll'
    def evaluate(self,code,traced=True):
        dll=self.trace if traced else self.reference
        with tempfile.TemporaryDirectory(prefix='isaac-trace-') as temp:
            source=Path(temp)/'eval.lua';source.write_text(code,encoding='utf-8')
            result=subprocess.run([str(self.runner),'--evaluate',str(dll),hashlib.sha256(dll.read_bytes()).hexdigest(),str(source),'trace' if traced else 'plain'],capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(result.stdout)
            def decode(v):
                if isinstance(v,dict) and 'text_hex' in v:
                    raw=bytes.fromhex(v['text_hex'])
                    try:return raw.decode('utf-8')
                    except UnicodeDecodeError:return raw
                return v
            report['values']=[decode(v) for v in report['values']]
            return report
    def compare(self,code):
        traced=self.evaluate(code);plain=self.evaluate(code,False)
        self.assertTrue(traced['success'],traced.get('error'));self.assertTrue(plain['success'],plain.get('error'))
        self.assertEqual(traced['values'],plain['values']);return traced
    def test_register_arithmetic_and_strings(self):
        out=self.compare("local n=__tag(7,'personal_config');return n*2+1,'coins='..n,n//2,n&3,-n")
        self.assertEqual(out['values'],[15,'coins=7',3,3,-7])
        for origins in out['origins']:self.assertIn('personal_config',origins)
    def test_table_alias_and_field(self):
        out=self.compare("local t={a=__tag(9,'world_read')};local alias=t;return alias.a")
        self.assertIn('world_read',out['origins'][0])
    def test_table_key_dependency(self):
        out=self.compare("local t={a=12};local key=__tag('a','personal_input');return t[key]")
        self.assertIn('personal_input',out['origins'][0])
    def test_table_length_after_dependent_write(self):
        out=self.compare("local t={};t[__tag(1,'personal_input')]=3;return #t,t[1]")
        self.assertEqual(out['values'],[1,3]);self.assertTrue(all('personal_input' in x for x in out['origins']))
    def test_missing_table_field_after_dependent_delete(self):
        out=self.compare("local t={x=3};t[__tag('x','personal_input')]=nil;return t.x,#t")
        self.assertEqual(out['values'],[None,0]);self.assertTrue(all('personal_input' in x for x in out['origins']))
    def test_closure_upvalue_and_mutation(self):
        out=self.compare("local n=__tag(2,'world_rng');local function f() n=n+3;return n end;return f(),f()")
        self.assertEqual(out['values'],[5,8]);self.assertTrue(all('world_rng' in x for x in out['origins']))
    def test_implicit_branch_dependency(self):
        for flag in ('true','false'):
            out=self.compare(f"local b=__tag({flag},'personal_input');local x;if b then x=4 else x=5 end;return x")
            self.assertIn('personal_input',out['origins'][0])
    def test_branch_control_ends_at_join(self):
        out=self.compare("local b=__tag(true,'personal_input');if b then local x=4 end;return 9")
        self.assertNotIn('personal_input',out['origins'][0])
    def test_skipped_assignment_still_depends_on_condition(self):
        out=self.compare("local b=__tag(false,'personal_input');local x=3;if b then x=4 end;return x")
        self.assertEqual(out['values'],[3]);self.assertIn('personal_input',out['origins'][0])
    def test_skipped_upvalue_write(self):
        out=self.compare("local x=3;local function f(b)if b then x=4 end end;f(__tag(false,'personal_input'));return x")
        self.assertEqual(out['values'],[3]);self.assertIn('personal_input',out['origins'][0])
    def test_skipped_table_write(self):
        out=self.compare("local t={x=3};if __tag(false,'personal_input') then t.x=4 end;return t.x")
        self.assertEqual(out['values'],[3]);self.assertIn('personal_input',out['origins'][0])
    def test_skipped_closure_call_write(self):
        out=self.compare("local x=3;local function f()x=4 end;if __tag(false,'personal_input') then f() end;return x")
        self.assertEqual(out['values'],[3]);self.assertIn('personal_input',out['origins'][0])
    def test_zero_iteration_dependency(self):
        out=self.compare("local n=__tag(0,'personal_config');local sum=0;for i=1,n do sum=sum+i end;return sum")
        self.assertEqual(out['values'],[0]);self.assertIn('personal_config',out['origins'][0])
    def test_skipped_nested_closure_call(self):
        out=self.compare("local x=3;local function g()x=4 end;local function f()g() end;if __tag(false,'personal_input') then f() end;return x")
        self.assertEqual(out['values'],[3]);self.assertIn('personal_input',out['origins'][0])
    def test_skipped_table_function_call(self):
        out=self.compare("local x=3;local t={f=function()x=4 end};if __tag(false,'personal_input') then t.f() end;return x")
        self.assertEqual(out['values'],[3]);self.assertIn('personal_input',out['origins'][0])
    def test_comparison_results(self):
        out=self.compare("local x=__tag(2,'world_read');return x>1,x==0,x<=3")
        self.assertEqual(out['values'],[True,False,True]);self.assertTrue(all('world_read' in x for x in out['origins']))
    def test_varargs_multiple_returns(self):
        out=self.compare("local function f(...)return ... end;return f(__tag(2,'world_read'),__tag(3,'personal_config'))")
        self.assertEqual(out['values'],[2,3]);self.assertIn('world_read',out['origins'][0]);self.assertIn('personal_config',out['origins'][1])
    def test_metatable_lookup_semantics(self):
        out=self.compare("local t=setmetatable({}, {__index=function(_,k)return __tag(12,'world_read') end});return t.x")
        self.assertEqual(out['values'],[12]);self.assertIn('world_read',out['origins'][0])
    def test_native_table_insert_index_dependency(self):
        out=self.compare("local t={3};table.insert(t,__tag(1,'personal_input'),7);return t[1],t[2]")
        self.assertEqual(out['values'],[7,3]);self.assertTrue(all('personal_input' in x for x in out['origins']))
    def test_native_table_sort_comparator_dependency(self):
        out=self.compare("local t={3,1,2};local backwards=__tag(true,'personal_config');table.sort(t,function(a,b)if backwards then return a>b else return a<b end end);return t[1],t[3]")
        self.assertEqual(out['values'],[3,1]);self.assertTrue(all('personal_config' in x for x in out['origins']))
    def test_unsupported_native_effects_are_explicit(self):
        for code in ('return os.getenv("PATH")','return math.random()','debug.setupvalue(function()end,1,3)','collectgarbage()','table.move({},1,0,1,{})'):
            out=self.evaluate(code);self.assertFalse(out['success']);self.assertIn('Unsupported trace native contract',out['error'])
    def test_finalizers_and_weak_tables_are_explicitly_rejected(self):
        for code in ("setmetatable({}, {__gc=function()end})","setmetatable({}, {__mode='k'})", "local m={};local t=setmetatable({},m);m.__mode='k'", "local m={};local t=setmetatable({},m);rawset(m,'__gc',function()end)"):
            out=self.evaluate(code);self.assertFalse(out['success']);self.assertIn('Unsupported trace metatable effect',out['error'])
    def test_numeric_loop_and_accumulator(self):
        out=self.compare("local n=__tag(3,'personal_config');local sum=0;for i=1,n do sum=sum+i end;return sum")
        self.assertEqual(out['values'],[6]);self.assertIn('personal_config',out['origins'][0])
    def test_generic_iteration_semantics(self):
        out=self.compare("local t={__tag(2,'world_rng'),4};local n=0;for _,v in ipairs(t) do n=n+v end;return n")
        self.assertEqual(out['values'],[6]);self.assertIn('world_rng',out['origins'][0])
    def test_known_c_string_propagation(self):
        out=self.compare("local s=__tag('abc','personal_config');return string.upper(s),string.len(s),tonumber(__tag('13','world_read'))")
        self.assertEqual(out['values'],['ABC',3,13]);self.assertIn('personal_config',out['origins'][0]);self.assertIn('world_read',out['origins'][2])
    def test_tail_call_preserves_return_origin(self):
        out=self.compare("local function g(x)return x+1 end;local function f(x)return g(x) end;return f(__tag(5,'world_read'))")
        self.assertEqual(out['values'],[6]);self.assertIn('world_read',out['origins'][0])
    def test_dynamic_load_preserves_semantics(self):
        out=self.compare("local f=assert(load('return function(x)return x+2 end','@dynamic','t'))();return f(__tag(5,'world_read'))")
        self.assertEqual(out['values'],[7]);self.assertIn('world_read',out['origins'][0])
    def test_dynamic_source_origin_is_not_lost(self):
        out=self.compare("local code=__tag('return 7','personal_config');local f=assert(load(code));return f()")
        self.assertEqual(out['values'],[7]);self.assertIn('personal_config',out['origins'][0])
    def test_unknown_native_is_rejected_before_execution(self):
        out=self.evaluate("return __opaque()")
        self.assertFalse(out['success']);self.assertIn('Unsupported trace C function',out['error'])
    def test_caught_unknown_native_still_marks_failure(self):
        out=self.evaluate("local ok=pcall(__opaque);return ok,12")
        self.assertTrue(out['success']);self.assertEqual(out['values'],[False,12]);self.assertIn('Unsupported trace C function',out['trace']['failure'])
    def test_protected_error_control_and_frame_cleanup(self):
        out=self.compare("local b=__tag(true,'personal_input');local ok=pcall(function()if b then error('x') end end);return ok,9")
        self.assertEqual(out['values'],[False,9]);self.assertIn('personal_input',out['origins'][0]);self.assertEqual(out['trace']['failure'],'')
    def test_instruction_budget(self):
        out=self.evaluate("while true do end")
        self.assertFalse(out['success']);self.assertIn('instruction budget',out['error'])
    def test_semantic_numeric_and_byte_strings(self):
        out=self.compare("local x=17;return x/2,x%3,2^4,~x,(x<<2),string.char(0,255)..'x',#'abc',not nil")
        self.assertEqual(out['values'][:5],[8.5,2,16,-18,68])
    def test_repeat_is_deterministic(self):
        code="local a=__tag(2,'world_read');local function f(x) if x>1 then return x+2 end return 0 end;return f(a)"
        self.assertEqual(self.evaluate(code),self.evaluate(code))

if __name__=='__main__':unittest.main()
