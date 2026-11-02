#pragma once
#include "mod_runtime.hpp"
namespace ia {
struct RuntimeSuiteCase { Json definition; std::vector<FrozenMod> mods; };
struct FrozenRuntimeSuite {
    Json manifest;
    std::string digest,bootstrap,enums;
    std::vector<RuntimeSuiteCase> cases;
    static FrozenRuntimeSuite load(const std::filesystem::path& manifest,const std::filesystem::path& game,const std::filesystem::path& research,bool allow_trace=false);
};
Json run_runtime_suite(const BridgeLuaApi&,BridgeLuaState*,const FrozenRuntimeSuite&,bool native_game);
}
