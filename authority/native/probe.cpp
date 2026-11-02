#include "platform.hpp"
#include "state_model.hpp"
#include "steam.hpp"
#include "bootstrap.hpp"
#include "lua_bridge.hpp"
#include "mod_runtime.hpp"
#include "runtime_suite.hpp"
#include "resources.hpp"
#include "engine_api.hpp"
#include <MinHook.h>
#include <array>
#include <atomic>
#include <cstring>
#include <deque>
#include <iomanip>
#include <memory>
#include <sstream>
#include <thread>
#include <vector>
#include <chrono>
#include <cmath>
#include <chrono>

extern "C" {
volatile unsigned long g_call_probe_calls;
volatile unsigned long g_call_probe_ecx_match;
volatile unsigned long g_call_probe_ecx_mismatch;
volatile unsigned long g_call_probe_first_ecx;
volatile unsigned long g_call_probe_last_ecx;
volatile unsigned long g_call_probe_game_ptr;
volatile unsigned long g_call_probe_duplicate_frames;
volatile unsigned long g_call_probe_first_frame;
volatile unsigned long g_call_probe_last_frame;
volatile unsigned long g_call_probe_players_first;
volatile unsigned long g_call_probe_players_last;
void* g_call_probe_original;
void (*g_call_probe_entry)(unsigned long);
}

namespace {
using namespace ia;
struct lua_State;
Json probe_engine_layout(lua_State* L);
Json probe_game_update_call(lua_State* L);
Json probe_game_update_skip(lua_State* L);
Json probe_state_layout(lua_State* L);
uint32_t probe_read_u32(uintptr_t address);
using LuaFunction = int (__cdecl*)(lua_State*);
using LuaContinuation = int (__cdecl*)(lua_State*, int, intptr_t);
using PCall = int (__cdecl*)(lua_State*, int, int, int, intptr_t, LuaContinuation);
struct LuaApi {
    int (__cdecl* gettop)(lua_State*){};
    void (__cdecl* settop)(lua_State*, int){};
    int (__cdecl* getglobal)(lua_State*, const char*){};
    int (__cdecl* getmetatable)(lua_State*, int){};
    int (__cdecl* getfield)(lua_State*, int, const char*){};
    int (__cdecl* toboolean)(lua_State*, int){};
    LuaFunction (__cdecl* tocfunction)(lua_State*, int){};
    void (__cdecl* pushvalue)(lua_State*, int){};
    int (__cdecl* reference)(lua_State*, int){};
    int (__cdecl* rawgeti)(lua_State*, int, int64_t){};
    void (__cdecl* setglobal)(lua_State*, const char*){};
    const char* (__cdecl* tostring)(lua_State*, int, size_t*){};
    const char* (__cdecl* pushstring)(lua_State*, const char*, size_t){};
    void (__cdecl* pushboolean)(lua_State*, int){};
    void (__cdecl* pushclosure)(lua_State*, LuaFunction, int){};
    int (__cdecl* loadbuffer)(lua_State*, const char*, size_t, const char*, const char*){};
    const void* (__cdecl* topointer)(lua_State*, int){};
    void* (__cdecl* touserdata)(lua_State*, int){};
    int (__cdecl* type)(lua_State*, int){};
    double (__cdecl* tonumberx)(lua_State*, int, int*){};
    PCall pcall{};
} lua;
Log log_file;
std::mutex queue_mutex, inbound_mutex;
std::deque<Json> outgoing;
Json incoming;
std::atomic<bool> started{}, stopped{}, disable_lua{}, lua_enabled{};
std::atomic<uint64_t> dropped_observations{};
std::atomic<unsigned> callback_calls{};
std::atomic<bool> world_seen{}, draws_seen{}, lua_seen{}, steam_seen{};
void** pcall_slot{};
PCall original_pcall{};
lua_State* attached_state{};
thread_local bool in_bridge{};
Json config;
HMODULE bridge_lua_module{};
std::atomic<bool> object_probe_attempted{};
bool readiness_logged{};
void install_object_probe(lua_State* L) {
    if(object_probe_attempted||disable_lua||stopped)return;
    const int top=lua.gettop(L);
    constexpr char ready[]="return REPENTANCE_PLUS==true and type(RegisterMod)=='function' and type(TearFlags)=='table' and TearFlags.TEAR_HOMING~=nil and (type(Font)=='function' or type(Font)=='table') and (type(Sprite)=='function' or type(Sprite)=='table')";
    in_bridge=true;
    int status=lua.loadbuffer(L,ready,sizeof(ready)-1,"@authority-object-ready","t");
    if(!status)status=original_pcall(L,0,1,0,0,nullptr);
    bool available=!status&&lua.toboolean(L,-1);lua.settop(L,top);
    if(available&&(config.value("api_probe",false)||config.value("runtime_probe",false))) {
        constexpr char late[]="return ModConfigMenu~=nil and ModConfigMenu.Skin~=nil and type(ModConfigMenu.Skin.AddFont)=='function' and ModConfigMenu.StandaloneSaveLoaded==true and EID~=nil and type(EID.OnGameExit)=='function' and EID.font~=nil and EID.itemConfig~=nil";
        status=lua.loadbuffer(L,late,sizeof(late)-1,"@authority-canonical-mods-ready","t");
        if(!status)status=original_pcall(L,0,1,0,0,nullptr);
        available=!status&&lua.toboolean(L,-1);lua.settop(L,top);
        if(!readiness_logged||available){log_file.write("diagnostic_readiness",{{"sdk_ready",true},{"canonical_mod_markers_ready",available},{"game_thread",true}});readiness_logged=true;}
    }
    if(!available){in_bridge=false;return;}
    if(object_probe_attempted.exchange(true)){in_bridge=false;return;}
    Json result;
    try {
        wchar_t module_path[MAX_PATH]{};GetModuleFileNameW(bridge_lua_module,module_path,MAX_PATH);
        if(sha256_file(module_path)!="fb84afbc5b227b06f71022bb6c0bcc0a39f85e5939b789489906bc128d05a13e")throw std::runtime_error("Unverified Lua runtime; object bridge refused");
        wchar_t game[MAX_PATH]{};GetModuleFileNameW(nullptr,game,MAX_PATH);
        auto api=BridgeLuaApi::resolve(bridge_lua_module);
        if(config.value("call_probe",false))result=probe_game_update_call(L);
        else if(config.value("skip_probe",false))result=probe_game_update_skip(L);
        else if(config.value("state_probe",false))result=probe_state_layout(L);
        else if(config.value("layout_probe",false))result=probe_engine_layout(L);
        else if(config.value("api_probe",false))result=probe_engine_api(api,reinterpret_cast<BridgeLuaState*>(L),std::filesystem::path(game).parent_path(),std::filesystem::path(wide(config.at("output").get<std::string>())));
        else if(config.value("runtime_probe",false)) {
            ResourceVerificationScope resources;
            std::unique_ptr<FrozenRuntimeSuite> suite;
            if(config.contains("runtime_suite")) {
                suite=std::make_unique<FrozenRuntimeSuite>(FrozenRuntimeSuite::load(wide(config.at("runtime_suite").get<std::string>()),std::filesystem::path(game).parent_path(),wide(config.at("runtime_source").get<std::string>())));
                if(suite->digest!=config.at("runtime_suite_sha256").get<std::string>())throw std::runtime_error("Runtime suite changed since launcher validation");
            }
            auto preflight=probe_engine_api(api,reinterpret_cast<BridgeLuaState*>(L),std::filesystem::path(game).parent_path(),std::filesystem::path(wide(config.at("output").get<std::string>())));
            if(preflight.value("probe_passed",false))result=probe_mod_runtime(api,reinterpret_cast<BridgeLuaState*>(L),std::filesystem::path(game).parent_path(),std::filesystem::path(wide(config.at("runtime_source").get<std::string>())));
            else result={{"fixture_probe_passed",false},{"playable",false},{"error","Engine API preflight failed; mod runtime not executed"}};
            result["engine_api_preflight"]=std::move(preflight);
            if(suite&&result["engine_api_preflight"].value("probe_passed",false)) {
                result["runtime_suite"]=run_runtime_suite(api,reinterpret_cast<BridgeLuaState*>(L),*suite,true);
                result["runtime_suite"]["shared_resource_preflight_count"]=1;
            }
            result["shared_resource_validation"]=resources.statistics();
        }
        else result=probe_game_objects(api,reinterpret_cast<BridgeLuaState*>(L),std::filesystem::path(game).parent_path());
    }catch(const std::exception& error){result={{"probe_passed",false},{"error",error.what()},{"native_game_used",true},{"playable",false}};}
    result["host_lua_stack_restored"]=lua.gettop(L)==top;
    lua.settop(L,top);in_bridge=false;
    if(config.value("state_probe",false) && !result.value("probe_passed",false) && result.value("reason","")=="not_in_run") {
        log_file.write("state_probe_not_in_run", result);
        object_probe_attempted=false; // Retry on a later Lua callback once a run is active.
        return;
    }
    if(config.value("call_probe",false)) {
        log_file.write("call_probe_installed", result);
        disable_lua=true; // Stop further Lua probing; the worker thread ends the timed call probe.
        return;
    }
    if(config.value("skip_probe",false)) {
        log_file.write("skip_probe_installed", result);
        disable_lua=true; // Skip probe is driven by its own worker thread.
        return;
    }
    const auto report_name=config.value("state_probe",false)?"state-probe.json":config.value("layout_probe",false)?"engine-layout.json":config.value("api_probe",false)?"engine-api.json":config.value("runtime_probe",false)?"mod-runtime.json":"object-bridge.json";
    std::ofstream(std::filesystem::path(wide(config.at("output").get<std::string>()))/report_name)<<result.dump(2);
    log_file.write(config.value("state_probe",false)?"state_layout_probe":config.value("layout_probe",false)?"engine_layout_probe":config.value("api_probe",false)?"engine_api_probe":config.value("runtime_probe",false)?"mod_runtime_probe":"object_bridge_probe",result);
    // No resident Lua callbacks or binding hooks; worker restores its IAT slot after this diagnostic.
    disable_lua=true;stopped=true;
}
constexpr int registry = -1001000; // Lua 5.3 public LUA_REGISTRYINDEX, not an engine offset.
struct Binding { void* target{}; LuaFunction original{}; lua_State* state{}; int callback{}; };
std::array<Binding, 16> bindings{};
std::atomic<unsigned> binding_count{}, native_calls{}, capture_errors{};
std::atomic<uint64_t> capture_us{}, capture_max_us{};
bool minhook_initialized{};
template<size_t I> int __cdecl observe_binding(lua_State* L) {
    // Lua may longjmp from the original function; keep this boundary free of C++ destructors.
    auto& binding = bindings[I];
    if (!disable_lua && !stopped && L == binding.state) {
        const int top = lua.gettop(L);
        const auto begin = std::chrono::steady_clock::now();
        lua.rawgeti(L, registry, binding.callback);
        for (int i = 1; i <= top; ++i) lua.pushvalue(L, i);
        const int result = original_pcall(L, top, 0, 0, 0, nullptr);
        lua.settop(L, top);
        const auto elapsed = static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - begin).count());
        capture_us += elapsed;
        auto maximum = capture_max_us.load();
        while (elapsed > maximum && !capture_max_us.compare_exchange_weak(maximum, elapsed)) {}
        ++native_calls; if (result) ++capture_errors;
    }
    return binding.original(L);
}
constexpr std::array<LuaFunction, 16> binding_detours{
    observe_binding<0>, observe_binding<1>, observe_binding<2>, observe_binding<3>,
    observe_binding<4>, observe_binding<5>, observe_binding<6>, observe_binding<7>,
    observe_binding<8>, observe_binding<9>, observe_binding<10>, observe_binding<11>,
    observe_binding<12>, observe_binding<13>, observe_binding<14>, observe_binding<15>};

