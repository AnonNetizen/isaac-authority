"""Functional outputs and policy proofs; a safe rejection is not compatibility."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RULE='personal-settings-authority-hud-v1'

class Slice3SuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=Path(os.environ['IA_TRACE_BINARY_DIR']);cls.game=Path(os.environ['IA_TRACE_GAME_DIR'])
        cls.runner=cls.binary/'authority-slice3-research.exe';cls.dll=cls.binary/'ia_lua533_slice3.dll'
        cls.manifest=json.loads((ROOT/'research/slice3_suite_v3.json').read_text())
        with tempfile.TemporaryFile() as output:
            p=subprocess.run([str(cls.runner),'--suite',str(cls.dll),hashlib.sha256(cls.dll.read_bytes()).hexdigest(),str(cls.game),str(ROOT),str(ROOT/'research/slice3_suite_v3.json')],stdout=output,stderr=subprocess.PIPE,timeout=300)
            output.seek(0);cls.report=json.load(output)
        if p.returncode:raise AssertionError([(c['id'],c.get('error'),[(f.get('error')) for f in c['frames']]) for c in cls.report['cases'] if not c['passed']])
        cls.cases={c['id']:c for c in cls.report['cases']}
    def frame(self,name,n=0):return self.cases['slice3-'+name]['frames'][n]
    def output(self,name,n=0):return self.frame(name,n)['output']
    def test_complete_diagnostics_and_functional_gate(self):
        self.assertTrue(self.report['diagnostic_passed']);self.assertEqual(len(self.cases),56)
        definitions={c['id']:c for c in self.manifest['cases']}
        for c in self.cases.values():
            self.assertTrue(c['source_unchanged']);self.assertTrue(c['host_stack_restored'])
            if definitions[c['id']].get('case_kind','functional')=='functional':self.assertTrue(c['compatibility_passed'],c['id'])
    def test_original_and_reversed_values(self):
        for name,amount in [('setting-versus-game-result-ambiguity',2),('setting-control-ambiguity',2),('slice_setting_ambiguity-2-1',1),('slice2_setting_control-2-1',1)]:
            o=self.output(name);self.assertEqual(o['draws'][1][0]['x'],124)
            key=next(iter(o['stores'][1]));self.assertEqual(json.loads(o['stores'][1][key])['amount'],amount)
    def test_json_fields_have_separate_sources(self):
        g=self.output('setting-versus-game-result-ambiguity')['execution_dependencies'][1]['value_graph']
        fields={tuple(str(k) for k in n['detail']['source_path']):n['id'] for n in g['nodes'] if n['operation']=='json_field_source' and n['detail']['source_path']}
        self.assertGreaterEqual(len(fields),4);self.assertEqual(len(set(fields.values())),len(fields))
        self.assertEqual(len(g['game_views']),1)
        for v in g['game_views'].values():self.assertEqual(v['personal_value']['value'],2);self.assertEqual(v['value']['value'],1)
    def test_menu_and_hud_have_different_purposes(self):
        g=self.output('menu-settings-1-2')['execution_dependencies'][1]['value_graph']
        menu=[p for p in g['purpose_records'] if p.get('source')=='trusted_framework_stack'];self.assertTrue(menu)
        self.assertEqual(menu[-1]['view'],'personal');self.assertEqual(menu[-1]['framework_identity']['contract'],'MCM-framework-model-v1')
        self.assertTrue(any(p.get('source')=='ordinary_hud' for p in g['purpose_records']))
    def test_fake_menu_name_has_no_trust(self):
        g=self.output('fake-menu-default-hud')['execution_dependencies'][1]['value_graph']
        self.assertFalse(any(p.get('source')=='trusted_framework_stack' for p in g['purpose_records']))
    def test_cross_frame_value_versions(self):
        o=self.output('cross-frame-host',1);texts=[bytes.fromhex(d['text_hex']).decode() for d in o['draws'][1]]
        self.assertEqual(texts,['en|amount=1','en|amount=2','native=2'])
        self.assertEqual(json.loads(o['stores'][1]['Slice3 Cross Frame'])['amount'],2)
    def test_display_state_uses_proven_candidate_union(self):
        for name,chosen in [('reward-controls-display-1-2',False),('reward-controls-display-2-1',True)]:
            b=self.output(name)['branch_search'];self.assertEqual(b['selected_choices'],[chosen])
            self.assertTrue(b['branch_purpose_proofs']);self.assertEqual(b['host_execution_count'],1)
            selected=next(a for a in b['attempts'] if a['outcome']=='consistent')
            self.assertTrue(selected['proof']['proofs'][0]['hud_purpose_proven_across_candidates'])
    def test_explicit_operands_not_label_set(self):
        g=self.output('ordered-operands')['execution_dependencies'][1]['value_graph']
        arithmetic=[n for n in g['nodes'] if n['operation'] in ('MUL','ADD','SUB')]
        self.assertTrue(arithmetic);self.assertTrue(all(len(n['detail']['operands'])==2 for n in arithmetic))
    def test_budget_includes_startup_history_projection(self):
        b=self.output('menu-settings-1-2',2)['branch_search']
        self.assertLessEqual(b['total_instructions'],2000000)
        self.assertEqual(b['total_instructions'],sum(a['instructions'] for a in b['attempts']))
        self.assertTrue(all(a['startup_instructions']>0 for a in b['attempts']))
        self.assertTrue(any(a.get('projection_instructions',0)>0 for a in b['attempts']))
    def test_refusals_and_rollback_are_separate(self):
        for name in ('ambiguous-producer-refusal','unknown-projection-refusal','lost-serialization-refusal','branch-budget','path-budget','instruction-budget'):
            f=self.frame(name);self.assertEqual(f['outcome'],'reject');self.assertTrue(f['rollback_passed'])
            self.assertFalse(self.cases['slice3-'+name]['compatibility_passed'])
    def test_full_transaction_and_duplicate(self):
        for f in self.cases['slice3-dual-view-transaction']['frames']:
            if f['outcome']=='reject':self.assertTrue(f['rollback_passed'])
            if f.get('output',{}).get('duplicate'):self.assertTrue(f['duplicate_state_unchanged'])
    def test_frozen_rule_and_abi_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'wrong.json';manifest=json.loads(json.dumps(self.manifest));manifest['view_rule']='guess'
            p.write_text(json.dumps(manifest))
            def invoke(dll,manifest):return subprocess.run([str(self.runner),'--suite',str(dll),hashlib.sha256(dll.read_bytes()).hexdigest(),str(self.game),str(ROOT),str(manifest)],capture_output=True,text=True,timeout=30)
            result=invoke(self.dll,p);self.assertNotEqual(result.returncode,0);self.assertIn('frozen view rule',result.stderr)
            original=ROOT/'research/slice3_counterexamples.json';result=invoke(self.binary/'ia_lua533_slice2.dll',original)
            self.assertEqual(result.returncode,2);self.assertIn('owned ABI 3',result.stdout)
    def test_game_entry_and_native_roots_refuse_slice3(self):
        result=subprocess.run([str(self.binary/'authority-suite-tests.exe'),str(self.game/'Lua5.3.3r.dll'),str(self.game),str(ROOT),str(ROOT/'research/slice3_counterexamples.json')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,1);self.assertIn('standalone only',result.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            manifest=json.loads((ROOT/'research/slice3_counterexamples.json').read_text());manifest['cases'][0]['native_roots']=True
            target=Path(tmp)/'native.json';target.write_text(json.dumps(manifest))
            result=subprocess.run([str(self.runner),'--suite',str(self.dll),hashlib.sha256(self.dll.read_bytes()).hexdigest(),str(self.game),str(ROOT),str(target)],capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,1);self.assertIn('cannot use game/native roots',result.stderr)

if __name__=='__main__':unittest.main(defaultTest='Slice3SuiteTests')
