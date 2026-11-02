#pragma once
#include "lua_bridge.hpp"
#include <map>
namespace ia {
// CLI object semantics only. There is no engine or rendering entry point here.
class StandaloneUiBackend {
    struct Handle {uint64_t id;int reference;};
    BridgeLuaApi api_;BridgeLuaState* state_;uint64_t sequence_{};
    std::map<uint64_t,std::string> labels_;
    static thread_local std::map<BridgeLuaState*,StandaloneUiBackend*> active_;
    static int __cdecl make(BridgeLuaState*);
    static int __cdecl get(BridgeLuaState*);
    static int __cdecl set(BridgeLuaState*);
    static int __cdecl operation(BridgeLuaState*);
    static int dispatch(BridgeLuaState*,int);
public:
    StandaloneUiBackend(const BridgeLuaApi&,BridgeLuaState*);
    ~StandaloneUiBackend();
};
class UiResourceScope {
    Json previous_;
public:
    explicit UiResourceScope(Json);
    ~UiResourceScope();
};
Json ui_resource_call(const std::string&,const Json&);
}