int __cdecl watch_native(lua_State* L) {
    const int top = lua.gettop(L);
    // Called with (object, methodName, observerCallback); raw native class fields stay untouched.
    size_t length{}; const char* method = lua.tostring(L, 2, &length);
    bool ok = false;
    if (method && length <= 128 && minhook_initialized && binding_count < bindings.size()) {
        lua.getfield(L, 1, method);
        auto function = lua.tocfunction(L, -1);
        if (!function) {
            lua.settop(L, top);
            if (lua.getmetatable(L, 1)) {
                lua.getfield(L, -1, method); function = lua.tocfunction(L, -1);
            }
        }
        lua.settop(L, top);
        MEMORY_BASIC_INFORMATION memory{};
        const auto target = reinterpret_cast<void*>(function);
        // Accept only an actual C binding in this pinned main executable, never guessed addresses.
        if (target && VirtualQuery(target, &memory, sizeof(memory)) && memory.AllocationBase == GetModuleHandleW(nullptr)
            && (memory.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
            bool duplicate{};
            for (unsigned i = 0; i < binding_count; ++i) duplicate |= bindings[i].target == target;
            if (!duplicate) {
                const auto index = binding_count.load(); auto& binding = bindings[index];
                binding.target = target; binding.state = L;
                lua.pushvalue(L, 3); binding.callback = lua.reference(L, registry);
                const auto created = MH_CreateHook(target, reinterpret_cast<void*>(binding_detours[index]), reinterpret_cast<void**>(&binding.original));
                if (created == MH_OK && MH_EnableHook(target) == MH_OK) { ++binding_count; ok = true; }
                log_file.write("native_binding_probe", {{"method", std::string(method, length)}, {"installed", ok},
                    {"create_result", int(created)}, {"rva", reinterpret_cast<uintptr_t>(target) - reinterpret_cast<uintptr_t>(memory.AllocationBase)}});
            }
        }
    }
    lua.settop(L, top); lua.pushboolean(L, ok); return 1;
}
struct EngineTextRange { uintptr_t begin{}, end{}; };

EngineTextRange engine_text_range() {
    auto* base = reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr));
    if (!base) return {};
    auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(base + dos->e_lfanew);
    auto* section = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i, ++section) {
        if (!std::strncmp(reinterpret_cast<const char*>(section->Name), ".text", 5)) {
            return {reinterpret_cast<uintptr_t>(base + section->VirtualAddress),
                    reinterpret_cast<uintptr_t>(base + section->VirtualAddress + section->Misc.VirtualSize)};
        }
    }
    return {};
}

bool engine_read(uintptr_t address, void* buffer, size_t size) {
    MEMORY_BASIC_INFORMATION info{};
    if (!VirtualQuery(reinterpret_cast<void*>(address), &info, sizeof(info))) return false;
    if (info.State != MEM_COMMIT || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) return false;
    const auto region_end = reinterpret_cast<uintptr_t>(info.BaseAddress) + info.RegionSize;
    if (address + size > region_end) return false;
    __try { std::memcpy(buffer, reinterpret_cast<const void*>(address), size); return true; }
    __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}

std::string engine_hex(uintptr_t value) {
    std::ostringstream out; out << "0x" << std::hex << value; return out.str();
}

std::string engine_hex_bytes(const uint8_t* data, size_t size) {
    std::ostringstream out; out << std::hex << std::setfill('0');
    for (size_t i = 0; i < size; ++i) out << std::setw(2) << static_cast<unsigned>(data[i]);
    return out.str();
}

void describe_layout_object(uintptr_t userdata, uintptr_t base, uintptr_t module_end, const EngineTextRange& text, Json& object) {
    object["userdata_va"] = engine_hex(userdata);
    object["userdata_rva"] = engine_hex(userdata - base);
    std::array<uint8_t, 256> bytes{};
    if (!engine_read(userdata, bytes.data(), bytes.size())) { object["error"] = "cannot read userdata"; return; }
    object["userdata_hex"] = engine_hex_bytes(bytes.data(), bytes.size());
    Json candidates = Json::array();
    auto dump_slots = [&](uintptr_t vtable, Json& holder) {
        Json slots = Json::array();
        for (int slot = 0; slot < 128; ++slot) {
            uint32_t function{};
            if (!engine_read(vtable + static_cast<uintptr_t>(slot) * 4, &function, 4)) break;
            if (!(text.begin <= function && function < text.end)) break;
            std::array<uint8_t, 16> code{};
            const bool code_ok = engine_read(function, code.data(), code.size());
            Json entry = {{"slot", slot}, {"rva", engine_hex(function - base)}};
            if (code_ok) entry["bytes"] = engine_hex_bytes(code.data(), code.size());
            slots.push_back(entry);
        }
        holder["vtable_slots"] = slots;
        holder["vtable_slot_count"] = static_cast<int>(slots.size());
    };
    for (int offset = 0; offset + 4 <= 256; offset += 4) {
        uint32_t value{};
        std::memcpy(&value, bytes.data() + offset, 4);
        if (value < 0x10000) continue;
        std::array<uint8_t, 256> target{};
        if (!engine_read(value, target.data(), target.size())) continue;
        uint32_t first{};
        std::memcpy(&first, target.data(), 4);
        const bool value_in_module = value >= base && value < module_end;
        const bool first_in_module = first >= base && first < module_end;
        Json candidate = {{"offset", offset}, {"value_va", engine_hex(value)}, {"value_rva", engine_hex(value - base)},
                          {"value_in_module", value_in_module}, {"first_dword", engine_hex(first)},
                          {"first_in_module", first_in_module}};
        if (first_in_module) {
            dump_slots(first, candidate);
        } else if (first >= 0x10000) {
            std::array<uint8_t, 256> second{};
            if (engine_read(first, second.data(), second.size())) {
                uint32_t second_first{};
                std::memcpy(&second_first, second.data(), 4);
                candidate["deref2_first_dword"] = engine_hex(second_first);
                candidate["deref2_first_in_module"] = second_first >= base && second_first < module_end;
                if (second_first >= base && second_first < module_end) dump_slots(second_first, candidate);
            }
        }
        candidates.push_back(candidate);
    }
    object["candidates"] = candidates;
}

void describe_cfunction(lua_State* L, int index, uintptr_t base, Json& out) {
    out["lua_type"] = lua.type ? lua.type(L, index) : -1;
    auto* function = lua.tocfunction ? lua.tocfunction(L, index) : nullptr;
    if (!function) { out["is_cfunction"] = false; return; }
    out["is_cfunction"] = true;
    const auto address = reinterpret_cast<uintptr_t>(function);
    out["rva"] = engine_hex(address - base);
    std::array<uint8_t, 64> code{};
    if (address >= base && engine_read(address, code.data(), code.size())) out["bytes"] = engine_hex_bytes(code.data(), code.size());
}

Json probe_engine_layout(lua_State* L) {
    Json report = {{"probe_passed", false}, {"native_game_used", true}, {"playable", false},
                   {"scope", "Read-only Lua object layout: no hooks are created, no engine function is called, no memory is written."}};
    const int top = lua.gettop(L);
    in_bridge = true;
    auto* module = reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr));
    const auto base = reinterpret_cast<uintptr_t>(module);
    const auto text = engine_text_range();
    uintptr_t module_end = base;
    if (module) {
        auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(module);
        auto* nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(module + dos->e_lfanew);
        module_end = base + nt->OptionalHeader.SizeOfImage;
    }
    if (!base || !text.begin) {
        report["error"] = "game .text section not found";
        lua.settop(L, top); in_bridge = false; return report;
    }
    report["module_base"] = engine_hex(base);
    report["text_begin_rva"] = engine_hex(text.begin - base);
    report["text_size"] = text.end - text.begin;
    report["module_size"] = module_end - base;
    Json objects = Json::array();
    const std::array<std::pair<const char*, const char*>, 4> targets{{
        {"return Game()", "Game"},
        {"return Isaac.GetPlayer(0)", "Player0"},
        {"return tostring(Game())", "GameToString"},
        {"return tostring(Isaac.GetPlayer(0))", "PlayerToString"},
    }};
    for (const auto& target : targets) {
        Json object = {{"label", target.second}};
        int status = lua.loadbuffer(L, target.first, std::strlen(target.first), "@authority-engine-layout", "t");
        if (!status) status = original_pcall(L, 0, 1, 0, 0, nullptr);
        if (status) { object["error"] = "lua evaluation failed"; objects.push_back(object); lua.settop(L, top); continue; }
        const int kind = lua.type ? lua.type(L, -1) : -1;
        object["lua_type"] = kind;
        if (kind == 4) {
            size_t length{};
            const char* text_value = lua.tostring ? lua.tostring(L, -1, &length) : nullptr;
            if (text_value) object["string_value"] = std::string(text_value, length);
        }
        const int result_index = lua.gettop(L);
        if (lua.getmetatable(L, -1)) {
            lua.getfield(L, -1, "__name");
            if (lua.type && lua.type(L, -1) == 4) {
                size_t length{};
                const char* name = lua.tostring ? lua.tostring(L, -1, &length) : nullptr;
                if (name) object["metatable_name"] = std::string(name, length);
            }
            lua.settop(L, result_index);
        }
        const void* pointer = lua.topointer ? lua.topointer(L, -1) : nullptr;
        const void* data_pointer = lua.touserdata ? lua.touserdata(L, -1) : nullptr;
        if (pointer) object["topointer_va"] = engine_hex(reinterpret_cast<uintptr_t>(pointer));
        if (data_pointer) object["touserdata_va"] = engine_hex(reinterpret_cast<uintptr_t>(data_pointer));
        if (pointer && kind == 7) describe_layout_object(reinterpret_cast<uintptr_t>(pointer), base, module_end, text, object);
        objects.push_back(object);
        lua.settop(L, top);
    }
    report["objects"] = objects;
    Json binding_records = Json::array();
    const std::array<std::pair<const char*, const char*>, 4> functions{{
        {"Game", ""},
        {"Isaac", "GetPlayer"},
        {"Isaac", "GetPtrHash"},
        {"tostring", ""},
    }};
    for (const auto& item : functions) {
        lua.settop(L, top);
        Json binding = {{"label", std::string(item.first) + (item.second[0] ? std::string(".") + item.second : std::string())}};
        lua.getglobal(L, item.first);
        if (item.second[0]) lua.getfield(L, -1, item.second);
        describe_cfunction(L, -1, base, binding);
        binding_records.push_back(binding);
    }
    report["bindings"] = binding_records;
    report["probe_passed"] = true;
    lua.settop(L, top);
    in_bridge = false;
    return report;
}

