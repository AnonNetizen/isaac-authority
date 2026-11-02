#include "mod_runtime.hpp"
#include "engine_api.hpp"
#include "resources.hpp"
#include <algorithm>
#include <cmath>
namespace ia {
namespace {
std::string read(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary);if(!file)throw std::runtime_error("Missing research source: "+utf8(path.wstring()));
    std::string data((std::istreambuf_iterator<char>(file)),{});
    if(data.size()>4*1024*1024)throw std::runtime_error("Research source size limit");return data;
}
int64_t integer(const Json& value) {
    if(!value.is_number_integer())throw std::runtime_error("Model integer argument required");
    if(value.is_number_unsigned()&&value.get<uint64_t>()>INT64_MAX)throw std::runtime_error("Model integer overflow");return value.get<int64_t>();
}
size_t player(const Json& value) {auto index=integer(value);if(index<0||index>1)throw std::runtime_error("Unmapped model player");return static_cast<size_t>(index);}
void arity(const Json& args,size_t count) {if(args.size()!=count)throw std::runtime_error("Invalid research API arity");}
std::string replace_slashes(std::string text) {std::replace(text.begin(),text.end(),'\\','/');return text;}
Json result(Json value) {return Json::array({std::move(value)});}
std::string byte_hex(const std::string& bytes) {
    const char digits[]="0123456789abcdef";std::string text;for(unsigned char b:bytes){text+=digits[b>>4];text+=digits[b&15];}return text;
}
Json validate_options(const Json& options) {
    if(!options.is_object()||options.size()!=2||!options.contains("Language")||!options.contains("HUDOffset"))throw std::runtime_error("Personal options schema");
    if(!options.at("Language").is_string())throw std::runtime_error("Personal Language must be a string");
    const auto& language=options.at("Language").get_ref<const std::string&>();
    if(language.empty()||language.size()>32||language.find_first_not_of("abcdefghijklmnopqrstuvwxyz_")!=std::string::npos)throw std::runtime_error("Personal Language code rejected");
    const auto& offset=options.at("HUDOffset");
    if(!offset.is_number()||!std::isfinite(offset.get<double>())||offset.get<double>()<0||offset.get<double>()>1)throw std::runtime_error("Personal HUDOffset range");
    return options;
}
Json model_options() {return {{"Language","en"},{"HUDOffset",0.0}};}
Json trace_snapshot(const NativeWorldModel& world){
    auto value=world.snapshot();std::ostringstream rng;rng<<world.rng;value["rng_sha256"]=sha256_bytes(rng.str());return value;
}
}
Json snapshot_personal_options(const BridgeLuaApi& api,BridgeLuaState* host) {
    LuaObjectBridge reader(api,host);
    reader.expose("Options",false);
    reader.set_policy([](const std::string& label,const std::string& operation,const std::vector<Json>&){
        if(label!="Options"||operation!="get")throw std::runtime_error("Read-only personal option snapshot");
    });
    auto values=reader.run("return Options.Language,Options.HUDOffset","@authority-read-personal-options");
    if(values.size()!=2||values[0].at("t")!="string"||(values[1].at("t")!="number"&&values[1].at("t")!="integer"))throw std::runtime_error("Native personal option types changed");
    const auto hex=values[0].at("hex").get<std::string>();
    if(hex.size()>64)throw std::runtime_error("Personal Language code rejected");
    std::string language;for(size_t i=0;i<hex.size();i+=2)language+=static_cast<char>(std::stoi(hex.substr(i,2),nullptr,16));
    return validate_options({{"Language",language},{"HUDOffset",values[1].at("v")}});
}
FrozenMod FrozenMod::directory(const std::filesystem::path& requested) {
    FrozenMod mod;mod.root=std::filesystem::canonical(requested);mod.hashes=Json::object();
    auto root_attributes=GetFileAttributesW(requested.c_str());
    if(root_attributes==INVALID_FILE_ATTRIBUTES||(root_attributes&FILE_ATTRIBUTE_REPARSE_POINT))throw std::runtime_error("Reparse mod root refused");
    size_t bytes{};
    for(const auto& item:std::filesystem::recursive_directory_iterator(mod.root)) {
        auto attributes=GetFileAttributesW(item.path().c_str());
        if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_REPARSE_POINT))throw std::runtime_error("Reparse file/directory in mod source refused");
        if(!item.is_regular_file()||item.path().extension()!=L".lua")continue;
        auto name=utf8(item.path().lexically_relative(mod.root).generic_wstring());auto code=read(item.path());bytes+=code.size();
        if(mod.files.size()>=4096||bytes>32*1024*1024)throw std::runtime_error("Frozen mod source limit");
        mod.hashes[name]=sha256_bytes(code);mod.files.emplace(name,std::move(code));
    }
    if(!mod.files.contains("main.lua"))throw std::runtime_error("Selected mod has no main.lua");return mod;
}
Json NativeWorldModel::snapshot() const {return {{"coins",coins},{"frame",frame},{"time_ms",time_ms}};}
Json NativeWorldModel::call(const std::string& op,const Json& args) {
    if(op=="Isaac.GetTime"){arity(args,0);return time_ms;}
    if(op=="Game.GetFrameCount"){arity(args,0);return frame;}
    if(op=="os.clock"){arity(args,0);return static_cast<double>(time_ms)/1000;}
    if(op=="os.time"){arity(args,0);return time_ms/1000;}
    if(op=="Player.GetNumCoins"){arity(args,1);return coins[player(args[0])];}
    if(op=="Player.AddCoins") {
        arity(args,2);auto index=player(args[0]);auto amount=integer(args[1]);
        if(amount < -1000000||amount>1000000)throw std::runtime_error("Model coin amount limit");
        coins[index]=std::clamp(coins[index]+amount,int64_t(0),int64_t(99));effects.push_back({{"op",op},{"player",index},{"amount",amount}});return nullptr;
    }
    if(op=="math.randomseed"){arity(args,1);rng.seed(static_cast<uint32_t>(integer(args[0])));return nullptr;}
    if(op=="math.random") {
        if(args.empty())return std::generate_canonical<double,53>(rng);
        if(args.size()>2)throw std::runtime_error("Model random arity");
        int64_t low=args.size()==1?1:integer(args[0]),high=integer(args.back());
        if(low>high||low<INT32_MIN||high>INT32_MAX)throw std::runtime_error("Model random interval");
        return std::uniform_int_distribution<int64_t>(low,high)(rng);
    }
    throw std::runtime_error("Unmapped world API: "+op);
}
NativeModContext::NativeModContext(const BridgeLuaApi& api,BridgeLuaState* host,std::string bootstrap,std::vector<FrozenMod> mods,bool native_roots,Json options,bool tracing,bool ui)
    :bridge_(api,host,true),bootstrap_(std::move(bootstrap)),mods_(std::move(mods)),options_(validate_options(options.is_null()?(native_roots?snapshot_personal_options(api,host):model_options()):options)),trace_(api.trace),slice_(api.slice),tracing_(tracing) {
    if(tracing_&&(!trace_.enable||native_roots))throw std::runtime_error("Trace replay requires standalone research Lua and coin-model roots");
    if(ui)ui_backend_=std::make_unique<StandaloneUiBackend>(api,bridge_.shadow());
    bridge_.install_service([this](const std::string& op,const Json& args){return service(op,args);});
    // Only the late-initialization diagnostic has verified these capabilities.
    bridge_.set_policy([](const std::string& label,const std::string& operation,const std::vector<Json>&){
        if(operation=="call") {
            const std::vector<std::string> allowed={"BitSet128","Vector","Color","KColor","Font","Sprite","Vector.Length","Font.Load","Font.GetStringWidth","Font.IsLoaded","Font.SetMissingCharacter",
                "Sprite.Load","Sprite.Play","Sprite.SetFrame","Sprite.GetFrame","Sprite.GetAnimation","Sprite.GetFilename","Sprite.ReplaceSpritesheet","Sprite.LoadGraphics","Isaac.GetItemConfig",
                "ItemConfig.Config.GetCollectible","ItemConfig.Config.GetTrinket","ItemConfig.Config.GetCard","ItemConfig.Config.GetPillEffect"};
            if(std::find(allowed.begin(),allowed.end(),label)==allowed.end())throw std::runtime_error("Unverified native API: "+label);
        }
    });
    if(native_roots) {
        wchar_t executable[MAX_PATH]{};GetModuleFileNameW(nullptr,executable,MAX_PATH);
        install_resource_capabilities(bridge_,std::filesystem::path(executable).parent_path());
        for(auto name:{"BitSet128","Vector","Color","KColor","Font","Sprite"})bridge_.expose(name);
        for(auto name:{"ItemConfig","RoomDescriptor"})bridge_.expose(name,false);
        expose_item_metadata(bridge_);
    }
    if(slice_.schedule){
        auto replace=[&](const std::string& a,const std::string& b){auto at=bootstrap_.find(a);if(at==std::string::npos)throw std::runtime_error("Slice2 framework patch missing");bootstrap_.replace(at,a.size(),b);};
        replace("for _,item in ipairs(list) do","for callbackIndex,item in ipairs(list) do");
        replace("local result=item.Function(item.Mod,...)","service('callback','begin',id,callbackIndex,item.Mod.Name,item.Function,item.Priority,item.Param)\n                local result=item.Function(item.Mod,...)\n                service('callback','end')");
    }
    const bool early_trace=tracing_&&slice_.purpose;
    if(early_trace)slice_.purpose(bridge_.shadow(),"{\"action\":\"startup_begin\"}");
    bridge_.run(bootstrap_,"@authority-native-mod-context");
    if(early_trace)startup_instructions_=Json::parse(slice_.purpose(bridge_.shadow(),"{\"action\":\"startup_end\"}")).at("instructions").get<unsigned>();
    if(tracing_){
        for(const auto& mod:mods_)for(auto it=mod.hashes.begin();it!=mod.hashes.end();++it){auto hash=it.value().get<std::string>();trace_.module(bridge_.shadow(),hash.c_str());}
        trace_.enable(bridge_.shadow());
    }
}
void NativeModContext::begin(NativeWorldModel* world,const Json* replay,PersonalMode mode) {
    world_=world;replay_=replay!=nullptr;mode_=mode;cursor_=0;budget_=0;tape=replay?*replay:Json::array();matched_.assign(tape.size(),false);draws=Json::array();logs=Json::array();suppressed=Json::array();
    if(tracing_){trace_epoch_=world->frame;trace_cursor_=0;world_calls_=Json::array();draw_origins_=Json::array();trace_.reset(bridge_.shadow(),trace_epoch_);}
    pending_draws_=Json::array();query_anchors_=Json::array();staged_events_=Json::array();callback_stack_.clear();state_point_=0;
    if(timeline_mode(mode)){if(!slice_.schedule||std::string(slice_.abi())!=(mode==PersonalMode::ExecutionUiIncremental?"ia-lua533-slice3-ui-incremental-1":mode==PersonalMode::ExecutionUiBounded?"ia-lua533-slice3-ui-bounded-1":(mode==PersonalMode::ExecutionSlice3UI?"ia-lua533-slice3-ui-1":(mode==PersonalMode::ExecutionSlice3?"ia-lua533-slice-3":"ia-lua533-slice-2"))))throw std::runtime_error(mode==PersonalMode::ExecutionSlice3?"Slice3 requires owned ABI 3":"Slice2 requires owned ABI 2");timeline_=Json::array();if(!replay_)point_slice2("frame_begin");}
    projection_=Json::array();ambiguous_draw_roots_=Json::array();draw_value_ids_=Json::array();
    if(mode==PersonalMode::ExecutionSlice&&(!slice_.abi||std::string(slice_.abi())!="ia-lua533-slice-1"))throw std::runtime_error("Slice mode requires owned graph ABI");
}
void NativeModContext::check() {
    if(replay_&&mode_==PersonalMode::StrictReplay&&cursor_!=tape.size())throw std::runtime_error("Shadow omitted authority world calls");
    if(tracing_){auto status=Json::parse(trace_.status(bridge_.shadow()));if(!status.at("failure").get<std::string>().empty())throw std::runtime_error(status.at("failure").get<std::string>());}
    if(timeline_mode(mode_)){
        finalize_draws_slice2();
    }
    if(slice_.graph&&(mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))){auto graph=Json::parse(slice_.graph(bridge_.shadow()));if(!graph.at("failure").get<std::string>().empty())throw std::runtime_error(graph.at("failure").get<std::string>());}
}
Json NativeModContext::trace_report() const{
    if(!tracing_)return nullptr;
    auto report=Json{{"world_calls",world_calls_},{"draw_origins",draw_origins_},{"store_origins",store_origins_},{"runtime",Json::parse(trace_.status(bridge_.shadow()))}};
    if((mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))){report["value_graph"]=Json::parse(slice_.graph(bridge_.shadow()));report["projection"]=projection_;report["draw_value_ids"]=draw_value_ids_;}
    if(slice3_mode(mode_)){report["view_rule"]="personal-settings-authority-hud-v1";report["startup_instructions"]=startup_instructions_;}
    if(timeline_mode(mode_)){report["bootstrap_effective_sha256"]=sha256_bytes(bootstrap_);report["state_timeline"]=timeline_;report["query_anchors"]=query_anchors_;report["staged_events"]=staged_events_;report["branch_state"]=branches_slice2();report["pending_draws"]=pending_draws_;}
    return report;
}
Json NativeModContext::module(const Json& args) {
    arity(args,3);auto name=replace_slashes(args[0].get<std::string>());auto kind=args[1].get<std::string>();
    auto caller=replace_slashes(args[2].get<std::string>());size_t index=current_mod_;
    for(size_t i=0;i<mods_.size();++i)if(caller.starts_with("@"+utf8(mods_[i].root.generic_wstring())+"/")){index=i;break;}
    const auto& mod=mods_.at(index);auto root=utf8(mod.root.generic_wstring());
    if(kind=="require") {
        if(name.find("..")!=std::string::npos||name.find(':')!=std::string::npos||name.starts_with('/'))throw std::runtime_error("Module path outside frozen roots");
        if(name.ends_with(".lua"))name.resize(name.size()-4);
        std::replace(name.begin(),name.end(),'.','/');name+=".lua";
    } else if(kind=="dofile") {
        if(name.starts_with(root+"/"))name.erase(0,root.size()+1);
        else if(name.find(':')!=std::string::npos||name.starts_with('/')||name.find("..")!=std::string::npos)throw std::runtime_error("Dofile path outside frozen roots");
    }else throw std::runtime_error("Unknown module resolver");
    for(const auto& candidate:std::vector<std::string>{name,"resources/"+name}) {
        auto found=mod.files.find(candidate);if(found!=mod.files.end()) {
            modules.push_back({{"mod",utf8(mod.root.filename().wstring())},{"file",candidate},{"sha256",mod.hashes.at(candidate)}});
            return Json::array({found->second,"@"+root+"/"+candidate});
        }
    }
    // Ordinary missing-module errors are catchable, preserving legacy filepath discovery.
    if(kind=="require")return Json::array({nullptr,"module not found:\n no file 'resources/scripts/"+name+"'\n no file '"+root+"/"+name+"'"});
    return Json::array({nullptr,"cannot open "+name+": not in frozen source"});
}
Json NativeModContext::service(const std::string& op,const Json& args) {
    if(ui_backend_&&op.starts_with("ui."))return ui_resource_call(op,args);
    auto resolve_value=[&](const Json& value)->Json {
        if(value.is_object()&&value.size()==1&&value.contains("__ia_deferred")){
            if((mode_!=PersonalMode::ExecutionSlice&&!timeline_mode(mode_))||!slice_.resolve)throw std::runtime_error("Deferred value outside slice mode");
            auto answer=Json::parse(slice_.resolve(bridge_.shadow(),value.at("__ia_deferred").get<unsigned>()));
            if(!answer.at("ok").get<bool>())throw std::runtime_error(answer.at("error").get<std::string>());
            return answer.at("value");
        }return value;
    };
    if(op=="unsupported") {arity(args,1);throw std::runtime_error("Unsupported boundary: "+args[0].get<std::string>());}
    if(op=="callback"){
        if(!timeline_mode(mode_))throw std::runtime_error("Callback timeline requires slice2");
        if(args.at(0)=="begin"){
            Json entry={{"callback",args.at(1)},{"mod",args.at(3)},{"function",args.at(4)},{"priority",args.at(5)},{"param",args.at(6)}};
            if(!replay_){point_slice2("callback_begin",entry);callback_stack_.push_back(state_point_);}
            else{std::vector<size_t> found;size_t parent=callback_stack_.empty()?0:callback_stack_.back();for(size_t n=0;n<timeline_.size();++n)if(timeline_[n].at("kind")=="callback_begin"&&timeline_[n].at("entry")==entry&&timeline_[n].value("parent",size_t(0))==parent)found.push_back(n);if(found.size()!=1)throw std::runtime_error("Ambiguous slice2 callback anchor");state_point_=found[0];callback_stack_.push_back(state_point_);}
        }else if(args.at(0)=="end"){if(callback_stack_.empty())throw std::runtime_error("Slice2 callback stack underflow");if(!replay_)point_slice2("callback_end");else{std::vector<size_t> exits;for(size_t n=0;n<timeline_.size();++n)if(timeline_[n].at("kind")=="callback_end"&&timeline_[n].at("parent")==callback_stack_.back())exits.push_back(n);if(exits.size()!=1)throw std::runtime_error("Ambiguous slice2 callback exit");state_point_=exits[0];}callback_stack_.pop_back();}
        else throw std::runtime_error("Slice2 callback operation");return Json::array();
    }
    if(op=="budget") {arity(args,0);if(++budget_>2000)throw std::runtime_error("Instruction budget exceeded");return Json::array();}
    if(op=="module")return module(args);
    if(op=="entry") {
        arity(args,1);current_mod_=static_cast<size_t>(integer(args[0]));auto& mod=mods_.at(current_mod_);
        modules.push_back({{"mod",utf8(mod.root.filename().wstring())},{"file","main.lua"},{"sha256",mod.hashes.at("main.lua")}});
        return Json::array({mod.files.at("main.lua"),"@"+utf8(mod.root.generic_wstring())+"/main.lua"});
    }
    if(op=="json.encode") {
        arity(args,1);auto metadata=(mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))?Json::parse(slice_.shape(bridge_.shadow(),2)):Json(nullptr);
        std::function<Json(const Json&,const Json&)> resolve_tree=[&](const Json& value,const Json& shape)->Json {
            if(shape.is_object()&&shape.contains("expression"))return resolve_value(value);
            if(!shape.is_object()||!shape.contains("children"))return value;
            Json out=value;
            for(const auto& entry:shape.at("children")){
                const auto& key=entry.at("key");const auto& child=entry.at("shape");
                if(value.is_array()){auto index=key.at("value").get<size_t>();if(index&&index<=value.size())out[index-1]=resolve_tree(value[index-1],child);}
                else if(value.is_object()&&key.at("type")=="string") {auto encoded=key.at("hex").get<std::string>();std::string name;for(size_t i=0;i<encoded.size();i+=2)name+=static_cast<char>(std::stoi(encoded.substr(i,2),nullptr,16));if(value.contains(name))out[name]=resolve_tree(value.at(name),child);}
            }return out;
        };
        auto text=resolve_tree(args[0],metadata).dump();if(text.size()>1024*1024)throw std::runtime_error("JSON output limit");if((mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_)))bridge_.set_service_shape(Json{{"serialized",metadata}});return result(text);
    }
    if(op=="json.decode") {
        arity(args,1);auto text=args[0].get<std::string>();auto decoded=Json::parse(text);
        if((mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))){auto metadata=Json::parse(slice_.shape(bridge_.shadow(),2));
            if(metadata.contains("serialized"))bridge_.set_service_shape(metadata.at("serialized"));
            else {
                auto source=metadata.at("value_id");std::function<Json(const Json&)> initial_shape=[&](const Json& value)->Json {Json shape={{"value_id",source},{"field_source",slice3_mode(mode_)}};if(value.is_object()||value.is_array()){shape["children"]=Json::array();size_t index=1;for(auto it=value.begin();it!=value.end();++it){Json key;if(value.is_array())key={{"type","integer"},{"value",index++}};else key={{"type","string"},{"hex",byte_hex(it.key())}};shape["children"].push_back({{"key",key},{"shape",initial_shape(it.value())}});}}return shape;};auto shape=initial_shape(decoded);if(slice3_mode(mode_)){std::function<void(Json&,Json)> annotate=[&](Json& entry,Json path){entry["source_path"]=path;if(entry.contains("children"))for(auto& child:entry["children"]){auto next=path;next.push_back(child.at("key"));annotate(child["shape"],next);}};annotate(shape,Json::array());}bridge_.set_service_shape(shape);
            }
        }return result(decoded);
    }
    if(op=="log") {arity(args,1);logs.push_back(args[0]);if(logs.size()>256)throw std::runtime_error("Log budget exceeded");return Json::array();}
    if(op=="options.get"||op=="options.set") {
        arity(args,op=="options.get"?1:2);auto name=args[0].get<std::string>();
        if(!options_.contains(name))throw std::runtime_error("Unsupported boundary: Options."+name);
        if(op=="options.get"){if(tracing_)bridge_.label_service_result("personal_option:"+name);return result(options_.at(name));}
        auto candidate=options_;candidate[name]=args[1];options_=validate_options(candidate);return Json::array();
    }
    if(op=="data") {
        if(args.size()<2)throw std::runtime_error("Mod data arity");auto action=args[0].get<std::string>(),name=args[1].get<std::string>();
        if(action=="load"){arity(args,2);if(tracing_){bridge_.label_service_result("personal_config:"+name);if(store_origins_.contains(name))for(const auto& origin:store_origins_.at(name))bridge_.label_service_result(origin.get<std::string>());}if((mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))&&store_graphs_.contains(name))bridge_.set_service_shape(Json{{"serialized",store_graphs_.at(name)}});return result(store.value(name,std::string{}));}
        if(action=="has"){arity(args,2);if(tracing_)bridge_.label_service_result("personal_config:"+name);return result(store.contains(name)&&!store.at(name).get<std::string>().empty());}
        if(action=="remove"){arity(args,2);store.erase(name);store_graphs_.erase(name);if(tracing_)store_origins_.erase(name);return Json::array();}
        if(action=="save") {arity(args,3);if(!args[2].is_string()||args[2].get_ref<const std::string&>().size()>1024*1024)throw std::runtime_error("Mod data string limit");store[name]=args[2];if(timeline_mode(mode_))staged_events_.push_back({{"op","save"},{"mod",name}});if(tracing_)store_origins_[name]=bridge_.trace_argument_origins(4);if((mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))){auto shape=Json::parse(slice_.shape(bridge_.shadow(),4));if(shape.contains("serialized"))store_graphs_[name]=shape.at("serialized");else{if(slice3_mode(mode_)){auto request=Json{{"action","serialization_check"},{"value_id",shape.at("value_id")}}.dump();auto provenance=Json::parse(slice_.purpose(bridge_.shadow(),request.c_str()));if(!provenance.at("ok").get<bool>())throw std::runtime_error(provenance.at("error").get<std::string>());}store_graphs_.erase(name);}}return Json::array();}
        throw std::runtime_error("Mod data operation");
    }
    if(op=="input") {
        arity(args,3);if(integer(args[2])!=0)throw std::runtime_error("Unmapped personal controller index");
        auto action=args[0].get<std::string>();auto key=integer(args[1]);
        if(tracing_)bridge_.label_service_result("personal_input:"+action+":"+std::to_string(key));
        if(action=="triggered"||action=="pressed"||action=="action_triggered"||action=="action_pressed") {auto keys=input.value(action,Json::array());return result(std::find(keys.begin(),keys.end(),Json(key))!=keys.end());}
        if(action=="action")return result(input.value("actions",Json::object()).value(std::to_string(key),0.0));
        throw std::runtime_error("Personal input operation");
    }
    if(op=="draw.text") {
        if(timeline_mode(mode_)&&replay_){if(args.size()!=7||pending_draws_.size()>=8192)throw std::runtime_error("Slice2 queued draw limit");Json ids=Json::array(),expressions=Json::array(),origins=Json::array();for(int i=2;i<=8;++i){ids.push_back(slice_.value(bridge_.shadow(),i));auto p=Json::parse(slice_.pending(bridge_.shadow(),i));expressions.push_back(p.is_null()?Json(0):p.at("expression"));origins.push_back(bridge_.trace_argument_origins(i));}Json draw={{"args",args},{"value_ids",ids},{"expressions",expressions},{"origins",origins}};if(slice3_mode(mode_)){auto request=Json{{"action","draw"},{"value_ids",ids}}.dump();draw["purpose"]=Json::parse(slice_.purpose(bridge_.shadow(),request.c_str()));}pending_draws_.push_back(draw);staged_events_.push_back({{"op","draw"},{"index",pending_draws_.size()-1}});return Json::array();}
        arity(args,7);Json actual=Json::array();for(const auto& v:args)actual.push_back(resolve_value(v));
        if((mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))&&replay_)for(const auto& root:ambiguous_draw_roots_)for(int i=2;i<=8;++i)
            if(slice_.uses(bridge_.shadow(),slice_.value(bridge_.shadow(),i),root.get<unsigned>()))throw std::runtime_error("Ambiguous slice draw: personal setting also drives world contribution");
        if(!actual[0].is_string()||actual[0].get_ref<const std::string&>().size()>65536)throw std::runtime_error("Draw text limit");
        for(size_t i=1;i<7;++i)if(!actual[i].is_number()||!std::isfinite(actual[i].get<double>()))throw std::runtime_error("Draw number required");
        if(draws.size()>=8192)throw std::runtime_error("Draw command limit");
        if(tracing_)draw_origins_.push_back({{"text",bridge_.trace_argument_origins(2)},{"x",bridge_.trace_argument_origins(3)},{"y",bridge_.trace_argument_origins(4)}});
        if((mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))){Json ids=Json::array();for(int i=2;i<=8;++i)ids.push_back(slice_.value(bridge_.shadow(),i));draw_value_ids_.push_back(ids);}
        draws.push_back({{"op","text"},{"text_hex",byte_hex(actual[0].get<std::string>())},{"x",actual[1]},{"y",actual[2]},
            {"color",{{"r",actual[3]},{"g",actual[4]},{"b",actual[5]},{"a",actual[6]}}}});return Json::array();
    }
    if(op=="world") {
        if(!world_||args.empty()||!args[0].is_string())throw std::runtime_error("World call outside model transaction");
        auto name=args[0].get<std::string>();Json values=Json::array();for(size_t i=1;i<args.size();++i)values.push_back(args[i]);
        Json site=nullptr,dependencies=Json::array();
        if(tracing_){site=Json::parse(trace_.context(bridge_.shadow()));for(int i=3;i<=static_cast<int>(args.size())+1;++i)dependencies.push_back(bridge_.trace_argument_origins(i));}
        if(replay_&&timeline_mode(mode_))return service_slice2(name,values,site,dependencies);
        if(replay_&&mode_==PersonalMode::ExecutionSlice){
            auto event=Json{{"op",name},{"args",values},{"site",site},{"executed",false},{"world_committed",false},{"argument_value_ids",Json::array()}};
            for(int i=3;i<=static_cast<int>(args.size())+1;++i)event["argument_value_ids"].push_back(slice_.value(bridge_.shadow(),i));
            auto reject=[&](const std::string& reason){event["rejected"]=reason;world_calls_.push_back(event);throw std::runtime_error(reason);};
            if(name=="math.random"){event["deferred"]=true;world_calls_.push_back(event);return result(Json{{"__ia_new_deferred",event}});}
            auto role=[](const Json& context){Json key=Json::array();for(const auto& frame:context.at("path"))key.push_back({{"source_sha256",frame.at("source_sha256")},{"prototype",frame.at("prototype")},{"instruction",frame.at("instruction")}});return key;};
            std::vector<size_t> candidates;for(size_t i=trace_cursor_;i<tape.size();++i)if(!matched_[i]&&tape[i].at("op")==name&&role(tape[i].at("site"))==role(site))candidates.push_back(i);
            if(candidates.size()>1)reject("Ambiguous slice authority consumer");
            const bool write=name=="Player.AddCoins"||name=="math.randomseed";
            if(candidates.empty()){
                if(write&&std::none_of(values.begin(),values.end(),[](const Json& v){return v.is_object();})){auto model=*world_;model.call(name,values);suppressed.push_back(event);world_calls_.push_back(event);return result(nullptr);}
                reject("Unmatched slice state point or contribution: "+name);
            }
            auto index=candidates[0];const auto& expected=tape[index];
            if(write){
                if(name=="Player.AddCoins"&&(values.size()!=2||values[0]!=expected.at("args")[0]))reject("Slice world target mismatch");
                for(size_t n=0;n<values.size();++n)if(values[n].is_object()&&values[n].contains("__ia_deferred")){
                    auto pending=Json::parse(slice_.pending(bridge_.shadow(),static_cast<int>(n)+3));if(pending.is_null()||pending.at("expression")!=values[n].at("__ia_deferred"))reject("Invalid slice deferred envelope");
                    auto evidence=Json{{"value",expected.at("args")[n]},{"authority_event",index},{"authority_value_id",expected.at("argument_value_ids")[n]},{"personal_expression_id",values[n].at("__ia_deferred")},{"operation",name},{"argument",n},{"authority_site",expected.at("site")},{"personal_site",site},{"binding_kind","world_contribution_reference"}};
                    auto text=evidence.dump();auto answer=Json::parse(slice_.bind(bridge_.shadow(),values[n].at("__ia_deferred").get<unsigned>(),text.c_str()));
                    if(!answer.at("ok").get<bool>())reject(answer.at("error").get<std::string>());projection_.push_back(evidence);
                }else if(values[n]!=expected.at("args")[n])ambiguous_draw_roots_.push_back(slice_.value(bridge_.shadow(),static_cast<int>(n)+3));
                suppressed.push_back(event);
            }else if(values!=expected.at("args"))reject("Slice query target/argument mismatch");
            matched_[index]=true;trace_cursor_=index+1;event["authority_event"]=index;event["state_before"]=expected.at("state_before");event["state_after"]=expected.at("state_after");
            if(!write)event["result"]=expected.at("result");world_calls_.push_back(event);
            bridge_.label_service_result("authority_reference:"+std::to_string(trace_epoch_)+":"+std::to_string(index));return result(write?Json(nullptr):expected.at("result"));
        }
        if(replay_&&mode_==PersonalMode::TraceReplay){
            auto reject=[&](const std::string& reason){world_calls_.push_back({{"op",name},{"args",values},{"site",site},{"argument_origins",dependencies},{"matched",false},{"rejected",reason}});throw std::runtime_error(reason);};
            if(site.value("ambiguous",true))reject("Ambiguous trace dynamic context");
            const bool void_write=name=="Player.AddCoins"||name=="math.randomseed";
            std::vector<size_t> candidates;
            for(size_t i=trace_cursor_;i<tape.size();++i)if(!matched_[i]&&tape[i].at("op")==name&&tape[i].at("site").at("key")==site.at("key"))candidates.push_back(i);
            if(candidates.size()>1)reject("Ambiguous trace authority event");
            if(candidates.empty()){
                if(void_write){auto validation=*world_;validation.call(name,values);auto event=Json{{"op",name},{"args",values},{"site",site},{"argument_origins",dependencies},{"matched",false}};suppressed.push_back(event);world_calls_.push_back(event);return result(nullptr);}
                reject("Unmatched trace return/query: "+name);
            }
            auto index=candidates[0];const auto& expected=tape[index];
            if(!void_write&&expected.at("args")!=values)reject("Trace authority argument mismatch: "+name);
            if(void_write){auto validation=*world_;validation.call(name,values);suppressed.push_back({{"op",name},{"args",values},{"site",site},{"matched",true},{"authority_event",index}});}
            matched_[index]=true;trace_cursor_=index+1;
            world_calls_.push_back({{"op",name},{"args",values},{"site",site},{"argument_origins",dependencies},{"matched",true},{"authority_event",index},{"state_before",expected.at("state_before")},{"state_after",expected.at("state_after")},{"result",expected.at("result")}});
            bridge_.label_service_result("world_result:"+std::to_string(trace_epoch_)+":"+std::to_string(index)+":"+name);
            return result(expected.at("result"));
        }
        if(replay_&&mode_==PersonalMode::Presentation) {
            // This candidate is deliberately confined to the coin model. No game-world bridge is used.
            if(name=="Player.AddCoins"||name=="math.randomseed") {
                if(suppressed.size()>=8192)throw std::runtime_error("Suppressed write limit");
                auto validation=*world_;validation.call(name,values); // Validate arguments; discard every effect.
                suppressed.push_back({{"op",name},{"args",values}});return result(nullptr);
            }
            if(name=="math.random") {
                // RNG advances authoritative state and returns a value. Never invent a personal result.
                for(size_t i=0;i<tape.size();++i)if(!matched_[i]&&tape[i].at("op")==name&&tape[i].at("args")==values) {
                    matched_[i]=true;return result(tape[i].at("result"));
                }
                throw std::runtime_error("Unmatched return-bearing world mutation: "+name);
            }
            if(name=="Player.GetNumCoins"||name=="Isaac.GetTime"||name=="Game.GetFrameCount"||name=="os.clock"||name=="os.time")return result(world_->call(name,values));
            throw std::runtime_error("Unsupported personal world boundary: "+name);
        }
        if(replay_) {
            if(cursor_>=tape.size())throw std::runtime_error("Shadow added authority world call: "+name);
            const auto& expected=tape[cursor_++];
            if(expected.at("op")!=name||expected.at("args")!=values)throw std::runtime_error("Shadow divergent authority world call: "+name);
            return result(expected.at("result"));
        }
        if(timeline_mode(mode_))point_slice2("world_before");
        if(tape.size()>=8192)throw std::runtime_error("World transcript limit");auto before=tracing_?trace_snapshot(*world_):world_->snapshot();auto output=world_->call(name,values);
        Json event={{"op",name},{"args",values},{"result",output}};
        if((mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))){event["argument_value_ids"]=Json::array();for(int i=3;i<=static_cast<int>(args.size())+1;++i)event["argument_value_ids"].push_back(slice_.value(bridge_.shadow(),i));}
        if(timeline_mode(mode_)){event["callback_anchor"]=callback_stack_.empty()?0:callback_stack_.back();event["state_before_id"]=state_point_;point_slice2("world_after");event["state_after_id"]=state_point_;}
        if(tracing_){
            event["site"]=site;event["argument_origins"]=dependencies;event["state_before"]=before;event["state_after"]=trace_snapshot(*world_);
            bridge_.label_service_result("world_result:"+std::to_string(trace_epoch_)+":"+std::to_string(tape.size())+":"+name);world_calls_.push_back(event);
        }
        tape.push_back(std::move(event));return result(output);
    }
    throw std::runtime_error("Unknown research service: "+op);
}
void NativeModContext::load_enums(const std::string& code) {if(!code.empty())bridge_.run(code,"@authority-frozen-j460-enums");if(tracing_&&slice_.purpose)startup_instructions_+=branches_slice2().at("instructions").get<unsigned>();}
void NativeModContext::load_mod(size_t index) {bridge_.run("__load_entry("+std::to_string(index)+")","@authority-load-entry");}
void NativeModContext::dispatch(int callback) {bridge_.run("__dispatch("+std::to_string(callback)+")","@authority-private-dispatch");}
Json NativeModContext::evaluate(const std::string& code) {return bridge_.run(code,"@authority-inspect");}
Json NativeModContext::summary() {
    auto encoded=bridge_.run("return __context_summary()", "@authority-runtime-summary");
    // Summary is deliberately scalar; no private function, table or native pointer is exported.
    auto hex=encoded.at(0).at("hex").get<std::string>();std::string text;
    for(size_t i=0;i<hex.size();i+=2)text+=static_cast<char>(std::stoi(hex.substr(i,2),nullptr,16));
    return {{"callbacks",Json::parse(text).at("callbacks")},{"modules",modules},{"native_bridge",bridge_.statistics()},{"personal_options",options_}};
}
NativeModSession::NativeModSession(const BridgeLuaApi& api,BridgeLuaState* host,std::string bootstrap,std::string enums,std::vector<FrozenMod> mods,Json stores,bool native_roots,Json option_overrides,PersonalMode mode)
    :api_(api),host_(host),bootstrap_(std::move(bootstrap)),enums_(std::move(enums)),mods_(std::move(mods)),initial_stores_(std::move(stores)),native_roots_(native_roots),mode_(mode) {
    if(!initial_stores_.is_array()||initial_stores_.size()!=2||!initial_stores_[0].is_object()||!initial_stores_[1].is_object())throw std::runtime_error("Two private stores required");
    auto base=native_roots?snapshot_personal_options(api,host):model_options();initial_options_=Json::array();
    if(!option_overrides.is_null()&&(!option_overrides.is_array()||option_overrides.size()!=2))throw std::runtime_error("Two personal option override objects required");
    for(size_t i=0;i<2;++i) {
        auto options=base;
        if(!option_overrides.is_null()) {
            const auto& overrides=option_overrides.at(i);if(!overrides.is_object())throw std::runtime_error("Personal option override must be an object");
            for(auto it=overrides.begin();it!=overrides.end();++it){if(!base.contains(it.key()))throw std::runtime_error("Unsupported personal option override: "+it.key());options[it.key()]=it.value();}
        }
        initial_options_.push_back(validate_options(options));
    }
    initialize();
}
void NativeModSession::initialize() {
    contexts_={};world=NativeWorldModel{};
    for(size_t i=0;i<2;++i){contexts_[i]=std::make_unique<NativeModContext>(api_,host_,bootstrap_,mods_,native_roots_,initial_options_.at(i),mode_==PersonalMode::TraceReplay||(mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_)),ui_mode(mode_));contexts_[i]->store=initial_stores_.at(i);}
    for(auto& context:contexts_)context->load_enums(enums_);
    contexts_[0]->begin(&world,nullptr,mode_);for(size_t i=0;i<mods_.size();++i)contexts_[0]->load_mod(i);contexts_[0]->check();
    if(timeline_mode(mode_)){initial_tape_=contexts_[0]->tape;initial_timeline_=contexts_[0]->timeline_slice2();initial_graph_=contexts_[0]->trace_report().at("value_graph");}
    contexts_[1]->begin(&world,&contexts_[0]->tape,mode_);if(timeline_mode(mode_))contexts_[1]->configure_slice2(initial_timeline_,initial_graph_,Json::array(),false);for(size_t i=0;i<mods_.size();++i)contexts_[1]->load_mod(i);contexts_[1]->check();
}
Json NativeModSession::apply(int64_t frame,int64_t time_ms,const Json& inputs,const std::function<void(const Json&)>& validator) {
    if(!inputs.is_array()||inputs.size()!=2||!inputs[0].is_object()||!inputs[1].is_object())throw std::runtime_error("Two model input objects required");
    NativeWorldModel candidate=world;candidate.frame=frame;candidate.time_ms=time_ms;candidate.effects=Json::array();
    contexts_[0]->input=inputs[0];contexts_[1]->input=inputs[1];
    contexts_[0]->begin(&candidate,nullptr,mode_);contexts_[0]->dispatch(1);contexts_[0]->dispatch(2);contexts_[0]->check();
    if(slice3_mode(mode_))project_personal_slice3(candidate,inputs);
    else if(timeline_mode(mode_))project_personal_slice2(candidate,inputs);
    else{contexts_[1]->begin(&candidate,&contexts_[0]->tape,mode_);contexts_[1]->dispatch(1);contexts_[1]->dispatch(2);contexts_[1]->check();}
    Json output={{"world",candidate.snapshot()},{"effects",candidate.effects},{"transcript",contexts_[0]->tape},
        {"draws",Json::array({contexts_[0]->draws,contexts_[1]->draws})},{"stores",stores()},{"personal_options",personal_options()},{"suppressed",contexts_[1]->suppressed},{"world_kind","coin_model"},{"native_world_committed",false}};
    if(mode_==PersonalMode::TraceReplay||(mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_)))output["execution_dependencies"]=Json::array({contexts_[0]->trace_report(),contexts_[1]->trace_report()});
    if(timeline_mode(mode_))output["branch_search"]=branch_search_;
    if(validator)validator(output); // A rejected oracle rolls back closures, stores, options and draws too.
    world=std::move(candidate);return output;
}
void NativeModSession::recover() {
    if(timeline_mode(mode_)){
        auto accepted_history=history_;history_=Json::array();
        try{initialize();for(const auto& accepted:accepted_history){auto replayed=apply(accepted.at("frame"),accepted.at("time_ms"),accepted.at("inputs"));if(replayed!=accepted.at("output"))throw std::runtime_error("Native model recovery diverged");history_.push_back(accepted);}}
        catch(...){history_=accepted_history;throw;}return;
    }
    initialize();for(const auto& accepted:history_) {
        auto replayed=apply(accepted.at("frame"),accepted.at("time_ms"),accepted.at("inputs"));
        if(replayed!=accepted.at("output"))throw std::runtime_error("Native model recovery diverged");
    }
}
Json NativeModSession::step(int64_t frame,int64_t time_ms,const Json& inputs,const std::function<void(const Json&)>& validator) {
    last_rejection_=nullptr;
    if(!usable_)throw std::runtime_error("Native model session recovery failed; restart required");
    for(const auto& accepted:history_)if(accepted.at("frame")==frame) {
        if(accepted.at("time_ms")!=time_ms||accepted.at("inputs")!=inputs)throw std::runtime_error("Duplicate model frame payload changed");
        auto output=accepted.at("output");output["duplicate"]=true;if(validator)validator(output);return output;
    }
    if(frame!=world.frame+1||time_ms<world.time_ms)throw std::runtime_error("Model frame sequence/time rejected");
    if(history_.size()>=128)throw std::runtime_error("Native model recovery history limit");
    try {
        auto output=apply(frame,time_ms,inputs,validator);history_.push_back({{"frame",frame},{"time_ms",time_ms},{"inputs",inputs},{"output",output}});return output;
    } catch(const std::exception& error) {
        auto message=std::string(error.what());
        if(mode_==PersonalMode::TraceReplay||(mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_)))last_rejection_={{"error",message},{"contexts",Json::array({contexts_[0]->trace_report(),contexts_[1]->trace_report()})},{"stores",stores()},{"draws",Json::array({contexts_[0]->draws,contexts_[1]->draws})},{"personal_options",personal_options()}};
        if(timeline_mode(mode_))last_rejection_["branch_search"]=branch_search_;
        try{recover();}catch(const std::exception& recovery){usable_=false;throw std::runtime_error(message+"; recovery failed: "+recovery.what());}
        throw std::runtime_error(message);
    }
}
Json NativeModSession::stores() const {return Json::array({contexts_[0]->store,contexts_[1]->store});}
Json NativeModSession::personal_options() const {return Json::array({contexts_[0]->personal_options(),contexts_[1]->personal_options()});}
Json NativeModSession::checkpoint() const {
    std::ostringstream rng;rng<<world.rng;
    Json output={{"world",world.snapshot()},{"rng_sha256",sha256_bytes(rng.str())},{"stores",stores()},{"personal_options",personal_options()},
        {"draws",Json::array({contexts_[0]->draws,contexts_[1]->draws})},{"suppressed",contexts_[1]->suppressed}};
    if(mode_==PersonalMode::TraceReplay||(mode_==PersonalMode::ExecutionSlice||timeline_mode(mode_))){auto a=contexts_[0]->trace_report(),b=contexts_[1]->trace_report();a.erase("runtime");b.erase("runtime");output["execution_dependencies"]=Json::array({a,b});}return output;
}
Json NativeModSession::inspect(size_t slot,const std::string& code) {return contexts_.at(slot)->evaluate(code);}
Json probe_mod_runtime(const BridgeLuaApi& api,BridgeLuaState* host,const std::filesystem::path& game,const std::filesystem::path& research) {
    const auto bootstrap_path=research/L"research/native_context.lua";auto bootstrap=read(bootstrap_path);
    auto enums=read(game/L"resources/scripts/enums.lua");
    Json report={{"native_game_used",true},{"playable",false},{"generic_mod_compatibility_passed",false},{"native_world_committed",false},
        {"bootstrap_sha256",sha256_file(bootstrap_path)},{"enums_sha256",sha256_file(game/L"resources/scripts/enums.lua")},
        {"callback_contract_source_sha256",sha256_file(game/L"resources/scripts/main.lua")},{"checks",Json::object()}};
    auto chaos=FrozenMod::directory(research/L"fixtures/legacy_chaos");report["fixture_source_sha256"]=chaos.hashes;
    try {
        auto baseline=snapshot_personal_options(api,host);
        NativeModContext first(api,host,bootstrap,{},true,Json{{"Language","zh"},{"HUDOffset",0.2}});
        NativeModContext second(api,host,bootstrap,{},true,Json{{"Language","en"},{"HUDOffset",0.6}});
        first.evaluate("assert(Options.Language=='zh' and Options.HUDOffset==0.2);local cached=Options;cached.Language='fr';cached.HUDOffset=0.8;assert(cached.Language=='fr')");
        second.evaluate("assert(Options.Language=='en' and Options.HUDOffset==0.6)");
        auto after=snapshot_personal_options(api,host);
        if(after!=baseline||first.personal_options().at("Language")!="fr"||second.personal_options().at("Language")!="en")throw std::runtime_error("Canonical/personal options leaked");
        report["personal_option_probe"]={{"passed",true},{"canonical_before",baseline},{"canonical_after",after},{"private_options",Json::array({first.personal_options(),second.personal_options()})},
            {"native_property_reads_only",true},{"native_options_written",false},{"mod_save_data_written",false},{"actual_eid_language_selection_tested",false}};
    }catch(const std::exception& error){report["personal_option_probe"]={{"passed",false},{"error",error.what()}};}
    const std::string name="Authority Research Legacy Chaos Fixture";
    Json stores=Json::array({Json{{name,Json({{"language","zh"},{"x",24},{"key",76}}).dump()}},Json{{name,Json({{"language","en"},{"x",124},{"key",77}}).dump()}}});
    try {
        NativeModSession session(api,host,bootstrap,enums,{chaos},stores);
        auto vector=session.inspect(0,"local v=Vector(3,4);v.X=6;return v:Length(),(BitSet128(1,2)|BitSet128(4,8)).h");
        if(std::abs(vector[0].at("v").get<double>()-std::sqrt(52.0))>0.0001||vector[1].at("v")!=10)throw std::runtime_error("Native values in mod context failed");
        report["checks"]["real_native_values_in_private_mod_vm"]=true;
        Json frames=Json::array();auto empty=Json::array({Json::object(),Json::object()});
        frames.push_back(session.step(1,1001,empty));
        frames.push_back(session.step(2,1017,Json::array({Json{{"triggered",Json::array({76})}},Json{{"triggered",Json::array({77})}}})));
        auto before=session.world.snapshot();auto duplicate=session.step(2,1017,Json::array({Json{{"triggered",Json::array({76})}},Json{{"triggered",Json::array({77})}}}));
        if(session.world.snapshot()!=before||!duplicate.at("duplicate"))throw std::runtime_error("Native model duplicate failed");
        frames.push_back(session.step(3,1034,empty));report["model_frames"]=frames;
        for(const auto& frame:frames)if(frame.at("effects").size()!=2||frame.at("draws")[0].size()!=1||frame.at("draws")[1].size()!=1)throw std::runtime_error("Mixed callback/model draw count failed");
        if(frames[1]["draws"][0][0]["x"]!=25||frames[1]["draws"][1][0]["x"]!=125)throw std::runtime_error("Native personal input/config failed");
        report["checks"]["unchanged_fixture_callbacks_private_input_config"]=true;
        report["checks"]["mixed_callback_world_model_committed_once"]=true;
        report["checks"]["duplicate_frame_deduplicated"]=true;
    }catch(const std::exception& error){report["fixture_error"]=error.what();}
    try {
        auto fixture=FrozenMod::directory(research/L"fixtures/native_private_ui");auto font=game/L"mods/external item descriptions_836319872/resources/font/eid_default.fnt";
        report["native_ui_fixture_source_sha256"]=fixture.hashes;report["font_asset_sha256"]=sha256_file(font);
        auto config=Json::array({Json{{"Native Private UI Fixture",Json({{"language","zh"},{"key",76},{"x",24},{"font",utf8(font.wstring())}}).dump()}},
            Json{{"Native Private UI Fixture",Json({{"language","en"},{"key",77},{"x",124},{"font",utf8(font.wstring())}}).dump()}}});
        NativeModSession session(api,host,bootstrap,enums,{fixture},config);
        auto empty=Json::array({Json::object(),Json::object()});auto first=session.step(1,100,empty);
        auto accepted=session.step(2,101,Json::array({Json::object(),Json{{"triggered",Json::array({77})}}}));
        if(session.world.coins[0]!=2||accepted["draws"][1][0]["x"]!=125||accepted["draws"][0][0]["x"]!=24)throw std::runtime_error("Native UI value context failed");
        auto world=session.world.snapshot(),saved=session.stores();bool rejected{};
        try{session.step(3,102,Json::array({Json::object(),Json{{"triggered",Json::array({77})},{"pressed",Json::array({999})}}}));}
        catch(const std::exception& error){rejected=std::string(error.what()).find("added authority world call")!=std::string::npos;report["native_ui_rejected_frame_reason"]=error.what();}
        if(!rejected||session.world.snapshot()!=world||session.stores()!=saved)throw std::runtime_error("Native UI failed frame recovery failed");
        auto recovered=session.step(3,102,empty);
        const std::string zh="zh|3|65",en="en|3|65";
        if(recovered["draws"][0][0]["text_hex"]!=byte_hex(zh)||recovered["draws"][1][0]["text_hex"]!=byte_hex(en)||recovered["draws"][1][0]["x"]!=125||session.world.coins[0]!=3)
            throw std::runtime_error("Native upvalue/font/position reconstruction failed");
        report["native_ui_model_frames"]=Json::array({first,accepted,recovered});
        report["checks"]["native_font_cached_method_inside_mod_callback"]=true;
        report["checks"]["native_ui_object_upvalues_reconstructed_after_rejection"]=true;
        report["checks"]["native_ui_failed_frame_world_and_config_rolled_back"]=true;
    }catch(const std::exception& error){report["native_ui_error"]=error.what();}
    report["unmodified_mod_probes"]=Json::array();
    for(const auto& directory:std::vector<std::wstring>{L"mod_config_menu_cn_2494192799",L"external item descriptions_836319872"}) {
        Json item={{"mod",utf8(directory)},{"loaded",false},{"callbacks_dispatched",false},{"generic_compatibility_passed",false}};
        try {
            auto source=FrozenMod::directory(game/L"mods"/directory);item["source_sha256"]=source.hashes;
            NativeModContext context(api,host,bootstrap,{source});NativeWorldModel model;context.begin(&model);context.load_enums(enums);
            try {context.load_mod(0);context.check();item["loaded"]=true;}catch(const std::exception& error){item["error"]=error.what();}
            item["runtime"]=context.summary();item["model_world"]=model.snapshot();
            auto after=FrozenMod::directory(game/L"mods"/directory);item["source_unchanged"]=source.hashes==after.hashes;
        }catch(const std::exception& error){item["error"]=error.what();}
        report["unmodified_mod_probes"].push_back(item);
    }
    Json combined={{"loaded",false},{"callbacks_dispatched",false},{"generic_compatibility_passed",false},{"personal_configuration_and_rendering_tested",false}};
    try {
        std::vector<FrozenMod> sources={FrozenMod::directory(game/L"mods/mod_config_menu_cn_2494192799"),FrozenMod::directory(game/L"mods/external item descriptions_836319872")};
        NativeModContext context(api,host,bootstrap,sources);NativeWorldModel model;context.begin(&model);context.load_enums(enums);
        try {context.load_mod(0);context.load_mod(1);context.check();combined["loaded"]=true;}catch(const std::exception& error){combined["error"]=error.what();}
        combined["runtime"]=context.summary();combined["model_world"]=model.snapshot();combined["source_unchanged"]=true;
        for(const auto& source:sources)combined["source_unchanged"]=combined.at("source_unchanged").get<bool>()&&source.hashes==FrozenMod::directory(source.root).hashes;
    }catch(const std::exception& error){combined["error"]=error.what();}
    report["combined_mcm_eid_private_initialization"]=combined;
    report["personal_mcm_eid_initializations"]=Json::array();
    for(const auto& language:std::vector<std::string>{"zh","en"}) {
        Json item={{"requested_language",language},{"loaded",false},{"callbacks_dispatched",false},{"generic_compatibility_passed",false},{"actual_eid_language_selection_tested",false}};
        try {
            std::vector<FrozenMod> sources={FrozenMod::directory(game/L"mods/mod_config_menu_cn_2494192799"),FrozenMod::directory(game/L"mods/external item descriptions_836319872")};
            NativeModContext context(api,host,bootstrap,sources,true,Json{{"Language",language},{"HUDOffset",language=="zh"?0.2:0.6}});
            NativeWorldModel model;context.begin(&model);context.load_enums(enums);
            try {context.load_mod(0);context.load_mod(1);context.check();item["loaded"]=true;}catch(const std::exception& error){item["error"]=error.what();}
            // If full initialization failed, this is explicitly a partial-source getter check.
            try {
                const auto value=context.evaluate("assert(type(EID)=='table' and type(EID.getLanguage)=='function');return EID:getLanguage()");
                const auto expected=language=="zh"?"zh_cn":"en_us";
                item["eid_language_wire"]=value;
                item["actual_eid_language_selection_tested"]=value.size()==1&&value[0].at("t")=="string"&&value[0].at("hex")==byte_hex(expected);
                item["language_check_after_partial_initialization"]=!item.at("loaded").get<bool>();
            }catch(const std::exception& error){item["language_error"]=error.what();}
            item["runtime"]=context.summary();item["source_unchanged"]=true;
            for(const auto& source:sources)item["source_unchanged"]=item.at("source_unchanged").get<bool>()&&source.hashes==FrozenMod::directory(source.root).hashes;
        }catch(const std::exception& error){item["error"]=error.what();}
        report["personal_mcm_eid_initializations"].push_back(item);
    }
    if(report["personal_option_probe"].value("passed",false)) {
        auto after=snapshot_personal_options(api,host);report["personal_option_probe"]["canonical_after_all_mod_probes"]=after;
        if(after!=report["personal_option_probe"].at("canonical_before"))report["personal_option_probe"]["passed"]=false;
    }
    report["fixture_probe_passed"]=report["checks"].size()==7&&!report.contains("fixture_error")&&!report.contains("native_ui_error");return report;
}
}
