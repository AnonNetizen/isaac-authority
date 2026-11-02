#pragma once
#include "lua_bridge.hpp"
#include <map>
#include <memory>
namespace ia {
class ResourceVerificationEnvironment;
// Shared only for this diagnostic/thread. Archive pins outlive individual private contexts.
class ResourceVerificationScope {
    std::shared_ptr<ResourceVerificationEnvironment> previous_,environment_;
public:
    ResourceVerificationScope();
    ~ResourceVerificationScope();
    ResourceVerificationScope(const ResourceVerificationScope&)=delete;
    Json statistics() const;
};
// A frozen candidate catalog, not a claim that arbitrary resources are safe.
// Runtime diagnostics use this only after the matching native preflight passes.
class ResourceCapabilities {
    struct SpriteState {size_t resource{};std::string animation;bool valid{true};std::map<int64_t,size_t> replacements;};
    std::filesystem::path game_;
    Json catalog_;
    std::map<std::wstring,size_t> paths_,aliases_;
    std::map<std::pair<uint64_t,uint64_t>,SpriteState> sprites_;
    std::map<std::pair<uint64_t,uint64_t>,size_t> fonts_;
    std::shared_ptr<ResourceVerificationEnvironment> verification_;
    bool packed_verified_{};
    std::filesystem::path path(const std::string&) const;
    size_t resolve(const std::string&,const char*) const;
    void verify_file(const Json&) const;
    void verify(size_t);
    void verify_packed_environment();
    std::string load_path(size_t) const;
    std::pair<uint64_t,uint64_t> receiver(const std::vector<Json>&) const;
    void animation(size_t,const std::string&,const Json* frame=nullptr) const;
public:
    ResourceCapabilities(const std::filesystem::path& game,Json catalog);
    ~ResourceCapabilities();
    ResourceCapabilities(const ResourceCapabilities&)=delete;
    static Json compiled_catalog();
    void prepare(const std::string& label,const std::string& operation,std::vector<Json>& args);
    void completed(const std::string& label,const std::string& operation,const std::vector<Json>& args,const std::vector<Json>& results);
    Json inventory() const;
};
void install_resource_capabilities(LuaObjectBridge&,const std::filesystem::path& game);
}