bool probe_dump_hex(uintptr_t address, size_t size, std::string& out) {
    out.clear();
    std::array<uint8_t, 256> buffer{};
    for (size_t offset = 0; offset < size;) {
        const auto chunk = std::min(buffer.size(), size - offset);
        if (!engine_read(address + offset, buffer.data(), chunk)) return false;
        out += engine_hex_bytes(buffer.data(), chunk);
        offset += chunk;
    }
    return true;
}

uintptr_t probe_userdata_payload(lua_State* L, int index) {
    const void* payload = lua.topointer ? lua.topointer(L, index) : nullptr;
    return reinterpret_cast<uintptr_t>(payload);
}

uintptr_t probe_userdata_pointer(lua_State* L, int index) {
    const auto payload = probe_userdata_payload(L, index);
    if (!payload) return 0;
    std::array<uint8_t, 8> bytes{};
    if (!engine_read(payload, bytes.data(), bytes.size())) return 0;
    uint32_t value{};
    std::memcpy(&value, bytes.data() + 4, 4);
    return value;
}

double probe_number(lua_State* L, int index) {
    int is_number{};
    return lua.tonumberx ? lua.tonumberx(L, index, &is_number) : 0.0;
}

bool probe_run_lua(lua_State* L, const char* source, int results) {
    int status = lua.loadbuffer(L, source, std::strlen(source), "@authority-state-layout", "t");
    if (!status) status = original_pcall(L, 0, results, 0, 0, nullptr);
    return status == 0;
}

double probe_object_number(lua_State* L, int object_index, const char* field) {
    lua.getfield(L, object_index, field);
    const double value = probe_number(L, -1);
    lua.settop(L, lua.gettop(L) - 1);
    return value;
}

double probe_vector_component(lua_State* L, int object_index, const char* vector_field, const char* component) {
    lua.getfield(L, object_index, vector_field);
    double value = 0.0;
    if (lua.type && lua.type(L, -1) == 7) {
        lua.getfield(L, -1, component);
        value = probe_number(L, -1);
        lua.settop(L, lua.gettop(L) - 1);
    }
    lua.settop(L, lua.gettop(L) - 1);
    return value;
}

Json probe_state_layout(lua_State* L) {
    Json report = {{"probe_passed", false}, {"native_game_used", true}, {"playable", false},
                   {"scope", "Read-only field discovery: no hooks, no writes, no engine function calls."}};
    const int top = lua.gettop(L);
    in_bridge = true;
    const auto base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    report["module_base"] = engine_hex(base);
    const int run_top = lua.gettop(L);
    const bool in_run = probe_run_lua(L, "return Isaac.GetPlayer(0) ~= nil and Game() ~= nil", 1) && lua.toboolean(L, -1);
    lua.settop(L, run_top);
    if (!in_run) {
        report["probe_passed"] = false;
        report["reason"] = "not_in_run";
        in_bridge = false;
        return report;
    }
    bool have_game = false;
    bool have_player = false;

    if (probe_run_lua(L, "local g=Game(); local l=g:GetLevel(); return g, g:GetFrameCount(), g:GetNumPlayers(), l:GetStage(), l:GetCurrentRoomIndex()", 5)) {
        const int n = lua.gettop(L);
        const int first = n - 4;
        const auto payload = probe_userdata_payload(L, first);
        const auto game_ptr = probe_userdata_pointer(L, first);
        Json game = {{"ptr", engine_hex(game_ptr)},
                     {"payload_hex", ""},
                     {"frame", probe_number(L, first + 1)},
                     {"num_players", probe_number(L, first + 2)},
                     {"stage", probe_number(L, first + 3)},
                     {"room", probe_number(L, first + 4)}};
        std::array<uint8_t, 8> payload_bytes{};
        if (payload && engine_read(payload, payload_bytes.data(), payload_bytes.size())) game["payload_hex"] = engine_hex_bytes(payload_bytes.data(), payload_bytes.size());
        if (game_ptr) {
            have_game = true;
            std::string hex;
            if (probe_dump_hex(game_ptr, 0x400, hex)) game["head_0x0_hex"] = hex;
            if (probe_dump_hex(game_ptr, 0x28000, hex)) game["dump_0x28000_hex"] = hex;
            if (probe_dump_hex(game_ptr + 0x18000, 0x600, hex)) game["head_0x18000_hex"] = hex;
            if (probe_dump_hex(game_ptr + 0x1ba00, 0x400, hex)) game["head_0x1ba00_hex"] = hex;
            if (probe_dump_hex(game_ptr + 0x26000, 0x800, hex)) game["head_0x26000_hex"] = hex;
            game["room_index"] = probe_read_u32(game_ptr + 0x18304);
            game["previous_room_index"] = probe_read_u32(game_ptr + 0x18308);
            game["room_index_copy"] = probe_read_u32(game_ptr + 0x1B850);
            const auto sub = probe_read_u32(game_ptr + 0x18300);
            game["ptr_0x18300"] = engine_hex(sub);
            if (sub) {
                if (probe_dump_hex(sub, 0x400, hex)) game["sub_0x18300_hex"] = hex;
                std::string level_hex;
                if (probe_dump_hex(sub, 0x8000, level_hex)) game["level_0x8000_hex"] = level_hex;
                if (probe_dump_hex(sub, 0x20000, level_hex)) game["level_0x20000_hex"] = level_hex;
                Json child_dumps = Json::array();
                Json pointer_candidates = Json::array();
                for (int offset = 0; offset < 0x200; offset += 4) {
                    const auto value = probe_read_u32(sub + offset);
                    if (value < 0x10000) continue;
                    std::array<uint8_t, 4> probe{};
                    if (!engine_read(value, probe.data(), probe.size())) continue;
                    pointer_candidates.push_back({{"offset", offset}, {"value", engine_hex(value)}});
                    if (child_dumps.size() < 16) {
                        std::string child_hex;
                        if (probe_dump_hex(value, 0x400, child_hex)) child_dumps.push_back({{"offset", offset}, {"value", engine_hex(value)}, {"hex", child_hex}});
                    }
                }
                game["level_pointer_candidates"] = pointer_candidates;
                game["level_child_dumps"] = child_dumps;
            }
        }
        report["game"] = game;
        lua.settop(L, top);
    }

    if (probe_run_lua(L, "local p=Isaac.GetPlayer(0); if not p then return nil end; return p, p.Position.X, p.Position.Y, p.Velocity.X, p.Velocity.Y, p.Size, p.InitSeed", 7)) {
        const int n = lua.gettop(L);
        const int first = n - 6;
        const int kind = lua.type ? lua.type(L, first) : -1;
        Json player = {{"lua_type", kind}};
        if (kind == 7) {
            have_player = true;
            const auto payload = probe_userdata_payload(L, first);
            const auto ptr = probe_userdata_pointer(L, first);
            player["ptr"] = engine_hex(ptr);
            std::array<uint8_t, 8> payload_bytes{};
            if (payload && engine_read(payload, payload_bytes.data(), payload_bytes.size())) player["payload_hex"] = engine_hex_bytes(payload_bytes.data(), payload_bytes.size());
            player["position"] = {{"x", probe_number(L, first + 1)}, {"y", probe_number(L, first + 2)}};
            player["velocity"] = {{"x", probe_number(L, first + 3)}, {"y", probe_number(L, first + 4)}};
            player["size"] = probe_number(L, first + 5);
            player["seed"] = probe_number(L, first + 6);
            if (ptr) {
                std::string hex;
                if (probe_dump_hex(ptr, 0x1000, hex)) player["dump_0x1000_hex"] = hex;
            }
        }
        report["player"] = player;
        lua.settop(L, top);
    }

    if (probe_run_lua(L, "local es=Isaac.GetRoomEntities(); local t={}; for i=1,math.min(#es,8) do t[i]=es[i] end; return t, #es", 2)) {
        const int n = lua.gettop(L);
        const int table_index = n - 1;
        const int count_index = n;
        const int room_count = static_cast<int>(probe_number(L, count_index));
        const int limit = std::min(8, room_count);
        Json entities = Json::array();
        for (int i = 1; i <= limit; ++i) {
            lua.rawgeti(L, table_index, i);
            if (lua.type && lua.type(L, -1) != 7) { lua.settop(L, count_index); continue; }
            const auto payload = probe_userdata_payload(L, -1);
            const auto ptr = probe_userdata_pointer(L, -1);
            Json entity = {{"index", i}, {"ptr", engine_hex(ptr)}};
            std::array<uint8_t, 8> payload_bytes{};
            if (payload && engine_read(payload, payload_bytes.data(), payload_bytes.size())) entity["payload_hex"] = engine_hex_bytes(payload_bytes.data(), payload_bytes.size());
            entity["position"] = {{"x", probe_vector_component(L, -1, "Position", "X")}, {"y", probe_vector_component(L, -1, "Position", "Y")}};
            entity["velocity"] = {{"x", probe_vector_component(L, -1, "Velocity", "X")}, {"y", probe_vector_component(L, -1, "Velocity", "Y")}};
            entity["seed"] = probe_object_number(L, -1, "InitSeed");
            entity["type"] = probe_object_number(L, -1, "Type");
            entity["variant"] = probe_object_number(L, -1, "Variant");
            if (ptr) {
                std::string hex;
                if (probe_dump_hex(ptr, 0x800, hex)) entity["dump_0x800_hex"] = hex;
            }
            entities.push_back(entity);
            lua.settop(L, count_index);
        }
        report["entities"] = entities;
        report["room_entity_count"] = room_count;
        lua.settop(L, top);
    }

    report["probe_passed"] = have_game && have_player;
    if (!report["probe_passed"].get<bool>()) report["reason"] = "not_in_run";
    lua.settop(L, top);
    in_bridge = false;
    return report;
}

