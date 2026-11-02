"""Freeze one explicit nonempty authority scene and menu API contracts; no asset copies."""
import copy,json,re,sys
from pathlib import Path
sys.dont_write_bytecode=True
import run_ui_flow as f
ROOT=f.ROOT;DIR=ROOT/'research/menu_environment';PROFILE=DIR/'profile-v3.json'
def freeze():
    enums=ROOT/'research/slice3_ui_inputs/resources/scripts/enums.lua'
    text=enums.read_text(encoding='utf-8');sound=text.split('SoundEffect = {',1)[1].split('}',1)[0]
    sounds=sorted(set(int(x)for x in re.findall(r'=\s*(\d+)\s*[,\n]',sound)))
    defs={k:{}for k in ['player','entity','room','game','level','seeds','audio']}
    def query(cls,name,field,type='integer',mode='query'):defs[cls][name]=dict(mode=mode,field=field,type=type)
    for cls in ['player','entity']:
        for name,field,t in [('Type','type','integer'),('Variant','variant','integer'),('SubType','subtype','integer'),('InitSeed','init_seed','integer'),('FrameCount','frame_count','integer'),('Position','position','vector'),('Velocity','velocity','vector'),('Parent','parent','actor')]:query(cls,name,field,t,'field')
        for name,t in [('Exists','boolean'),('IsActiveEnemy','boolean'),('IsBoss','boolean')]:query(cls,name,dict(Exists='exists',IsActiveEnemy='enemy',IsBoss='boss')[name],t)
        defs[cls]['GetData']=dict(mode='data');defs[cls]['HasEntityFlags']=dict(mode='flags',field='flags')
        for name,target in [('ToPlayer','player'),('ToPickup','pickup'),('ToNPC','npc'),('ToEffect','effect'),('ToFamiliar','familiar'),('ToProjectile','projectile')]:defs[cls][name]=dict(mode='cast',**{'class':target})
    query('player','ControllerIndex','controller',mode='field')
    query('player','GetPlayerType','player_type');query('player','GetOtherTwin','other_twin','actor');query('player','GetMainTwin','main_twin','actor')
    query('player','IsCoopGhost','coop_ghost','boolean')
    for name,field in [('GetEffectiveMaxHearts','effective_max_hearts'),('GetSoulHearts','soul_hearts'),('GetBrokenHearts','broken_hearts')]:query('player',name,field)
    for name,field,t in [('HasCollectible','collectibles','boolean'),('GetCollectibleNum','collectibles','integer'),('HasTrinket','trinkets','boolean')]:query('player',name,field,t,'inventory')
    for name,field in [('GetActiveItem','active_items'),('GetCard','cards'),('GetPill','pills')]:query('player',name,field,mode='slot')
    query('entity','IsShopItem','shop','boolean');query('entity','Price','price',mode='field');query('entity','OptionsPickupIndex','options_index',mode='field')
    for name,field,t in [('IsClear','clear','boolean'),('GetType','type','integer'),('GetRoomShape','shape','integer'),('GetRenderScrollOffset','render_scroll','vector'),('GetCenterPos','center','vector'),('GetTopLeftPos','top_left','vector'),('GetBottomRightPos','bottom_right','vector')]:query('room',name,field,t)
    defs['room']['WorldToScreenPosition']=dict(mode='world_to_screen')
    query('game','ScreenShakeOffset','screen_shake','vector','field');query('game','IsGreedMode','greed','boolean')
    query('game','GetVictoryLap','victory_lap');query('game','Challenge','challenge',mode='field');query('game','Difficulty','difficulty',mode='field')
    query('seeds','IsCustomRun','custom_run','boolean');query('seeds','GetStartSeed','start_seed');query('seeds','GetStartSeedString','start_seed_string','string')
    for name,field in [('GetCurrentRoomIndex','room_index'),('GetStage','stage'),('GetStageType','stage_type'),('GetCurses','curses'),('GetAbsoluteStage','absolute_stage')]:query('level',name,field)
    defs['audio']['Play']=dict(mode='audio')
    players=[]
    for i in range(2):players.append(dict(id=i+1,**{'class':'player'},type=1,player_type=i,variant=0,subtype=0,init_seed=460+i,frame_count=42,controller=i,position=[160+i*20,120],velocity=[0,0],parent=None,other_twin=None,main_twin=i+1,ptr_hash=1001+i,data={},coins=0,collectibles_complete=True,collectibles={},trinkets_complete=True,trinkets={},active_items={str(j):0 for j in range(4)},cards={str(j):0 for j in range(4)},pills={str(j):0 for j in range(4)},partition=32,exists=True,enemy=False,boss=False,friendly=False,flags=0,coop_ghost=False))
    for p in players:p.update(collectibles_base_complete=True,collectibles_base={},trinkets_base_complete=True,trinkets_base={},effective_max_hearts=6,soul_hearts=0,broken_hearts=0)
    pickup=dict(id=3,**{'class':'pickup'},type=5,variant=100,subtype=1,init_seed=462,frame_count=42,position=[180,120],velocity=[0,0],parent=None,ptr_hash=2001,data={},partition=16,exists=True,enemy=False,boss=False,friendly=False,flags=0,shop=False,price=0,options_index=0)
    scene=dict(revision=1,players=players,entities=[pickup],complete_entities=True,room=dict(id=1,world_to_screen=[1,0,0,1,112,-2],render_scroll=[0,0],clear=True,type=1,shape=1,center=[320,280],top_left=[0,0],bottom_right=[640,560]),level=dict(id=1,room_index=0,stage=1,stage_type=0,curses=0,absolute_stage=1),seeds=dict(id=1,custom_run=False,start_seed=460,start_seed_string='RESEARCH'),game=dict(screen_shake=[0,0],greed=False,challenge=0,difficulty=0,victory_lap=0))
    device=dict(controllers=list(range(5)),unlisted_released=True,buttons={str(i):{'-1':dict(pressed=False,triggered=False,value=0)}for i in range(5)},actions={},mouse_world=[100,120],mouse_screen=[212,118])
    data=dict(schema='frozen-menu-environment-1',main_sha256=f.load(f.PROFILE)['main_sha256'],session='menu-research-session-1',snapshot=scene,initial_inputs=[dict(device=copy.deepcopy(device))for _ in range(2)],definitions=defs,sound_ids=sounds,enums_sha256=f.digest(enums),source='explicit authority scenario; not a native memory snapshot',docs=['https://wofsauge.github.io/IsaacDocs/rep/Input.html','https://wofsauge.github.io/IsaacDocs/rep/SFXManager.html','https://wofsauge.github.io/IsaacDocs/rep/Room.html'])
    DIR.mkdir(parents=True,exist_ok=True);f.freeze_json(PROFILE,data)
    print(json.dumps(dict(frozen=True,actors=3,audio_ids=len(sounds),copied_assets=0)))
if __name__=='__main__':freeze()
