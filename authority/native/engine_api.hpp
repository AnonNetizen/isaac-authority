#pragma once
#include "lua_bridge.hpp"
namespace ia {
Json probe_engine_api(const BridgeLuaApi&,BridgeLuaState*,const std::filesystem::path& game,const std::filesystem::path& output);
void expose_item_metadata(LuaObjectBridge&);
}