std::atomic<bool> call_probe_active{}, call_probe_installed{}, call_probe_measuring{};
uint64_t call_probe_deadline{}, call_probe_started{}, call_probe_installed_at{};
bool state_capture{};
unsigned long g_state_rooms[64][3];
int g_state_room_count{};
unsigned long g_state_last_room{};
unsigned long g_state_room_change_count{};
unsigned long g_state_room_min{0xffffffff}, g_state_room_max{};
unsigned long g_state_entity_count_min{0xffffffff}, g_state_entity_count_max{};
unsigned long g_state_entity_base{}, g_state_entity_base_changes{};
unsigned long g_state_player_base{}, g_state_player_base_changes{};
unsigned long g_state_position_mismatch{}, g_state_first_mismatch_frame{};
float g_state_first_pos1[2]{}, g_state_first_pos2[2]{};
std::atomic<bool> packet_capture{false};
std::atomic<unsigned> g_packet_sample_limit{120};
unsigned long long g_packet_count{};
unsigned long long g_packet_bytes_min{0xffffffffffffffffull}, g_packet_bytes_max{};
unsigned long long g_packet_bytes_total{};
unsigned long long g_packet_time_total_us{};
unsigned long g_packet_entities_min{0xffffffff}, g_packet_entities_max{};
std::string g_packet_first_hex, g_packet_last_hex;
uintptr_t call_probe_target_rva{};
void* call_probe_target{};
uint32_t call_probe_frame_before{};
Json call_probe_report;
std::atomic<bool> skip_active{};
void* g_skip_original{};
unsigned long g_skip_calls{}, g_skip_skipped{}, g_skip_forwarded{}, g_skip_game_ptr{};

uint32_t probe_read_u32(uintptr_t address) {
    uint32_t value{};
    return engine_read(address, &value, 4) ? value : 0;
}

uint32_t probe_game_frame_count() {
    const auto base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    const auto game = probe_read_u32(base + 0x871678);
    return game ? probe_read_u32(game + 0x264f8) : 0;
}

void probe_log_call(const char* event, const Json& data) {
    log_file.write(event, data);
}

float probe_read_float(uintptr_t address) {
    float value{};
    return engine_read(address, &value, 4) ? value : 0.0f;
}

uint32_t buffer_u32(const uint8_t* data, size_t offset) {
    uint32_t value{};
    std::memcpy(&value, data + offset, 4);
    return value;
}

float buffer_float(const uint8_t* data, size_t offset) {
    float value{};
    std::memcpy(&value, data + offset, 4);
    return value;
}

void probe_call_entry(unsigned long this_ptr) {
    ++g_call_probe_calls;
    if (g_call_probe_game_ptr == 0 && this_ptr != 0) g_call_probe_game_ptr = this_ptr;
    if (this_ptr == g_call_probe_game_ptr) ++g_call_probe_ecx_match;
    else ++g_call_probe_ecx_mismatch;
    if (g_call_probe_first_ecx == 0) g_call_probe_first_ecx = this_ptr;
    g_call_probe_last_ecx = this_ptr;
    const auto frame = this_ptr ? probe_read_u32(static_cast<uintptr_t>(this_ptr) + 0x264f8) : 0;
    if (g_call_probe_calls == 1) g_call_probe_first_frame = frame;
    if (g_call_probe_calls > 1 && frame == g_call_probe_last_frame) ++g_call_probe_duplicate_frames;
    g_call_probe_last_frame = frame;
    if (this_ptr) {
        const auto start = probe_read_u32(static_cast<uintptr_t>(this_ptr) + 0x1baa8);
        const auto end = probe_read_u32(static_cast<uintptr_t>(this_ptr) + 0x1baac);
        if (start && end >= start) {
            const auto count = (end - start) / 4;
            if (g_call_probe_calls == 1) g_call_probe_players_first = count;
            g_call_probe_players_last = count;
        }
    }
    if (state_capture && this_ptr) {
        const auto level = probe_read_u32(static_cast<uintptr_t>(this_ptr) + 0x18300);
        if (level) {
            const auto room = probe_read_u32(static_cast<uintptr_t>(this_ptr) + 0x18304);
            const auto previous_room = probe_read_u32(static_cast<uintptr_t>(this_ptr) + 0x18308);
            if (room < g_state_room_min) g_state_room_min = room;
            if (room > g_state_room_max) g_state_room_max = room;
            if (room != g_state_last_room) {
                g_state_last_room = room;
                if (g_state_room_change_count < 64) {
                    g_state_rooms[g_state_room_count][0] = frame;
                    g_state_rooms[g_state_room_count][1] = room;
                    g_state_rooms[g_state_room_count][2] = previous_room;
                    ++g_state_room_count;
                }
                ++g_state_room_change_count;
            }
            const auto base = probe_read_u32(level + 0x125C);
            const auto count = probe_read_u32(level + 0x1264);
            if (g_state_entity_base == 0) g_state_entity_base = base;
            else if (base != g_state_entity_base) { ++g_state_entity_base_changes; g_state_entity_base = base; }
            if (count < g_state_entity_count_min) g_state_entity_count_min = count;
            if (count > g_state_entity_count_max) g_state_entity_count_max = count;
        }
        const auto players = probe_read_u32(static_cast<uintptr_t>(this_ptr) + 0x1BAA8);
        if (players) {
            if (g_state_player_base == 0) g_state_player_base = players;
            else if (players != g_state_player_base) { ++g_state_player_base_changes; g_state_player_base = players; }
            const auto player = probe_read_u32(players);
            if (player) {
                const auto x1 = probe_read_float(player + 0x33C);
                const auto y1 = probe_read_float(player + 0x340);
                const auto x2 = probe_read_float(player + 0x38C);
                const auto y2 = probe_read_float(player + 0x390);
                if (x1 != x2 || y1 != y2) {
                    ++g_state_position_mismatch;
                    if (g_state_first_mismatch_frame == 0) {
                        g_state_first_mismatch_frame = frame;
                        g_state_first_pos1[0] = x1;
                        g_state_first_pos1[1] = y1;
                        g_state_first_pos2[0] = x2;
                        g_state_first_pos2[1] = y2;
                    }
                }
            }
        }
    }
    // Packet bytes come from the global Game*, not this hook's ecx. 0x2fadc0's ecx
    // happens to be Game*; 0x554cd0's is not. NativeCaptureBuilder is the shared layout.
    if (packet_capture.load(std::memory_order_acquire) && g_packet_count < g_packet_sample_limit.load(std::memory_order_relaxed)) {
        const auto module_base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
        const auto game = static_cast<uintptr_t>(probe_read_u32(module_base + 0x871678));
        if (game) {
        const auto begin = std::chrono::steady_clock::now();
        NativeCaptureBuilder builder;
        const auto level = probe_read_u32(game + 0x18300);
        builder.set_header(probe_read_u32(game + 0x264f8), probe_read_u32(game + 0x18304), probe_read_u32(game + 0x18308));
        const auto players_start = probe_read_u32(game + 0x1BAA8);
        const auto players_end = probe_read_u32(game + 0x1BAAC);
        uint32_t player_count = players_start && players_end >= players_start ? (players_end - players_start) / 4 : 0;
        if (player_count > kMaxNativePlayers) player_count = static_cast<uint32_t>(kMaxNativePlayers);
        std::array<uint8_t, 0x400> block{};
        for (uint32_t i = 0; i < player_count; ++i) {
            const auto player = probe_read_u32(players_start + i * 4);
            const bool readable = player && engine_read(player, block.data(), block.size());
            builder.add_player(player,
                readable ? buffer_float(block.data(), 0x33C) : 0.0f,
                readable ? buffer_float(block.data(), 0x340) : 0.0f,
                readable ? buffer_float(block.data(), 0x360) : 0.0f,
                readable ? buffer_float(block.data(), 0x364) : 0.0f,
                readable ? buffer_float(block.data(), 0x370) : 0.0f);
        }
        const auto entities_base = level ? probe_read_u32(level + 0x125C) : 0;
        uint32_t entity_count = level ? probe_read_u32(level + 0x1264) : 0;
        if (entity_count > kMaxNativeEntities) entity_count = static_cast<uint32_t>(kMaxNativeEntities);
        for (uint32_t i = 0; i < entity_count && entities_base; ++i) {
            const auto entity = probe_read_u32(entities_base + i * 4);
            const bool readable = entity && engine_read(entity, block.data(), block.size());
            builder.add_entity(entity,
                readable ? buffer_u32(block.data(), 0x28) : 0,
                readable ? buffer_u32(block.data(), 0x2C) : 0,
                readable ? buffer_u32(block.data(), 0x3EC) : 0,
                readable ? buffer_float(block.data(), 0x33C) : 0.0f,
                readable ? buffer_float(block.data(), 0x340) : 0.0f,
                readable ? buffer_float(block.data(), 0x360) : 0.0f,
                readable ? buffer_float(block.data(), 0x364) : 0.0f,
                readable ? buffer_float(block.data(), 0x370) : 0.0f);
        }
        const auto packet = builder.finish();
        const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - begin).count();
        const auto bytes = packet.size();
        if (bytes < g_packet_bytes_min) g_packet_bytes_min = bytes;
        if (bytes > g_packet_bytes_max) g_packet_bytes_max = bytes;
        g_packet_bytes_total += bytes;
        g_packet_time_total_us += elapsed;
        if (entity_count < g_packet_entities_min) g_packet_entities_min = entity_count;
        if (entity_count > g_packet_entities_max) g_packet_entities_max = entity_count;
        if (g_packet_count == 0) g_packet_first_hex = engine_hex_bytes(packet.data(), packet.size());
        g_packet_last_hex = engine_hex_bytes(packet.data(), packet.size());
        ++g_packet_count;
        }
    }
}

