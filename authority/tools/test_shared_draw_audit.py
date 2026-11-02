import copy,hashlib,json,unittest
import shared_draw_audit as wire
def entry(value):
    raw=json.dumps(value,separators=(',',':'),ensure_ascii=False)
    return dict(json=raw,sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest())
def message():
    state={'resource':'中文','clip':[0,1],'ready':False}
    frame=[{'text_hex':'e4b8ad00','x':17.0,'capture_state':{'$ia_capture_state':0}}]
    return dict(semantic={'draws':[{'$ia_draw_frame':0}]},steps=[{'draws':{'$ia_draw_frame':0},'branch_views':{'ordinary_draws':{'$ia_draw_frame':0}}}],shared_draw_audit=dict(schema='ia-shared-draw-audit-1',self_round_trip_verified=True,states=[entry(state)],frames=[entry(frame)]))
class SharedDrawTests(unittest.TestCase):
    def test_preserves_bytes_types_and_independent_copies(self):
        decoded=wire.decode(message());a=decoded['semantic']['draws'][0];b=decoded['steps'][0]['draws'];self.assertEqual(a,b)
        self.assertIs(type(a[0]['x']),float);self.assertEqual(a[0]['text_hex'],'e4b8ad00');self.assertIs(a[0]['capture_state']['ready'],False)
        a[0]['capture_state']['clip'][0]=999;self.assertEqual(b[0]['capture_state']['clip'][0],0)
    def test_corrupt_hash_refuses(self):
        m=message();m['shared_draw_audit']['states'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash mismatch'):wire.decode(m)
    def test_negative_reference_refuses(self):
        m=message();m['steps'][0]['draws']['$ia_draw_frame']=-1
        with self.assertRaisesRegex(ValueError,'reference invalid'):wire.decode(m)
    def test_boolean_reference_refuses(self):
        m=message();m['semantic']['draws'][0]['$ia_draw_frame']=False
        with self.assertRaisesRegex(ValueError,'reference invalid'):wire.decode(m)
    def test_extra_reference_keys_refuse(self):
        m=message();m['semantic']['draws'][0]['extra']=1
        with self.assertRaisesRegex(ValueError,'reference invalid'):wire.decode(m)
    def test_wrong_state_type_refuses(self):
        m=message();m['shared_draw_audit']['states'][0]=entry([])
        with self.assertRaisesRegex(ValueError,'state type invalid'):wire.decode(m)
    def test_dictionary_capacity_refuses(self):
        m=message();m['shared_draw_audit']['frames']*=257
        with self.assertRaisesRegex(ValueError,'dictionary capacity'):wire.decode(m)
    def test_expansion_bomb_refuses(self):
        m=message();m['shared_draw_audit']['states']=[entry({'large':'x'*(1024**2)})]
        m['shared_draw_audit']['frames']=[entry([{'capture_state':{'$ia_capture_state':0}}for _ in range(17)])]
        with self.assertRaisesRegex(ValueError,'expansion capacity'):wire.decode(m)
    def test_nonfinite_json_refuses(self):
        m=message();raw='{"v":NaN}';m['shared_draw_audit']['states']=[dict(json=raw,sha256=hashlib.sha256(raw.encode()).hexdigest())]
        with self.assertRaisesRegex(ValueError,'Nonfinite'):wire.decode(m)
if __name__=='__main__':unittest.main()
