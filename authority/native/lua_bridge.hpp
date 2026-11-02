#pragma once
#include "platform.hpp"
#include <unordered_map>
#include <vector>
#include <functional>
namespace ia {
struct BridgeLuaState;
using BridgeLuaFunction = int (__cdecl*)(BridgeLuaState*);
// Optional exports exist only in the standalone research DLL, never in Game Lua.
struct TraceLuaApi {
    void (__cdecl* enable)(BridgeLuaState*){};
    void (__cdecl* reset)(BridgeLuaState*,int64_t){};
    void (__cdecl* allow)(BridgeLuaState*,BridgeLuaFunction,const char*){};
    void (__cdecl* module)(BridgeLuaState*,const char*){};
    unsigned (__cdecl* source)(BridgeLuaState*,const char*){};
    unsigned (__cdecl* origin)(BridgeLuaState*,int){};
    void (__cdecl* mark)(BridgeLuaState*,int,unsigned){};
    const char* (__cdecl* origins)(BridgeLuaState*,unsigned){};
    const char* (__cdecl* context)(BridgeLuaState*){};
    const char* (__cdecl* status)(BridgeLuaState*){};
};
struct SliceLuaApi {
    void (__cdecl* ui_register)(BridgeLuaState*,int,const char*,uint64_t){};
    const char* (__cdecl* abi)(){};
    const char* (__cdecl* graph)(BridgeLuaState*){};
    unsigned (__cdecl* value)(BridgeLuaState*,int){};
    const char* (__cdecl* pending)(BridgeLuaState*,int){};
    void (__cdecl* push)(BridgeLuaState*,const char*){};
    void (__cdecl* source)(BridgeLuaState*,int,const char*){};
    const char* (__cdecl* resolve)(BridgeLuaState*,unsigned){};
    const char* (__cdecl* bind)(BridgeLuaState*,unsigned,const char*){};
    int (__cdecl* uses)(BridgeLuaState*,unsigned,unsigned){};
    const char* (__cdecl* shape)(BridgeLuaState*,int){};
    void (__cdecl* apply)(BridgeLuaState*,int,const char*){};
    const char* (__cdecl* function)(BridgeLuaState*,int){};
    void (__cdecl* schedule)(BridgeLuaState*,const char*){};
    const char* (__cdecl* branches)(BridgeLuaState*){};
    const char* (__cdecl* finish)(BridgeLuaState*){};
    const char* (__cdecl* view_bind)(BridgeLuaState*,unsigned,const char*){};
    const char* (__cdecl* view_resolve)(BridgeLuaState*,unsigned){};
    const char* (__cdecl* purpose)(BridgeLuaState*,const char*){};
};
struct BridgeLuaApi {
    TraceLuaApi trace;
    SliceLuaApi slice;
    BridgeLuaState* (__cdecl* newstate)(){};
    void (__cdecl* openlibs)(BridgeLuaState*){};
    void (__cdecl* close)(BridgeLuaState*){};
    int (__cdecl* gettop)(BridgeLuaState*){};
    int (__cdecl* checkstack)(BridgeLuaState*,int){};
    void (__cdecl* settop)(BridgeLuaState*,int){};
    int (__cdecl* type)(BridgeLuaState*,int){};
    int (__cdecl* isinteger)(BridgeLuaState*,int){};
    int64_t (__cdecl* integer)(BridgeLuaState*,int,int*){};
    double (__cdecl* number)(BridgeLuaState*,int,int*){};
    int (__cdecl* boolean)(BridgeLuaState*,int){};
    const char* (__cdecl* string)(BridgeLuaState*,int,size_t*){};
    const void* (__cdecl* pointer)(BridgeLuaState*,int){};
    BridgeLuaFunction (__cdecl* tocfunction)(BridgeLuaState*,int){};
    void (__cdecl* pushnil)(BridgeLuaState*){};
    void (__cdecl* pushboolean)(BridgeLuaState*,int){};
    void (__cdecl* pushinteger)(BridgeLuaState*,int64_t){};
    void (__cdecl* pushnumber)(BridgeLuaState*,double){};
    const char* (__cdecl* pushstring)(BridgeLuaState*,const char*,size_t){};
    void (__cdecl* pushvalue)(BridgeLuaState*,int){};
    void (__cdecl* pushclosure)(BridgeLuaState*,BridgeLuaFunction,int){};
    void (__cdecl* createtable)(BridgeLuaState*,int,int){};
    void* (__cdecl* newuserdata)(BridgeLuaState*,size_t){};
    void* (__cdecl* testuserdata)(BridgeLuaState*,int,const char*){};
    int (__cdecl* newmetatable)(BridgeLuaState*,const char*){};
    int (__cdecl* setmetatable)(BridgeLuaState*,int){};
    int (__cdecl* getglobal)(BridgeLuaState*,const char*){};
    int (__cdecl* getfield)(BridgeLuaState*,int,const char*){};
    int (__cdecl* gettable)(BridgeLuaState*,int){};
    void (__cdecl* settable)(BridgeLuaState*,int){};
    void (__cdecl* setglobal)(BridgeLuaState*,const char*){};
    void (__cdecl* setfield)(BridgeLuaState*,int,const char*){};
    int (__cdecl* reference)(BridgeLuaState*,int){};
    void (__cdecl* unreference)(BridgeLuaState*,int,int){};
    int (__cdecl* rawgeti)(BridgeLuaState*,int,int64_t){};
    void (__cdecl* rawset)(BridgeLuaState*,int){};
    void (__cdecl* rawseti)(BridgeLuaState*,int,int64_t){};
    int (__cdecl* next)(BridgeLuaState*,int){};
    int (__cdecl* loadbuffer)(BridgeLuaState*,const char*,size_t,const char*,const char*){};
    int (__cdecl* pcall)(BridgeLuaState*,int,int,int,intptr_t,void*){};
    int (__cdecl* error)(BridgeLuaState*){};
    static BridgeLuaApi resolve(HMODULE module);
    void execute(BridgeLuaState*,const std::string&,const char* name) const;
};

// Native objects stay in host's registry. Only scalar data and scoped IDs cross states.
// This bridge is synchronous and thread-bound; it does not isolate world mutations.
class LuaObjectBridge {
    struct Object { int host_ref{},shadow_ref{},kind{}; bool owned{},factory{},method{}; std::string label;
        bool readonly_call{}; std::string receiver_label,result_label; };
    struct Proxy { uint64_t scope{},id{}; };
    BridgeLuaApi api_;
    BridgeLuaState* host_{};
    BridgeLuaState* shadow_{};
    int dispatch_ref_{};
    uint64_t scope_{},calls_{};
    DWORD thread_{};
    std::vector<Object> objects_;
    std::unordered_map<const void*,uint64_t> host_ids_,shadow_ids_;
    std::unordered_map<std::string,uint64_t> method_ids_;
    std::unordered_map<std::string,std::string> readonly_methods_;
    std::string failure_;
    size_t data_nodes_{},data_bytes_{};
    std::function<Json(const std::string&,const Json&)> service_;
    std::vector<unsigned> service_origins_;
    Json service_shape_=nullptr;
    bool deferred_response_{};
    std::function<void(const std::string&,const std::string&,const std::vector<Json>&)> policy_;
    std::function<void(const std::string&,const std::string&,std::vector<Json>&)> prepare_call_;
    std::function<void(const std::string&,const std::string&,const std::vector<Json>&,const std::vector<Json>&)> completed_call_;
    static thread_local LuaObjectBridge* active_;
    static constexpr int registry_=-1001000;
    static constexpr const char* metatable_="IsaacAuthority.ObjectProxy.v1";
    Json encode(BridgeLuaState*,int,bool host,bool owned=false,bool method=false);
    Json encode_method(int index,uint64_t receiver,const std::string& member);
    void decode(BridgeLuaState*,const Json&,bool host);
    void push_proxy(uint64_t);
    int perform(const char*,const Json&,int);
    static int __cdecl index(BridgeLuaState*);
    static int __cdecl newindex(BridgeLuaState*);
    static int __cdecl call(BridgeLuaState*);
    static int __cdecl function(BridgeLuaState*);
    static int __cdecl operation(BridgeLuaState*);
    static int __cdecl describe(BridgeLuaState*);
    static int __cdecl service(BridgeLuaState*);
    Json read_data(BridgeLuaState*,int,unsigned depth=0);
    void push_data(BridgeLuaState*,const Json&,unsigned depth=0);
    static int callback(BridgeLuaState*,const char*,bool function=false);
    uint64_t proxy_id(BridgeLuaState*,int);
public:
    LuaObjectBridge(const BridgeLuaApi&,BridgeLuaState* host,bool runtime_profile=false);
    ~LuaObjectBridge();
    LuaObjectBridge(const LuaObjectBridge&)=delete;
    void expose(const char* name,bool constructor=true);
    // Select one no-argument host getter without exposing its namespace. Results
    // remain borrowed; only explicitly declared read methods may be invoked.
    void expose_readonly_getter(const char* alias,const char* root,const char* member,const char* result_type);
    void allow_readonly_method(const std::string& receiver_type,const std::string& member,const std::string& result_type="");
    // Service values are bounded plain data, never host pointers or proxy userdata.
    void install_service(std::function<Json(const std::string&,const Json&)>);
    void label_service_result(const std::string&);
    Json trace_argument_origins(int index) const;
    void set_service_shape(Json metadata) { service_shape_=std::move(metadata); }
    void set_policy(std::function<void(const std::string&,const std::string&,const std::vector<Json>&)> policy) { policy_=std::move(policy); }
    // Completion runs only after native invocation and result encoding succeed.
    void set_call_adapter(decltype(prepare_call_) prepare,decltype(completed_call_) completed) {
        prepare_call_=std::move(prepare);completed_call_=std::move(completed);
    }
    Json run(const std::string&,const char* name="@authority-object-test");
    Json statistics() const;
    BridgeLuaState* shadow() const { return shadow_; }
};
Json probe_game_objects(const BridgeLuaApi&,BridgeLuaState*,const std::filesystem::path& game_root);
}
