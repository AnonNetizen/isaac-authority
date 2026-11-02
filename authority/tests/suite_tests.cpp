#include "runtime_suite.hpp"
#include <iostream>
int wmain(int argc,wchar_t** argv) {
    using namespace ia;HMODULE module{};BridgeLuaState* host{};BridgeLuaApi api;
    try {
        if(argc!=5)throw std::runtime_error("Usage: authority-suite-tests.exe LUA_DLL GAME_DIR SOURCE_DIR SUITE_JSON");
        if(sha256_file(argv[1])!="fb84afbc5b227b06f71022bb6c0bcc0a39f85e5939b789489906bc128d05a13e")throw std::runtime_error("Unverified Lua runtime");
        auto suite=FrozenRuntimeSuite::load(argv[4],argv[2],argv[3]);
        module=LoadLibraryExW(argv[1],nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        if(!module)throw std::runtime_error("Load pinned Lua failed");api=BridgeLuaApi::resolve(module);host=api.newstate();api.openlibs(host);
        auto report=run_runtime_suite(api,host,suite,false);api.close(host);host=nullptr;FreeLibrary(module);module=nullptr;
        std::cout<<report.dump(2)<<'\n';return report.at("diagnostic_passed").get<bool>()?0:2;
    }catch(const std::exception& error) {
        if(host)api.close(host);if(module)FreeLibrary(module);std::cerr<<error.what()<<'\n';return 1;
    }
}
