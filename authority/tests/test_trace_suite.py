"""Temporal state, dependency reports, rollback, dedup and CLI refusal in the coin model."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class TraceSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bin=Path(os.environ['IA_TRACE_BINARY_DIR']).resolve()
        cls.game=Path(os.environ['IA_TRACE_GAME_DIR']).resolve()
        cls.runner=cls.bin/'authority-trace-research.exe';cls.dll=cls.bin/'ia_lua533_trace.dll'
        cls.sha=hashlib.sha256(cls.dll.read_bytes()).hexdigest()
        cls.manifest=json.loads((ROOT/'research/trace_suite.json').read_text())
        cls.report=cls.run_suite(cls.manifest)
    @classmethod
    def run_suite(cls,manifest,expected=0,sha=None,dll=None):
        with tempfile.TemporaryDirectory(prefix='isaac-trace-suite-') as temp:
            path=Path(temp)/'suite.json';path.write_text(json.dumps(manifest),encoding='utf-8')
            result=subprocess.run([str(cls.runner),'--suite',str(dll or cls.dll),sha or cls.sha,str(cls.game),str(ROOT),str(path)],capture_output=True,text=True,encoding='utf-8',timeout=45)
            if result.returncode!=expected:raise AssertionError((result.returncode,result.stderr,result.stdout[:800]))
            return json.loads(result.stdout) if result.stdout else result.stderr
    def case(self,name):return next(c for c in self.report['cases'] if c['id']==name)
    def selected(self,name):
        manifest=copy.deepcopy(self.manifest);manifest['cases']=[next(c for c in manifest['cases'] if c['id']==name)];return manifest
    def test_historical_13_cases_preserved_exactly(self):
        original=json.loads((ROOT/'research/runtime_suite.json').read_text())
        self.assertEqual(self.manifest['cases'][:13],original['cases'])
    def test_repeat_is_identical_and_uses_no_game_process(self):
        self.assertEqual(self.report,self.run_suite(self.manifest));self.assertFalse(self.report['game_process_used']);self.assertFalse(self.report['native_game_used'])
    def test_diagnostic_and_compatibility_are_distinct(self):
        self.assertTrue(self.report['diagnostic_passed']);self.assertEqual(self.report['failed'],0);self.assertEqual(self.report['skipped'],1)
        self.assertFalse(self.report['trace_mode_gate_passed']);self.assertFalse(self.report['generic_mod_compatibility_passed'])
        failed=[c['id'] for c in self.report['cases'] if c['mode']=='trace' and not c['compatibility_passed']]
        self.assertEqual(len(failed),5)
    def test_reads_use_before_and_after_state(self):
        out=self.case('trace-read-write-read')['frames'][0]['output'];events=out['transcript']
        reads=[(i,e) for i,e in enumerate(events) if e['op']=='Player.GetNumCoins']
        self.assertEqual([e['result'] for _,e in reads],[0,1])
        guest=out['execution_dependencies'][1]['world_calls']
        self.assertEqual([e['result'] for e in guest if e['op']=='Player.GetNumCoins'],[0,1])
        self.assertEqual(reads[0][1]['state_before']['coins'],[0,0]);self.assertEqual(reads[1][1]['state_before']['coins'],[1,0])
    def test_unique_consumption_exact_parameters_and_results(self):
        for case in self.report['cases']:
            if case['mode']!='trace':continue
            for frame in case['frames']:
                if frame['outcome']!='accept':continue
                out=frame['output'];tape=out['transcript'];guest=out['execution_dependencies'][1]['world_calls'];indices=[]
                for call in guest:
                    if not call.get('matched'):continue
                    i=call['authority_event'];indices.append(i);event=tape[i]
                    self.assertEqual(call['site']['key'],event['site']['key']);self.assertEqual(call['op'],event['op']);self.assertEqual(call['result'],event['result'])
                    if call['op'] not in ('Player.AddCoins','math.randomseed'):self.assertEqual(call['args'],event['args'])
                self.assertEqual(indices,sorted(set(indices)))
    def test_same_line_and_shared_helper_keep_distinct_sites(self):
        for fixture in ('trace-same-line','trace-helper','trace-tail','trace-dynamic','trace-cached'):
            out=self.case('trace-authority-award-'+fixture)['frames'][0]['output']
            rng=[e for e in out['transcript'] if e['op']=='math.random']
            self.assertEqual(len(rng),2);self.assertNotEqual(rng[0]['site']['key'],rng[1]['site']['key'])
            guest_rng=[e for e in out['execution_dependencies'][1]['world_calls'] if e['op']=='math.random']
            self.assertEqual(len(guest_rng),1);self.assertEqual(guest_rng[0]['result'],rng[1]['result'])
    def test_tail_loop_context_is_retained_across_framework_wrappers(self):
        case=self.case('trace-tail-loop-context');attempt=case['frames'][0]['execution_dependencies_at_rejection']
        host=next(e for e in attempt['contexts'][0]['world_calls'] if e['op']=='math.random')
        guest=attempt['contexts'][1]['world_calls'][-1]
        self.assertNotEqual(host['site']['key'],guest['site']['key'])
        tail=[f for f in host['site']['path'] if f.get('tail_call') and f['loops']]
        self.assertEqual(tail[0]['loops'][0]['limit'],2)
    def test_configuration_serialization_retains_world_and_personal_origins(self):
        case=self.case('trace-config-save-roundtrip');first=case['frames'][0]['output'];second=case['frames'][1]['output']
        for slot in (0,1):
            stored=first['execution_dependencies'][slot]['store_origins']['Trace Serialization Fixture']
            self.assertIn('personal_config:Trace Serialization Fixture',stored)
            self.assertTrue(any(s.startswith('world_result:1:') for s in stored))
            text=second['execution_dependencies'][slot]['draw_origins'][0]['text'];self.assertTrue(any(s.startswith('world_result:1:') for s in text))
        self.assertIn('personal_input:triggered:77',second['execution_dependencies'][1]['draw_origins'][0]['x'])
    def test_rejection_retains_attempt_then_restores(self):
        for name in ('trace-presentation-return-mutation-mismatch-recovery','trace-presentation-extra-return-mutation-no-reuse','trace-personal-loop-cardinality','trace-generic-loop-unresolved','trace-tail-loop-context'):
            case=self.case(name);self.assertTrue(case['passed']);self.assertFalse(case['compatibility_passed'])
            for frame in case['frames']:
                if frame['outcome']!='reject':continue
                self.assertTrue(frame['rollback_passed']);attempt=frame['execution_dependencies_at_rejection']['contexts'][1]['world_calls'][-1]
                self.assertIn('rejected',attempt);self.assertNotIn('result',attempt);self.assertTrue(attempt['site']['path'])
    def test_duplicate_keeps_entire_dependency_output(self):
        case=self.case('trace-config-save-roundtrip');first=case['frames'][1];second=case['frames'][2]
        self.assertTrue(second['duplicate_state_unchanged']);out=copy.deepcopy(second['output']);self.assertTrue(out.pop('duplicate'));self.assertEqual(first['output'],out)
    def test_corrupted_hash_and_native_roots_refused(self):
        self.assertIn('runtime hash mismatch',self.run_suite(self.manifest,1,sha='0'*64))
        m=self.selected('trace-read-write-read');m['cases'][0]['native_roots']=True
        self.assertIn('cannot use game/native roots',self.run_suite(m,1))
        m=self.selected('trace-read-write-read');m['cases'][0]['mods'][0]['sha256']['main.lua']='0'*64
        self.assertIn('frozen mod hash mismatch',self.run_suite(m,1))
    def test_reference_dll_and_game_suite_entry_refuse_trace(self):
        reference=self.bin/'ia_lua533_reference.dll'
        self.assertIn('requires the owned trace runtime',self.run_suite(self.manifest,1,dll=reference,sha=hashlib.sha256(reference.read_bytes()).hexdigest()))
        result=subprocess.run([str(self.bin/'authority-suite-tests.exe'),str(self.game/'Lua5.3.3r.dll'),str(self.game),str(ROOT),str(ROOT/'research/trace_suite.json')],capture_output=True,text=True,encoding='utf-8',timeout=45)
        self.assertEqual(result.returncode,1);self.assertIn('standalone only',result.stderr)
    def test_semantic_oracle_failure_is_not_diagnostic_success(self):
        m=self.selected('trace-read-write-read');m['cases'][0]['frames'][0]['expect']['texts'][1][0]='invented'
        report=self.run_suite(m,2);self.assertFalse(report['diagnostic_passed']);self.assertEqual(report['failed'],1)
        self.assertTrue(report['cases'][0]['frames'][0]['rollback_passed'])

if __name__=='__main__':unittest.main()
