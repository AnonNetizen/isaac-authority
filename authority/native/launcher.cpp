#include "platform.hpp"
#include "steam.hpp"
#include "runtime_suite.hpp"
#include <tlhelp32.h>
#include <shellapi.h>
#include <iostream>
#include <map>
#include <set>
#include <thread>
namespace {
using namespace ia;
struct Handle {
    HANDLE value{};
    explicit Handle(HANDLE h = nullptr) : value(h) {}
    ~Handle() { if (value && value != INVALID_HANDLE_VALUE) CloseHandle(value); }
    Handle(const Handle&) = delete;
};
void check(bool value, const char* error) { if (!value) throw std::runtime_error(std::string(error) + " (Win32=" + std::to_string(GetLastError()) + ")"); }
std::filesystem::path self_directory() {
    wchar_t name[MAX_PATH]{}; GetModuleFileNameW(nullptr, name, MAX_PATH); return std::filesystem::path(name).parent_path();
}
uintptr_t remote_function(DWORD pid, const char* symbol) {
    const auto function = GetProcAddress(GetModuleHandleW(L"kernel32.dll"), symbol);
    MEMORY_BASIC_INFORMATION info{}; check(VirtualQuery(function, &info, sizeof(info)) != 0, "Resolve system export");
    wchar_t path[MAX_PATH]{}; GetModuleFileNameW(static_cast<HMODULE>(info.AllocationBase), path, MAX_PATH);
    auto filename = std::filesystem::path(path).filename().wstring();
    Handle snapshot(CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid));
    check(snapshot.value != INVALID_HANDLE_VALUE, "Enumerate target modules");
    MODULEENTRY32W entry{}; entry.dwSize = sizeof(entry);
    for (BOOL found = Module32FirstW(snapshot.value, &entry); found; found = Module32NextW(snapshot.value, &entry))
        if (_wcsicmp(entry.szModule, filename.c_str()) == 0)
            return reinterpret_cast<uintptr_t>(entry.modBaseAddr) + reinterpret_cast<uintptr_t>(function) - reinterpret_cast<uintptr_t>(info.AllocationBase);
    throw std::runtime_error("Required system module is not loaded in target");
}
DWORD remote_call(HANDLE process, uintptr_t function, const std::wstring& text) {
    const size_t bytes = (text.size() + 1) * sizeof(wchar_t);
    auto* memory = VirtualAllocEx(process, nullptr, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    check(memory != nullptr, "Allocate remote argument");
    if (!WriteProcessMemory(process, memory, text.c_str(), bytes, nullptr)) {
        VirtualFreeEx(process, memory, 0, MEM_RELEASE); check(false, "Write remote argument");
    }
    Handle thread(CreateRemoteThread(process, nullptr, 0, reinterpret_cast<LPTHREAD_START_ROUTINE>(function), memory, 0, nullptr));
    if (!thread.value) { VirtualFreeEx(process, memory, 0, MEM_RELEASE); check(false, "Create remote loader thread"); }
    DWORD wait = WaitForSingleObject(thread.value, 15000);
    // A timed-out remote thread may still reference its argument; never free that memory prematurely.
    if (wait != WAIT_OBJECT_0) throw std::runtime_error("Remote call timed out; argument retained until game exit");
    DWORD result{}; check(GetExitCodeThread(thread.value, &result) != 0, "Read remote call result");
    VirtualFreeEx(process, memory, 0, MEM_RELEASE); return result;
}
void attach(DWORD pid, const std::filesystem::path& out, const Json& config) {
    Handle process(OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION | PROCESS_CREATE_THREAD, FALSE, pid));
    check(process.value != nullptr, "Open Isaac process");
    wchar_t name[32768]{}; DWORD length = 32768; check(QueryFullProcessImageNameW(process.value, 0, name, &length) != 0, "Read game path");
    if (!supported_game(name)) throw std::runtime_error("Unsupported game hash; no DLL was injected");
    if (std::filesystem::exists(out / "launch.json") || std::filesystem::exists(out / "stop"))
        throw std::runtime_error("Run directory already used; choose a fresh --out directory");
    std::filesystem::create_directories(out);
    auto config_path = out / "launch.json"; std::ofstream file(config_path); file << config.dump(2); file.close();
    auto dll = self_directory() / "isaac_authority_probe.dll";
    auto remote_base = remote_call(process.value, remote_function(pid, "LoadLibraryW"), dll.wstring());
    if (!remote_base) throw std::runtime_error("LoadLibrary failed in game; see native dependencies");
    auto local = LoadLibraryExW(dll.c_str(), nullptr, DONT_RESOLVE_DLL_REFERENCES);
    check(local != nullptr, "Read probe export");
    auto entry = GetProcAddress(local, "IaInitialize");
    if (!entry) entry = GetProcAddress(local, "_IaInitialize@4");
    if (!entry) { FreeLibrary(local); throw std::runtime_error("Probe initialization export missing"); }
    uintptr_t rva = reinterpret_cast<uintptr_t>(entry) - reinterpret_cast<uintptr_t>(local); FreeLibrary(local);
    auto initialized = remote_call(process.value, remote_base + rva, config_path.wstring());
    if (initialized != 0) {
        std::string reason = initialized == 2 ? "observer already initialized in this process; restart the game to attach a fresh probe"
            : initialized == 3 ? "invalid role in config"
            : initialized == 4 ? "could not create observer thread"
            : initialized == 5 ? "could not parse launch.json"
            : "unknown initialization failure";
        throw std::runtime_error("Observer initialization refused (" + std::to_string(initialized) + "): " + reason);
    }
    std::cout << Json({{"attached", true}, {"pid", pid}, {"output", utf8(out.wstring())}, {"playable", false}}).dump(2) << '\n';
}
DWORD running_game(const std::filesystem::path& exe) {
    auto normalized_exe=std::filesystem::absolute(exe).lexically_normal();normalized_exe.make_preferred();
    Handle snapshot(CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0));
    check(snapshot.value != INVALID_HANDLE_VALUE, "Enumerate processes");
    PROCESSENTRY32W entry{}; entry.dwSize = sizeof(entry); DWORD found{};
    for (BOOL next = Process32FirstW(snapshot.value, &entry); next; next = Process32NextW(snapshot.value, &entry)) {
        if (_wcsicmp(entry.szExeFile, L"isaac-ng.exe") != 0) continue;
        Handle process(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, entry.th32ProcessID));
        wchar_t path[32768]{}; DWORD length = 32768;
        if (process.value && QueryFullProcessImageNameW(process.value, 0, path, &length) && _wcsicmp(path, normalized_exe.c_str()) == 0) {
            if (found) throw std::runtime_error("Multiple matching games; choose --attach PID explicitly");
            found = entry.th32ProcessID;
        }
    }
    return found;
}
}
int wmain(int argc, wchar_t** argv) {
    try {
        std::map<std::wstring, std::wstring> args;
        const std::set<std::wstring> switches{L"--help", L"--launch", L"--steam-launch", L"--steam-probe", L"--stop", L"--check",L"--object-probe",L"--layout-probe",L"--call-probe",L"--state-probe",L"--capture-state",L"--capture-packet",L"--skip-probe",L"--runtime-probe",L"--api-probe"};
        const std::set<std::wstring> values{L"--game", L"--out", L"--role", L"--session", L"--peer", L"--manifest", L"--attach",L"--runtime-source",L"--runtime-suite",L"--candidate-rva",L"--probe-ms",L"--wait-ms",L"--skip-ms",L"--skip-cycles",L"--skip-ret",L"--packet-rva"};
        for (int i = 1; i < argc; ++i) {
            std::wstring key = argv[i];
            if (args.contains(key)) throw std::runtime_error("Duplicate option");
            if (switches.contains(key)) args[key] = L"1";
            else if (values.contains(key) && i + 1 < argc && !std::wstring(argv[i+1]).starts_with(L"--")) args[key] = argv[++i];
            else throw std::runtime_error("Unknown option or missing value; use --help");
        }
        if (args.contains(L"--help")) {
            std::cout << "Isaac Authority Research 0.8.0 (NOT PLAYABLE)\n"
                "Choose one: --check | --steam-probe | --steam-launch | --launch | --attach PID | --stop\n"
                "Options: --game DIR --out FRESH_DIR --role capture|preview\n"
                "Peer observation only: --peer STEAM_ID --session TOKEN --manifest FILE\n"
                "Owned-object diagnostic: add --object-probe to --attach/--steam-launch/--launch; no peer or draw hooks.\n"
                "Read-only engine layout: --layout-probe; dumps Game/Player userdata candidates and vtables; no hooks.\n"
                "Call-count verification: --call-probe --candidate-rva RVA; forwards every call, reverts after 10s.\n"
                "Field discovery: --state-probe; waits for an active run, dumps Game/Level/entity fields; read-only.\n"
                "Packet capture: --call-probe --candidate-rva RVA --capture-packet; measures serialized native state packets.\n"
                "State statistics: --call-probe --candidate-rva RVA --capture-state; records room-index changes and entity-count churn.\n"
                "Guest-skip dry run: --skip-probe --candidate-rva RVA --skip-ret 4 [--skip-cycles 2000,5000,2000] [--packet-rva 0x2fadc0].\n"
                "  --packet-rva also hooks that sub-update and records packet size/time. It is off unless set. 0x554cd0 needs --skip-ret 4.\n"
                "Private mod runtime diagnostic: --runtime-probe --runtime-source RESEARCH_SOURCE_DIR; no native world commit.\n"
                "Batch diagnostic: --runtime-suite FROZEN_JSON --runtime-source RESEARCH_SOURCE_DIR; one attach and preflight.\n"
                "Engine resource/metadata diagnostic: --api-probe; requires canonical MCM and EID loaded.\n"
                "Stop: --stop --out EXACT_RUN_DIR; the DLL stays resident until game exit.\n";
            return 0;
        }
        unsigned modes{};
        for (const auto* key : {L"--check", L"--steam-probe", L"--steam-launch", L"--launch", L"--attach", L"--stop"}) modes += args.contains(key) ? 1u : 0u;
        if (modes != 1) throw std::runtime_error("Choose exactly one mode; use --help");
        if(args.contains(L"--runtime-suite"))args[L"--runtime-probe"]=L"true";
        if(args.contains(L"--api-probe")) {
            if(!(args.contains(L"--attach")||args.contains(L"--launch")||args.contains(L"--steam-launch")))throw std::runtime_error("--api-probe requires attach/launch/steam-launch");
            if(args.contains(L"--object-probe")||args.contains(L"--runtime-probe")||args.contains(L"--peer")||args.contains(L"--role")||args.contains(L"--runtime-source"))throw std::runtime_error("--api-probe cannot combine other diagnostics/peer/role/source");
        }
        if(args.contains(L"--object-probe")&&!(args.contains(L"--attach")||args.contains(L"--launch")||args.contains(L"--steam-launch")))throw std::runtime_error("--object-probe requires attach/launch/steam-launch");
        if(args.contains(L"--object-probe")&&(args.contains(L"--peer")||args.contains(L"--role")))throw std::runtime_error("--object-probe cannot combine peer/role observation");
        if(args.contains(L"--layout-probe")) {
            if(!(args.contains(L"--attach")||args.contains(L"--launch")||args.contains(L"--steam-launch")))throw std::runtime_error("--layout-probe requires attach/launch/steam-launch");
            if(args.contains(L"--peer")||args.contains(L"--role")||args.contains(L"--api-probe")||args.contains(L"--runtime-probe")||args.contains(L"--object-probe"))throw std::runtime_error("--layout-probe cannot combine other diagnostics/peer/role");
        }
        if(args.contains(L"--call-probe")) {
            if(!(args.contains(L"--attach")||args.contains(L"--launch")||args.contains(L"--steam-launch")))throw std::runtime_error("--call-probe requires attach/launch/steam-launch");
            if(args.contains(L"--peer")||args.contains(L"--role")||args.contains(L"--api-probe")||args.contains(L"--runtime-probe")||args.contains(L"--object-probe")||args.contains(L"--layout-probe"))throw std::runtime_error("--call-probe cannot combine other diagnostics/peer/role");
            if(!args.contains(L"--candidate-rva"))throw std::runtime_error("--call-probe requires --candidate-rva");
        }
        if(args.contains(L"--capture-state") && !args.contains(L"--call-probe"))throw std::runtime_error("--capture-state requires --call-probe");
        if(args.contains(L"--capture-packet") && !args.contains(L"--call-probe"))throw std::runtime_error("--capture-packet requires --call-probe");
        if(args.contains(L"--skip-probe")) {
            if(!(args.contains(L"--attach")||args.contains(L"--launch")||args.contains(L"--steam-launch")))throw std::runtime_error("--skip-probe requires attach/launch/steam-launch");
            if(args.contains(L"--peer")||args.contains(L"--role")||args.contains(L"--api-probe")||args.contains(L"--runtime-probe")||args.contains(L"--object-probe")||args.contains(L"--layout-probe")||args.contains(L"--call-probe")||args.contains(L"--state-probe"))throw std::runtime_error("--skip-probe cannot combine other diagnostics/peer/role");
            if(!args.contains(L"--candidate-rva"))throw std::runtime_error("--skip-probe requires --candidate-rva");
        }
        if(args.contains(L"--packet-rva") && !args.contains(L"--skip-probe"))throw std::runtime_error("--packet-rva requires --skip-probe");
        if(args.contains(L"--state-probe")) {
            if(!(args.contains(L"--attach")||args.contains(L"--launch")||args.contains(L"--steam-launch")))throw std::runtime_error("--state-probe requires attach/launch/steam-launch");
            if(args.contains(L"--peer")||args.contains(L"--role")||args.contains(L"--api-probe")||args.contains(L"--runtime-probe")||args.contains(L"--object-probe")||args.contains(L"--layout-probe")||args.contains(L"--call-probe"))throw std::runtime_error("--state-probe cannot combine other diagnostics/peer/role");
        }
        if(args.contains(L"--runtime-probe")) {
            if(!(args.contains(L"--attach")||args.contains(L"--launch")||args.contains(L"--steam-launch")))throw std::runtime_error("--runtime-probe requires attach/launch/steam-launch");
            if(args.contains(L"--object-probe")||args.contains(L"--peer")||args.contains(L"--role"))throw std::runtime_error("--runtime-probe cannot combine object/peer/role observation");
            if(!args.contains(L"--runtime-source"))throw std::runtime_error("--runtime-probe requires --runtime-source");
            auto source=std::filesystem::path(args.at(L"--runtime-source"));
            if(!std::filesystem::is_regular_file(source/L"research/native_context.lua")||!std::filesystem::is_regular_file(source/L"fixtures/legacy_chaos/main.lua"))throw std::runtime_error("Missing runtime research source tree");
        }else if(args.contains(L"--runtime-source"))throw std::runtime_error("--runtime-source requires --runtime-probe");
        auto game = std::filesystem::path(args.contains(L"--game") ? args[L"--game"] : L"E:\\SteamLibrary\\steamapps\\common\\The Binding of Isaac Rebirth");
        const auto exe = game / "isaac-ng.exe";
        std::string suite_digest;
        if(args.contains(L"--runtime-suite"))suite_digest=FrozenRuntimeSuite::load(args.at(L"--runtime-suite"),game,args.at(L"--runtime-source")).digest;
        if (args.contains(L"--check")) {
            Coverage coverage;
            std::cout << Json({{"game_supported", supported_game(exe)}, {"game_sha256", sha256_file(exe)}, {"coverage", coverage.report()}}).dump(2) << '\n'; return 0;
        }
        auto out = std::filesystem::absolute(args.contains(L"--out") ? std::filesystem::path(args[L"--out"]) : self_directory() / "runs" / std::to_wstring(GetTickCount64()));
        if (args.contains(L"--stop")) {
            if (!args.contains(L"--out") || !std::filesystem::is_regular_file(out / "launch.json")) throw std::runtime_error("--stop requires the exact run --out directory");
            std::ofstream(out / "stop") << "stop observer\n";
            std::cout << "Observer stop requested; resident DLL exits with the game.\n"; return 0;
        }
        if (!supported_game(exe)) throw std::runtime_error("Unsupported game hash; refusing game integration");
        if (args.contains(L"--steam-probe")) {
            SetEnvironmentVariableW(L"SteamAppId", L"250900");
            auto module = LoadLibraryExW((game / "steam_api.dll").c_str(), nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
            check(module != nullptr, "Load installed Steam API");
            SteamTransport transport; bool ok = transport.initialize(module, true);
            auto report = Json({{"steam_messages_available", ok}, {"interface", "SteamNetworkingMessages002"},
                                {"self_identity_available", transport.self() != 0}, {"peer_exchange_tested", false}});
            std::filesystem::create_directories(out); std::ofstream(out / "steam-probe.json") << report.dump(2);
            std::cout << report.dump(2) << '\n'; transport.stop(); FreeLibrary(module); return ok ? 0 : 2;
        }
        if (!args.contains(L"--launch") && !args.contains(L"--steam-launch") && !args.contains(L"--attach")) throw std::runtime_error("Choose --steam-launch, --launch, --attach PID, --steam-probe or --check");
        if (std::filesystem::exists(out / "launch.json") || std::filesystem::exists(out / "stop"))
            throw std::runtime_error("Run directory already used; choose a fresh --out directory");
        auto role = args.contains(L"--role") ? utf8(args[L"--role"]) : "capture";
        if (role != "capture" && role != "preview") throw std::runtime_error("Only capture/preview research roles exist; playable host/client gates have not passed");
        auto session = args.contains(L"--session") ? utf8(args[L"--session"]) : "local-observation";
        auto peer = args.contains(L"--peer") ? std::stoull(args[L"--peer"]) : uint64_t(0);
        auto manifest = sha256_file(exe);
        if (args.contains(L"--manifest")) { std::ifstream source(args[L"--manifest"]); manifest = Json::parse(source).at("digest").get<std::string>(); }
        if (peer && (!args.contains(L"--session") || !args.contains(L"--manifest"))) throw std::runtime_error("Peer exchange requires an explicit session token and full build/mod manifest");
        if (session.size() < 8 || session.size() > 128 || manifest.size() != 64) throw std::runtime_error("Invalid session/manifest");
        Json config = {{"output", utf8(out.wstring())}, {"role", role}, {"peer", peer}, {"session", session}, {"manifest", manifest}, {"research_only", true}};
        config["object_probe"]=args.contains(L"--object-probe")||args.contains(L"--layout-probe")||args.contains(L"--call-probe")||args.contains(L"--state-probe")||args.contains(L"--skip-probe")||args.contains(L"--runtime-probe")||args.contains(L"--api-probe");
        config["layout_probe"]=args.contains(L"--layout-probe");
        config["call_probe"]=args.contains(L"--call-probe");
        config["state_probe"]=args.contains(L"--state-probe");
        config["capture_state"]=args.contains(L"--capture-state");
        config["capture_packet"]=args.contains(L"--capture-packet");
        config["skip_probe"]=args.contains(L"--skip-probe");
        config["skip_cycles"]=args.contains(L"--skip-cycles")?utf8(args.at(L"--skip-cycles")):"2000,5000,2000";
        config["skip_ret"]=args.contains(L"--skip-ret")?static_cast<uint64_t>(std::stoul(std::string(args.at(L"--skip-ret").begin(),args.at(L"--skip-ret").end()))):0;
        if(args.contains(L"--call-probe") || args.contains(L"--skip-probe")) {
            const auto candidate = std::stoull(args.at(L"--candidate-rva"), nullptr, 0);
            if(candidate == 0 || candidate > 0xffffffffull) throw std::runtime_error("Invalid --candidate-rva");
            config["candidate_rva"]=candidate;
        }
        config["packet_rva"]=uint64_t(0);
        if(args.contains(L"--packet-rva")) {
            const auto packet_rva = std::stoull(args.at(L"--packet-rva"), nullptr, 0);
            if(packet_rva == 0 || packet_rva > 0xffffffffull) throw std::runtime_error("Invalid --packet-rva");
            if(packet_rva == config.at("candidate_rva").get<uint64_t>()) throw std::runtime_error("--packet-rva must differ from --candidate-rva");
            config["packet_rva"]=packet_rva;
        }
        if(args.contains(L"--call-probe")) {
            uint64_t probe_ms = 10000;
            if(args.contains(L"--probe-ms")) probe_ms = std::stoull(args.at(L"--probe-ms"));
            if(probe_ms < 1000 || probe_ms > 300000) throw std::runtime_error("Invalid --probe-ms");
            config["call_probe_ms"]=probe_ms;
            uint64_t wait_ms = 600000;
            if(args.contains(L"--wait-ms")) wait_ms = std::stoull(args.at(L"--wait-ms"));
            if(wait_ms < 60000 || wait_ms > 1800000) throw std::runtime_error("Invalid --wait-ms");
            config["call_probe_wait_ms"]=wait_ms;
        }
        config["api_probe"]=args.contains(L"--api-probe");
        config["runtime_probe"]=args.contains(L"--runtime-probe");
        if(config["runtime_probe"])config["runtime_source"]=utf8(std::filesystem::absolute(args.at(L"--runtime-source")).wstring());
        if(args.contains(L"--runtime-suite")) {config["runtime_suite"]=utf8(std::filesystem::absolute(args.at(L"--runtime-suite")).wstring());config["runtime_suite_sha256"]=suite_digest;}
        if (args.contains(L"--attach")) attach(static_cast<DWORD>(std::stoul(args[L"--attach"])), out, config);
        else if (args.contains(L"--steam-launch")) {
            if (running_game(exe)) throw std::runtime_error("Game already running; use --attach PID or close it normally first");
            const auto result = ShellExecuteW(nullptr, L"open", L"steam://run/250900", nullptr, nullptr, SW_HIDE);
            check(reinterpret_cast<intptr_t>(result) > 32, "Launch through Steam");
            const auto deadline = GetTickCount64() + 60000; DWORD pid{};
            while (!(pid = running_game(exe)) && GetTickCount64() < deadline) std::this_thread::sleep_for(std::chrono::milliseconds(250));
            if (!pid) throw std::runtime_error("Steam did not start the expected game within 60 seconds");
            std::this_thread::sleep_for(std::chrono::milliseconds(250)); attach(pid, out, config);
        }
        else {
            if (running_game(exe)) throw std::runtime_error("Game already running; choose --attach PID explicitly");
            SetEnvironmentVariableW(L"SteamAppId", L"250900"); SetEnvironmentVariableW(L"SteamGameId", L"250900");
            std::wstring cmd = L"\"" + exe.wstring() + L"\"";
            STARTUPINFOW startup{}; startup.cb = sizeof(startup); PROCESS_INFORMATION process{};
            check(CreateProcessW(exe.c_str(), cmd.data(), nullptr, nullptr, FALSE, CREATE_SUSPENDED, nullptr, game.c_str(), &startup, &process) != 0, "Launch game");
            Handle game_process(process.hProcess), main_thread(process.hThread);
            // Resume the normal loader, then attach promptly. No executable or workshop files are replaced.
            ResumeThread(main_thread.value);
            std::this_thread::sleep_for(std::chrono::milliseconds(250));
            attach(process.dwProcessId, out, config);
        }
        return 0;
    } catch (const std::exception& e) { std::cerr << "ERROR: " << e.what() << '\n'; return 1; }
}
