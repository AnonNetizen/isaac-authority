#include "lua_bridge.hpp"
#include <iostream>
#include <stdexcept>
namespace {
using namespace ia;
BridgeLuaApi api;
constexpr int registry=-1001000;
constexpr const char* value_meta="AuthorityBridge.NativeTestValue";
struct Value {int64_t x{},y{};};
int __cdecl fail(BridgeLuaState* state) {api.pushstring(state,"native fixture error",20);return api.error(state);}
Value* value(BridgeLuaState* state,int index) {return static_cast<Value*>(api.testuserdata(state,index,value_meta));}
void push_value(BridgeLuaState* state,int64_t x,int64_t y) {
    *static_cast<Value*>(api.newuserdata(state,sizeof(Value)))={x,y};api.newmetatable(state,value_meta);api.setmetatable(state,-2);
}
int __cdecl construct(BridgeLuaState* state) {push_value(state,api.integer(state,1,nullptr),api.integer(state,2,nullptr));return 1;}
int __cdecl add(BridgeLuaState* state) {
    auto self=value(state,1);if(!self)return fail(state);
    self->x+=api.integer(state,2,nullptr);api.pushinteger(state,self->x);return 1;
}
int __cdecl outputs(BridgeLuaState* state) {api.pushnil(state);api.pushinteger(state,INT64_MAX);api.pushboolean(state,1);const char raw[]{'a',0,static_cast<char>(0xff)};api.pushstring(state,raw,sizeof(raw));return 4;}
int __cdecl echo_number(BridgeLuaState* state) {api.pushnumber(state,api.number(state,2,nullptr));return 1;}
int __cdecl read_x(BridgeLuaState* state) {auto self=value(state,1);if(!self)return fail(state);api.pushinteger(state,self->x);return 1;}
int __cdecl read_preset(BridgeLuaState* state) {api.getglobal(state,"Preset");return 1;}
int __cdecl index(BridgeLuaState* state) {
    auto self=value(state,1);if(!self)return fail(state);auto key=api.string(state,2,nullptr);
    if(!strcmp(key,"X"))api.pushinteger(state,self->x);
    else if(!strcmp(key,"Y"))api.pushinteger(state,self->y);
    else if(!strcmp(key,"Add"))api.pushclosure(state,add,0);
    else if(!strcmp(key,"Outputs"))api.pushclosure(state,outputs,0);
    else if(!strcmp(key,"EchoNumber"))api.pushclosure(state,echo_number,0);
    else if(!strcmp(key,"Fail"))api.pushclosure(state,fail,0);
    else if(!strcmp(key,"Self"))api.pushvalue(state,1);
    else if(!strcmp(key,"ReadX")||!strcmp(key,"ReadAlias"))api.pushclosure(state,read_x,0);
    else api.pushnil(state);
    return 1;
}
int __cdecl assign(BridgeLuaState* state) {
    auto self=value(state,1);if(!self)return fail(state);auto key=api.string(state,2,nullptr);
    if(strcmp(key,"X"))return fail(state);self->x=api.integer(state,3,nullptr);return 0;
}
int __cdecl sum(BridgeLuaState* state) {
    auto a=value(state,1),b=value(state,2);if(!a||!b)return fail(state);push_value(state,a->x+b->x,a->y+b->y);return 1;
}
void check(bool condition,const char* label) {if(!condition)throw std::runtime_error(label);}
}
int wmain(int argc,wchar_t** argv) {
    using namespace ia;BridgeLuaState* host{};HMODULE module{};
    try {
        if(argc!=2)throw std::runtime_error("Usage: authority-bridge-tests.exe PATH_TO_INSTALLED_Lua5.3.3r.dll");
        std::filesystem::path path=std::filesystem::absolute(argv[1]);
        if(sha256_file(path)!="fb84afbc5b227b06f71022bb6c0bcc0a39f85e5939b789489906bc128d05a13e")throw std::runtime_error("Unverified Lua runtime hash");
        module=LoadLibraryExW(path.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        if(!module)throw std::runtime_error("Cannot load local Lua runtime");api=BridgeLuaApi::resolve(module);host=api.newstate();check(host!=nullptr,"Create host");api.openlibs(host);
        api.newmetatable(host,value_meta);
        for(auto [name,fn]:std::initializer_list<std::pair<const char*,BridgeLuaFunction>>{{"__index",index},{"__newindex",assign},{"__add",sum}}){api.pushclosure(host,fn,0);api.setfield(host,-2,name);}
        api.settop(host,0);api.pushclosure(host,construct,0);api.setglobal(host,"Fixture");
        push_value(host,50,60);api.setglobal(host,"Preset");
        api.execute(host,"ConstructorTable=setmetatable({Preset=Preset},{__call=function(_,...)return Fixture(...)end}); sentinel='host-private'","@host-fixture");
        unsigned passed{};
        {
            LuaObjectBridge bridge(api,host);bridge.expose("Fixture");bridge.expose("ConstructorTable");
            auto test=[&](const char* code){bridge.run(code);++passed;check(api.gettop(host)==0,"Host stack restored");check(api.gettop(bridge.shadow())==0,"Shadow stack restored");};
            test("v=Fixture(3,4);assert(type(v)=='userdata' and v.X==3 and v.Y==4)");
            test("v.X=6;assert(v.X==6)");
            test("assert(v:Add(2)==8);cached=v.Add;assert(cached(v,3)==11)");
            test("assert(rawequal(v.Self,v) and v.Self==v)");
            test("local a,b,c,d=v:Outputs();assert(a==nil and b==9223372036854775807 and c==true and d==string.char(97,0,255))");
            test("local n=Fixture(-9223372036854775807,1);assert(n.X==-9223372036854775807)");
            test("assert(v:EchoNumber(0.25)==0.25 and v:EchoNumber(-1.5)==-1.5)");
            test("local n=v+Fixture(1,2);assert(n.X==12 and n.Y==6);n.X=20;assert(v.X==11)");
            test("local n=ConstructorTable(7,9);assert(n.X==7 and n.Y==9)");
            test("assert(type(ConstructorTable)=='table');ConstructorTable.localSetting='personal';rawset(ConstructorTable,'LOCAL_FLAG',123);assert(ConstructorTable.localSetting=='personal' and ConstructorTable.LOCAL_FLAG==123)");
            test("assert(ConstructorTable.Preset.X==50 and getmetatable(v)=='AuthorityObjectProxy')");
            test("assert(Isaac==nil and Game==nil and sentinel==nil);sentinel='shadow-private'");
            auto reject=[&](const char* code,const char* expected){bool refused{};try{bridge.run(code);}catch(const std::exception& error){refused=std::string(error.what()).find(expected)!=std::string::npos;}check(refused,expected);++passed;check(api.gettop(host)==0,"Error restored host stack");check(api.gettop(bridge.shadow())==0,"Error restored shadow stack");};
            reject("pcall(function()ConstructorTable.Preset.X=99 end)","Borrowed host objects");
            test("assert(ConstructorTable.Preset.X==50)");
            reject("pcall(function()ConstructorTable.Preset:Add(1)end)","owned object receiver");
            reject("pcall(function()v:Add({})end)","Foreign table/function/userdata");
            reject("pcall(function()v:Fail()end)","native fixture error");
            reject("pcall(function()Fixture(0/0,1)end)","Nonfinite bridge number");
            reject("local c=coroutine.create(function()Fixture(1,2)end);coroutine.resume(c)","Coroutine bridge calls");
            test("assert(v.X==11)");
            {LuaObjectBridge second(api,host);second.expose("Fixture");second.run("w=Fixture(100,200);w.X=300;assert(w.X==300 and v==nil)");++passed;}
            test("assert(v.X==11 and sentinel=='shadow-private')");
            api.execute(host,"assert(sentinel=='host-private' and Preset.X==50 and rawget(ConstructorTable,'localSetting')==nil and rawget(ConstructorTable,'LOCAL_FLAG')==nil)","@host-unchanged");++passed;
            auto result=bridge.run("return v, v.Self, true, string.char(0,255)");check(result[0]==result[1]&&result[0]["t"]=="ref"&&result[3]["hex"]=="00ff","Wire IDs and bytes");++passed;
            bridge.install_service([](const std::string& op,const Json& args){if(op=="fail")throw std::runtime_error("service fixture failure");return args;});
            test("local a,b=__authority_service('echo',{x=1,array={true,3.5}},'z\\0q');assert(a.x==1 and a.array[1] and a.array[2]==3.5 and b=='z\\0q')");
            test("local t={leaf=42};for i=1,22 do t={inner=t} end;local q=__authority_service('echo',t);for i=1,22 do q=q.inner end;assert(q.leaf==42)");
            test("local args={};for i=1,64 do args[i]=i end;local out=table.pack(__authority_service('echo',table.unpack(args)));assert(out.n==64 and out[64]==64)");
            reject("pcall(function()__authority_service('echo',v)end)","cannot become service data");
            reject("pcall(function()__authority_service('echo',ConstructorTable)end)","Native proxy cannot");
            reject("pcall(function()__authority_service('fail')end)","service fixture failure");
            bridge.set_policy([](const std::string& label,const std::string& op,const std::vector<Json>&){if(op=="call"&&label=="Fixture.Add")throw std::runtime_error("fixture method policy denied");});
            reject("pcall(function()cached(v,1)end)","fixture method policy denied");
            test("assert(v.X==11)");
        }
        {
            LuaObjectBridge bridge(api,host);bridge.expose("Fixture");unsigned completed{};
            bridge.set_call_adapter([](const auto& label,const auto& op,auto& args){if(op=="call"&&label=="Fixture.Add")args[1]={{"t","integer"},{"v",7}};},
                [&](const auto& label,const auto& op,const auto&,const auto&){if(op=="call"&&label.starts_with("Fixture."))++completed;});
            bridge.run("v=Fixture(1,2);assert(v:Add(123)==8)");check(completed==1,"Adapter transforms wire arguments");++passed;
            bool refused{};try{bridge.run("pcall(function()v:Fail()end)");}catch(const std::exception& e){refused=std::string(e.what()).find("native fixture error")!=std::string::npos;}
            check(refused&&completed==1,"Failed native call never reaches completion adapter");++passed;
        }
        api.createtable(host,0,1);api.pushclosure(host,read_preset,0);api.setfield(host,-2,"GetPreset");api.setglobal(host,"ReadNamespace");
        {
            LuaObjectBridge bridge(api,host);bridge.expose_readonly_getter("ReadPreset","ReadNamespace","GetPreset","BorrowedValue");
            bridge.allow_readonly_method("BorrowedValue","ReadX");bridge.allow_readonly_method("BorrowedValue","Self","BorrowedValue");
            bridge.expose("Fixture");
            auto test=[&](const char* code){bridge.run(code);++passed;check(api.gettop(host)==0&&api.gettop(bridge.shadow())==0,"Read API stack restored");};
            auto reject=[&](const char* code,const char* expected){bool refused{};try{bridge.run(code);}catch(const std::exception& e){refused=std::string(e.what()).find(expected)!=std::string::npos;}check(refused,expected);++passed;check(api.gettop(host)==0&&api.gettop(bridge.shadow())==0,"Read error stack restored");};
            test("r=ReadPreset();assert(r.X==50 and Isaac==nil and ReadNamespace==nil);cachedRead=r.ReadX;assert(cachedRead(r)==50)");
            reject("pcall(function()r.X=999 end)","Borrowed host objects");
            reject("pcall(function()r:Add(1)end)","owned object receiver");
            reject("pcall(function()r:ReadAlias()end)","owned object receiver");
            reject("pcall(function()cachedRead(Fixture(8,9))end)","receiver capability mismatch");
            reject("pcall(function()ReadPreset(1)end)","takes no arguments");
            test("assert(ReadPreset()==r and r.X==50 and cachedRead(r)==50)");
        }
        api.execute(host,"assert(Preset.X==50)","@borrowed-host-unchanged");++passed;
        api.execute(host,"LuaNamespace={GetPreset=function()Preset.X=999;return Preset end}","@unsafe-read-fixture");
        {
            LuaObjectBridge bridge(api,host);bool refused{};
            try{bridge.expose_readonly_getter("Read","LuaNamespace","GetPreset","BorrowedValue");}
            catch(const std::exception& e){refused=std::string(e.what()).find("native C binding")!=std::string::npos;}
            check(refused&&api.gettop(host)==0,"Lua replacement read getter refused before execution");++passed;
        }
        api.execute(host,"assert(Preset.X==50)","@unsafe-getter-not-executed");++passed;
        api.close(host);host=nullptr;FreeLibrary(module);module=nullptr;
        std::cout<<Json({{"passed",passed},{"x86",true},{"actual_lua_c_api",true},{"native_test_userdata",true},{"live_game_test",false},{"playable",false}}).dump()<<'\n';return 0;
    }catch(const std::exception& error){if(host)api.close(host);if(module)FreeLibrary(module);std::cerr<<error.what()<<'\n';return 1;}
}
