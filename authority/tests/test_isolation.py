"""Positive host-side isolation experiment and counterexamples that MUST fail closed."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.isolation import HostIsolation, IsolationFailure, ModSource, config_store

CHAOS_NAME='Authority Research Legacy Chaos Fixture'
DRIVES_NAME='Config Drives World Fixture'
def source(folder='legacy_chaos'): return ModSource.directory(ROOT/'fixtures'/folder)
def configs(name=CHAOS_NAME):
    return config_store(name,{'language':'zh','x':24,'key':76,'amount':1},
                        {'language':'en','x':124,'key':77,'amount':1})
def text(record,slot): return bytes.fromhex(record['draws'][str(slot)][0]['text_hex']).decode()
def store(instance,slot,name=CHAOS_NAME): return json.loads(instance.stores[str(slot)][name.encode().hex()])
def custom(code): return ModSource('inline_fixture',{'main.lua':code.encode()})

class IsolationTests(unittest.TestCase):
    def test_unchanged_mod_two_huds_single_world_commit(self):
        original=source(); before=original.manifest()
        experiment=HostIsolation(original,configs())
        record=experiment.step(1,100)
        self.assertTrue(text(record,0).startswith('zh|1|100|'))
        self.assertTrue(text(record,1).startswith('en|1|100|'))
        self.assertEqual(text(record,0).split('|')[1:],text(record,1).split('|')[1:])
        amounts=sum(e['amount'] for e in record['effects'])
        self.assertEqual(experiment.world.coins,[amounts,0])
        self.assertEqual(len(record['effects']),2) # One update write and one render write, both from authority.
        self.assertEqual(original.manifest(),before)

    def test_personal_key_position_and_save_are_independent(self):
        experiment=HostIsolation(source(),configs())
        record=experiment.step(1,100,{'0':{'triggered':[77]},'1':{'triggered':[77]}})
        self.assertEqual(record['draws']['0'][0]['x'],24)
        self.assertEqual(record['draws']['1'][0]['x'],125)
        self.assertEqual((store(experiment,0)['x'],store(experiment,1)['x']),(24,125))
        experiment.step(2,101,{'0':{'triggered':[76]},'1':{'triggered':[76]}})
        self.assertEqual((store(experiment,0)['x'],store(experiment,1)['x']),(25,125))

    def test_random_time_and_cached_functions_replay_exactly(self):
        fixture=custom('''local m=RegisterMod('cache',1); local rnd=math.random; local clock=os.clock
          local p=Isaac.GetPlayer(0); local count=0
          m:AddCallback(ModCallbacks.MC_POST_RENDER,function()
            count=count+1; local n=rnd(1,5); p:AddCoins(n)
            local coins=p:GetNumCoins(); Isaac.RenderText(count..'|'..n..'|'..clock()..'|'..coins,1,2,1,1,1,1)
          end)''')
        experiment=HostIsolation(fixture)
        first=experiment.step(1,123)
        self.assertEqual(first['draws']['0'],first['draws']['1'])
        self.assertEqual(len(first['effects']),1)
        second=experiment.step(2,246)
        self.assertTrue(text(second,1).startswith('2|'))
        self.assertEqual(second['draws']['0'],second['draws']['1'])

    def test_duplicate_frame_does_not_repeat_gameplay_or_config(self):
        experiment=HostIsolation(source(),configs())
        request={'1':{'triggered':[77]}}
        first=experiment.step(1,100,request); before=deepcopy(experiment.stores)
        repeated=experiment.step(1,100,request)
        self.assertEqual(first,repeated)
        self.assertEqual(len(experiment.history),1)
        self.assertEqual(experiment.stores,before)
        self.assertTrue(text(experiment.step(2,101),1).startswith('en|2|'))

    def test_conflicting_duplicate_and_stale_frame_are_refused(self):
        experiment=HostIsolation(source(),configs())
        experiment.step(2,100)
        with self.assertRaisesRegex(IsolationFailure,'different input'): experiment.step(2,101)
        with self.assertRaisesRegex(IsolationFailure,'stale'): experiment.step(1,99)
        self.assertEqual(experiment.world.frame,2)

    def test_setting_that_changes_world_aborts_world_config_and_private_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'
            experiment=HostIsolation(source('config_drives_world'),configs(DRIVES_NAME),journal=path)
            first=experiment.step(1,100); before=path.read_bytes()
            with self.assertRaisesRegex(IsolationFailure,'divergent world call'):
                experiment.step(2,101,{'1':{'triggered':[77]}})
            self.assertEqual(experiment.world.snapshot(),first['world'])
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(store(experiment,1,DRIVES_NAME)['amount'],1)
            restored=experiment.step(2,101)
            self.assertEqual((text(restored,0),text(restored,1)),('zh|2','en|2'))
            self.assertEqual(experiment.world.coins,[2,0])

    def test_disk_error_aborts_and_rebuilds_private_upvalues(self):
        with tempfile.TemporaryDirectory() as tmp:
            experiment=HostIsolation(source(),configs(),journal=Path(tmp)/'state.json')
            first=experiment.step(1,100); saved=experiment.journal.read_bytes()
            with patch.object(experiment,'_persist',side_effect=OSError('disk unavailable')):
                with self.assertRaisesRegex(IsolationFailure,'disk unavailable'): experiment.step(2,101)
            self.assertEqual(experiment.world.snapshot(),first['world'])
            self.assertEqual(experiment.journal.read_bytes(),saved)
            record=experiment.step(2,101)
            self.assertTrue(text(record,0).startswith('zh|2|'))
            self.assertTrue(text(record,1).startswith('en|2|'))

    def test_resume_restores_configs_rng_and_private_render_counters(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'
            original=source(); experiment=HostIsolation(original,configs(),journal=path)
            experiment.step(1,100,{'1':{'triggered':[77]}})
            experiment.step(2,101)
            resumed=HostIsolation.resume(original,path)
            self.assertEqual(resumed.world.snapshot(),experiment.world.snapshot())
            self.assertEqual(resumed.stores,experiment.stores)
            expected=experiment.step(3,102)
            actual=resumed.step(3,102)
            self.assertEqual(expected,actual)
            self.assertTrue(text(actual,1).startswith('en|3|'))
            self.assertEqual(actual['draws']['1'][0]['x'],125)

    def test_corrupt_checkpoint_or_changed_code_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; original=source()
            experiment=HostIsolation(original,configs(),journal=path); experiment.step(1,100)
            envelope=json.loads(path.read_bytes()); envelope['checkpoint']['seed']+=1
            path.write_text(json.dumps(envelope))
            with self.assertRaisesRegex(IsolationFailure,'hash mismatch'): HostIsolation.resume(original,path)
            experiment.step(2,101)
            changed=ModSource(original.name,{**original.files,'main.lua':original.files['main.lua']+b'\n-- changed'})
            with self.assertRaisesRegex(IsolationFailure,'code/schema'): HostIsolation.resume(changed,path)

    def test_rehashed_but_inconsistent_history_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.json'; original=source()
            experiment=HostIsolation(original,configs(),journal=path); experiment.step(1,100)
            envelope=json.loads(path.read_bytes()); envelope['checkpoint']['history'][0]['world']['coins'][0]=99
            canonical=json.dumps(envelope['checkpoint'],sort_keys=True,separators=(',',':')).encode()
            envelope['body_sha256']=hashlib.sha256(canonical).hexdigest(); path.write_text(json.dumps(envelope))
            with self.assertRaisesRegex(IsolationFailure,'reconstruct'): HostIsolation.resume(original,path)

    def test_unsupported_api_inside_pcall_still_fails_closed(self):
        fixture=custom("local ok=pcall(function() Isaac.GetItemConfig() end)")
        with self.assertRaisesRegex(IsolationFailure,'Isaac.GetItemConfig'): HostIsolation(fixture)

    def test_unsupported_argument_inside_pcall_still_fails_closed(self):
        fixture=custom("pcall(function() Isaac.GetPlayer(0):AddCoins({1}) end)")
        with self.assertRaisesRegex(IsolationFailure,'non-scalar API'): HostIsolation(fixture)

    def test_native_sdk_constructor_is_explicitly_unsupported(self):
        fixture=ModSource('sdk_fixture',{'main.lua':b"error('must not run mod')"},definitions=b'TearFlags={NORMAL=BitSet128(0,0)}')
        with self.assertRaisesRegex(IsolationFailure,'authority_sdk_definitions.*BitSet128.native_adapter'):
            HostIsolation(fixture)

    def test_direct_and_raw_world_property_writes_refused(self):
        for code in ("Isaac.GetPlayer(0).Damage=99","rawset(Isaac.GetPlayer(0),'Damage',99)"):
            with self.subTest(code=code):
                with self.assertRaisesRegex(IsolationFailure,'property_write'): HostIsolation(custom(code))

    def test_raw_text_bytes_are_preserved_without_utf8_decoding(self):
        experiment=HostIsolation(custom("local m=RegisterMod('raw',1); m:AddCallback(2,function() Isaac.RenderText(string.char(0xb0,0xb4,0,0xff),1,2,1,1,1,1) end)"))
        record=experiment.step(1,100)
        self.assertEqual(bytes.fromhex(record['draws']['1'][0]['text_hex']),bytes([0xb0,0xb4,0,0xff]))

    def test_callback_return_difference_is_refused(self):
        fixture=custom("local m=RegisterMod('returns',1); local j=require('json'); local c=j.decode(m:LoadData()); m:AddCallback(2,function() if c.language=='en' then return false end end)")
        experiment=HostIsolation(fixture,config_store('returns',{'language':'zh'},{'language':'en'}))
        with self.assertRaisesRegex(IsolationFailure,'callback return'): experiment.step(1,100)
        self.assertEqual(experiment.world.frame,0)

    def test_local_module_sources_are_frozen_and_unknown_paths_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'resources'/'scripts').mkdir(parents=True)
            (root/'main.lua').write_text("local m=RegisterMod('module',1); local amount=require('scripts.amount'); m:AddCallback(2,function() Isaac.GetPlayer(0):AddCoins(amount) end)")
            dependency=root/'resources'/'scripts'/'amount.lua'; dependency.write_text('return 2')
            frozen=ModSource.directory(root); dependency.write_text('return 3')
            with self.assertRaises(TypeError): frozen.files['main.lua']=b'error("changed")'
            experiment=HostIsolation(frozen); experiment.step(1,100)
            self.assertEqual(experiment.world.coins,[2,0])
            with self.assertRaisesRegex(IsolationFailure,'outside selected root'): HostIsolation(custom("require('../escape')"))

    def test_world_read_after_write_uses_authority_point_in_time(self):
        experiment=HostIsolation(custom("local m=RegisterMod('reads',1); m:AddCallback(1,function() local p=Isaac.GetPlayer(0); p:AddCoins(1); local n=p:GetNumCoins(); p:AddCoins(n) end)"))
        record=experiment.step(1,100)
        self.assertEqual(experiment.world.coins,[2,0])
        self.assertEqual(record['transcripts']['update'][1]['result'],1)

if __name__=='__main__': unittest.main(verbosity=2)
