"""Dual views first preserve ordinary Lua results, bytes, heap state and errors."""
import unittest
from test_slice_runtime import SliceRuntimeTests

class Slice3RuntimeTests(SliceRuntimeTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.runner=cls.bin/'authority-slice3-research.exe';cls.trace=cls.bin/'ia_lua533_slice3.dll'
    def test_named_storage_and_explicit_operands(self):
        out=self.compare('local first=2;local second=first;first=7;return first,second')
        self.assertEqual(out['values'],[7,2]);self.assertTrue(out['value_graph']['storage_versions'])
        self.assertEqual(out['value_graph']['schema'],'isaac-value-graph-3')
        self.assertEqual(out['value_graph']['game_views'],{})
        out=self.compare('local a=2;return a*3+4')
        arithmetic=[n for n in out['value_graph']['nodes'] if n['operation'] in ('MUL','ADD')]
        self.assertEqual([len(n['detail']['operands']) for n in arithmetic],[2,2])

if __name__=='__main__':unittest.main(defaultTest='Slice3RuntimeTests')
