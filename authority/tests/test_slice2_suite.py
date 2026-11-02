"""Check functionality separately from safe refusal, with immutable legacy oracles."""
import copy,hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Slice2SuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=Path(os.environ['IA_TRACE_BINARY_DIR']);cls.game=Path(os.environ['IA_TRACE_GAME_DIR'])
        cls.dll=cls.binary/'ia_lua533_slice2.dll';cls.runner=cls.binary/'authority-slice2-research.exe'
        cls.manifest=json.loads((ROOT/'research/slice2_suite.json').read_text())
        cls.report=cls.invoke(cls.manifest);cls.cases={c['id']:c for c in cls.report['cases']}
    @classmethod
    def invoke(cls,manifest,dll=None,sha=None):
        dll=dll or cls.dll
        with tempfile.TemporaryDirectory(prefix='isaac-slice2-') as t:
            p=Path(t)/'suite.json';p.write_text(json.dumps(manifest))
            r=subprocess.run([str(cls.runner),'--suite',str(dll),sha or hashlib.sha256(dll.read_bytes()).hexdigest(),str(cls.game),str(ROOT),str(p)],capture_output=True,text=True,encoding='utf-8',timeout=300)
            return json.loads(r.stdout) if r.stdout else {'stderr':r.stderr,'returncode':r.returncode}
    def output(self,name,index=0):
        c=self.cases['slice2-'+name];self.assertTrue(c['passed'],c.get('first_unsupported_entry'));return c['frames'][index]['output']
    def texts(self,out,side=1):return [bytes.fromhex(d['text_hex']).decode() for d in out['draws'][side]]
    def test_full_diagnostic(self):
        self.assertTrue(self.report['diagnostic_passed'],[(c['id'],c.get('first_unsupported_entry')) for c in self.report['cases'] if not c['passed']])
    def test_extra_queries_use_two_distinct_anchors(self):
        out=self.output('new-queries-before-and-after')
        self.assertEqual(self.texts(out),['before=0','after=1'])
        guest=out['execution_dependencies'][1];a,b=guest['query_anchors']
        self.assertNotEqual(a['state_point'],b['state_point'])
        self.assertEqual(a['anchor_kind'],'callback_begin');self.assertEqual(b['anchor_kind'],'world_after')
    def test_timeline_has_immutable_snapshots_and_rng_hashes(self):
        out=self.output('new-queries-before-and-after')
        timeline=out['execution_dependencies'][0]['state_timeline']
        self.assertEqual(timeline[0]['kind'],'frame_begin')
        self.assertTrue(all(p['id']==i and len(p['rng_sha256'])==64 for i,p in enumerate(timeline)))
        self.assertIn(0,[p['state']['coins'][0] for p in timeline]);self.assertIn(1,[p['state']['coins'][0] for p in timeline])
    def test_helper_query_uses_deepest_proven_common_call_context(self):
        self.assertEqual(self.texts(self.output('helper-queries-before-and-after')),['before=0','after=1'])
    def test_previously_unmatched_query_and_config_save(self):
        out=self.output('unmatched-query-recovery',1)
        self.assertEqual(self.texts(out),['queued','extra=2','en|2'])
        self.assertEqual(json.loads(out['stores'][1]['Slice Query Gate'])['x'],125)
    def test_delayed_condition_uses_host_contribution(self):
        out=self.output('unresolved-control-recovery',1)
        self.assertEqual(out['draws'][1][1]['x'],125)
        self.assertEqual(self.texts(out)[1],f"en|2|reward={out['effects'][0]['amount']}")
        search=out['branch_search'];self.assertEqual(search['host_execution_count'],1);self.assertTrue(search['staged_committed'])
        self.assertEqual(search['selected_choices'],[False])
        self.assertTrue(any(a['outcome']=='inconsistent' for a in search['attempts']))
    def test_two_register_uses_have_distinct_world_producers(self):
        out=self.output('multiple-authority-consumers');self.assertEqual(self.texts(out),['first=3|second=6'])
        projection=out['execution_dependencies'][1]['projection'];self.assertEqual(len(projection),2)
        self.assertNotEqual(projection[0]['authority_owner_version'],projection[1]['authority_owner_version'])
        self.assertNotEqual(projection[0]['personal_owner']['owner_base'],projection[1]['personal_owner']['owner_base'])
    def test_two_upvalue_rewards_and_shared_helper(self):
        for i in (0,1):
            out=self.output('two-rewards-upvalues-helper',i)
            self.assertEqual(self.texts(out),[f"first={out['effects'][0]['amount']}|second={out['effects'][1]['amount']}"])
    def test_references_do_not_depend_on_consumer_order(self):
        out=self.output('reversed-consumers')
        self.assertEqual(self.texts(out),['first=3|second=6'])
        self.assertEqual([p['value'] for p in out['execution_dependencies'][1]['projection']],[6,3])
    def test_field_alias_closure_and_cross_frame_save(self):
        previous=(0,0);awards=[]
        for i,frame in enumerate(self.cases['slice2-two-rewards-fields-cross-frame']['frames'],1):
            self.assertEqual(frame['outcome'],'accept',frame.get('error'));out=frame['output']
            a,b=(e['amount'] for e in out['effects']);awards.append((a,b))
            self.assertEqual(self.texts(out),[f'en|{i}|first={a}|second={b}|prev={previous[0]},{previous[1]}'])
            config=json.loads(out['stores'][1]['Slice2 Two Rewards Fields'])
            self.assertEqual((config['previousFirst'],config['previousSecond']),(a,b));self.assertEqual(config['x'],124 if i==1 else 125);previous=(a,b)
        self.assertGreater(len(set(awards)),1)
    def test_consumption_versions_are_recorded(self):
        graph=self.output('multiple-authority-consumers')['execution_dependencies'][1]['value_graph']
        self.assertTrue(graph['storage_versions']);self.assertTrue(graph['consumption_records'])
        self.assertTrue(all('value_version' in use and 'site' in use for use in graph['consumption_records']))
    def test_comparisons_preserve_lua_numeric_equality_and_truth(self):
        out=self.output('lua-comparison-semantics');self.assertEqual(self.texts(out),['equal|less|le|truth|3'])
        selected=next(a for a in out['branch_search']['attempts'] if a['outcome']=='consistent')
        self.assertTrue(selected['proof']['resolved']);self.assertTrue(selected['proof']['consistent'])
        self.assertTrue(all(p['actual']==p['chosen'] for p in selected['proof']['proofs']))
    def test_personal_random_never_executes_or_has_a_fake_result(self):
        guest=self.output('unresolved-control-recovery',1)['execution_dependencies'][1]
        calls=[c for c in guest['world_calls'] if c['op']=='math.random']
        self.assertEqual(len(calls),2);self.assertTrue(all(c['deferred'] and not c['executed'] and 'result' not in c for c in calls))
    def test_failure_discards_saved_config_private_count_and_queued_draw(self):
        case=self.cases['slice2-failure-after-save-state-draw'];self.assertTrue(case['passed'],case['first_unsupported_entry'])
        failed=case['frames'][1];self.assertTrue(failed['rollback_passed'])
        attempt=failed['execution_dependencies_at_rejection']['branch_search']['attempts'][0]
        discarded=attempt['staged_discarded'];self.assertEqual(json.loads(discarded['stores']['Slice2 Transaction Failure'])['x'],125)
        self.assertEqual(len(discarded['pending_draws']),1);self.assertEqual([e['op'] for e in discarded['events']],['save','draw'])
        self.assertEqual(case['frames'][2]['output']['draws'][1][0]['x'],124)
        self.assertTrue(case['frames'][3]['duplicate_state_unchanged']);self.assertTrue(case['frames'][4]['rollback_passed'])
    def test_duplicate_branch_frame_is_cached(self):
        c=self.cases['slice2-unresolved-control-recovery'];self.assertTrue(c['frames'][2]['duplicate_state_unchanged'])
    def test_instruction_ledger_includes_context_and_history_reconstruction(self):
        out=self.output('unresolved-control-recovery',1);search=out['branch_search']
        self.assertEqual(search['total_instructions'],sum(a['instructions'] for a in search['attempts']))
        for a in search['attempts']:
            self.assertGreater(a['reconstruction_instructions'],0)
            self.assertEqual(a['instructions'],a['reconstruction_instructions']+a['frame_instructions'])
    def test_ambiguities_are_refused_and_restore(self):
        for name in ('query-frontier-ambiguity','unresolved-paths','callback-anchor-ambiguity','unproven-heap-instances','setting-versus-game-result-ambiguity'):
            c=self.cases['slice2-'+name];self.assertTrue(c['passed'],c.get('first_unsupported_entry'));self.assertFalse(c['compatibility_passed']);self.assertTrue(c['frames'][0]['rollback_passed'])
    def test_native_lookup_does_not_invent_nil_or_catchable_error(self):
        for key in (77,78,79):
            c=self.cases['slice2-native-deferred-key-'+str(key)]
            self.assertTrue(c['passed'],c['first_unsupported_entry']);self.assertFalse(c['compatibility_passed']);self.assertTrue(c['frames'][0]['rollback_passed'])
    def test_setting_ambiguity_reaches_presentation_through_control(self):
        c=self.cases['slice2-setting-control-ambiguity']
        self.assertTrue(c['passed'],c['first_unsupported_entry']);self.assertFalse(c['compatibility_passed']);self.assertTrue(c['frames'][0]['rollback_passed'])
    def test_exploration_budgets_are_bounded(self):
        for name in ('branch-budget','path-budget','instruction-budget'):
            c=self.cases['slice2-'+name];self.assertTrue(c['passed'],c.get('first_unsupported_entry'));self.assertTrue(c['frames'][0]['rollback_passed'])
            search=c['frames'][0]['execution_dependencies_at_rejection']['branch_search']
            self.assertLessEqual(len(search['attempts']),32);self.assertLessEqual(search['total_instructions'],2000000)
        search=self.cases['slice2-path-budget']['frames'][0]['execution_dependencies_at_rejection']['branch_search']
        self.assertEqual(len(search['attempts']),32)
        search=self.cases['slice2-instruction-budget']['frames'][0]['execution_dependencies_at_rejection']['branch_search']
        # The preserved 1,000-instruction Lua hook may reject slightly before
        # the new exact counter, because its first tick spans initialization.
        self.assertGreater(search['total_instructions'],1900000)
    def selected(self):
        m=copy.deepcopy(self.manifest);m['cases']=[next(c for c in m['cases'] if c['id']=='slice2-read-write-read')];return m
    def test_hash_and_abi_gate(self):
        r=self.invoke(self.selected(),sha='0'*64);self.assertIn('runtime hash mismatch',r['stderr'])
        r=self.invoke(self.selected(),dll=self.binary/'ia_lua533_slice.dll');self.assertIn('owned ABI 2',r['cases'][0]['error'])
    def test_game_and_native_roots_refuse_new_mode(self):
        m=self.selected();m['cases'][0]['native_roots']=True;r=self.invoke(m);self.assertIn('cannot use game/native roots',r['stderr'])
        r=subprocess.run([str(self.binary/'authority-suite-tests.exe'),str(self.game/'Lua5.3.3r.dll'),str(self.game),str(ROOT),str(ROOT/'research/slice2_suite.json')],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(r.returncode,1);self.assertIn('standalone only',r.stderr)
    def test_semantic_oracle_failure_after_draw_rolls_back(self):
        m=self.selected();m['cases'][0]['frames'][0]['expect']['texts'][1][0]='invented';r=self.invoke(m)
        self.assertFalse(r['diagnostic_passed']);self.assertTrue(r['cases'][0]['frames'][0]['rollback_passed'])
    def test_historical_manifests_unchanged(self):
        for name,sha in [('runtime_suite.json','7713261c2c0b0369b5811facaba5f07244afa75cb0d85ef51208c693e2db9eea'),('trace_suite.json','10507d2faf2310f330a27855d4921806fc7cefb97b4e2fe6af68167af50e59a8'),('slice_suite.json','4482e516593df2190874baaf47b7aaab4563e9fd3eda8727e5539f49b291a934')]:
            self.assertEqual(hashlib.sha256((ROOT/'research'/name).read_bytes()).hexdigest(),sha)
    def test_safe_refusals_do_not_claim_generic_compatibility(self):
        self.assertFalse(self.report['slice2_mode_gate_passed']);self.assertFalse(self.report['generic_mod_compatibility_passed'])

if __name__=='__main__':unittest.main()