void __declspec(naked) probe_call_detour() {
    __asm {
        pushfd
        pushad
        push ecx
        call dword ptr [g_call_probe_entry]
        add esp, 4
        popad
        popfd
        jmp dword ptr [g_call_probe_original]
    }
}

void finish_call_probe() {
    if (!call_probe_installed.exchange(false)) { call_probe_active = false; return; }
    const bool measured = call_probe_measuring.exchange(false);
    bool disabled = false;
    if (call_probe_target) {
        const auto result = MH_DisableHook(call_probe_target);
        disabled = result == MH_OK || result == MH_ERROR_DISABLED;
    }
    const auto frame_after = probe_game_frame_count();
    const auto frame_delta = frame_after >= call_probe_frame_before ? frame_after - call_probe_frame_before : 0;
    const auto calls = g_call_probe_calls;
    const auto elapsed = GetTickCount64() - call_probe_started;
    const double per_frame = frame_delta ? static_cast<double>(calls) / static_cast<double>(frame_delta) : 0.0;
    Json report = call_probe_report;
    report["calls"] = calls;
    report["ecx_match"] = g_call_probe_ecx_match;
    report["ecx_mismatch"] = g_call_probe_ecx_mismatch;
    report["first_ecx"] = engine_hex(g_call_probe_first_ecx);
    report["last_ecx"] = engine_hex(g_call_probe_last_ecx);
    report["duplicate_frames"] = g_call_probe_duplicate_frames;
    report["first_frame"] = g_call_probe_first_frame;
    report["last_frame"] = g_call_probe_last_frame;
    report["players_first"] = g_call_probe_players_first;
    report["players_last"] = g_call_probe_players_last;
    if (state_capture) {
        Json rooms = Json::array();
        for (int i = 0; i < g_state_room_count; ++i) rooms.push_back({{"frame", g_state_rooms[i][0]}, {"room", g_state_rooms[i][1]}, {"previous_room", g_state_rooms[i][2]}});
        report["state_capture"] = true;
        report["room_observations"] = rooms;
        report["room_change_count"] = g_state_room_change_count;
        report["room_index_min"] = g_state_room_min == 0xffffffff ? 0 : g_state_room_min;
        report["room_index_max"] = g_state_room_max;
        report["entity_base_changes"] = g_state_entity_base_changes;
        report["entity_count_min"] = g_state_entity_count_min == 0xffffffff ? 0 : g_state_entity_count_min;
        report["entity_count_max"] = g_state_entity_count_max;
        report["player_base_changes"] = g_state_player_base_changes;
        report["position_mismatch_frames"] = g_state_position_mismatch;
        Json first = {{"frame", g_state_first_mismatch_frame}};
        first["pos_0x33c"] = Json::array({g_state_first_pos1[0], g_state_first_pos1[1]});
        first["pos_0x38c"] = Json::array({g_state_first_pos2[0], g_state_first_pos2[1]});
        report["first_position_mismatch"] = first;
    }
    if (packet_capture.load()) {
        const auto frames = g_packet_count;
        report["packet_capture"] = true;
        report["packet_frames"] = frames;
        report["packet_entities_min"] = g_packet_entities_min == 0xffffffff ? 0 : g_packet_entities_min;
        report["packet_entities_max"] = g_packet_entities_max;
        report["packet_bytes_min"] = frames ? g_packet_bytes_min : 0;
        report["packet_bytes_max"] = g_packet_bytes_max;
        report["packet_bytes_total"] = g_packet_bytes_total;
        report["packet_bytes_average"] = frames ? static_cast<double>(g_packet_bytes_total) / frames : 0.0;
        report["packet_time_total_us"] = g_packet_time_total_us;
        report["packet_time_average_us"] = frames ? static_cast<double>(g_packet_time_total_us) / frames : 0.0;
        report["packet_first_hex"] = g_packet_first_hex;
        report["packet_last_hex"] = g_packet_last_hex;
    }
    report["frame_before"] = call_probe_frame_before;
    report["frame_after"] = frame_after;
    report["frame_delta"] = frame_delta;
    report["calls_per_frame"] = frame_delta ? Json(per_frame) : Json();
    report["elapsed_ms"] = elapsed;
    report["hook_disabled"] = disabled;
    report["measurement_started"] = measured;
    report["probe_passed"] = measured && calls > 0 && frame_delta > 0 && g_call_probe_ecx_mismatch == 0 && g_call_probe_duplicate_frames == 0 && per_frame >= 0.5 && per_frame <= 3.0;
    report["phase"] = !measured ? "no_gameplay_update_observed" : (report["probe_passed"].get<bool>() ? "verified_once_per_frame_game_this" : "not_verified");
    const auto output = std::filesystem::path(wide(config.at("output").get<std::string>()));
    std::ofstream(output / "call-probe.json") << report.dump(2);
    log_file.write("call_probe_finished", report);
    call_probe_active = false;
    stopped = true;
}

Json probe_game_update_call(lua_State* L) {
    Json report = {{"probe_passed", false}, {"native_game_used", true}, {"playable", false},
                   {"scope", "Read-only call-count verification: MinHook trampoline always forwards to the original function; no engine state is written."}};
    const int top = lua.gettop(L);
    if (!minhook_initialized) minhook_initialized = MH_Initialize() == MH_OK;
    if (!minhook_initialized) { report["error"] = "MinHook initialization failed"; return report; }
    const auto rva = static_cast<uintptr_t>(config.value("candidate_rva", uint64_t(0)));
    auto* module = reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr));
    const auto base = reinterpret_cast<uintptr_t>(module);
    if (!rva) { report["error"] = "candidate_rva is missing"; return report; }
    auto* target = reinterpret_cast<void*>(base + rva);
    MEMORY_BASIC_INFORMATION memory{};
    if (!VirtualQuery(target, &memory, sizeof(memory)) || memory.AllocationBase != module ||
        !(memory.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        report["error"] = "candidate is not executable game code";
        return report;
    }
    if (call_probe_installed) { report["error"] = "call probe already installed"; return report; }
    call_probe_target = target;
    call_probe_target_rva = rva;
    g_call_probe_calls = 0;
    g_call_probe_ecx_match = 0;
    g_call_probe_ecx_mismatch = 0;
    g_call_probe_first_ecx = 0;
    g_call_probe_last_ecx = 0;
    g_call_probe_game_ptr = probe_read_u32(base + 0x871678);
    call_probe_frame_before = probe_game_frame_count();
    call_probe_started = GetTickCount64();
    g_call_probe_duplicate_frames = 0;
    g_call_probe_first_frame = 0;
    g_call_probe_last_frame = 0;
    g_call_probe_players_first = 0;
    g_call_probe_players_last = 0;
    g_call_probe_entry = probe_call_entry;
    state_capture = config.value("capture_state", false);
    g_state_room_count = 0; g_state_last_room = 0; g_state_room_change_count = 0;
    g_state_room_min = 0xffffffff; g_state_room_max = 0;
    g_state_entity_count_min = 0xffffffff; g_state_entity_count_max = 0;
    g_state_entity_base = 0; g_state_entity_base_changes = 0;
    g_state_player_base = 0; g_state_player_base_changes = 0;
    g_state_position_mismatch = 0; g_state_first_mismatch_frame = 0;
    g_state_first_pos1[0] = g_state_first_pos1[1] = 0.0f;
    g_state_first_pos2[0] = g_state_first_pos2[1] = 0.0f;
    packet_capture.store(false);
    g_packet_sample_limit.store(120);
    g_packet_count = 0;
    g_packet_bytes_min = 0xffffffffffffffffull; g_packet_bytes_max = 0; g_packet_bytes_total = 0;
    g_packet_time_total_us = 0;
    g_packet_entities_min = 0xffffffff; g_packet_entities_max = 0;
    g_packet_first_hex.clear(); g_packet_last_hex.clear();
    const auto created = MH_CreateHook(target, reinterpret_cast<void*>(probe_call_detour), &g_call_probe_original);
    if (created != MH_OK) {
        report["error"] = "MH_CreateHook failed";
        report["create_result"] = static_cast<int>(created);
        return report;
    }
    const auto enabled = MH_EnableHook(target);
    if (enabled != MH_OK) {
        MH_RemoveHook(target);
        report["error"] = "MH_EnableHook failed";
        report["enable_result"] = static_cast<int>(enabled);
        return report;
    }
    call_probe_installed = true;
    call_probe_active = true;
    call_probe_measuring = false;
    call_probe_installed_at = call_probe_started;
    call_probe_deadline = call_probe_started + static_cast<uint64_t>(config.value("call_probe_wait_ms", 600000)); // overall wait for a gameplay update to appear
    report["target_rva"] = engine_hex(rva);
    report["game_global_ptr"] = engine_hex(g_call_probe_game_ptr);
    report["frame_before"] = call_probe_frame_before;
    report["planned_ms"] = config.value("call_probe_ms", 10000);
    report["phase"] = "hook_installed_waiting_for_gameplay";
    report["probe_passed"] = true;
    call_probe_report = report;
    lua.settop(L, top);
    return report;
}

int skip_check(unsigned long this_ptr) {
    if (!g_skip_game_ptr && this_ptr) g_skip_game_ptr = this_ptr;
    ++g_skip_calls;
    if (skip_active.load(std::memory_order_relaxed)) {
        ++g_skip_skipped;
        return 1;
    }
    ++g_skip_forwarded;
    return 0;
}

