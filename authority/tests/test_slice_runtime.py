"""Reference execution comes first; graph claims are checked separately from labels."""
import os
from pathlib import Path
import unittest
from test_trace_runtime import TraceRuntimeTests

class SliceRuntimeTests(TraceRuntimeTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass();cls.runner=cls.bin/'authority-slice-research.exe';cls.trace=cls.bin/'ia_lua533_slice.dll'
    def ancestry(self,out,index):
        nodes={n['id']:n for n in out['value_graph']['nodes']};todo=[out['value_ids'][index]];seen=set()
        while todo:
            i=todo.pop()
            if not i or i in seen:continue
            seen.add(i);todo.extend(nodes[i]['data']);todo.extend(nodes[i]['control'])
        return [nodes[i] for i in sorted(seen)]
    def labels(self,out,index):
        return [n['detail']['label'] for n in self.ancestry(out,index) if n['operation']=='source']
    def test_value_versions_have_actual_producers(self):
        out=self.compare("local x=__tag(2,'world');local a=x+3;local b=a*2;return a,b")
        self.assertEqual(out['values'],[5,10]);self.assertNotEqual(*out['value_ids'])
        self.assertTrue(any(n['operation']=='ADD' for n in self.ancestry(out,1)))
        self.assertTrue(any(n['operation']=='MUL' for n in self.ancestry(out,1)))
    def test_fields_do_not_inherit_sibling_value(self):
        out=self.compare("local t={world=__tag(4,'world'),ui=__tag(8,'personal')};local a=t;return a.ui")
        self.assertTrue(any('personal' in x for x in self.labels(out,0)))
        self.assertFalse(any('world' in x for x in self.labels(out,0)))
    def test_field_write_versions_and_aliases(self):
        out=self.compare("local t={x=1};local alias=t;local a=t.x;alias.x=9;return a,t.x")
        self.assertEqual(out['values'],[1,9]);fields=[n for n in out['value_graph']['nodes'] if n['operation']=='field_write']
        self.assertGreaterEqual(len(fields),2);self.assertEqual(fields[0]['detail']['object'],fields[-1]['detail']['object'])
    def test_upvalue_versions_and_closure_identity(self):
        out=self.compare("local x=2;local function f()x=x+1;return x end;return f(),f()")
        self.assertEqual(out['values'],[3,4]);writes=[n for n in out['value_graph']['nodes'] if n['operation']=='SETUPVAL']
        self.assertEqual(len(writes),2);self.assertEqual(writes[0]['detail']['upvalue'],writes[1]['detail']['upvalue'])
    def test_skipped_branches_are_recorded_without_purity_claim(self):
        out=self.compare("local x=2;if __tag(false,'personal') then x=9 end;return x")
        regions=out['value_graph']['static_regions'];self.assertTrue(regions)
        self.assertTrue(any(r['potential_definitions'] for r in regions));self.assertTrue(all(not r['used_as_purity_proof'] for r in regions))
        self.assertTrue(any(n['operation']=='condition' for n in self.ancestry(out,0)))
    def test_skipped_upvalue_has_control_dependency(self):
        out=self.compare("local x=2;local function f(b)if b then x=9 end end;f(__tag(false,'personal'));return x")
        self.assertTrue(any(n['operation']=='condition' for n in self.ancestry(out,0)))
    def test_overwritten_field_has_only_current_data_producer(self):
        out=self.compare("local t={x=__tag(1,'world')};t.x=__tag(2,'personal');return t.x")
        self.assertTrue(any('personal' in x for x in self.labels(out,0)));self.assertFalse(any('world' in x for x in self.labels(out,0)))
    def test_string_producer_not_lost_during_tostring(self):
        out=self.compare("local x=__tag(3,'personal');return tostring(x)..'x'")
        self.assertTrue(any('personal' in x for x in self.labels(out,0)))
    def test_error_behavior_matches_reference(self):
        code="return pcall(function()error('ordinary failure')end)"
        out=self.compare(code);self.assertFalse(out['values'][0]);self.assertIn('ordinary failure',out['values'][1])
    def test_dynamic_code_and_cfg_are_hashed(self):
        out=self.compare("return assert(load('return 7','@nested'))()")
        self.assertGreaterEqual(len({c['source_sha256'] for c in out['value_graph']['code']}),2)
        self.assertTrue(all(c['cfg'] for c in out['value_graph']['code']))
    def test_graph_has_no_pointer_identity(self):
        out=self.compare("local t={x=2};local f=function()return t.x end;return f()")
        text=str(out['value_graph']);self.assertNotIn('0x',text);self.assertNotIn('pointer',text)

if __name__=='__main__':
    # Loading a base test class is convenient, but run it once against this ABI.
    unittest.main(defaultTest='SliceRuntimeTests')
