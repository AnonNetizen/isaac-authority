#pragma once
#include "lua_bridge.hpp"
#include "ui_backend.hpp"
#include <array>
#include <map>
#include <memory>
#include <random>
namespace ia {
struct FrozenMod {
    std::filesystem::path root;
    std::map<std::string,std::string> files;
    Json hashes;
    static FrozenMod directory(const std::filesystem::path&);
};
struct NativeWorldModel {
    std::array<int64_t,2> coins{};
    int64_t frame{},time_ms{};
    std::mt19937 rng{460};
    Json effects=Json::array();
    Json call(const std::string&,const Json&);
    Json snapshot() const;
};
// Copy only verified scalar settings. The returned data has no native references.
Json snapshot_personal_options(const BridgeLuaApi&,BridgeLuaState*);
enum class PersonalMode { StrictReplay, Presentation, TraceReplay, ExecutionSlice, ExecutionSlice2, ExecutionSlice3, ExecutionSlice3UI, ExecutionUiBounded, ExecutionUiIncremental };
inline bool ui_mode(PersonalMode mode){return mode==PersonalMode::ExecutionSlice3UI||mode==PersonalMode::ExecutionUiBounded||mode==PersonalMode::ExecutionUiIncremental;}
inline bool slice3_mode(PersonalMode mode){return mode==PersonalMode::ExecutionSlice3||ui_mode(mode);}
inline bool timeline_mode(PersonalMode mode){return mode==PersonalMode::ExecutionSlice2||slice3_mode(mode);}
class NativeModContext {
    LuaObjectBridge bridge_;
    std::unique_ptr<StandaloneUiBackend> ui_backend_;
    std::string bootstrap_;
    std::vector<FrozenMod> mods_;
    size_t current_mod_{},cursor_{};
    unsigned budget_{};
    unsigned startup_instructions_{};
    bool replay_{};
    PersonalMode mode_{PersonalMode::StrictReplay};
    std::vector<bool> matched_;
    NativeWorldModel* world_{};
    Json options_;
    TraceLuaApi trace_;
    SliceLuaApi slice_;
    Json projection_=Json::array(),ambiguous_draw_roots_=Json::array();
    Json draw_value_ids_=Json::array();
    std::map<std::string,Json> store_graphs_;
    bool tracing_{};
    int64_t trace_epoch_{};
    size_t trace_cursor_{};
    Json timeline_=Json::array(),authority_graph_=nullptr,pending_draws_=Json::array(),query_anchors_=Json::array(),staged_events_=Json::array();
    std::vector<size_t> callback_stack_;size_t state_point_{};
    Json service_slice2(const std::string&,const Json&,const Json&,const Json&);
    void point_slice2(const std::string&,Json entry=nullptr);
    void finalize_draws_slice2();
    Json world_calls_=Json::array(),draw_origins_=Json::array(),store_origins_=Json::object();
    Json service(const std::string&,const Json&);
    Json module(const Json&);
public:
    Json store=Json::object(),input=Json::object(),tape=Json::array(),draws=Json::array(),logs=Json::array(),modules=Json::array(),suppressed=Json::array();
    NativeModContext(const BridgeLuaApi&,BridgeLuaState*,std::string bootstrap,std::vector<FrozenMod>,bool native_roots=true,Json options=nullptr,bool tracing=false,bool ui=false);
    void begin(NativeWorldModel*,const Json* replay=nullptr,PersonalMode mode=PersonalMode::StrictReplay);
    void check();
    void configure_slice2(const Json& timeline,const Json& graph,const Json& choices,bool search,unsigned instruction_limit=2000000);
    Json branches_slice2() const;
    Json finish_slice2() const;
    Json staged_slice2() const;
    void branch_purposes_slice3(const Json&);
    void limit_slice3(unsigned);
    unsigned startup_instructions_slice3() const {return startup_instructions_;}
    const Json& timeline_slice2() const {return timeline_;}
    void load_enums(const std::string&);
    void load_mod(size_t index);
    void dispatch(int callback);
    Json evaluate(const std::string&);
    Json summary();
    const Json& personal_options() const { return options_; }
    Json trace_report() const;
};
class NativeModSession {
    BridgeLuaApi api_;
    BridgeLuaState* host_{};
    std::string bootstrap_,enums_;
    std::vector<FrozenMod> mods_;
    Json initial_stores_,initial_options_,history_=Json::array(),last_rejection_=nullptr;
    bool native_roots_{};
    bool usable_{true};
    Json initial_tape_,initial_timeline_,initial_graph_,branch_search_=Json::array();
    PersonalMode mode_;
    std::array<std::unique_ptr<NativeModContext>,2> contexts_;
    void initialize();
    Json apply(int64_t,int64_t,const Json&,const std::function<void(const Json&)>& validator={});
    void recover();
    std::unique_ptr<NativeModContext> rebuild_personal_slice2(unsigned limit,unsigned& cost);
    void project_personal_slice2(NativeWorldModel&,const Json&);
    void project_personal_slice3(NativeWorldModel&,const Json&);
public:
    NativeWorldModel world;
    NativeModSession(const BridgeLuaApi&,BridgeLuaState*,std::string bootstrap,std::string enums,std::vector<FrozenMod>,Json stores,bool native_roots=true,Json option_overrides=nullptr,PersonalMode mode=PersonalMode::StrictReplay);
    Json step(int64_t frame,int64_t time_ms,const Json& inputs,const std::function<void(const Json&)>& validator={});
    Json checkpoint() const;
    const Json& rejection_report() const { return last_rejection_; }
    Json stores() const;
    Json personal_options() const;
    Json inspect(size_t slot,const std::string&);
};
Json probe_mod_runtime(const BridgeLuaApi&,BridgeLuaState*,const std::filesystem::path& game_root,const std::filesystem::path& research_root);
}