void __declspec(naked) skip_detour() {
    __asm {
        pushfd
        pushad
        push ecx
        call skip_check
        add esp, 4
        test eax, eax
        jz skip_forward
        popad
        popfd
        ret
    skip_forward:
        popad
        popfd
        jmp dword ptr [g_skip_original]
    }
}

void __declspec(naked) skip_detour_ret4() {
    __asm {
        pushfd
        pushad
        push ecx
        call skip_check
        add esp, 4
        test eax, eax
        jz skip_forward
        popad
        popfd
        ret 4
    skip_forward:
        popad
        popfd
        jmp dword ptr [g_skip_original]
    }
}

void __declspec(naked) skip_detour_ret8() {
    __asm {
        pushfd
        pushad
        push ecx
        call skip_check
        add esp, 4
        test eax, eax
        jz skip_forward
        popad
        popfd
        ret 8
    skip_forward:
        popad
        popfd
        jmp dword ptr [g_skip_original]
    }
}

Json probe_game_update_skip(lua_State* L) {
    Json report = {{"probe_passed", false}, {"native_game_used", true}, {"playable", false},
                   {"scope", "Guest-skip dry run: Game.Update is skipped for a bounded interval, then the hook is disabled; no state is written."}};
    const int top = lua.gettop(L);
    if (!minhook_initialized) minhook_initialized = MH_Initialize() == MH_OK;
    if (!minhook_initialized) { report["error"] = "MinHook initialization failed"; return report; }
    const auto rva = static_cast<uintptr_t>(config.value("candidate_rva", uint64_t(0)));
    auto* module = reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr));
    const auto base = reinterpret_cast<uintptr_t>(module);
    if (!rva) { report["error"] = "candidate_rva is missing"; return report; }
    auto* target = reinterpret_cast<void*>(base + rva);
    MEMORY_BASIC_INFORMATION memory{};
    if (!VirtualQuery(target, &memory, sizeof(memory)) || memory.State != MEM_COMMIT || !(memory.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE))) {
        report["error"] = "candidate_rva is not executable";
        return report;
    }
    g_skip_game_ptr = 0;
    g_skip_calls = 0;
    g_skip_skipped = 0;
    g_skip_forwarded = 0;
    skip_active = false;
    const auto skip_ret = config.value("skip_ret", 0);
    void* skip_detour_fn = skip_ret == 4 ? reinterpret_cast<void*>(skip_detour_ret4)
        : skip_ret == 8 ? reinterpret_cast<void*>(skip_detour_ret8)
        : reinterpret_cast<void*>(skip_detour);
    const auto created = MH_CreateHook(target, skip_detour_fn, &g_skip_original);
    if (created != MH_OK) {
        report["error"] = "MH_CreateHook failed";
        report["create_result"] = static_cast<int>(created);
        return report;
    }
    const auto enabled = MH_EnableHook(target);
    if (enabled != MH_OK) {
        MH_RemoveHook(target);
        report["error"] = "MH_EnableHook failed";
        report["enable_result"] = static_cast<int>(enabled);
        return report;
    }
    bool packet_hook = false;
    void* packet_target = nullptr;
    // Opt-in. The previous default of 0x2fadc0 installed probe_call_detour without
    // assigning g_call_probe_entry, which would call a null function pointer.
    const auto packet_rva = config.value("packet_rva", uint64_t(0));
    g_call_probe_entry = probe_call_entry;
    if (packet_rva && packet_rva != rva) {
        packet_target = reinterpret_cast<void*>(base + static_cast<uintptr_t>(packet_rva));
        MEMORY_BASIC_INFORMATION packet_memory{};
        if (VirtualQuery(packet_target, &packet_memory, sizeof(packet_memory)) && packet_memory.AllocationBase == module &&
            packet_memory.State == MEM_COMMIT && (packet_memory.Protect & (PAGE_EXECUTE | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE))) {
            const auto packet_created = MH_CreateHook(packet_target, reinterpret_cast<void*>(probe_call_detour), &g_call_probe_original);
            if (packet_created == MH_OK) {
                packet_hook = MH_EnableHook(packet_target) == MH_OK;
                if (!packet_hook) MH_RemoveHook(packet_target);
            }
        }
    }
    report["packet_hook"] = packet_hook;
    const auto wait_ms = config.value("skip_wait_ms", 600000);
    const auto recovery_ms = config.value("skip_recovery_ms", 5000);
    std::vector<uint64_t> skip_cycles;
    {
        const auto text = config.value("skip_cycles", std::string("2000,5000,2000"));
        size_t start = 0;
        while (start < text.size()) {
            const auto end = text.find(',', start);
            const auto part = text.substr(start, end == std::string::npos ? std::string::npos : end - start);
            if (!part.empty()) {
                const auto value = std::stoull(part);
                if (value >= 500 && value <= 10000) skip_cycles.push_back(value);
            }
            if (end == std::string::npos) break;
            start = end + 1;
        }
    }
    if (skip_cycles.empty()) skip_cycles.push_back(2000);
    if (skip_cycles.size() > 5) skip_cycles.resize(5);
    std::thread([skip_cycles, wait_ms, recovery_ms, target, packet_target, packet_hook, packet_rva] {
        Json out = {{"probe_passed", false}, {"native_game_used", true}, {"playable", false}};
        try {
            const auto wait_begin = GetTickCount64();
            uint32_t first_frame = 0;
            bool gameplay = false;
            auto current_frame = [] { return probe_game_frame_count(); };
            auto read_player = [](float& x, float& y) {
                const auto base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
                const auto game = probe_read_u32(base + 0x871678);
                if (!game) return false;
                const auto players = probe_read_u32(game + 0x1BAA8);
                if (!players) return false;
                const auto player = probe_read_u32(players);
                if (!player) return false;
                x = probe_read_float(player + 0x33C);
                y = probe_read_float(player + 0x340);
                return true;
            };
            auto packet_phase = [](uint32_t ms, const char* name) {
                g_packet_count = 0;
                g_packet_bytes_min = 0xffffffffffffffffull; g_packet_bytes_max = 0; g_packet_bytes_total = 0;
                g_packet_time_total_us = 0;
                g_packet_entities_min = 0xffffffff; g_packet_entities_max = 0;
                g_packet_first_hex.clear(); g_packet_last_hex.clear();
                g_packet_sample_limit.store(2048, std::memory_order_relaxed);
                packet_capture.store(true, std::memory_order_release);
                Sleep(ms);
                packet_capture.store(false, std::memory_order_release);
                Sleep(50);
                const auto frames = g_packet_count;
                const auto limit = g_packet_sample_limit.load();
                return Json{{"name", name}, {"frames", frames},
                            {"bytes_min", frames ? g_packet_bytes_min : 0}, {"bytes_max", g_packet_bytes_max},
                            {"bytes_average", frames ? static_cast<double>(g_packet_bytes_total) / frames : 0.0},
                            {"entities_min", g_packet_entities_min == 0xffffffff ? 0 : g_packet_entities_min},
                            {"entities_max", g_packet_entities_max},
                            {"time_average_us", frames ? static_cast<double>(g_packet_time_total_us) / frames : 0.0},
                            {"sample_limit", limit}, {"sample_capped", frames >= limit}};
            };
            Json packet_phases = Json::array();
            while (!stopped && GetTickCount64() - wait_begin < wait_ms) {
                if (g_skip_calls > 0) {
                    const auto frame = current_frame();
                    if (!first_frame) first_frame = frame;
                    if (frame > first_frame) { gameplay = true; break; }
                }
                Sleep(50);
            }
            Json cycles = Json::array();
            bool all_recovered = true;
            bool all_during = true;
            if (gameplay) {
                // Let the run settle so the first skip happens after the opening frames.
                const auto settle_deadline = GetTickCount64() + 3000;
                while (!stopped && GetTickCount64() < settle_deadline) Sleep(50);
                packet_phases.push_back(packet_phase(10000, "normal_before"));
            }
            for (size_t i = 0; gameplay && i < skip_cycles.size() && !stopped; ++i) {
                const auto ms = skip_cycles[i];
                float start_x = 0.0f, start_y = 0.0f, end_x = 0.0f, end_y = 0.0f;
                const bool player_readable = read_player(start_x, start_y);
                const auto start_frame = current_frame();
                skip_active = true;
                float max_displacement = 0.0f;
                const auto skip_deadline = GetTickCount64() + ms;
                while (!stopped && GetTickCount64() < skip_deadline) {
                    Sleep(50);
                    if (player_readable) {
                        float x = 0.0f, y = 0.0f;
                        if (read_player(x, y)) {
                            const auto dx = x - start_x, dy = y - start_y;
                            const auto distance = std::sqrt(dx * dx + dy * dy);
                            if (distance > max_displacement) max_displacement = distance;
                            end_x = x; end_y = y;
                        }
                    }
                }
                skip_active = false;
                const auto end_frame = current_frame();
                const bool moved_during_skip = player_readable && max_displacement > 0.01f;
                bool recovered = false;
                uint32_t after_frame = 0;
                const auto recovery_deadline = GetTickCount64() + recovery_ms;
                while (!stopped && GetTickCount64() < recovery_deadline) {
                    after_frame = current_frame();
                    if (after_frame > end_frame) { recovered = true; break; }
                    Sleep(20);
                }
                const auto during = end_frame >= start_frame ? end_frame - start_frame : 0;
                cycles.push_back({{"index", i}, {"skip_ms", ms}, {"start_frame", start_frame}, {"end_frame", end_frame},
                                  {"frame_delta_during_skip", during}, {"recovered", recovered}, {"frame_after", after_frame},
                                  {"player_readable", player_readable}, {"player_moved_during_skip", moved_during_skip},
                                  {"player_max_displacement", max_displacement},
                                  {"player_start", Json::array({start_x, start_y})}, {"player_end", Json::array({end_x, end_y})}});
                all_recovered &= recovered;
                all_during &= during <= 1;
            }
            skip_active = false;
            if (gameplay) packet_phases.push_back(packet_phase(5000, "normal_after"));
            const auto disabled = MH_DisableHook(target);
            bool packet_disabled = true;
            if (packet_hook && packet_target) packet_disabled = MH_DisableHook(packet_target) == MH_OK || MH_DisableHook(packet_target) == MH_ERROR_DISABLED;
            out["packet_rva"] = packet_rva;
            out["packet_hook"] = packet_hook;
            out["packet_phases"] = packet_phases;
            out["packet_hook_disabled"] = packet_disabled;
            out["gameplay_observed"] = gameplay;
            out["first_frame"] = first_frame;
            out["calls_total"] = g_skip_calls;
            out["skipped_calls"] = g_skip_skipped;
            out["forwarded_calls"] = g_skip_forwarded;
            out["cycles"] = cycles;
            out["recovered"] = all_recovered && gameplay;
            out["frame_delta_during_skip_ok"] = all_during;
            out["hook_disabled"] = disabled == MH_OK || disabled == MH_ERROR_DISABLED;
            out["probe_passed"] = gameplay && all_recovered && all_during;
        } catch (const std::exception& error) {
            out["error"] = error.what();
            skip_active = false;
            MH_DisableHook(target);
            if (packet_hook && packet_target) MH_DisableHook(packet_target);
        }
        try {
            const auto out_dir = std::filesystem::path(wide(config.at("output").get<std::string>()));
            std::ofstream(out_dir / "skip-probe.json") << out.dump(2);
        } catch (...) {}
        log_file.write("skip_probe_finished", out);
        stopped = true;
    }).detach();
    report["target_rva"] = engine_hex(rva);
    report["packet_rva"] = packet_rva;
    report["packet_hook"] = packet_hook;
    report["skip_ret"] = skip_ret;
    report["skip_cycles"] = config.value("skip_cycles", std::string("2000,5000,2000"));
    report["probe_passed"] = true;
    report["phase"] = "skip_hook_installed_waiting_for_gameplay";
    lua.settop(L, top);
    return report;
}

