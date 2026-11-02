#include "runtime_suite.hpp"
#include <set>
namespace ia {
namespace {
std::string read_source(const std::filesystem::path& path) {
    if(std::filesystem::file_size(path)>4*1024*1024)throw std::runtime_error("Suite source/manifest size limit");
    std::ifstream file(path,std::ios::binary);if(!file)throw std::runtime_error("Missing suite source");return {(std::istreambuf_iterator<char>(file)),{}};
}
std::filesystem::path child(const std::filesystem::path& base,const std::string& relative) {
    if(relative.empty()||relative.find(':')!=std::string::npos||relative.find('\\')!=std::string::npos||relative.starts_with('/'))throw std::runtime_error("Suite mod path outside roots");
    auto rel=std::filesystem::path(wide(relative));for(const auto& part:rel)if(part==L".."||part==L".")throw std::runtime_error("Suite mod path outside roots");
    auto root=std::filesystem::canonical(base),path=std::filesystem::canonical(root/rel);
    auto checked=path.lexically_relative(root);if(checked.empty()||*checked.begin()==L"..")throw std::runtime_error("Suite mod path outside roots");return path;
}
std::string draw_text(const Json& draw) {
    auto hex=draw.at("text_hex").get<std::string>();std::string bytes;
    for(size_t i=0;i<hex.size();i+=2)bytes+=static_cast<char>(std::stoi(hex.substr(i,2),nullptr,16));return bytes;
}
Json first_difference(const Json& a,const Json& b,const std::string& path="") {
    if(a==b)return nullptr;
    if(a.type()!=b.type())return {{"path",path},{"before",a.type_name()},{"after",b.type_name()}};
    if(a.is_object()){for(auto it=a.begin();it!=a.end();++it){if(!b.contains(it.key()))return {{"path",path+"/"+it.key()},{"missing_after",true}};auto found=first_difference(it.value(),b.at(it.key()),path+"/"+it.key());if(!found.is_null())return found;}return {{"path",path},{"before_size",a.size()},{"after_size",b.size()}};}
    if(a.is_array()){if(a.size()!=b.size())return {{"path",path},{"before_size",a.size()},{"after_size",b.size()}};for(size_t i=0;i<a.size();++i){auto found=first_difference(a[i],b[i],path+"/"+std::to_string(i));if(!found.is_null())return found;}}
    return {{"path",path},{"before",a},{"after",b}};
}
void verify_output(const Json& output,const Json& expect) {
    if(expect.contains("values"))for(auto it=expect.at("values").begin();it!=expect.at("values").end();++it) {
        Json::json_pointer pointer(it.key());
        if(!output.contains(pointer)||output.at(pointer)!=it.value())throw std::runtime_error("Semantic oracle mismatch: "+it.key());
    }
    if(expect.contains("texts")) {
        Json texts=Json::array();for(const auto& slot:output.at("draws")) {
            Json row=Json::array();for(const auto& draw:slot)row.push_back(draw_text(draw));texts.push_back(row);
        }
        if(texts!=expect.at("texts"))throw std::runtime_error("Semantic oracle mismatch: personal draw text");
    }
    if(expect.contains("text_templates")) {
        const auto& templates=expect.at("text_templates");
        for(size_t slot=0;slot<2;++slot) {
            if(templates[slot].size()!=output.at("draws")[slot].size())throw std::runtime_error("Semantic oracle mismatch: draw count");
            for(size_t i=0;i<templates[slot].size();++i) {
                auto wanted=templates[slot][i].get<std::string>();size_t at{};
                while((at=wanted.find("${",at))!=std::string::npos) {
                    auto end=wanted.find('}',at);if(end==std::string::npos)throw std::runtime_error("Suite text template syntax");
                    auto value=output.at(Json::json_pointer(wanted.substr(at+2,end-at-2)));
                    auto replacement=value.is_string()?value.get<std::string>():value.dump();wanted.replace(at,end-at+1,replacement);at+=replacement.size();
                }
                if(draw_text(output.at("draws")[slot][i])!=wanted)throw std::runtime_error("Semantic oracle mismatch: personal draw text");
            }
        }
    }
}
}
FrozenRuntimeSuite FrozenRuntimeSuite::load(const std::filesystem::path& file,const std::filesystem::path& game,const std::filesystem::path& research,bool allow_trace) {
    FrozenRuntimeSuite suite;auto bytes=read_source(file);suite.digest=sha256_bytes(bytes);suite.manifest=Json::parse(bytes);
    const auto& manifest=suite.manifest;
    if(manifest.value("mode",std::string{})=="slice3-ui")throw std::runtime_error("Slice3 UI requires its standalone runner; game integration refused");
    if(manifest.value("mode",std::string{})=="ui-bounded"||manifest.value("mode",std::string{})=="ui-incremental")throw std::runtime_error("Bounded UI requires its standalone runner; game integration refused");
    if(manifest.at("schema")!="isaac-runtime-suite-1"||!manifest.at("cases").is_array()||manifest.at("cases").empty()||manifest.at("cases").size()>64)throw std::runtime_error("Suite schema/case limit");
    suite.bootstrap=read_source(research/L"research/native_context.lua");suite.enums=read_source(game/L"resources/scripts/enums.lua");
    if(manifest.at("bootstrap_sha256")!=sha256_bytes(suite.bootstrap)||manifest.at("enums_sha256")!=sha256_bytes(suite.enums))throw std::runtime_error("Suite bootstrap/enums hash mismatch");
    std::set<std::string> ids;std::map<std::string,FrozenMod> shared;size_t total_frames{},frozen_bytes{},copied_bytes{};
    for(const auto& definition:manifest.at("cases")) {
        auto id=definition.at("id").get<std::string>();auto mode=definition.at("mode").get<std::string>();
        if(mode=="slice3"&&manifest.value("view_rule",std::string{})!="personal-settings-authority-hud-v1")throw std::runtime_error("Slice3 requires frozen view rule personal-settings-authority-hud-v1");
        if(mode=="trace"&&!allow_trace)throw std::runtime_error("Trace suite is standalone only; game integration refused");
        if((mode=="slice"||mode=="slice2"||mode=="slice3")&&!allow_trace)throw std::runtime_error("Slice suite is standalone only; game integration refused");
        if(id.empty()||id.size()>80||!ids.insert(id).second||(mode!="strict"&&mode!="presentation"&&mode!="trace"&&mode!="slice"&&mode!="slice2"&&mode!="slice3"))throw std::runtime_error("Suite case identity/mode");
        if(mode=="trace"&&definition.value("native_roots",false))throw std::runtime_error("Trace suite cannot use game/native roots");
        if((mode=="slice"||mode=="slice2"||mode=="slice3")&&definition.value("native_roots",false))throw std::runtime_error("Slice suite cannot use game/native roots");
        if(!definition.at("stores").is_array()||definition.at("stores").size()!=2||!definition.at("stores")[0].is_object()||!definition.at("stores")[1].is_object())throw std::runtime_error("Suite requires two stores");
        if(!definition.at("mods").is_array()||definition.at("mods").empty()||definition.at("mods").size()>16)throw std::runtime_error("Suite mod count");
        if(!definition.at("frames").is_array()||definition.at("frames").size()>128)throw std::runtime_error("Suite frame limit");
        total_frames+=definition.at("frames").size();if(total_frames>256)throw std::runtime_error("Suite total frame limit");
        if(definition.at("frames").empty()&&!definition.contains("inspect"))throw std::runtime_error("Suite missing functional expectations");
        for(const auto& frame:definition.at("frames")) {
            if(!frame.at("frame").is_number_integer()||!frame.at("time_ms").is_number_integer()||!frame.at("inputs").is_array()||frame.at("inputs").size()!=2)throw std::runtime_error("Suite frame schema");
            const auto& expect=frame.at("expect");auto outcome=expect.at("outcome").get<std::string>();
            if(outcome!="accept"&&outcome!="reject")throw std::runtime_error("Suite expected outcome");
            if(outcome=="reject"&&expect.at("error_contains").get<std::string>().empty())throw std::runtime_error("Suite missing rejection boundary");
            if(outcome=="accept"&&!expect.contains("values")&&!expect.contains("texts")&&!expect.contains("text_templates"))throw std::runtime_error("Suite missing result oracle");
            if(expect.contains("values")){if(!expect.at("values").is_object()||expect.at("values").empty())throw std::runtime_error("Suite value oracle schema");for(auto it=expect.at("values").begin();it!=expect.at("values").end();++it){Json::json_pointer pointer(it.key());}}
            if(expect.contains("texts")&&(!expect.at("texts").is_array()||expect.at("texts").size()!=2))throw std::runtime_error("Suite draw oracle schema");
        }
        RuntimeSuiteCase item{definition,{}};
        for(const auto& selected:definition.at("mods")) {
            auto base=selected.at("base").get<std::string>(),relative=selected.at("root").get<std::string>();
            if(base!="game"&&base!="research")throw std::runtime_error("Suite source base");
            auto key=base+":"+relative;auto found=shared.find(key);
            if(found==shared.end()) {
                found=shared.emplace(key,FrozenMod::directory(child(base=="game"?game:research,relative))).first;
                for(const auto& [name,code]:found->second.files){(void)name;frozen_bytes+=code.size();}
                if(frozen_bytes>32*1024*1024)throw std::runtime_error("Suite frozen source budget");
            }
            if(selected.at("sha256")!=found->second.hashes)throw std::runtime_error("Suite frozen mod hash mismatch: "+relative);
            for(const auto& [name,code]:found->second.files){(void)name;copied_bytes+=code.size();}
            if(copied_bytes>64*1024*1024)throw std::runtime_error("Suite context source budget");
            item.mods.push_back(found->second);
        }
        suite.cases.push_back(std::move(item));
    }
    return suite;
}
Json run_runtime_suite(const BridgeLuaApi& api,BridgeLuaState* host,const FrozenRuntimeSuite& suite,bool native_game) {
    Json report={{"schema","isaac-runtime-suite-result-1"},{"manifest_sha256",suite.digest},{"cases",Json::array()},
        {"fresh_private_contexts_per_case",true},{"native_game_used",native_game},{"native_world_committed",false},{"playable",false},
        {"expected_outcomes_passed",0},{"failed",0},{"skipped",0},{"mode_results",Json::object()},{"presentation_gate_passed",true},{"generic_mod_compatibility_passed",false}};
    for(const auto& item:suite.cases) {
        const auto& def=item.definition;auto top=api.gettop(host);
        Json result={{"id",def.at("id")},{"mode",def.at("mode")},{"frames",Json::array()},{"source_sha256",Json::array()},
            {"first_unsupported_entry",nullptr},{"restoration","not_needed"},{"passed",true},{"compatibility_passed",true}};
        for(size_t i=0;i<item.mods.size();++i)result["source_sha256"].push_back({{"root",def.at("mods")[i].at("root")},{"sha256",item.mods[i].hashes}});
        const bool native=def.value("native_roots",false);
        if(native&&!native_game) {
            result["status"]="unverified_requires_game";result["passed"]=false;result["compatibility_passed"]=false;
            report["skipped"]=report.at("skipped").get<int>()+1;
        }else {
            try {
                NativeModSession session(api,host,suite.bootstrap,def.value("load_enums",false)?suite.enums:"",item.mods,def.at("stores"),native,def.value("options",Json(nullptr)),
                    def.at("mode")=="slice3"?PersonalMode::ExecutionSlice3: def.at("mode")=="slice2"?PersonalMode::ExecutionSlice2:(def.at("mode")=="slice"?PersonalMode::ExecutionSlice:(def.at("mode")=="trace"?PersonalMode::TraceReplay:(def.at("mode")=="presentation"?PersonalMode::Presentation:PersonalMode::StrictReplay))));
                for(const auto& action:def.at("frames")) {
                    const auto& expect=action.at("expect");auto before=session.checkpoint();Json frame={{"frame",action.at("frame")},{"passed",false}};
                    Json candidate=nullptr;std::string error;
                    try {
                        auto output=session.step(action.at("frame").get<int64_t>(),action.at("time_ms").get<int64_t>(),action.at("inputs"),[&](const Json& value){candidate=value;verify_output(value,expect);});
                        frame["outcome"]="accept";frame["output"]=std::move(output);frame["passed"]=expect.at("outcome")=="accept";
                        if(frame["output"].value("duplicate",false))frame["duplicate_state_unchanged"]=session.checkpoint()==before;
                        if(frame.contains("duplicate_state_unchanged")&&!frame.at("duplicate_state_unchanged").get<bool>())frame["passed"]=false;
                    }catch(const std::exception& err) {
                        error=err.what();frame["outcome"]="reject";frame["error"]=error;auto restored=session.checkpoint();frame["rollback_passed"]=restored==before;
                        if(restored!=before)frame["rollback_difference"]=first_difference(before,restored);
                        if(!session.rejection_report().is_null())frame["execution_dependencies_at_rejection"]=session.rejection_report();
                        if(!candidate.is_null())frame["rejected_candidate"]=candidate;
                        frame["passed"]=expect.at("outcome")=="reject"&&error.find(expect.value("error_contains",std::string{}))!=std::string::npos&&frame.at("rollback_passed").get<bool>();
                        result["restoration"]=frame.at("rollback_passed").get<bool>()?"passed":"failed";
                        if(result["first_unsupported_entry"].is_null())result["first_unsupported_entry"]=error;
                        if(action.value("gate_required",false))result["compatibility_passed"]=false;
                    }
                    if(!frame.at("passed").get<bool>())result["passed"]=false;
                    result["frames"].push_back(std::move(frame));
                    if(!result.at("passed").get<bool>())break;
                }
                if(result.at("passed").get<bool>()&&def.contains("inspect"))for(const auto& inspection:def.at("inspect")) {
                    auto actual=session.inspect(inspection.at("slot").get<size_t>(),inspection.at("code").get<std::string>());
                    if(actual!=inspection.at("expected"))throw std::runtime_error("Suite private inspection mismatch");
                }
            }catch(const std::exception& err) {
                result["passed"]=false;result["compatibility_passed"]=false;result["error"]=err.what();
                if(result["first_unsupported_entry"].is_null())result["first_unsupported_entry"]=err.what();
            }
            bool unchanged=true;for(const auto& mod:item.mods)if(FrozenMod::directory(mod.root).hashes!=mod.hashes)unchanged=false;
            result["source_unchanged"]=unchanged;result["host_stack_restored"]=api.gettop(host)==top;
            if(!unchanged||!result.at("host_stack_restored").get<bool>())result["passed"]=false;
            result["status"]=result.at("passed").get<bool>()?"expected_outcome_verified":"failed";
            auto key=result.at("passed").get<bool>()?"expected_outcomes_passed":"failed";report[key]=report.at(key).get<int>()+1;
        }
        if(!result.at("compatibility_passed").get<bool>()||!result.at("passed").get<bool>())report["presentation_gate_passed"]=false;
        auto mode=def.at("mode").get<std::string>();
        if(!report["mode_results"].contains(mode))report["mode_results"][mode]={{"cases",0},{"expected_outcomes_passed",0},{"failed",0},{"skipped",0},{"compatibility_gate_passed",true}};
        auto& group=report["mode_results"][mode];group["cases"]=group["cases"].get<int>()+1;
        auto count_key=result.at("status")=="unverified_requires_game"?"skipped":(result.at("passed").get<bool>()?"expected_outcomes_passed":"failed");group[count_key]=group[count_key].get<int>()+1;
        if(!result.at("compatibility_passed").get<bool>()||!result.at("passed").get<bool>())group["compatibility_gate_passed"]=false;
        report["cases"].push_back(std::move(result));
    }
    // Success means the diagnostic expectations were met, including explicit incompatibility examples.
    report["diagnostic_passed"]=report.at("failed")==0;
    if(report["mode_results"].contains("trace"))report["trace_mode_gate_passed"]=report["mode_results"]["trace"]["compatibility_gate_passed"];
    if(report["mode_results"].contains("slice2"))report["slice2_mode_gate_passed"]=report["mode_results"]["slice2"]["compatibility_gate_passed"];
    if(report["mode_results"].contains("slice"))report["slice_mode_gate_passed"]=report["mode_results"]["slice"]["compatibility_gate_passed"];
    return report;
}
}
