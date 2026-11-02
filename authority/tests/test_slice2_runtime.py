"""ABI 2 must preserve ordinary Lua before any projection is claimed."""
import unittest
from test_slice_runtime import SliceRuntimeTests

class Slice2RuntimeTests(SliceRuntimeTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.runner=cls.bin/'authority-slice2-research.exe'
        cls.trace=cls.bin/'ia_lua533_slice2.dll'

    def test_named_storage_is_versioned_without_changing_values(self):
        out=self.compare('local first=2;local second=first;first=7;return first,second')
        self.assertEqual(out['values'],[7,2])
        self.assertTrue(out['value_graph']['storage_versions'])
        self.assertEqual(out['value_graph']['schema'],'isaac-value-graph-2')

if __name__=='__main__':unittest.main(defaultTest='Slice2RuntimeTests')