bool disable_native_bindings() {
    // Keep trampolines and callback references resident; a running Lua call can still return through them.
    bool ok = true;
    for (unsigned i = 0; i < binding_count; ++i) {
        const auto result = MH_DisableHook(bindings[i].target);
        if (result != MH_OK && result != MH_ERROR_DISABLED) {
            ok = false; log_file.write("binding_disable_error", {{"index", i}, {"result", int(result)}});
        }
    }
    return ok;
}

int __cdecl emit(lua_State* L) {
    if (stopped || disable_lua) return 0;
    try {
        size_t length{}; auto* value = lua.tostring(L, 1, &length);
        if (!value) return 0;
        if (length > kMaxPacket) { ++dropped_observations; log_file.write("oversized_observation_rejected"); return 0; }
        Json item = Json::parse(value, value + length);
        auto kind = item.value("kind", "");
        if (kind == "world") {
            auto& entities = item.at("body").at("entities");
            if (entities.is_object() && entities.empty()) entities = Json::array();
            validate_world(item.at("body"));
            if (!entities.empty()) world_seen = true;
        }
        else if (kind == "draw") {
            auto& commands = item.at("body").at("commands");
            if (commands.is_object() && commands.empty()) commands = Json::array();
            validate_draws(item.at("body"));
            if (!commands.empty()) draws_seen = true;
        }
        else if (kind != "input" && kind != "event") return 0;
        std::lock_guard lock(queue_mutex);
        if (outgoing.size() >= 128) { ++dropped_observations; return 0; }
        outgoing.push_back(std::move(item));
    } catch (const std::exception& e) { log_file.write("lua_observation_rejected", {{"error", e.what()}}); }
    return 0;
}
int __cdecl consume(lua_State* L) {
    try {
        if (disable_lua) { auto text = Json({{"stop", true}}).dump(); lua.pushstring(L, text.data(), text.size()); return 1; }
        std::lock_guard lock(inbound_mutex);
        auto text = incoming.dump(); lua.pushstring(L, text.data(), text.size()); return 1;
    } catch (...) { lua.pushstring(L, "null", 4); return 1; }
}
int __cdecl native_metatable(lua_State* L) {
    // Lua's public C API exposes the real metatable even when __metatable hides it from scripts.
    return lua.getmetatable(L, 1) ? 1 : 0;
}
int __cdecl lua_stopped(lua_State*) {
    // Control acknowledgement is allowed after the observation worker stops.
    log_file.write("lua_observer_stopped", {{"callbacks_inert", true}}); return 0;
}
int __cdecl hooked_pcall(lua_State*, int, int, int, intptr_t, LuaContinuation);
bool restore_slot() {
    if (!pcall_slot || !original_pcall) return true;
    DWORD old{};
    if (VirtualProtect(pcall_slot, sizeof(void*), PAGE_READWRITE, &old)) {
        // A later extension may have chained this slot. Never overwrite somebody else's hook.
        auto prior = InterlockedCompareExchangePointer(pcall_slot, reinterpret_cast<void*>(original_pcall), reinterpret_cast<void*>(hooked_pcall));
        DWORD ignored{}; VirtualProtect(pcall_slot, sizeof(void*), old, &ignored);
        const bool ok = prior == reinterpret_cast<void*>(hooked_pcall) || prior == reinterpret_cast<void*>(original_pcall);
        if (!ok) log_file.write("lua_iat_restore_deferred", {{"reason", "slot changed by another extension; observer remains inert"}});
        return ok;
    }
    log_file.write("lua_iat_restore_error"); return false;
}
void install_bootstrap(lua_State* L) {
    if (attached_state || stopped || disable_lua) return;
    int top = lua.gettop(L);
    const int isaac = lua.getglobal(L, "Isaac"); lua.settop(L, top);
    const int register_mod = lua.getglobal(L, "RegisterMod"); lua.settop(L, top);
    const int callbacks = lua.getglobal(L, "ModCallbacks"); lua.settop(L, top);
    if (isaac != 5 || register_mod != 6 || callbacks != 5) return;
    in_bridge = true;
    // A public, read-only readiness check avoids startup callback registries. No engine offset is used.
    // Probe at most five times per second; a menu or an early initialization state is not sufficient.
    static uint64_t last_ready_check{};
    const auto now = GetTickCount64();
    if (now - last_ready_check < 200) { in_bridge = false; return; }
    last_ready_check = now;
    constexpr char readiness[] = "return REPENTANCE_PLUS == true and type(Isaac.GetCallbacks) == 'function' and Game():GetFrameCount() > 0 and #Isaac.GetCallbacks(ModCallbacks.MC_POST_RENDER) > 0";
    int ready_result = lua.loadbuffer(L, readiness, sizeof(readiness)-1, "@authority-readiness", "t");
    if (!ready_result) ready_result = original_pcall(L, 0, 1, 0, 0, nullptr);
    const bool ready = !ready_result && lua.toboolean(L, -1);
    lua.settop(L, top);
    if (!ready) { in_bridge = false; return; }
    lua.pushclosure(L, emit, 0); lua.setglobal(L, "IsaacAuthorityNativeEmit");
    lua.pushclosure(L, consume, 0); lua.setglobal(L, "IsaacAuthorityNativeConsume");
    lua.pushclosure(L, native_metatable, 0); lua.setglobal(L, "IsaacAuthorityNativeMetatable");
    lua.pushclosure(L, watch_native, 0); lua.setglobal(L, "IsaacAuthorityNativeWatch");
    lua.pushclosure(L, lua_stopped, 0); lua.setglobal(L, "IsaacAuthorityNativeStopped");
    wchar_t filename[MAX_PATH]{}; GetModuleFileNameW(nullptr, filename, MAX_PATH);
    const auto game_root = utf8(std::filesystem::path(filename).parent_path().wstring());
    lua.pushstring(L, game_root.data(), game_root.size()); lua.setglobal(L, "IsaacAuthorityGameRoot");
    auto role = config.value("role", "capture"); lua.pushstring(L, role.data(), role.size()); lua.setglobal(L, "IsaacAuthorityRole");
    int result = lua.loadbuffer(L, kLuaBootstrap, sizeof(kLuaBootstrap) - 1, "@isaac-authority-observer", "t");
    if (!result) result = original_pcall(L, 0, 0, 0, 0, nullptr);
    if (result) {
        size_t length{}; const char* error = lua.tostring(L, -1, &length);
        log_file.write("bootstrap_error", {{"error", error ? std::string(error, length) : "non-string Lua error"}});
        disable_lua = true;
    } else { attached_state = L; lua_seen = true; lua_enabled = true; log_file.write("lua_observer_installed"); }
    lua.settop(L, top); in_bridge = false;
}
int __cdecl hooked_pcall(lua_State* L, int nargs, int results, int err, intptr_t ctx, LuaContinuation continuation) {
    // The original Lua call, including its exact stack/return convention, always runs.
    const int result = original_pcall(L, nargs, results, err, ctx, continuation);
    if (!in_bridge && !stopped) {
        ++callback_calls;
        if (!attached_state && !disable_lua) {
            try {if(config.value("object_probe",false))install_object_probe(L);else install_bootstrap(L);}
            catch(...) {disable_lua=true;}
        }
    }
    return result;
}
bool hook_lua() {
    auto* base = reinterpret_cast<uint8_t*>(GetModuleHandleW(nullptr));
    auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(base + dos->e_lfanew);
    auto rva = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!rva) return false;
    auto* desc = reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(base + rva);
    for (; desc->Name; ++desc) {
        if (!desc->OriginalFirstThunk) continue;
        auto* names = reinterpret_cast<IMAGE_THUNK_DATA32*>(base + desc->OriginalFirstThunk);
        auto* addresses = reinterpret_cast<IMAGE_THUNK_DATA32*>(base + desc->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++addresses) {
            if (IMAGE_SNAP_BY_ORDINAL32(names->u1.Ordinal)) continue;
            const auto* name = reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(base + names->u1.AddressOfData);
            if (std::string(reinterpret_cast<const char*>(name->Name)) != "lua_pcallk") continue;
            auto module = GetModuleHandleA(reinterpret_cast<const char*>(base + desc->Name));
            if (!module) return false;
            bridge_lua_module=module;
#define IA_LUA(field, symbol) lua.field = reinterpret_cast<decltype(lua.field)>(GetProcAddress(module, symbol)); if (!lua.field) return false
            IA_LUA(gettop, "lua_gettop"); IA_LUA(settop, "lua_settop"); IA_LUA(getglobal, "lua_getglobal");
            IA_LUA(getmetatable, "lua_getmetatable");
            IA_LUA(getfield, "lua_getfield"); IA_LUA(tocfunction, "lua_tocfunction"); IA_LUA(pushvalue, "lua_pushvalue");
            IA_LUA(toboolean, "lua_toboolean");
            IA_LUA(reference, "luaL_ref"); IA_LUA(rawgeti, "lua_rawgeti");
            IA_LUA(setglobal, "lua_setglobal"); IA_LUA(tostring, "lua_tolstring"); IA_LUA(pushstring, "lua_pushlstring");
            IA_LUA(pushboolean, "lua_pushboolean"); IA_LUA(pushclosure, "lua_pushcclosure"); IA_LUA(loadbuffer, "luaL_loadbufferx");
            IA_LUA(topointer, "lua_topointer"); IA_LUA(touserdata, "lua_touserdata"); IA_LUA(type, "lua_type"); IA_LUA(tonumberx, "lua_tonumberx");
            IA_LUA(pcall, "lua_pcallk");
#undef IA_LUA
            pcall_slot = reinterpret_cast<void**>(&addresses->u1.Function);
            original_pcall = reinterpret_cast<PCall>(*pcall_slot);
            DWORD old{}; if (!VirtualProtect(pcall_slot, sizeof(void*), PAGE_READWRITE, &old)) return false;
            InterlockedExchangePointer(pcall_slot, reinterpret_cast<void*>(hooked_pcall));
            DWORD ignored{}; VirtualProtect(pcall_slot, sizeof(void*), old, &ignored);
            log_file.write("lua_iat_observer_attached", {{"imports_only", true}, {"disk_game_code_modified", false}}); return true;
        }
    }
    return false;
}
DWORD WINAPI worker(void*) {
    try {
        const auto out = std::filesystem::path(wide(config.at("output").get<std::string>()));
        log_file.open(out / "native.jsonl");
        wchar_t exe[MAX_PATH]{}; GetModuleFileNameW(nullptr, exe, MAX_PATH);
        if (!supported_game(exe)) { log_file.write("unsupported_game_refused"); stopped = true; return 1; }
        if(!config.value("object_probe",false)||config.value("call_probe",false))minhook_initialized = MH_Initialize() == MH_OK;
        log_file.write("research_started", {{"role", config.value("role", "capture")}, {"playable", false}});
        SteamTransport steam;
        bool hook_attempted{};
        const auto diagnostic_begin=GetTickCount64();
        uint64_t sequence{}, last_hello{}, last_status{};
        Session session(config.value("role", "capture") == "preview" ? Role::preview : Role::capture,
                        config.at("session").get<std::string>(), config.at("manifest").get<std::string>());
        for (; !stopped;) {
            uint64_t now = GetTickCount64();
            if(call_probe_active && !call_probe_measuring) {
                const auto frame = probe_game_frame_count();
                if(g_call_probe_calls > 0 && frame != call_probe_frame_before) {
                    call_probe_frame_before = frame;
                    call_probe_started = now;
                    call_probe_deadline = now + static_cast<uint64_t>(config.value("call_probe_ms", 10000));
                    g_call_probe_calls = 0; g_call_probe_ecx_match = 0; g_call_probe_ecx_mismatch = 0;
                    g_call_probe_first_ecx = 0; g_call_probe_last_ecx = 0;
                    g_call_probe_duplicate_frames = 0; g_call_probe_first_frame = 0; g_call_probe_last_frame = 0;
                    g_call_probe_players_first = 0; g_call_probe_players_last = 0;
                    state_capture = config.value("capture_state", false);
                    g_state_room_count = 0; g_state_last_room = 0; g_state_room_change_count = 0;
                    g_state_room_min = 0xffffffff; g_state_room_max = 0;
                    g_state_entity_count_min = 0xffffffff; g_state_entity_count_max = 0;
                    g_state_entity_base = 0; g_state_entity_base_changes = 0;
                    g_state_player_base = 0; g_state_player_base_changes = 0;
                    g_state_position_mismatch = 0; g_state_first_mismatch_frame = 0;
                    g_packet_sample_limit.store(120);
                    packet_capture.store(config.value("capture_packet", false));
                    g_packet_count = 0;
                    g_packet_bytes_min = 0xffffffffffffffffull; g_packet_bytes_max = 0; g_packet_bytes_total = 0;
                    g_packet_time_total_us = 0;
                    g_packet_entities_min = 0xffffffff; g_packet_entities_max = 0;
                    g_packet_first_hex.clear(); g_packet_last_hex.clear();
                    call_probe_measuring = true;
                    log_file.write("call_probe_measurement_started", {{"frame", frame}});
                } else if(now >= call_probe_deadline) {
                    finish_call_probe();
                }
            } else if(call_probe_active && now >= call_probe_deadline) {
                finish_call_probe();
            }
            if(config.value("object_probe",false)&&now-diagnostic_begin>120000&&!object_probe_attempted.exchange(true)) {
                disable_lua=true;stopped=true;
                Json failed={{"probe_passed",false},{"playable",false},{"error","Diagnostic readiness timeout; canonical MCM/EID required for API/runtime probes"},{"no_diagnostic_native_calls",true}};
                const auto name=config.value("call_probe",false)?"call-probe.json":config.value("state_probe",false)?"state-probe.json":config.value("layout_probe",false)?"engine-layout.json":config.value("api_probe",false)?"engine-api.json":config.value("runtime_probe",false)?"mod-runtime.json":"object-bridge.json";
                std::ofstream(out/name)<<failed.dump(2);log_file.write("diagnostic_readiness_timeout",failed);
            }
            if (!hook_attempted && (GetModuleHandleA("Lua5.3.3r.dll") || GetModuleHandleA("Lua5.3.3f.dll"))) {
                hook_attempted = hook_lua();
            }
            if (!config.value("object_probe",false)&&!steam.available() && steam.initialize(GetModuleHandleW(L"steam_api.dll"), false)) {
                steam.set_peer(config.value("peer", uint64_t(0))); steam_seen = true;
                log_file.write("steam_messages_available", {{"interface", "SteamNetworkingMessages002"}, {"self_identity_available", steam.self() != 0}});
            }
            const bool has_peer = config.value("peer", uint64_t(0)) != 0;
            if (has_peer && steam.available()) {
                if (now - last_hello > 1000) {
                    Packet hello{"hello", config.at("session"), config.at("manifest"), ++sequence, 0,
                        {{"role", config.value("role", "capture")}, {"research_only", true}}};
                    hello.player = config.value("role", "capture") == "capture" ? 0 : 1;
                    const auto result = steam.send(hello);
                    if (result != k_EResultOK) log_file.write("steam_send_error", {{"result", int(result)}});
                    last_hello = now;
                }
                steam.poll([&](const Packet& p) {
                    if (session.receive(p, now)) {
                        std::lock_guard lock(inbound_mutex);
                        incoming = {{"world", session.world}, {"draw", session.draws}, {"frame", p.frame}, {"research_only", true}};
                        log_file.write("peer_packet", {{"kind", p.kind}, {"frame", p.frame}});
                    }
                }, log_file);
            }
            std::deque<Json> batch;
            { std::lock_guard lock(queue_mutex); batch.swap(outgoing); }
            for (auto& item : batch) {
                log_file.write("observation", item);
                const auto kind = item.value("kind", "event");
                const bool sendable = config.value("role", "capture") == "capture" ? (kind == "world" || kind == "draw") : kind == "input";
                if (has_peer && steam.available() && session.state == LinkState::active && sendable) {
                    Packet p{kind, config.at("session"), config.at("manifest"), ++sequence, item.value("frame", uint64_t(0)), item.at("body")};
                    p.player = config.value("role", "capture") == "capture" ? 0 : 1;
                    auto result = steam.send(p);
                    if (result != k_EResultOK) log_file.write("steam_send_error", {{"result", int(result)}});
                }
            }
            session.tick(now);
            if (session.state == LinkState::paused) { std::lock_guard lock(inbound_mutex); incoming = {{"paused", true}, {"research_only", true}}; }
            if (now - last_status >= 1000) {
                Coverage coverage; coverage.lua_observer = lua_seen; coverage.world_capture = world_seen;
                coverage.draw_capture = draws_seen; coverage.steam_interface = steam_seen;
                auto report = coverage.report(); report["lua_calls"] = callback_calls.load(); report["dropped_observations"] = dropped_observations.load();
                report["native_binding_hooks"] = binding_count.load(); report["native_binding_calls"] = native_calls.load();
                report["native_capture_errors"] = capture_errors.load(); report["native_capture_us"] = capture_us.load();
                report["native_capture_max_us"] = capture_max_us.load();
                // The status file is observational only; it never marks unimplemented gameplay gates as passed.
                std::ofstream status(out / "status.json.tmp"); status << report.dump(2); status.close();
                MoveFileExW((out / "status.json.tmp").c_str(), (out / "status.json").c_str(), MOVEFILE_REPLACE_EXISTING);
                last_status = now;
            }
            if (std::filesystem::exists(out / "stop")) { disable_lua = true; stopped = true; }
            std::this_thread::sleep_for(std::chrono::milliseconds(16));
        }
        if (call_probe_installed.exchange(false) && call_probe_target) MH_DisableHook(call_probe_target);
        const bool restored = restore_slot(), disabled = disable_native_bindings(); steam.stop();
        auto final_report = Coverage().report(); final_report["stopped"] = true;
        final_report["native_binding_hooks_disabled"] = disabled; final_report["lua_iat_restored"] = restored;
        std::ofstream(out / "stopped.json") << final_report.dump(2);
        log_file.write("observer_stopped", {{"dll_resident_until_game_exit", true}});
    } catch (const std::exception& e) { log_file.write("native_error", {{"error", e.what()}}); disable_lua = true; stopped = true; restore_slot(); disable_native_bindings(); }
    return 0;
}
}
extern "C" __declspec(dllexport) DWORD WINAPI IaInitialize(void* path) {
    if (started.exchange(true)) return 2;
    try {
        std::ifstream source(static_cast<const wchar_t*>(path)); config = Json::parse(source);
        const auto role = config.value("role", "capture");
        if (role != "capture" && role != "preview") return 3;
        auto handle = CreateThread(nullptr, 0, worker, nullptr, 0, nullptr);
        if (!handle) return 4; CloseHandle(handle); return 0;
    } catch (...) { return 5; }
}
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(instance);
    // Threads and Lua closures retain this module until the game exits; never FreeLibrary an active observer.
    return TRUE;
}
