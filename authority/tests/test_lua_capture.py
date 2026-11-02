"""Exercise the actual injected observer, including a legacy-mod isolation counterexample."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / ".tools"))
from lupa.lua53 import LuaRuntime

FIXTURE = r'''
emissions, callbacks, pending, inbound = {}, {}, nil, nil
json = {encode = function(value) pending = value; return "encoded" end,
        decode = function(text) return inbound end}
require = function(name) assert(name == "json"); return json end
IsaacAuthorityNativeEmit = function(text) emissions[#emissions + 1] = pending end
IsaacAuthorityNativeConsume = function() return "inbound" end
ModCallbacks = {MC_POST_UPDATE=1, MC_POST_RENDER=2}
RegisterMod = function(name, version)
    return {AddCallback = function(self, id, fn) callbacks[id] = fn end}
end
Vector = function(x,y) return {X=x,Y=y} end
Color = function(r,g,b,a,ro,go,bo) return {R=r,G=g,B=b,A=a,RO=ro,GO=go,BO=bo} end
KColor = function(r,g,b,a) return Color(r,g,b,a,0,0,0) end
Input = {GetActionValue=function(action, controller) return action == 0 and 1 or 0 end}
spriteMethods = {
    Load=function(self,path) self.path=path; return true end,
    ReplaceSpritesheet=function(self,layer,path) self.sheet=path; return true end,
    LoadGraphics=function(self) return true end,
    GetFilename=function(self) return self.path or "gfx/example.anm2" end,
    GetAnimation=function(self) return self.anim or "Idle" end,
    GetFrame=function(self) return self.frame or 0 end,
    SetFrame=function(self,anim,frame) self.anim,self.frame=anim,frame end,
    Render=function(self,position) nativeDraws=nativeDraws+1; return "sprite",23 end,
    RenderLayer=function(self,layer,position) nativeDraws=nativeDraws+1; return "layer",24 end
}
nativeDraws=0
spriteMeta={__index=spriteMethods}
Sprite=function() return setmetatable({Scale=Vector(1,1),Offset=Vector(0,0),Rotation=0,
    FlipX=false,FlipY=false,Color=Color(1,1,1,1,0,0,0)}, spriteMeta) end
fontMethods={Load=function(self,path) self.path=path; return true end}
for _,name in ipairs({"DrawString","DrawStringUTF8","DrawStringScaled","DrawStringScaledUTF8"}) do
    fontMethods[name]=function(self,...) nativeDraws=nativeDraws+1; return "font",42 end
end
fontMeta={__index=fontMethods}
Font=function() return setmetatable({}, fontMeta) end
Isaac={RenderText=function(text,...) nativeDraws=nativeDraws+1; return "text",17 end}
cachedRenderBeforeObserver=Isaac.RenderText
entities={}
Isaac.GetRoomEntities=function() return entities end
GetPtrHash=function(entity) return entity.ptr end
local level={GetCurrentRoomIndex=function() return 12 end,GetStage=function() return 2 end}
local seeds={GetStartSeed=function() return 12345 end}
gameFrame=0
Game=function() return {GetFrameCount=function() return gameFrame end,
    GetLevel=function() return level end,GetSeeds=function() return seeds end} end
function newEntity(ptr,seed,parent)
    local sprite=Sprite(); sprite:Load("gfx/monster.anm2")
    return {ptr=ptr,InitSeed=seed,Type=10,Variant=0,SubType=0,Position=Vector(12,34),
        Velocity=Vector(1,0),HitPoints=10,MaxHitPoints=10,Parent=parent,
        GetSprite=function() return sprite end,ToPlayer=function() return nil end}
end
function update() gameFrame=gameFrame+1; callbacks[1]() end
function postRender() callbacks[2]() end
function clearEmissions() emissions={} end
function lastKind(kind)
    for i=#emissions,1,-1 do if emissions[i].kind==kind then return emissions[i] end end
end
'''

def runtime(role="capture"):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(FIXTURE)
    lua.globals().IsaacAuthorityRole = role
    lua.execute((ROOT / "lua" / "probe.lua").read_text(encoding="utf-8"))
    return lua

class CaptureTests(unittest.TestCase):
    def test_original_results_and_single_draw_preserved(self):
        lua = runtime()
        lua.execute("update(); a,b=Isaac.RenderText('hello',1,2,1,1,1,1)")
        self.assertEqual((lua.globals().a, lua.globals().b), ("text", 17))
        self.assertEqual(lua.globals().nativeDraws, 1)

    def test_font_asset_and_private_result_captured(self):
        lua = runtime()
        lua.execute("update(); update(); update(); f=Font(); f:Load('font/test.fnt'); f:DrawStringUTF8('私有状态=47',12,13,KColor(1,1,1,1),0,false); postRender()")
        draw = lua.globals().lastKind("draw").body.commands[1]
        self.assertEqual(draw.op, "font")
        self.assertEqual(draw.asset, "font/test.fnt")
        self.assertEqual(bytes.fromhex(draw.text_hex).decode(), "私有状态=47")

    def test_sprite_resources_and_native_return_values(self):
        lua = runtime()
        lua.execute("update(); update(); update(); s=Sprite(); s:Load('gfx/test.anm2'); s:ReplaceSpritesheet(0,'gfx/test.png'); a,b=s:Render(Vector(4,5)); postRender()")
        self.assertEqual((lua.globals().a, lua.globals().b), ("sprite", 23))
        draw = lua.globals().lastKind("draw").body.commands[1]
        self.assertEqual(draw.asset, "gfx/test.anm2")
        self.assertEqual(draw.sheets["0"], "gfx/test.png")

    def test_callable_constructors_and_native_metatable_accessor(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(FIXTURE + r'''
          local spriteFactory, fontFactory, realMetatable = Sprite, Font, debug.getmetatable
          Sprite=setmetatable({}, {__call=function() return spriteFactory() end})
          Font=setmetatable({}, {__call=function() return fontFactory() end})
          IsaacAuthorityNativeMetatable=realMetatable
          debug=nil
        ''')
        lua.execute((ROOT / "lua" / "probe.lua").read_text(encoding="utf-8"))
        event = lua.globals().lastKind("event").body
        self.assertTrue(event.sprite)
        self.assertTrue(event.font)

    def test_entity_identity_lifecycle_and_parent_reference(self):
        lua = runtime()
        lua.execute("e1=newEntity(100,77); e2=newEntity(200,78,e1); entities={e1,e2}; update(); update(); update()")
        world = lua.globals().lastKind("world").body
        first, second = world.entities[1].id, world.entities[2].id
        self.assertEqual(world.entities[2].parent, first)
        lua.execute("entities={e2}; update(); update(); update()")
        world = lua.globals().lastKind("world").body
        self.assertEqual(world.removed[1], first)
        self.assertIsNone(world.entities[1].parent)
        lua.execute("e1=newEntity(100,77); entities={e1,e2}; update(); update(); update()")
        self.assertGreater(lua.globals().lastKind("world").body.entities[2].id, second)

    def test_stop_restores_wrappers_and_keeps_callback_inert(self):
        lua = runtime()
        lua.execute("inbound={stop=true}; update(); clearEmissions(); update(); postRender(); same=Isaac.RenderText==cachedRenderBeforeObserver")
        self.assertTrue(lua.globals().same)
        self.assertEqual(len(lua.globals().emissions), 0)

    def test_native_errors_are_not_swallowed_by_wrapper(self):
        lua = runtime()
        # A different fixture with a real failing original proves wrapper error semantics.
        lua2 = LuaRuntime(unpack_returned_tuples=True)
        lua2.execute(FIXTURE + "\nIsaac.RenderText=function() error('original failure') end")
        lua2.execute((ROOT / "lua" / "probe.lua").read_text(encoding="utf-8"))
        lua2.execute("ok,err=pcall(function() Isaac.RenderText('x',1,1,1,1,1,1) end)")
        self.assertFalse(lua2.globals().ok)
        self.assertIn("original failure", lua2.globals().err)

    def test_cached_native_function_bypasses_lua_wrapper(self):
        lua = runtime()
        lua.execute("update(); update(); update(); cachedRenderBeforeObserver('uncaptured',1,2,1,1,1,1); postRender()")
        self.assertEqual(len(lua.globals().lastKind("draw").body.commands), 0)
        self.assertEqual(lua.globals().nativeDraws, 3)  # Mod draw, transparent selftest and observer label.

    def test_cpp_dispatcher_method_fields_remain_untouched(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(FIXTURE + r'''
          local expectedFont = {}; for k,v in pairs(fontMethods) do expectedFont[k]=v end
          local expectedSprite = {}; for k,v in pairs(spriteMethods) do expectedSprite[k]=v end
          fontMeta.__index=function(self,key)
            assert(fontMethods[key] == expectedFont[key], 'native C dispatcher received replaced method')
            return fontMethods[key]
          end
          spriteMeta.__index=function(self,key)
            assert(spriteMethods[key] == expectedSprite[key], 'native C dispatcher received replaced method')
            return spriteMethods[key]
          end
        ''')
        lua.execute((ROOT / "lua" / "probe.lua").read_text(encoding="utf-8"))
        lua.execute("update(); f=Font(); f:Load('font/test.fnt'); s=Sprite(); s:Load('gfx/test.anm2'); s:Render(Vector(1,2)); f:DrawString('test',1,2,KColor(1,1,1,1)); inbound={stop=true}; update(); f:Load('font/test.fnt')")

    def test_native_watch_path_does_not_modify_class_metatable(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(FIXTURE + r'''
          watched={}; originalSpriteIndex=spriteMeta.__index; originalFontIndex=fontMeta.__index
          IsaacAuthorityNativeWatch=function(object,name,callback)
            watched[#watched+1]={object=object,name=name,callback=callback}; return true
          end
        ''')
        lua.execute((ROOT / "lua" / "probe.lua").read_text(encoding="utf-8"))
        self.assertTrue(lua.eval("spriteMeta.__index == originalSpriteIndex and fontMeta.__index == originalFontIndex"))
        self.assertEqual(len(lua.globals().watched), 10)

    def test_j460_raw_font_signature_and_render_settings(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(FIXTURE + r'''
          watched={}
          IsaacAuthorityNativeWatch=function(object,name,callback)
            watched[#watched+1]={object=object,name=name,callback=callback}; return true
          end
        ''')
        lua.execute((ROOT / "lua" / "probe.lua").read_text(encoding="utf-8"))
        lua.execute(r'''
          update(); update(); update()
          local f=Font()
          watched[6].callback(f,'font/test.fnt')
          local settings={GetAlignment=function() return 2 end,GetLineHeightModifier=function() return 1.25 end,
            GetMaxCharacters=function() return 100 end,GetMissingCharacterOverride=function() return 63 end,
            IsAutoWrapEnabled=function() return true end,IsTruncationEnabled=function() return false end}
          watched[7].callback(f,'私有文字',12,13,0.7,0.8,KColor(1,0.5,1,1),settings)
          postRender()
        ''')
        draw = lua.globals().lastKind("draw").body.commands[1]
        self.assertTrue(draw.native_signature)
        self.assertEqual((draw.sx, draw.sy, draw.color.g), (0.7, 0.8, 0.5))
        self.assertEqual(draw.settings.alignment, 2)
        self.assertTrue(draw.settings.auto_wrap)

    def test_stop_works_during_render_without_game_update(self):
        lua = runtime()
        lua.execute("stopAcks=0; IsaacAuthorityNativeStopped=function() stopAcks=stopAcks+1 end; inbound={stop=true}; postRender(); postRender(); same=Isaac.RenderText==cachedRenderBeforeObserver")
        self.assertTrue(lua.globals().same)
        self.assertEqual(lua.globals().stopAcks, 1)

    def test_absolute_local_resource_is_mapped_to_game_relative_path(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute(FIXTURE)
        lua.globals().IsaacAuthorityGameRoot = "E:\\SteamLibrary\\steamapps\\common\\Isaac"
        lua.execute((ROOT / "lua" / "probe.lua").read_text(encoding="utf-8"))
        lua.execute("update(); update(); update(); f=Font(); f:Load('e:/steamlibrary/steamapps/common/Isaac/mods/menu/resources/font.fnt'); f:DrawString('test',1,2,KColor(1,1,1,1)); postRender()")
        self.assertEqual(lua.globals().lastKind("draw").body.commands[1].asset, "mods/menu/resources/font.fnt")

    def test_repeating_legacy_render_mutates_private_gameplay_state(self):
        lua = runtime()
        lua.execute("""
          local privateCounter=0
          legacyRender=function()
            privateCounter=privateCounter+1
            Isaac.RenderText('counter='..privateCounter,1,2,1,1,1,1)
            return privateCounter
          end
          first=legacyRender(); second=legacyRender()
        """)
        self.assertEqual((lua.globals().first, lua.globals().second), (1, 2))
        # Calling once per recipient is not a transparent, generic UI solution.

    def test_local_setting_change_cannot_change_already_captured_upvalue(self):
        lua = runtime()
        lua.execute("""
          local savedConfig={language='zh'}
          legacyRender=function() Isaac.RenderText(savedConfig.language,1,2,1,1,1,1) end
          update(); update(); update()
          peerConfig={language='en'}
          legacyRender(); postRender()
        """)
        self.assertEqual(bytes.fromhex(lua.globals().lastKind("draw").body.commands[1].text_hex).decode(), "zh")

    def test_raw_legacy_text_bytes_are_preserved(self):
        lua = runtime()
        lua.execute("update(); update(); update(); f=Font(); f:Load('font/test.fnt'); f:DrawString(string.char(0xb0,0xb4,0,0xff),1,2,{Red=0.2,Green=0.3,Blue=0.4,Alpha=0.5}); postRender()")
        draw = lua.globals().lastKind("draw").body.commands[1]
        self.assertEqual(bytes.fromhex(draw.text_hex), bytes([0xb0, 0xb4, 0, 0xff]))
        self.assertEqual((draw.color.r, draw.color.g, draw.color.b, draw.color.a), (0.2, 0.3, 0.4, 0.5))

def chaos_runtime(random_value=1, clock=100, language="zh", key=76):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(FIXTURE)
    lua.globals().fixtureRandom = random_value
    lua.globals().fixtureClock = clock
    lua.globals().fixtureLanguage = language
    lua.globals().fixtureKey = key
    lua.execute(r'''
      Keyboard={KEY_L=76}; pressedKey=nil; worldCoins=0; configWrites=0
      fixtureConfig={language=fixtureLanguage,x=24,key=fixtureKey}
      json.decode=function() return fixtureConfig end
      RegisterMod=function()
        return {HasData=function() return true end,LoadData=function() return 'local-config' end,
                SaveData=function() configWrites=configWrites+1 end,
                AddCallback=function(self,id,fn) callbacks[id]=fn end}
      end
      math.random=function() return fixtureRandom end
      Isaac.GetTime=function() return fixtureClock end
      Isaac.GetPlayer=function() return {AddCoins=function(self,amount) worldCoins=worldCoins+amount end} end
      Isaac.RenderText=function(text,x) lastText=text; lastX=x end
      Input.IsButtonTriggered=function(key,controller) return key==pressedKey end
    ''')
    lua.execute((ROOT / "fixtures" / "legacy_chaos" / "main.lua").read_text(encoding="utf-8"))
    return lua

class LegacyChaosTests(unittest.TestCase):
    def test_random_and_clock_require_suppression_of_guest_logic(self):
        host, guest = chaos_runtime(1, 100), chaos_runtime(3, 103)
        host.execute("update(); postRender()")
        guest.execute("update(); postRender()")
        self.assertEqual((host.globals().worldCoins, guest.globals().worldCoins), (2, 7))
        # This is a counterexample, not a successful client isolation test.

    def test_second_recipient_render_repeats_world_mutation(self):
        lua = chaos_runtime()
        lua.execute("update(); postRender(); firstCoins=worldCoins; firstText=lastText; postRender()")
        self.assertEqual((lua.globals().firstCoins, lua.globals().worldCoins), (2, 3))
        self.assertEqual((lua.globals().firstText, lua.globals().lastText), ("zh|1|100|1", "zh|2|100|1"))

    def test_private_language_key_and_config_save_remain_per_vm(self):
        host, guest = chaos_runtime(language="zh", key=76), chaos_runtime(language="en", key=77)
        host.execute("peerConfig={language='en',key=77}; pressedKey=77; update(); postRender()")
        guest.execute("pressedKey=77; update(); postRender()")
        self.assertTrue(host.globals().lastText.startswith("zh|"))
        self.assertTrue(guest.globals().lastText.startswith("en|"))
        self.assertEqual((host.globals().configWrites, guest.globals().configWrites), (0, 1))
        self.assertEqual((host.globals().lastX, guest.globals().lastX), (24, 25))

if __name__ == "__main__":
    unittest.main(verbosity=2)
