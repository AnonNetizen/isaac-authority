#include "lua_bridge.hpp"
#include <atomic>
#include <cmath>
#include <sstream>
namespace ia {
namespace {
constexpr int nil=0,boolean=1,number=3,string=4,table=5,lua_function=6,userdata=7;
constexpr int registry=-1001000;
const char* kind_name(int kind) {
    switch(kind) { case table:return "table"; case lua_function:return "function"; case userdata:return "userdata"; default:return "unknown"; }
}
std::string hex(const char* bytes,size_t count) {
    constexpr char digits[]="0123456789abcdef"; std::string result; result.reserve(count*2);
    for(size_t i=0;i<count;++i) { auto b=static_cast<unsigned char>(bytes[i]); result+=digits[b>>4];result+=digits[b&15]; }
    return result;
}
std::string unhex(const std::string& value) {
    if(value.size()%2 || value.size()>2*1024*1024) throw std::runtime_error("Invalid bridge string");
    auto digit=[](char c)->unsigned { if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("Invalid bridge hex"); };
    std::string result; result.reserve(value.size()/2);
    for(size_t i=0;i<value.size();i+=2)result+=static_cast<char>((digit(value[i])<<4)|digit(value[i+1]));
    return result;
}
std::string lua_error_text(const BridgeLuaApi& api,BridgeLuaState* state) {
    size_t n{}; auto text=api.string(state,-1,&n);
    return text?std::string(text,n):"Non-string Lua error";
}
bool main_native_binding(const BridgeLuaApi& api,BridgeLuaState* state,int index) {
    auto target=reinterpret_cast<void*>(api.tocfunction(state,index));MEMORY_BASIC_INFORMATION memory{};
    return target&&VirtualQuery(target,&memory,sizeof(memory))&&memory.AllocationBase==GetModuleHandleW(nullptr)
        &&(memory.Protect&(PAGE_EXECUTE|PAGE_EXECUTE_READ|PAGE_EXECUTE_READWRITE|PAGE_EXECUTE_WRITECOPY));
}
constexpr char dispatcher[]=R"LUA(return function(op,target,...)
  local a,b=...
  if op=='call' then return target(...) end
  if op=='get' then return target[a] end
  if op=='set' then target[a]=b; return end
  if op=='add' then return target+a end
  if op=='sub' then return target-a end
  if op=='mul' then return target*a end
  if op=='div' then return target/a end
  if op=='mod' then return target%a end
  if op=='pow' then return target^a end
  if op=='idiv' then return target//a end
  if op=='band' then return target&a end
  if op=='bor' then return target|a end
  if op=='bxor' then return target~a end
  if op=='shl' then return target<<a end
  if op=='shr' then return target>>a end
  if op=='unm' then return -target end
  if op=='bnot' then return ~target end
  if op=='len' then return #target end
  if op=='eq' then return target==a end
  if op=='lt' then return target<a end
  if op=='le' then return target<=a end
  error('Unsupported bridge operation: '..op)
end)LUA";
}
BridgeLuaApi BridgeLuaApi::resolve(HMODULE module) {
    BridgeLuaApi api;
#define IA_API(field,symbol) api.field=reinterpret_cast<decltype(api.field)>(GetProcAddress(module,symbol)); if(!api.field)throw std::runtime_error("Missing Lua export: " symbol)
    IA_API(newstate,"luaL_newstate"); IA_API(openlibs,"luaL_openlibs"); IA_API(close,"lua_close");
    IA_API(gettop,"lua_gettop"); IA_API(settop,"lua_settop"); IA_API(type,"lua_type"); IA_API(isinteger,"lua_isinteger");
    IA_API(checkstack,"lua_checkstack");
    IA_API(integer,"lua_tointegerx"); IA_API(number,"lua_tonumberx"); IA_API(boolean,"lua_toboolean");
    IA_API(string,"lua_tolstring"); IA_API(pointer,"lua_topointer"); IA_API(pushnil,"lua_pushnil");
    IA_API(tocfunction,"lua_tocfunction");
    IA_API(pushboolean,"lua_pushboolean"); IA_API(pushinteger,"lua_pushinteger"); IA_API(pushnumber,"lua_pushnumber");
    IA_API(pushstring,"lua_pushlstring"); IA_API(pushvalue,"lua_pushvalue"); IA_API(pushclosure,"lua_pushcclosure");
    IA_API(createtable,"lua_createtable"); IA_API(newuserdata,"lua_newuserdata"); IA_API(testuserdata,"luaL_testudata");
    IA_API(newmetatable,"luaL_newmetatable"); IA_API(setmetatable,"lua_setmetatable");
    IA_API(getfield,"lua_getfield");IA_API(gettable,"lua_gettable");IA_API(settable,"lua_settable");
    IA_API(getglobal,"lua_getglobal"); IA_API(setglobal,"lua_setglobal"); IA_API(setfield,"lua_setfield");
    IA_API(reference,"luaL_ref"); IA_API(unreference,"luaL_unref"); IA_API(rawgeti,"lua_rawgeti");
    IA_API(rawset,"lua_rawset");
    IA_API(rawseti,"lua_rawseti"); IA_API(next,"lua_next");
    IA_API(loadbuffer,"luaL_loadbufferx"); IA_API(pcall,"lua_pcallk"); IA_API(error,"lua_error");
#undef IA_API
    auto marker=GetProcAddress(module,"ia_trace_enable");
    if(marker){
#define IA_TRACE(field,symbol) api.trace.field=reinterpret_cast<decltype(api.trace.field)>(GetProcAddress(module,symbol));if(!api.trace.field)throw std::runtime_error("Incomplete research trace ABI: " symbol)
        IA_TRACE(enable,"ia_trace_enable");IA_TRACE(reset,"ia_trace_reset");IA_TRACE(allow,"ia_trace_allow");IA_TRACE(module,"ia_trace_module");
        IA_TRACE(source,"ia_trace_source");IA_TRACE(origin,"ia_trace_getorigin");IA_TRACE(mark,"ia_trace_setorigin");
        IA_TRACE(origins,"ia_trace_origins");IA_TRACE(context,"ia_trace_context");IA_TRACE(status,"ia_trace_status");
#undef IA_TRACE
    }
    if(GetProcAddress(module,"ia_slice_abi")){
#define IA_SLICE(field,symbol) api.slice.field=reinterpret_cast<decltype(api.slice.field)>(GetProcAddress(module,symbol));if(!api.slice.field)throw std::runtime_error("Incomplete slice ABI: " symbol)
        IA_SLICE(abi,"ia_slice_abi");IA_SLICE(graph,"ia_slice_graph");IA_SLICE(value,"ia_slice_value");IA_SLICE(pending,"ia_slice_pending");
        IA_SLICE(push,"ia_slice_push");IA_SLICE(source,"ia_slice_source");IA_SLICE(resolve,"ia_slice_resolve");IA_SLICE(bind,"ia_slice_bind");IA_SLICE(uses,"ia_slice_uses");
        IA_SLICE(shape,"ia_slice_shape");IA_SLICE(apply,"ia_slice_apply");
        if(std::string(api.slice.abi())=="ia-lua533-slice-2"||std::string(api.slice.abi())=="ia-lua533-slice-3"||(std::string(api.slice.abi())=="ia-lua533-slice3-ui-1"||(std::string(api.slice.abi())=="ia-lua533-slice3-ui-bounded-1"||std::string(api.slice.abi())=="ia-lua533-slice3-ui-incremental-1"))){
            IA_SLICE(function,"ia_slice_function");IA_SLICE(schedule,"ia_slice_schedule");IA_SLICE(branches,"ia_slice_branches");IA_SLICE(finish,"ia_slice_finish");
        }
        if(std::string(api.slice.abi())=="ia-lua533-slice-3"||(std::string(api.slice.abi())=="ia-lua533-slice3-ui-1"||(std::string(api.slice.abi())=="ia-lua533-slice3-ui-bounded-1"||std::string(api.slice.abi())=="ia-lua533-slice3-ui-incremental-1"))){
            IA_SLICE(view_bind,"ia_slice_view_bind");IA_SLICE(view_resolve,"ia_slice_view_resolve");IA_SLICE(purpose,"ia_slice_purpose");
        }
        if((std::string(api.slice.abi())=="ia-lua533-slice3-ui-1"||(std::string(api.slice.abi())=="ia-lua533-slice3-ui-bounded-1"||std::string(api.slice.abi())=="ia-lua533-slice3-ui-incremental-1"))){IA_SLICE(ui_register,"ia_ui_register");}
#undef IA_SLICE
        if(std::string(api.slice.abi())!="ia-lua533-slice-1"&&std::string(api.slice.abi())!="ia-lua533-slice-2"&&std::string(api.slice.abi())!="ia-lua533-slice-3"&&std::string(api.slice.abi())!="ia-lua533-slice3-ui-1"&&std::string(api.slice.abi())!="ia-lua533-slice3-ui-bounded-1"&&std::string(api.slice.abi())!="ia-lua533-slice3-ui-incremental-1")throw std::runtime_error("Unknown slice ABI");
    }
    return api;
}
void BridgeLuaApi::execute(BridgeLuaState* state,const std::string& source,const char* name) const {
    int top=gettop(state); int result=loadbuffer(state,source.data(),source.size(),name,"t");
    if(!result) result=pcall(state,0,0,0,0,nullptr);
    if(result) { auto message=lua_error_text(*this,state);settop(state,top);throw std::runtime_error(message); }
    settop(state,top);
}
thread_local LuaObjectBridge* LuaObjectBridge::active_{};
LuaObjectBridge::LuaObjectBridge(const BridgeLuaApi& api,BridgeLuaState* host,bool runtime_profile):api_(api),host_(host),thread_(GetCurrentThreadId()) {
    static std::atomic<uint64_t> scopes{}; scope_=++scopes;
    const int top=api_.gettop(host_);
    try {
        int status=api_.loadbuffer(host_,dispatcher,sizeof(dispatcher)-1,"@authority-object-dispatch","t");
        if(!status)status=api_.pcall(host_,0,1,0,0,nullptr);
        if(status)throw std::runtime_error(lua_error_text(api_,host_));
        dispatch_ref_=api_.reference(host_,registry);
        shadow_=api_.newstate();if(!shadow_)throw std::runtime_error("Cannot create shadow Lua state");
        api_.openlibs(shadow_);
        api_.newmetatable(shadow_,metatable_);
        for(auto [key,fn]:std::initializer_list<std::pair<const char*,BridgeLuaFunction>>{
            {"__index",index},{"__newindex",newindex},{"__call",call},{"__tostring",describe}}) {
            api_.pushclosure(shadow_,fn,0);api_.setfield(shadow_,-2,key);
        }
        for(auto name:{"add","sub","mul","div","mod","pow","idiv","unm","band","bor","bxor","bnot","shl","shr","len","eq","lt","le"}) {
            api_.pushstring(shadow_,name,strlen(name));api_.pushclosure(shadow_,operation,1);
            auto key=std::string("__")+name;api_.setfield(shadow_,-2,key.c_str());
        }
        api_.pushstring(shadow_,"AuthorityObjectProxy",20);api_.setfield(shadow_,-2,"__metatable");
        api_.settop(shadow_,0); objects_.push_back({});
        if(runtime_profile)api_.execute(shadow_,"__authority_debug={getinfo=debug.getinfo,traceback=debug.traceback,sethook=debug.sethook};__authority_date=os.date","@authority-runtime-debug");
        // A runtime profile additionally replaces require/load/coroutines in its bootstrap.
        api_.execute(shadow_,"io=nil; os=nil; package=nil; debug=nil; dofile=nil; loadfile=nil","@authority-object-profile");
    } catch(...) {
        api_.settop(host_,top);if(shadow_)api_.close(shadow_);if(dispatch_ref_)api_.unreference(host_,registry,dispatch_ref_);throw;
    }
    api_.settop(host_,top);
}
LuaObjectBridge::~LuaObjectBridge() {
    if(shadow_)api_.close(shadow_);
    for(size_t i=1;i<objects_.size();++i)api_.unreference(host_,registry,objects_[i].host_ref);
    if(dispatch_ref_)api_.unreference(host_,registry,dispatch_ref_);
}
Json LuaObjectBridge::encode(BridgeLuaState* state,int index,bool host,bool owned,bool method) {
    const int kind=api_.type(state,index);
    if(kind==nil)return {{"t","nil"}};
    if(kind==boolean)return {{"t","boolean"},{"v",api_.boolean(state,index)!=0}};
    if(kind==number) {
        if(api_.isinteger(state,index))return {{"t","integer"},{"v",api_.integer(state,index,nullptr)}};
        double value=api_.number(state,index,nullptr);if(!std::isfinite(value))throw std::runtime_error("Nonfinite bridge number");
        return {{"t","number"},{"v",value}};
    }
    if(kind==string) {size_t n{};auto bytes=api_.string(state,index,&n);if(n>1024*1024)throw std::runtime_error("Bridge string limit");return {{"t","string"},{"hex",hex(bytes,n)}};}
    if(kind!=table&&kind!=lua_function&&kind!=userdata)throw std::runtime_error("Unsupported bridge value type");
    auto pointer=api_.pointer(state,index);uint64_t id{};
    if(host) {
        auto found=host_ids_.find(pointer);
        if(found!=host_ids_.end()) {id=found->second;objects_[static_cast<size_t>(id)].method|=method&&kind==lua_function;}
        else {
            if(objects_.size()>=2049)throw std::runtime_error("Bridge object limit");
            api_.pushvalue(state,index);int ref=api_.reference(state,registry);
            id=objects_.size();objects_.push_back({ref,0,kind,owned&&kind==userdata,false,method&&kind==lua_function});host_ids_[pointer]=id;
        }
    } else {
        auto found=shadow_ids_.find(pointer);
        if(found==shadow_ids_.end())throw std::runtime_error("Foreign table/function/userdata cannot cross bridge");id=found->second;
    }
    return {{"t","ref"},{"scope",scope_},{"id",id},{"kind",kind_name(objects_[static_cast<size_t>(id)].kind)}};
}
void LuaObjectBridge::decode(BridgeLuaState* state,const Json& value,bool host) {
    auto kind=value.at("t").get<std::string>();
    if(kind=="nil")api_.pushnil(state);
    else if(kind=="boolean")api_.pushboolean(state,value.at("v").get<bool>());
    else if(kind=="integer")api_.pushinteger(state,value.at("v").get<int64_t>());
    else if(kind=="number")api_.pushnumber(state,value.at("v").get<double>());
    else if(kind=="string") {auto text=unhex(value.at("hex"));api_.pushstring(state,text.data(),text.size());}
    else if(kind=="ref") {
        uint64_t id=value.at("id");if(value.at("scope")!=scope_||!id||id>=objects_.size()||value.at("kind")!=kind_name(objects_[static_cast<size_t>(id)].kind))throw std::runtime_error("Invalid scoped object handle");
        if(host)api_.rawgeti(state,registry,objects_[static_cast<size_t>(id)].host_ref);else push_proxy(id);
    } else throw std::runtime_error("Unknown bridge wire type");
}
void LuaObjectBridge::push_proxy(uint64_t id) {
    auto& object=objects_.at(static_cast<size_t>(id));
    if(object.shadow_ref){api_.rawgeti(shadow_,registry,object.shadow_ref);return;}
    if(object.kind==lua_function) {
        api_.pushinteger(shadow_,static_cast<int64_t>(id));api_.pushclosure(shadow_,function,1);
    } else {
        // Namespace tables keep local overlays; userdata stores only a scoped handle, never its native payload.
        if(object.kind==table)api_.createtable(shadow_,0,0);
        else {auto proxy=static_cast<Proxy*>(api_.newuserdata(shadow_,sizeof(Proxy)));*proxy={scope_,id};}
        api_.newmetatable(shadow_,metatable_);api_.setmetatable(shadow_,-2);
    }
    auto shadow_pointer=api_.pointer(shadow_,-1);shadow_ids_[shadow_pointer]=id;
    api_.pushvalue(shadow_,-1);object.shadow_ref=api_.reference(shadow_,registry);
}
uint64_t LuaObjectBridge::proxy_id(BridgeLuaState* state,int index) {
    auto value=encode(state,index,false);if(value.at("t")!="ref")throw std::runtime_error("Expected bridge object");return value.at("id");
}
void LuaObjectBridge::expose(const char* name,bool constructor) {
    if(thread_!=GetCurrentThreadId())throw std::runtime_error("Bridge thread mismatch");
    const int top=api_.gettop(host_);
    try {
        api_.getglobal(host_,name);if(api_.type(host_,-1)==nil)throw std::runtime_error(std::string("Missing host root: ")+name);
        auto value=encode(host_,-1,true);if(value.at("t")!="ref")throw std::runtime_error("Constructor root must be a function/table");
        auto& root=objects_[value.at("id").get<size_t>()];root.factory=constructor;root.label=name;decode(shadow_,value,false);api_.setglobal(shadow_,name);
    }
    catch(...){api_.settop(host_,top);throw;}api_.settop(host_,top);
}
void LuaObjectBridge::expose_readonly_getter(const char* alias,const char* root,const char* member,const char* result_type) {
    if(thread_!=GetCurrentThreadId()||active_)throw std::runtime_error("Read API installation outside bridge thread");
    auto identifier=[](const char* name){std::string s=name;return !s.empty()&&s.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")==std::string::npos&&!(s[0]>='0'&&s[0]<='9');};
    if(!identifier(alias)||!identifier(root)||!identifier(member)||!*result_type)throw std::runtime_error("Invalid read API selector");
    int top=api_.gettop(host_);
    try {
        auto code=std::string("return ")+root+"."+member;
        int status=api_.loadbuffer(host_,code.data(),code.size(),"@authority-select-read-api","t");
        if(!status)status=api_.pcall(host_,0,1,0,0,nullptr);
        if(status)throw std::runtime_error(lua_error_text(api_,host_));
        if(api_.type(host_,-1)!=lua_function)throw std::runtime_error("Missing read API function");
        if(!main_native_binding(api_,host_,-1))throw std::runtime_error("Read API requires a main executable native C binding");
        if(host_ids_.contains(api_.pointer(host_,-1)))throw std::runtime_error("Read API function capability alias refused");
        auto encoded=encode(host_,-1,true);auto& object=objects_.at(encoded.at("id").get<size_t>());
        object.readonly_call=true;object.label=std::string(root)+"."+member;object.result_label=result_type;
        decode(shadow_,encoded,false);api_.setglobal(shadow_,alias);
    }catch(...){api_.settop(host_,top);throw;}api_.settop(host_,top);
}
void LuaObjectBridge::allow_readonly_method(const std::string& receiver_type,const std::string& member,const std::string& result_type) {
    if(thread_!=GetCurrentThreadId()||active_)throw std::runtime_error("Read method installation outside bridge thread");
    if(receiver_type.empty()||member.empty())throw std::runtime_error("Invalid read method declaration");
    if(!readonly_methods_.emplace(receiver_type+"."+member,result_type).second)throw std::runtime_error("Duplicate read method declaration");
}
Json LuaObjectBridge::encode_method(int index,uint64_t receiver,const std::string& member) {
    const auto label=objects_.at(static_cast<size_t>(receiver)).label;
    const bool owned=objects_.at(static_cast<size_t>(receiver)).owned;
    // A C function may be shared by unrelated fields or classes. Bind capability
    // to the receiver and field, rather than upgrading a function pointer globally.
    const auto key=std::to_string(receiver)+":"+member;
    uint64_t id{};auto found=method_ids_.find(key);
    if(found!=method_ids_.end()) {
        id=found->second;api_.rawgeti(host_,registry,objects_.at(static_cast<size_t>(id)).host_ref);
        bool same=api_.pointer(host_,-1)==api_.pointer(host_,index);api_.settop(host_,api_.gettop(host_)-1);
        if(!same)throw std::runtime_error("Native method changed after capability binding");
    }else {
        if(objects_.size()>=2049)throw std::runtime_error("Bridge object limit");
        api_.pushvalue(host_,index);int ref=api_.reference(host_,registry);id=objects_.size();
        Object method{ref,0,lua_function,false,false,true,label+"."+member};method.receiver_label=label;
        auto allowed=readonly_methods_.find(method.label);
        if(!owned&&allowed!=readonly_methods_.end()){
            if(!main_native_binding(api_,host_,index)) {api_.unreference(host_,registry,ref);throw std::runtime_error("Read method requires a main executable native C binding");}
            method.readonly_call=true;method.result_label=allowed->second;
        }
        objects_.push_back(std::move(method));method_ids_.emplace(key,id);
    }
    return {{"t","ref"},{"scope",scope_},{"id",id},{"kind","function"}};
}
int LuaObjectBridge::perform(const char* op,const Json& target,int first) {
    if(thread_!=GetCurrentThreadId())throw std::runtime_error("Bridge thread mismatch");
    if(++calls_>8192)throw std::runtime_error("Bridge call limit");
    int top=api_.gettop(host_);int count=api_.gettop(shadow_)-first+1;if(count>64)throw std::runtime_error("Bridge argument limit");
    if(!api_.checkstack(host_,count+16))throw std::runtime_error("Host Lua stack reservation failed");
    try {
        std::vector<Json> args;for(int i=first;i<=api_.gettop(shadow_);++i)args.push_back(encode(shadow_,i,false));
        const Object* object=target.at("t")=="ref"?&objects_.at(target.at("id").get<size_t>()):nullptr;
        const bool factory=object&&object->factory;
        const bool method=object&&object->method;
        const bool owner=object&&object->owned;
        const int object_kind=object?object->kind:nil;
        const std::string label=object?object->label:"scalar";
        const bool readonly_call=object&&object->readonly_call;
        const std::string receiver_label=object?object->receiver_label:"";
        const std::string result_label=object?object->result_label:"";
        if(policy_)policy_(label,op,args);
        if(!strcmp(op,"set")&&!owner)throw std::runtime_error("Borrowed host objects are read-only");
        if(!strcmp(op,"call")&&!factory) {
            if(readonly_call&&!method) {if(!args.empty())throw std::runtime_error("Read getter takes no arguments");}
            else {
                if(!method||args.empty()||args[0].at("t")!="ref")throw std::runtime_error("Native methods require an owned object receiver");
                const auto& receiver=objects_.at(args[0].at("id").get<size_t>());
                if(!receiver.owned&&!readonly_call)throw std::runtime_error("Native methods require an owned object receiver");
                if(receiver.label!=receiver_label)throw std::runtime_error("Native method receiver capability mismatch");
            }
        }
        api_.rawgeti(host_,registry,dispatch_ref_);api_.pushstring(host_,op,strlen(op));
        if(prepare_call_)prepare_call_(label,op,args);
        decode(host_,target,true);
        for(const auto& value:args)decode(host_,value,true);
        int status=api_.pcall(host_,count+2,-1,0,0,nullptr);if(status)throw std::runtime_error(lua_error_text(api_,host_));
        const bool value_result=(!strcmp(op,"call")&&factory)||(strcmp(op,"get")&&strcmp(op,"set")&&strcmp(op,"call"));
        std::vector<Json> results;
        for(int i=top+1;i<=api_.gettop(host_);++i) {
            const bool member_function=!strcmp(op,"get")&&object_kind==userdata&&api_.type(host_,i)==lua_function&&!args.empty()&&args[0].at("t")=="string";
            auto value=member_function?encode_method(i,target.at("id"),unhex(args[0].at("hex"))):encode(host_,i,true,value_result);
            if(value.at("t")=="ref") {
                auto& result=objects_.at(value.at("id").get<size_t>());
                if(!strcmp(op,"call")&&readonly_call&&result.kind==userdata) {
                    if(result_label.empty())throw std::runtime_error("Read API returned undeclared object type");
                    if(result.owned||(!result.label.empty()&&result.label!=result_label))throw std::runtime_error("Read API object capability alias refused");
                    result.label=result_label;
                }
                if(result.label.empty()) {
                    result.label=label;
                    if(!strcmp(op,"get")&&!args.empty()&&args[0].at("t")=="string")result.label+="."+unhex(args[0].at("hex"));
                }
            }
            results.push_back(std::move(value));
        }
        if(results.size()>64||!api_.checkstack(shadow_,static_cast<int>(results.size())+16))throw std::runtime_error("Bridge result stack/arity limit");
        if(completed_call_)completed_call_(label,op,args,results);
        api_.settop(host_,top);for(const auto& value:results)decode(shadow_,value,false);return static_cast<int>(results.size());
    } catch(...){api_.settop(host_,top);throw;}
}
int LuaObjectBridge::callback(BridgeLuaState* state,const char* op,bool is_function) {
    auto self=active_;if(!self)return 0;
    if(self->shadow_!=state) {
        self->failure_="Coroutine bridge calls are unsupported";
        self->api_.pushstring(state,self->failure_.data(),self->failure_.size());return self->api_.error(state);
    }
    int result{};bool failed{};
    {
        try {
            Json target;
            if(is_function) {
                auto id=static_cast<uint64_t>(self->api_.integer(state,registry-1,nullptr));
                target={{"t","ref"},{"scope",self->scope_},{"id",id},{"kind",kind_name(self->objects_.at(static_cast<size_t>(id)).kind)}};
            } else target=self->encode(state,1,false);
            result=self->perform(op,target,is_function?1:2);
        } catch(const std::exception& error){self->failure_=error.what();failed=true;}
    }
    // lua_error may longjmp; every automatic C++ object above has already been destroyed.
    if(failed){self->api_.pushstring(state,self->failure_.data(),self->failure_.size());return self->api_.error(state);}return result;
}
int __cdecl LuaObjectBridge::index(BridgeLuaState* state){return callback(state,"get");}
int __cdecl LuaObjectBridge::newindex(BridgeLuaState* state){
    auto self=active_;
    if(self&&self->shadow_==state&&self->api_.type(state,1)==table) {
        self->api_.pushvalue(state,2);self->api_.pushvalue(state,3);self->api_.rawset(state,1);return 0;
    }
    return callback(state,"set");
}
int __cdecl LuaObjectBridge::call(BridgeLuaState* state){return callback(state,"call");}
int __cdecl LuaObjectBridge::function(BridgeLuaState* state){return callback(state,"call",true);}
int __cdecl LuaObjectBridge::operation(BridgeLuaState* state) {
    auto self=active_;if(!self)return 0;
    const char* op=self->api_.string(state,registry-1,nullptr);
    return callback(state,op);
}
int __cdecl LuaObjectBridge::describe(BridgeLuaState* state) {
    auto self=active_;if(!self)return 0;
    if(self->shadow_!=state)return callback(state,"describe");
    // Do not leak the host's pointer-form tostring. This diagnostic representation is intentionally different.
    const char text[]="AuthorityObjectProxy";self->api_.pushstring(state,text,sizeof(text)-1);return 1;
}
Json LuaObjectBridge::run(const std::string& source,const char* name) {
    if(active_)throw std::runtime_error("Nested bridge execution unsupported");
    if(thread_!=GetCurrentThreadId())throw std::runtime_error("Bridge thread mismatch");
    active_=this;failure_.clear();int top=api_.gettop(shadow_);
    try {
        int status=api_.loadbuffer(shadow_,source.data(),source.size(),name,"t");if(!status)status=api_.pcall(shadow_,0,-1,0,0,nullptr);
        if(status)throw std::runtime_error(lua_error_text(api_,shadow_));
        if(!failure_.empty())throw std::runtime_error(failure_); // Sticky failure even when Lua pcall catches it.
        Json results=Json::array();for(int i=top+1;i<=api_.gettop(shadow_);++i)results.push_back(encode(shadow_,i,false));
        api_.settop(shadow_,top);active_=nullptr;return results;
    } catch(...){api_.settop(shadow_,top);active_=nullptr;throw;}
}
Json LuaObjectBridge::statistics() const {return {{"calls",calls_},{"objects",objects_.size()-1},{"native_userdata_copied",false},{"native_class_fields_replaced",false},{"world_isolation",false}};}
Json LuaObjectBridge::read_data(BridgeLuaState* state,int index,unsigned depth) {
    if(depth>24)throw std::runtime_error("Service data depth/cycle limit");
    if(++data_nodes_>16384)throw std::runtime_error("Service aggregate data limit");
    if(!api_.checkstack(state,8))throw std::runtime_error("Service input stack reservation failed");
    if(index<0)index=api_.gettop(state)+index+1;
    if(api_.slice.pending){auto pending=Json::parse(api_.slice.pending(state,index));if(!pending.is_null())return {{"__ia_deferred",pending.at("expression")}};}
    switch(api_.type(state,index)) {
    case nil:return nullptr;
    case boolean:return api_.boolean(state,index)!=0;
    case number: {
        if(api_.isinteger(state,index))return api_.integer(state,index,nullptr);
        double value=api_.number(state,index,nullptr);if(!std::isfinite(value))throw std::runtime_error("Nonfinite service data");return value;
    }
    case string: {size_t n{};auto text=api_.string(state,index,&n);data_bytes_+=n;if(n>1024*1024||data_bytes_>4*1024*1024)throw std::runtime_error("Service string limit");return std::string(text,n);}
    case table: {
        if(shadow_ids_.contains(api_.pointer(state,index)))throw std::runtime_error("Native proxy cannot become service data");
        Json fields=Json::object();std::map<int64_t,Json> sequence;size_t entries{};
        api_.pushnil(state);
        while(api_.next(state,index)) {
            if(++entries>8192)throw std::runtime_error("Service table limit");
            auto value=read_data(state,-1,depth+1);
            if(api_.type(state,-2)==string) {size_t n{};auto key=api_.string(state,-2,&n);data_bytes_+=n;if(data_bytes_>4*1024*1024)throw std::runtime_error("Service key size limit");fields[std::string(key,n)]=std::move(value);}
            else if(api_.type(state,-2)==number&&api_.isinteger(state,-2)) {auto key=api_.integer(state,-2,nullptr);sequence[key]=std::move(value);}
            else throw std::runtime_error("Service table key type");
            api_.settop(state,api_.gettop(state)-1);
        }
        if(sequence.empty())return fields;
        if(!fields.empty())throw std::runtime_error("Mixed service table keys");
        Json array=Json::array();int64_t expected=1;
        for(auto& [key,value]:sequence){if(key!=expected++)throw std::runtime_error("Sparse service array");array.push_back(std::move(value));}return array;
    }
    default:throw std::runtime_error("Functions/userdata/threads cannot become service data");
    }
}
void LuaObjectBridge::push_data(BridgeLuaState* state,const Json& data,unsigned depth) {
    if(depth>24)throw std::runtime_error("Service result depth limit");
    if(++data_nodes_>16384)throw std::runtime_error("Service result aggregate limit");
    if(!api_.checkstack(state,8))throw std::runtime_error("Service result stack reservation failed");
    if(deferred_response_&&api_.slice.push&&data.is_object()&&data.size()==1&&data.contains("__ia_new_deferred")){auto detail=data.at("__ia_new_deferred").dump();api_.slice.push(state,detail.c_str());}
    else if(data.is_null())api_.pushnil(state);
    else if(data.is_boolean())api_.pushboolean(state,data.get<bool>());
    else if(data.is_number_unsigned()) {auto value=data.get<uint64_t>();if(value>INT64_MAX)throw std::runtime_error("Service unsigned overflow");api_.pushinteger(state,static_cast<int64_t>(value));}
    else if(data.is_number_integer())api_.pushinteger(state,data.get<int64_t>());
    else if(data.is_number_float()) {auto value=data.get<double>();if(!std::isfinite(value))throw std::runtime_error("Nonfinite service result");api_.pushnumber(state,value);}
    else if(data.is_string()) {auto& value=data.get_ref<const std::string&>();data_bytes_+=value.size();if(value.size()>1024*1024||data_bytes_>4*1024*1024)throw std::runtime_error("Service result string limit");api_.pushstring(state,value.data(),value.size());}
    else if(data.is_array()||data.is_object()) {
        if(data.size()>8192)throw std::runtime_error("Service result table limit");
        api_.createtable(state,0,0);int index=api_.gettop(state);
        if(data.is_array()) {int64_t key=1;for(const auto& value:data){push_data(state,value,depth+1);api_.rawseti(state,index,key++);}}
        else for(auto it=data.begin();it!=data.end();++it){data_bytes_+=it.key().size();if(data_bytes_>4*1024*1024)throw std::runtime_error("Service result key size limit");api_.pushstring(state,it.key().data(),it.key().size());push_data(state,it.value(),depth+1);api_.rawset(state,index);}
    }else throw std::runtime_error("Unsupported service result");
}
void LuaObjectBridge::install_service(std::function<Json(const std::string&,const Json&)> service) {
    if(thread_!=GetCurrentThreadId()||active_)throw std::runtime_error("Service installation outside bridge thread");
    service_=std::move(service);api_.pushclosure(shadow_,LuaObjectBridge::service,0);api_.setglobal(shadow_,"__authority_service");
    if(api_.trace.allow)api_.trace.allow(shadow_,LuaObjectBridge::service,"authority.model_service");
}
void LuaObjectBridge::label_service_result(const std::string& label){
    if(!api_.trace.enable)return;
    service_origins_.push_back(api_.trace.source(shadow_,label.c_str()));
}
Json LuaObjectBridge::trace_argument_origins(int index) const{
    if(!api_.trace.enable)return Json::array();
    return Json::parse(api_.trace.origins(shadow_,api_.trace.origin(shadow_,index)));
}
int __cdecl LuaObjectBridge::service(BridgeLuaState* state) {
    auto self=active_;if(!self)return 0;bool failed{};int results{};
    {
        try {
            if(state!=self->shadow_)throw std::runtime_error("Coroutine service calls are unsupported");
            if(!self->service_||self->api_.type(state,1)!=string)throw std::runtime_error("Invalid bridge service");
            if(self->api_.gettop(state)>65)throw std::runtime_error("Service argument limit");
            self->data_nodes_=self->data_bytes_=0;
            self->service_origins_.clear();
            self->service_shape_=nullptr;
            auto op=self->read_data(state,1).get<std::string>();Json args=Json::array();
            for(int i=2;i<=self->api_.gettop(state);++i){
                if(op=="callback"&&i==6&&self->api_.slice.function)args.push_back(Json::parse(self->api_.slice.function(state,i)));
                else args.push_back(self->read_data(state,i));
            }
            auto response=self->service_(op,args);if(!response.is_array()||response.size()>64)throw std::runtime_error("Service result arity limit");
            self->deferred_response_=op=="world";
            self->data_nodes_=self->data_bytes_=0;
            for(const auto& value:response){self->push_data(state,value);for(auto origin:self->service_origins_)self->api_.trace.mark(state,-1,origin);if(!self->service_shape_.is_null()){auto shape=self->service_shape_.dump();self->api_.slice.apply(state,-1,shape.c_str());}}results=static_cast<int>(response.size());self->deferred_response_=false;
        }catch(const std::exception& error){self->failure_=error.what();failed=true;}
    }
    if(failed){self->api_.pushstring(state,self->failure_.data(),self->failure_.size());return self->api_.error(state);}return results;
}
Json probe_game_objects(const BridgeLuaApi& api,BridgeLuaState* host,const std::filesystem::path& game_root) {
    Json report={{"native_game_used",true},{"playable",false},{"generic_mod_compatibility_passed",false},{"probe_passed",false},{"checks",Json::object()}};
    LuaObjectBridge bridge(api,host);
    try {
    report["stage"]="expose_owned_object_roots";
    for(auto name:{"BitSet128","Vector","Color","KColor","Font","Sprite"})bridge.expose(name);
    for(auto name:{"ItemConfig","RoomDescriptor"})bridge.expose(name,false);
    std::ifstream source(game_root/L"resources/scripts/enums.lua",std::ios::binary);
    if(!source)throw std::runtime_error("Missing local enums.lua");std::string enums((std::istreambuf_iterator<char>(source)),{});
    report["stage"]="unchanged_game_enums";
    bridge.run(enums,"@authority-unchanged-j460-enums");report["checks"]["unchanged_game_enums_loaded"]=true;
    bridge.run("assert(type(ItemConfig)=='table');rawset(ItemConfig,'__authority_context','shadow');assert(ItemConfig.__authority_context=='shadow')");
    api.execute(host,"assert(rawget(ItemConfig,'__authority_context')==nil)","@authority-namespace-check");
    report["checks"]["private_class_namespace_overlay"]=true;
    report["stage"]="native_value_objects";
    bridge.run(R"LUA(
      local a,b=BitSet128(1,2),BitSet128(4,8)
      local union=a|b;assert(type(a)=='userdata' and union.l==5 and union.h==10)
      assert((a&b).l==0 and (~a).l==~1)
      local v=Vector(3,4);assert(v.X==3 and v.Y==4 and v:Length()==5)
      v.X=6;assert(v.X==6 and (v+Vector(1,2)).Y==6)
      local c=Color(0.25,0.5,0.75,1);assert(c.R==0.25 and c.G==0.5)
      local k=KColor(0.25,0.5,0.75,1);assert(k.Red==0.25 and k.Alpha==1)
      local f,s=Font(),Sprite();assert(type(f)=='userdata' and type(s)=='userdata')
      local cached=v.Length;assert(math.abs(cached(v)-math.sqrt(52))<0.00001)
      return true
    )LUA");
    report["checks"]["native_value_objects_and_cached_methods"]=true;
    report["stage"]="personal_native_contexts";
    bridge.run("personalVector=Vector(1,2);personalVector.X=11;privateUI='zh';Vector.personalX=24");
    {
        LuaObjectBridge second(api,host);
        for(auto name:{"BitSet128","Vector","Color","KColor","Font","Sprite"})second.expose(name);
        for(auto name:{"ItemConfig","RoomDescriptor"})second.expose(name,false);
        second.run(enums,"@authority-second-unchanged-j460-enums");
        second.run("personalVector=Vector(1,2);personalVector.X=22;privateUI='en';Vector.personalX=124;assert(personalVector.X==22)");
        report["second_context_bridge"]=second.statistics();
    }
    bridge.run("assert(personalVector.X==11 and privateUI=='zh' and Vector.personalX==24)");
    api.execute(host,"assert(rawget(Vector,'personalX')==nil and rawget(_G,'personalVector')==nil and rawget(_G,'privateUI')==nil)","@authority-canonical-context-check");
    report["checks"]["two_private_native_contexts"]=true;
    const auto font=game_root/L"mods/external item descriptions_836319872/resources/font/eid_default.fnt";
    if(std::filesystem::is_regular_file(font)) {
        report["stage"]="native_font_load_and_measure";
        auto quoted=Json(utf8(font.wstring())).dump();
        auto measurements=bridge.run("local f=Font();f:Load("+quoted+");local width=f.GetStringWidth;local n=width(f,'native bridge');assert(n>0);return n");
        report["font_width"]=measurements.at(0).at("v");
        report["checks"]["native_font_load_and_cached_measure"]=true;
        report["font_asset_sha256"]=sha256_file(font);
    } else report["checks"]["native_font_load_and_cached_measure"]="NOT_TESTED_ASSET_ABSENT";
    report["probe_passed"]=true;report["stage"]="complete";
    }catch(const std::exception& error){report["error"]=error.what();}
    report["bridge"]=bridge.statistics();report["scope"]="Menu-safe owned value/UI objects only; no entity, gameplay, mod or save calls.";
    report["game_enums_sha256"]=sha256_file(game_root/L"resources/scripts/enums.lua");return report;
}
}
