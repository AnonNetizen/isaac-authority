"""Functional projection assertions include authority results, personal state and refusals."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import copy
import unittest
ROOT=Path(__file__).resolve().parents[1]
class SliceSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=Path(os.environ['IA_TRACE_BINARY_DIR']);cls.game=Path(os.environ['IA_TRACE_GAME_DIR'])
        cls.dll=cls.binary/'ia_lua533_slice.dll';cls.runner=cls.binary/'authority-slice-research.exe'
        p=subprocess.run([str(cls.runner),'--suite',str(cls.dll),hashlib.sha256(cls.dll.read_bytes()).hexdigest(),str(cls.game),str(ROOT),str(ROOT/'research/slice_suite.json')],capture_output=True,text=True,encoding='utf-8',timeout=90)
        if not p.stdout:raise RuntimeError(p.stderr)
        cls.report=json.loads(p.stdout);cls.cases={c['id']:c for c in cls.report['cases']}
    def output(self,name,frame=0):
        c=self.cases[name];self.assertTrue(c['passed'],c['first_unsupported_entry']);return c['frames'][frame]['output']
    def test_full_diagnostic(self):
        self.assertTrue(self.report['diagnostic_passed'],[(c['id'],c.get('error'),c['first_unsupported_entry']) for c in self.report['cases'] if not c['passed']])
    def test_new_range_preserves_personal_changes(self):
        out=self.output('slice-personal-new-range-keeps-ui',1)
        self.assertEqual(out['personal_options'][1]['Language'],'fr');self.assertEqual(out['draws'][1][1]['x'],125)
        self.assertEqual(json.loads(out['stores'][1]['Random Gate Fixture'])['x'],125)
    def test_extra_random_is_not_reported_as_executed(self):
        out=self.output('slice-personal-extra-random-no-execution',1)
        guest=out['execution_dependencies'][1];random=[e for e in guest['world_calls'] if e['op']=='math.random']
        self.assertEqual(len(random),2);self.assertTrue(all(e['deferred'] and not e['executed'] and 'result' not in e for e in random))
        self.assertEqual(len(out['effects']),1);self.assertEqual(len(guest['projection']),1)
    def test_loop_binds_final_world_contribution(self):
        out=self.output('slice-trace-loop');self.assertEqual(out['effects'][0]['amount'],88)
        self.assertIn('award=88',bytes.fromhex(out['draws'][1][0]['text_hex']).decode())
    def test_generic_loop_uses_derived_final_value(self):
        out=self.output('slice-trace-generic-loop');self.assertEqual(out['effects'][0]['amount'],90)
    def test_tail_early_return(self):
        out=self.output('slice-trace-loop-tail');self.assertEqual(out['effects'][0]['amount'],87)
    def test_query_state_points(self):
        out=self.output('slice-read-write-read');self.assertEqual([bytes.fromhex(row[0]['text_hex']).decode() for row in out['draws']],['0->1|count=1']*2)
    def test_aliases_do_not_consume_discarded_random(self):
        for suffix in ('presentation-random-alias','trace-same-line','trace-helper','trace-cached','trace-tail','trace-dynamic'):
            out=self.output('slice-authority-award-'+suffix)
            self.assertEqual(out['execution_dependencies'][1]['projection'][0]['value'],out['effects'][0]['amount'])
    def test_serialized_field_provenance_survives(self):
        out=self.output('slice-mixed-fields-alias-closure-save',1)
        graph=out['execution_dependencies'][1]['value_graph'];self.assertTrue(any(n['operation']=='json_field_restore' for n in graph['nodes']))
        self.assertEqual(out['draws'][1][0]['x'],125)
    def test_duplicate_does_not_execute_again(self):
        case=self.cases['slice-personal-new-range-keeps-ui'];self.assertTrue(case['frames'][2]['duplicate_state_unchanged'])
    def test_refusals_restore_every_private_component(self):
        for name in ('slice-unresolved-control-recovery','slice-unmatched-query-recovery'):
            case=self.cases[name];self.assertTrue(case['passed'],case);self.assertTrue(case['frames'][1]['rollback_passed']);self.assertFalse(case['compatibility_passed']);self.assertTrue(case['frames'][3]['duplicate_state_unchanged'])
    def test_ambiguous_consumers_not_silently_bound(self):
        case=self.cases['slice-multiple-authority-consumers'];self.assertTrue(case['passed'],case);self.assertFalse(case['compatibility_passed'])
    def test_setting_role_ambiguity_is_not_guessed_from_text(self):
        case=self.cases['slice-setting-versus-game-result-ambiguity'];self.assertTrue(case['passed'],case);self.assertFalse(case['compatibility_passed'])
    def test_rejections_do_not_count_as_compatibility(self):
        self.assertFalse(self.report['slice_mode_gate_passed']);self.assertFalse(self.report['generic_mod_compatibility_passed'])
    def test_identical_json_keeps_separate_value_identity(self):
        out=self.output('slice-identical-json-distinct-producers');graph=out['execution_dependencies'][1]['value_graph'];self.assertTrue(any(n['operation']=='json_serialize' for n in graph['nodes']))
        self.assertEqual(bytes.fromhex(out['draws'][1][1]['text_hex']).decode(),'en|literal=0|17|literal')
        nodes={n['id']:n for n in graph['nodes']}
        def source_labels(root):
            todo=[root];seen=set();labels=[]
            while todo:
                i=todo.pop()
                if not i or i in seen:continue
                seen.add(i);n=nodes[i];todo.extend(n['data']);todo.extend(n['control'])
                if n['operation']=='source':labels.append(n['detail']['label'])
            return labels
        ids=out['execution_dependencies'][1]['draw_value_ids']
        self.assertTrue(any('authority_reference:' in label for label in source_labels(ids[0][0])))
        self.assertFalse(any('authority_reference:' in label for label in source_labels(ids[1][0])))
    def invoke_selected(self,mutate=lambda m:None,dll=None,sha=None,case_id='slice-read-write-read'):
        m=json.loads((ROOT/'research/slice_suite.json').read_text());m['cases']=[next(c for c in m['cases'] if c['id']==case_id)];mutate(m);dll=dll or self.dll
        with tempfile.TemporaryDirectory(prefix='isaac-slice-negative-') as t:
            f=Path(t)/'suite.json';f.write_text(json.dumps(m))
            return subprocess.run([str(self.runner),'--suite',str(dll),sha or hashlib.sha256(dll.read_bytes()).hexdigest(),str(self.game),str(ROOT),str(f)],capture_output=True,text=True,encoding='utf-8',timeout=90)
    def test_cross_frame_reload_uses_previous_authority_value(self):
        def mutate(m):
            frames=[]
            for i in range(1,9):
                frames.append({'frame':i,'time_ms':1000+(i-1)*16,'inputs':[{}, {'triggered':[77]}] if i==2 else [{},{}],'expect':{'outcome':'accept','values':{'/world/frame':i}}})
            m['cases'][0]['frames']=frames
        p=self.invoke_selected(mutate,case_id='slice-mixed-fields-alias-closure-save')
        self.assertEqual(p.returncode,0,p.stderr)
        case=json.loads(p.stdout)['cases'][0];previous=0;awards=[]
        for index,frame in enumerate(case['frames'],1):
            out=frame['output'];award=out['effects'][0]['amount'];awards.append(award)
            for side,language in enumerate(('zh','en')):
                text=bytes.fromhex(out['draws'][side][0]['text_hex']).decode()
                self.assertEqual(text,f'{language}|award={award}|previous={previous}|count={index}')
                saved=json.loads(out['stores'][side]['Slice Mixed Fields'])
                self.assertEqual(saved['previous'],award)
            self.assertEqual(out['draws'][1][0]['x'],124 if index==1 else 125)
            previous=award
        self.assertGreater(len(set(awards)),1,'Cross-frame oracle must use different rewards')
    def test_hash_and_owned_abi_required(self):
        p=self.invoke_selected(sha='0'*64);self.assertEqual(p.returncode,1);self.assertIn('runtime hash mismatch',p.stderr)
        p=self.invoke_selected(dll=self.binary/'ia_lua533_trace.dll');self.assertEqual(p.returncode,2);self.assertIn('requires owned graph ABI',p.stdout)
    def test_game_entry_and_native_roots_refuse_slice(self):
        p=self.invoke_selected(lambda m:m['cases'][0].update(native_roots=True));self.assertEqual(p.returncode,1);self.assertIn('cannot use game/native roots',p.stderr)
        p=subprocess.run([str(self.binary/'authority-suite-tests.exe'),str(self.game/'Lua5.3.3r.dll'),str(self.game),str(ROOT),str(ROOT/'research/slice_suite.json')],capture_output=True,text=True,encoding='utf-8',timeout=90)
        self.assertEqual(p.returncode,1);self.assertIn('standalone only',p.stderr)
    def test_semantic_failure_after_draws_rolls_back(self):
        def mutate(m):m['cases'][0]['frames'][0]['expect']['texts'][1][0]='invented'
        p=self.invoke_selected(mutate);self.assertEqual(p.returncode,2);r=json.loads(p.stdout);self.assertFalse(r['diagnostic_passed']);self.assertTrue(r['cases'][0]['frames'][0]['rollback_passed'])
    def test_historical_manifests_unchanged(self):
        for name,sha in [('runtime_suite.json','7713261c2c0b0369b5811facaba5f07244afa75cb0d85ef51208c693e2db9eea'),('trace_suite.json','10507d2faf2310f330a27855d4921806fc7cefb97b4e2fe6af68167af50e59a8')]:
            self.assertEqual(hashlib.sha256((ROOT/'research'/name).read_bytes()).hexdigest(),sha)

if __name__=='__main__':unittest.main()
