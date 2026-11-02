"""Functional suite and refusal checks using the pinned Lua DLL; never attaches to Isaac."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class RuntimeSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=Path(os.environ['IA_SUITE_BINARY'])
        cls.lua=Path(os.environ['IA_SUITE_LUA'])
        cls.manifest=json.loads((ROOT/'research/runtime_suite.json').read_text())
        cls.result=cls.run_manifest(cls.manifest)

    @classmethod
    def run_manifest(cls,manifest,expected_code=0):
        with tempfile.TemporaryDirectory(prefix='isaac-suite-check-') as temporary:
            source=Path(temporary)/'suite.json';source.write_text(json.dumps(manifest),encoding='utf-8')
            result=subprocess.run([str(cls.binary),str(cls.lua),str(cls.lua.parent),str(ROOT),str(source)],capture_output=True,text=True,encoding='utf-8')
            if result.returncode!=expected_code:raise AssertionError((result.returncode,result.stderr,result.stdout[:600]))
            return json.loads(result.stdout) if result.stdout else result.stderr

    def modified(self,change):
        manifest=copy.deepcopy(self.manifest);change(manifest);return manifest
    def refused(self,change,error):
        self.assertIn(error,self.run_manifest(self.modified(change),1))
    def test_repeat_has_identical_outcomes(self):
        self.assertEqual(self.result,self.run_manifest(self.manifest))
    def test_skipped_native_case_is_unverified(self):
        self.assertEqual(self.result['skipped'],1)
        case=self.result['cases'][-1];self.assertFalse(case['passed']);self.assertEqual(case['status'],'unverified_requires_game')
    def test_semantic_counterexample_is_not_a_compatibility_pass(self):
        case=next(c for c in self.result['cases'] if c['id']=='presentation-read-write-read-semantic-boundary')
        self.assertTrue(case['passed']);self.assertFalse(case['compatibility_passed'])
        self.assertEqual(case['restoration'],'passed');self.assertFalse(self.result['presentation_gate_passed'])
        candidates=[f['rejected_candidate'] for f in case['frames']]
        self.assertEqual(candidates[0],candidates[1]) # Rebuilt private counter and queues, not just coins.
    def test_failed_frame_restores_private_options_store_and_rng(self):
        case=next(c for c in self.result['cases'] if c['id']=='presentation-return-mutation-mismatch-recovery')
        self.assertTrue(case['frames'][1]['rollback_passed'])
        output=case['frames'][2]['output']
        self.assertEqual(output['personal_options'][1]['Language'],'en')
        self.assertEqual(json.loads(output['stores'][1]['Random Gate Fixture'])['x'],124)
        self.assertEqual(output['draws'][1][0]['x'],124)
        self.assertTrue(case['frames'][3]['duplicate_state_unchanged'])
    def test_authoritative_results_and_personal_settings(self):
        case=next(c for c in self.result['cases'] if c['id']=='presentation-config-extra-writes-cached-query-dedup')
        output=case['frames'][2]['output']
        self.assertEqual(output['world']['coins'],[3,0])
        self.assertEqual(output['suppressed'][0]['args'],[0,2])
        self.assertEqual(output['suppressed'][1]['args'],[0,2])
        self.assertEqual(json.loads(output['stores'][1]['Presentation Gate Fixture'])['amount'],2)
    def test_extra_identical_return_call_cannot_reuse_authority_result(self):
        case=next(c for c in self.result['cases'] if c['id']=='presentation-extra-return-mutation-no-reuse')
        self.assertTrue(case['frames'][1]['rollback_passed']);self.assertIn('Unmatched return-bearing',case['frames'][1]['error'])
    def test_identical_return_arguments_can_still_mean_different_operations(self):
        case=next(c for c in self.result['cases'] if c['id']=='presentation-identical-return-arguments-ambiguous')
        self.assertFalse(case['compatibility_passed']);self.assertTrue(case['frames'][0]['rollback_passed'])
        output=case['frames'][0]['rejected_candidate']
        first,second=output['transcript'][:2]
        self.assertEqual(first['op'],second['op']);self.assertEqual(first['args'],second['args'])
        self.assertNotEqual(first['result'],second['result'])
        self.assertNotEqual(output['draws'][0][0]['text_hex'],output['draws'][1][0]['text_hex'])
    def test_first_case_failure_does_not_contaminate_next_case(self):
        manifest=copy.deepcopy(self.manifest)
        manifest['cases'][0]['frames'][0]['expect']['values']['/world/coins/0']=99
        result=self.run_manifest(manifest,2)
        self.assertFalse(result['cases'][0]['passed']);self.assertEqual(result['cases'][0]['restoration'],'passed')
        self.assertTrue(result['cases'][1]['passed']);self.assertEqual(result['failed'],1)
    def test_changed_source_hash_refused(self):
        self.refused(lambda m:m['cases'][0]['mods'][0]['sha256'].update({'main.lua':'0'*64}),'frozen mod hash mismatch')
    def test_changed_bootstrap_refused(self):
        self.refused(lambda m:m.update({'bootstrap_sha256':'0'*64}),'bootstrap/enums hash mismatch')
    def test_traversal_refused(self):
        self.refused(lambda m:m['cases'][0]['mods'][0].update({'root':'../authority/fixtures/legacy_chaos'}),'outside roots')
    def test_missing_oracle_refused(self):
        self.refused(lambda m:m['cases'][0]['frames'][0].update({'expect':{'outcome':'accept'}}),'missing result oracle')
    def test_duplicate_case_refused(self):
        self.refused(lambda m:m['cases'].append(m['cases'][0]),'identity/mode')
    def test_frame_budget_refused(self):
        self.refused(lambda m:m['cases'][0].update({'frames':[m['cases'][0]['frames'][0]]*129}),'frame limit')
    def test_malformed_pointer_refused(self):
        self.refused(lambda m:m['cases'][0]['frames'][0]['expect']['values'].update({'invalid':1}),'JSON pointer')

if __name__=='__main__':unittest.main()
