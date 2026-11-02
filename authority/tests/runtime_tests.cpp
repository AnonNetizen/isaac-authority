#include "mod_runtime.hpp"
#include <iostream>
namespace {
using namespace ia;
void check(bool ok,const char* message) {if(!ok)throw std::runtime_error(message);}
std::string read(const std::filesystem::path& path) {std::ifstream file(path,std::ios::binary);if(!file)throw std::runtime_error("Missing test source");return std::string((std::istreambuf_iterator<char>(file)),{});}
FrozenMod inline_mod(const std::filesystem::path& root,const std::string& name,const std::string& code) {
    FrozenMod mod;mod.root=root/L"fixtures"/wide(name);mod.files["main.lua"]=code;mod.hashes={{"main.lua","synthetic-test-source"}};return mod;
}
Json configs(const std::string& name) {
    return Json::array({Json{{name,Json({{"language","zh"},{"key",76},{"x",24},{"amount",1}}).dump()}},
        Json{{name,Json({{"language","en"},{"key",77},{"x",124},{"amount",1}}).dump()}}});
}
std::string text(const Json& frame,size_t slot) {auto hex=frame.at("draws").at(slot).at(0).at("text_hex").get<std::string>();std::string text;for(size_t i=0;i<hex.size();i+=2)text+=static_cast<char>(std::stoi(hex.substr(i,2),nullptr,16));return text;}
}
int wmain(int argc,wchar_t** argv) {
    using namespace ia;HMODULE module{};BridgeLuaState* host{};BridgeLuaApi api;
    try {
        if(argc!=3)throw std::runtime_error("Usage: authority-runtime-tests.exe LUA_RUNTIME RESEARCH_SOURCE_DIR");
        std::filesystem::path runtime=std::filesystem::absolute(argv[1]),root=std::filesystem::absolute(argv[2]);
        if(sha256_file(runtime)!="fb84afbc5b227b06f71022bb6c0bcc0a39f85e5939b789489906bc128d05a13e")throw std::runtime_error("Unverified Lua runtime");
        module=LoadLibraryExW(runtime.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);check(module!=nullptr,"Load pinned Lua");
        api=BridgeLuaApi::resolve(module);host=api.newstate();check(host!=nullptr,"Create host Lua");api.openlibs(host);
        auto bootstrap=read(root/L"research/native_context.lua");auto chaos=FrozenMod::directory(root/L"fixtures/legacy_chaos");unsigned passed{};
        auto test=[&](auto body){body();++passed;check(api.gettop(host)==0,"Host stack restored");};
        auto reject=[&](auto body,const char* expected){bool refused{};try{body();}catch(const std::exception& error){refused=std::string(error.what()).find(expected)!=std::string::npos;}check(refused,expected);++passed;check(api.gettop(host)==0,"Error stack restored");};
        auto empty=Json::array({Json::object(),Json::object()});auto stores=configs("Authority Research Legacy Chaos Fixture");
        test([&]{check(sha256_bytes("abc")=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad","Known SHA256 bytes");check(chaos.hashes.at("main.lua")==sha256_bytes(chaos.files.at("main.lua")),"Frozen code hash matches executed bytes");});
        {
            NativeModSession session(api,host,bootstrap,"",{chaos},stores,false);Json first;
            test([&]{first=session.step(1,1001,empty);check(first["effects"].size()==2,"Exactly two canonical model writes");check(session.world.coins[0]==first["effects"][0]["amount"].get<int64_t>()+1,"World only committed once");});
            test([&]{check(text(first,0).starts_with("zh|1|1001|")&&text(first,1).starts_with("en|1|1001|"),"Private labels/shared random time");check(text(first,0).substr(2)==text(first,1).substr(2),"Shared decision transcript");});
            Json input=Json::array({Json{{"triggered",Json::array({77})}},Json{{"triggered",Json::array({77})}}});auto second=session.step(2,1017,input);
            test([&]{check(second["draws"][0][0]["x"]==24&&second["draws"][1][0]["x"]==125,"Independent key/config");});
            test([&]{auto decoded=Json::parse(session.stores()[1]["Authority Research Legacy Chaos Fixture"].get<std::string>());check(decoded["x"]==125,"Private config stored");});
            test([&]{auto world=session.world.snapshot();auto store=session.stores();auto duplicate=session.step(2,1017,input);check(duplicate["duplicate"]==true&&session.world.snapshot()==world&&session.stores()==store,"Duplicate no effects/config");});
            reject([&]{session.step(2,1018,input);},"Duplicate model frame payload changed");
            reject([&]{session.step(4,1020,empty);},"sequence/time");
            reject([&]{session.step(3,1000,empty);},"sequence/time");
            test([&]{auto third=session.step(3,1034,empty);check(text(third,0).starts_with("zh|3|")&&text(third,1).starts_with("en|3|"),"Private render counts");});
        }
        {
            auto drives=FrozenMod::directory(root/L"fixtures/config_drives_world");NativeModSession session(api,host,bootstrap,"",{drives},configs("Config Drives World Fixture"),false);
            auto first=session.step(1,100,empty);auto before_store=session.stores();
            reject([&]{session.step(2,101,Json::array({Json::object(),Json{{"triggered",Json::array({77})}}}));},"divergent authority world call");
            test([&]{check(session.world.snapshot()==first["world"]&&session.stores()==before_store,"Failure model/config rollback");});
            test([&]{auto recovered=session.step(2,101,empty);check(text(recovered,0)=="zh|2"&&text(recovered,1)=="en|2"&&session.world.coins[0]==2,"Upvalue/history reconstruction");});
        }
        {
            auto a=inline_mod(root,"shared_a","shared={count=0};local m=RegisterMod('a',1);m:AddCallback(2,function()shared.count=shared.count+1 end)");
            auto b=inline_mod(root,"shared_b","local m=RegisterMod('b',1);m:AddCallback(2,function()Isaac.RenderText('n='..shared.count,1,2,1,1,1,1)end)");
            NativeModSession session(api,host,bootstrap,"",{a,b},Json::array({Json::object(),Json::object()}),false);
            test([&]{auto frame=session.step(1,10,empty);check(text(frame,0)=="n=1"&&text(frame,1)=="n=1","Mods share globals within context");});
            test([&]{session.inspect(0,"shared.count=7");auto private_state=session.inspect(1,"return shared.count");check(private_state[0]["v"]==1,"Contexts isolate shared globals");});
        }
        auto make=[&](const std::string& code){return std::make_unique<NativeModSession>(api,host,bootstrap,"",std::vector<FrozenMod>{inline_mod(root,"synthetic",code)},Json::array({Json::object(),Json::object()}),false);};
        test([&]{api.execute(host,"Options={Language='zh',HUDOffset=0.4}","@synthetic-native-options");auto snapshot=snapshot_personal_options(api,host);check(snapshot["Language"]=="zh"&&snapshot["HUDOffset"]==0.4,"Typed read-only option snapshot");api.execute(host,"assert(Options.Language=='zh' and Options.HUDOffset==0.4)","@original-options-unchanged");});
        reject([&]{api.execute(host,"Options={Language=1,HUDOffset=0.4}","@invalid-native-options");snapshot_personal_options(api,host);},"Native personal option types changed");
        reject([&]{api.execute(host,"Options={Language='zh',HUDOffset=0/0}","@nonfinite-native-options");snapshot_personal_options(api,host);},"Nonfinite bridge number");
        {
            auto mod=inline_mod(root,"private_options","local m=RegisterMod('private options',1);local cached=Options;m:AddCallback(2,function() if Input.IsButtonTriggered(78,0)then cached.Language='fr';cached.HUDOffset=0.8 end;if Input.IsButtonPressed(999,0)then cached.Language='de';Isaac.GetPlayer(0):AddCoins(1)end;Isaac.RenderText(cached.Language, cached.HUDOffset,2,1,1,1,1)end)");
            Json overrides=Json::array({Json{{"Language","zh"},{"HUDOffset",0.2}},Json{{"Language","en"},{"HUDOffset",0.6}}});
            NativeModSession session(api,host,bootstrap,"",{mod},Json::array({Json::object(),Json::object()}),false,overrides);
            test([&]{auto first=session.step(1,100,empty);check(text(first,0)=="zh"&&text(first,1)=="en"&&first["draws"][0][0]["x"]==0.2&&first["draws"][1][0]["x"]==0.6,"Independent language/HUD defaults");});
            auto changed_input=Json::array({Json::object(),Json{{"triggered",Json::array({78})}}});auto accepted=session.step(2,101,changed_input);
            test([&]{check(text(accepted,0)=="zh"&&text(accepted,1)=="fr"&&accepted["personal_options"][1]["HUDOffset"]==0.8,"Private option writes and cached reference");});
            test([&]{auto duplicate=session.step(2,101,changed_input);check(duplicate["duplicate"]==true&&session.personal_options()==accepted["personal_options"],"Option event duplicate preserved");});
            reject([&]{session.step(3,102,Json::array({Json::object(),Json{{"pressed",Json::array({999})}}}));},"added authority world call");
            test([&]{check(session.personal_options()==accepted["personal_options"],"Rejected option mutation rolled back");auto recovered=session.step(3,102,empty);check(text(recovered,0)=="zh"&&text(recovered,1)=="fr"&&recovered["stores"][0].empty()&&recovered["stores"][1].empty(),"Recovery freezes overrides and separates mod save data");});
        }
        reject([&]{make("pcall(function() Options.Language=3 end)");},"Personal Language must be a string");
        reject([&]{make("Options.HUDOffset=1.1");},"Personal HUDOffset range");
        reject([&]{make("pcall(function() local value=Options.Unknown end)");},"Unsupported boundary: Options.Unknown");
        reject([&]{make("Options.Unknown=true");},"Unsupported boundary: Options.Unknown");
        reject([&]{make("rawset(Options,'Language','fr')");},"Options.raw_property_write");
        reject([&]{make("Options.Language=string.rep('a',33)");},"Personal Language code rejected");
        reject([&]{NativeModSession session(api,host,bootstrap,"",{},Json::array({Json::object(),Json::object()}),false,Json::array({Json{{"Unknown",true}},Json::object()}));},"Unsupported personal option override");
        test([&]{make("local m=RegisterMod('callbacks',1);local order='';m:AddPriorityCallback('custom',10,function(self,n) assert(self==m and n==7);order=order..'c';return false end);m:AddPriorityCallback('custom',0,function()order=order..'b' end);m:AddPriorityCallback('custom',-10,function()order=order..'a' end);m:AddPriorityCallback('custom',10,function()error('false must stop')end);assert(Isaac.RunCallback('custom',7)==false and order=='abc');local list=Isaac.GetCallbacks('custom');assert(#list==4 and list[1].Mod==m and type(list[1].Function)=='function' and list[1].Priority==-10)");});
        test([&]{make("local m=RegisterMod('params',1);local n=0;m:AddCallback('p',function()n=n+1 end,3);Isaac.RunCallbackWithParam('p',2);assert(n==0);Isaac.RunCallbackWithParam('p',3);Isaac.RunCallbackWithParam('p',-1);Isaac.RunCallback('p');assert(n==3)");});
        test([&]{make("local m=RegisterMod('match meta',1);local list=Isaac.GetCallbacks('custom',true);assert(list==Isaac.GetCallbacks('custom'));setmetatable(list,{__matchParams=function(a,b)return a==b+1 end});m:AddCallback('custom',function()return 42 end,3);assert(Isaac.RunCallbackWithParam('custom',4)==42 and Isaac.RunCallbackWithParam('custom',3)==nil);assert(#Isaac.GetCallbacks('missing')==0)");});
        test([&]{make("local a,b=RegisterMod('a',1),RegisterMod('b',1);local fn=function()return 1 end;a:AddCallback('remove',fn);b:AddCallback('remove',fn);a:RemoveCallback('remove',fn);assert(#Isaac.GetCallbacks('remove')==0 and Isaac.RunCallback('remove')==nil)");});
        test([&]{auto session=make("local m=RegisterMod('cached callback',1);local run=Isaac.RunCallback;m:AddCallback('inner',function(self,v)return Options.Language..v end);m:AddCallback(2,function()Isaac.RenderText(run('inner','!'),1,2,1,1,1,1)end)");session->inspect(0,"Options.Language='zh';Isaac.GetCallbacks('inner')[1].Function=function()return 'private!'end");auto frame=session->step(1,100,empty);check(text(frame,0)=="private!"&&text(frame,1)=="en!","Custom callback state stays private and cached API works");});
        test([&]{auto session=make("local m=RegisterMod('nested world',1);m:AddCallback('nested',function()Isaac.GetPlayer(0):AddCoins(1)end);m:AddCallback(2,function()Isaac.RunCallback('nested')end)");auto frame=session->step(1,100,empty);check(frame["effects"].size()==1&&session->world.coins[0]==1,"Nested callback world calls commit one model copy");});
        {
            auto session=make("local m=RegisterMod('private actions',1);local triggered,pressed,button,value=Input.IsActionTriggered,Input.IsActionPressed,Input.IsButtonTriggered,Input.GetActionValue;m:AddCallback(2,function()Isaac.RenderText('action', (triggered(6,0)and 1 or 0)+(button(6,0)and 10 or 0),pressed(6,0)and 100 or 0,value(6,0),1,1,1)end)");
            auto inputs=Json::array({Json{{"action_triggered",Json::array({6})},{"action_pressed",Json::array({6})},{"actions",{{"6",0.25}}}},Json{{"triggered",Json::array({6})},{"actions",{{"6",0.8}}}}});
            test([&]{auto frame=session->step(1,100,inputs);check(frame["draws"][0][0]["x"]==1&&frame["draws"][0][0]["y"]==100&&frame["draws"][0][0]["color"]["r"]==0.25,"Private action states/analog values");check(frame["draws"][1][0]["x"]==10&&frame["draws"][1][0]["y"]==0&&frame["draws"][1][0]["color"]["r"]==0.8,"Button/action namespaces separate");});
            test([&]{session->inspect(0,"Input.IsActionTriggered=function()return false end");auto a=session->inspect(0,"return Input.IsActionTriggered(6,0)");auto b=session->inspect(1,"return Input.IsActionTriggered(6,0)");check(a[0]["v"]==false&&b[0]["v"]==false,"Private input override state");auto frame=session->step(2,101,Json::array({inputs[0],inputs[0]}));check(frame["draws"][0][0]["x"]==1&&frame["draws"][1][0]["x"]==1,"Cached input functions preserved after private override");auto other=session->inspect(1,"return Input.IsActionTriggered(6,0)");check(other[0]["v"]==true,"Input override stays in one context");});
        }
        reject([&]{make("Input.IsActionTriggered(6,1)");},"Unmapped personal controller index");
        test([&]{make("assert(os.date('!%Y-%m-%d',0)=='1970-01-01');local t=os.date('!*t',86400);assert(t.year==1970 and t.month==1 and t.day==2);assert(os.date('!%m/%d',7776000)=='04/01')");});
        test([&]{auto session=make("local m=RegisterMod('model calendar',1);m:AddCallback(2,function()Isaac.RenderText(os.date('!%Y-%m-%d'),1,2,1,1,1,1)end)");auto frame=session->step(1,86400000,empty);check(text(frame,0)=="1970-01-02"&&text(frame,1)=="1970-01-02","Date uses shared replayed model time");});
        test([&]{make("local ok,err=pcall(os.date,string.rep('x',257),0);assert(not ok and err:find('date format limit',1,true))");});
        test([&]{auto session=make("local json=require('json');local t={s='中\\0文',nested={1,true,2.5},n=-9223372036854775807};local d=json.decode(json.encode(t));assert(d.s==t.s and d.n==t.n and d.nested[2]);assert(package.loaded.json==json)");});
        test([&]{auto session=make("local ok,err=pcall(require,'');assert(not ok);assert(err:find(\"no file 'resources/scripts/.lua'\",1,true));assert(err:find('/synthetic/.lua',1,true))");});
        test([&]{auto mod=inline_mod(root,"module_tree","assert(require('nested.value').x==41);assert(require('nested.value')==require('nested.value'));assert(dofile('nested/value.lua').x==41)");mod.files["nested/value.lua"]="return {x=41}";mod.hashes["nested/value.lua"]="synthetic-test-source";NativeModSession session(api,host,bootstrap,"",{mod},Json::array({Json::object(),Json::object()}),false);});
        reject([&]{make("pcall(function()Isaac.Spawn(1,2,3)end)");},"Unsupported boundary: Isaac.Spawn");
        reject([&]{make("pcall(function()require('../outside')end)");},"Module path outside frozen roots");
        reject([&]{make("pcall(function()dofile('C:/outside.lua')end)");},"Dofile path outside frozen roots");
        reject([&]{make("pcall(function()rawset(Isaac.GetPlayer(0),'Coins',99)end)");},"raw_property_write");
        reject([&]{make("pcall(function()coroutine.create(function()end)end)");},"coroutine.create");
        reject([&]{make("pcall(function()debug.sethook()end)");},"debug.sethook");
        reject([&]{make("while true do end");},"Instruction budget");
        reject([&]{make("require('json').encode(function()end)");},"cannot become service data");
        reject([&]{make("local t={};t.self=t;require('json').encode(t)");},"depth/cycle");
        reject([&]{make("require('json').encode({[1]='x',key='y'})");},"Mixed service table keys");
        test([&]{auto frozen=chaos;auto session=std::make_unique<NativeModSession>(api,host,bootstrap,"",std::vector<FrozenMod>{frozen},stores,false);frozen.files["main.lua"]="error('changed caller snapshot')";session->step(1,1,empty);check(chaos.hashes==FrozenMod::directory(root/L"fixtures/legacy_chaos").hashes,"Original fixture source unchanged");});
        api.close(host);host=nullptr;FreeLibrary(module);module=nullptr;
        std::cout<<Json({{"passed",passed},{"x86",true},{"actual_lua_c_api",true},{"native_game_world",false},{"world_kind","coin_model"},{"playable",false}}).dump()<<'\n';return 0;
    }catch(const std::exception& error){if(host)api.close(host);if(module)FreeLibrary(module);std::cerr<<error.what()<<'\n';return 1;}
}
