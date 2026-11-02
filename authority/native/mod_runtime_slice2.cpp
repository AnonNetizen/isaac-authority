#include "mod_runtime.hpp"
#include <deque>
#include <set>
#include <cmath>
namespace ia { namespace {
bool write_op(const std::string& op){return op=="Player.AddCoins"||op=="math.randomseed";}
Json role(const Json& site){Json key=Json::array();for(const auto& f:site.at("path"))key.push_back({{"source_sha256",f.at("source_sha256")},{"prototype",f.at("prototype")},{"instruction",f.at("instruction")},{"loops",f.at("loops")}});return key;}
bool reaches_pc(const Json& graph,const Json& from,const Json& to){
    if(from.at("source_sha256")!=to.at("source_sha256")||from.at("prototype")!=to.at("prototype"))return true;
    const Json* cfg=nullptr;for(const auto& c:graph.at("code"))if(c.at("source_sha256")==from.at("source_sha256")&&c.at("prototype")==from.at("prototype"))cfg=&c.at("cfg");
    if(!cfg)return true;std::vector<int> todo{from.at("instruction").get<int>()};std::set<int> seen;int target=to.at("instruction");
    while(!todo.empty()){auto pc=todo.back();todo.pop_back();if(pc==target)return true;if(pc<0||pc>=static_cast<int>(cfg->size())||!seen.insert(pc).second)continue;for(const auto& e:cfg->at(pc).at("successors"))todo.push_back(e.get<int>());}return false;
}
Json callback_frame(const Json& site,const Json& entry){for(const auto& f:site.at("path"))if(f.at("source_sha256")==entry.at("function").at("source_sha256")&&f.at("prototype")==entry.at("function").at("prototype"))return f;throw std::runtime_error("Slice2 missing callback frame proof");}
bool may_precede_query(const Json& graph,const Json& writer,const Json& query,const Json& entry){
    const auto& from=writer.at("path");const auto& to=query.at("path");size_t a{},b{};
    auto is_callback=[&](const Json& f){return f.at("source_sha256")==entry.at("function").at("source_sha256")&&f.at("prototype")==entry.at("function").at("prototype");};
    while(a<from.size()&&!is_callback(from[a]))++a;while(b<to.size()&&!is_callback(to[b]))++b;
    if(a==from.size()||b==to.size())throw std::runtime_error("Slice2 missing callback flow proof");
    Json left=from[a],right=to[b];
    for(;a<from.size()&&b<to.size();++a,++b){
        if(from[a].at("source_sha256")!=to[b].at("source_sha256")||from[a].at("prototype")!=to[b].at("prototype"))break;
        left=from[a];right=to[b];if(left.at("loops")!=right.at("loops"))return true;
        if(left.at("instruction")!=right.at("instruction"))break;
    }
    return reaches_pc(graph,left,right);
}
Json query_snapshot(const std::string& op,const Json& args,const Json& state){
    if(op=="Player.GetNumCoins"){if(args.size()!=1||!args[0].is_number_integer()||args[0].get<int64_t>()<0||args[0].get<int64_t>()>1)throw std::runtime_error("Slice2 snapshot player target");return state.at("coins")[args[0].get<size_t>()];}
    if(!args.empty())throw std::runtime_error("Slice2 snapshot query arity");
    if(op=="Isaac.GetTime")return state.at("time_ms");if(op=="Game.GetFrameCount")return state.at("frame");
    if(op=="os.time")return state.at("time_ms").get<int64_t>()/1000;if(op=="os.clock")return state.at("time_ms").get<double>()/1000.0;
    throw std::runtime_error("Unsupported slice2 snapshot query: "+op);
}
Json authority_owner(const Json& graph,unsigned root,const Json& owner,const Json& value){
    if(owner.is_null())return nullptr;std::vector<unsigned> todo{root};std::set<unsigned> seen;Json found=Json::array();
    // Different table/closure instances need an allocation-context proof that
    // this bounded candidate does not yet supply. A shared prototype is not it.
    if(owner.at("kind")=="field"||owner.at("kind")=="upvalue"){
        std::set<unsigned> instances;for(const auto& record:graph.at("storage_versions"))if(record.at("owner_base")==owner.at("owner_base"))instances.insert(record.at("owner").get<unsigned>());
        if(instances.size()!=1)throw std::runtime_error("Ambiguous slice2 authority heap instance");
    }
    while(!todo.empty()){auto id=todo.back();todo.pop_back();if(!id||id>graph.at("nodes").size()||!seen.insert(id).second)continue;if(seen.size()>16384)throw std::runtime_error("Slice2 producer walk budget");const auto& n=graph.at("nodes")[id-1];
        if(n.at("operation")=="storage_version"&&n.at("detail").at("owner_base")==owner.at("owner_base")&&n.at("value").contains("value")&&n.at("value").at("value")==value){found.push_back(id);continue;}
        for(const auto& parent:n.at("data"))todo.push_back(parent.get<unsigned>());
    }
    if(found.size()!=1)throw std::runtime_error("Ambiguous slice2 authority storage producer");return found[0];
}
}
void NativeModContext::point_slice2(const std::string& kind,Json entry){
    if(timeline_.size()>=32768)throw std::runtime_error("Slice2 timeline budget");state_point_=timeline_.size();
    std::ostringstream rng;rng<<world_->rng;
    timeline_.push_back({{"id",state_point_},{"kind",kind},{"entry",entry},{"parent",callback_stack_.empty()?0:callback_stack_.back()},{"state",world_->snapshot()},{"rng_sha256",sha256_bytes(rng.str())}});
}
void NativeModContext::configure_slice2(const Json& timeline,const Json& graph,const Json& choices,bool search,unsigned limit){
    timeline_=timeline;authority_graph_=graph;auto j=Json{{"choices",choices},{"search",search},{"instruction_limit",limit}}.dump();slice_.schedule(bridge_.shadow(),j.c_str());
}
Json NativeModContext::branches_slice2() const {return Json::parse(slice_.branches(bridge_.shadow()));}
Json NativeModContext::finish_slice2() const {return Json::parse(slice_.finish(bridge_.shadow()));}
Json NativeModContext::staged_slice2() const {return {{"stores",store},{"personal_options",options_},{"events",staged_events_},{"pending_draws",pending_draws_},{"projection",projection_},{"query_anchors",query_anchors_}};}
void NativeModContext::finalize_draws_slice2(){
    for(const auto& draw:pending_draws_){Json values=draw.at("args");for(size_t n=0;n<7;++n){auto expression=draw.at("expressions")[n].get<unsigned>();if(slice3_mode(mode_)&&draw.at("purpose").at("view")=="game"){auto resolved=Json::parse(slice_.view_resolve(bridge_.shadow(),draw.at("value_ids")[n]));if(!resolved.at("ok").get<bool>())throw std::runtime_error(resolved.at("error").get<std::string>());values[n]=resolved.at("value");expression=0;}if(expression){auto resolved=Json::parse(slice_.resolve(bridge_.shadow(),expression));if(!resolved.at("ok").get<bool>())throw std::runtime_error(resolved.at("error").get<std::string>());values[n]=resolved.at("value");}
        for(const auto& root:ambiguous_draw_roots_)if(slice_.uses(bridge_.shadow(),draw.at("value_ids")[n],root))throw std::runtime_error("Ambiguous slice draw: personal setting also drives world contribution");}
        if(!values[0].is_string()||values[0].get_ref<const std::string&>().size()>65536)throw std::runtime_error("Slice2 draw text limit");for(size_t n=1;n<7;++n)if(!values[n].is_number()||!std::isfinite(values[n].get<double>()))throw std::runtime_error("Slice2 draw number required");
        std::string encoded;const char* hex="0123456789abcdef";for(unsigned char c:values[0].get_ref<const std::string&>()){encoded+=hex[c>>4];encoded+=hex[c&15];}
        draws.push_back({{"op","text"},{"text_hex",encoded},{"x",values[1]},{"y",values[2]},{"color",{{"r",values[3]},{"g",values[4]},{"b",values[5]},{"a",values[6]}}}});draw_value_ids_.push_back(draw.at("value_ids"));
        draw_origins_.push_back({{"text",draw.at("origins")[0]},{"x",draw.at("origins")[1]},{"y",draw.at("origins")[2]}});
    }pending_draws_=Json::array();
}
Json NativeModContext::service_slice2(const std::string& name,const Json& values,const Json& site,const Json&){
    Json event={{"op",name},{"args",values},{"site",site},{"executed",false},{"world_committed",false},{"argument_value_ids",Json::array()}};
    for(size_t n=0;n<values.size();++n)event["argument_value_ids"].push_back(slice_.value(bridge_.shadow(),static_cast<int>(n)+3));
    auto reject=[&](const std::string& why)->void{event["rejected"]=why;world_calls_.push_back(event);throw std::runtime_error(why);};
    if(name=="math.random"){
        if(values.size()>2)reject("Model random arity");
        if(std::none_of(values.begin(),values.end(),[](const Json& v){return v.is_object();})&&!values.empty()){
            for(const auto& value:values)if(!value.is_number_integer())reject("Model integer argument required");
            auto low=values.size()==1?1:values[0].get<int64_t>(),high=values.back().get<int64_t>();if(low>high||low<INT32_MIN||high>INT32_MAX)reject("Model random interval");
        }
        event["deferred"]=true;world_calls_.push_back(event);return Json::array({Json{{"__ia_new_deferred",event}}});
    }
    auto callback=callback_stack_.empty()?0:callback_stack_.back();
    if(!write_op(name)){
        if(state_point_>=timeline_.size())reject("Ambiguous slice2 query state point");
        for(size_t i=0;i<tape.size();++i)if(!matched_[i]&&write_op(tape[i].at("op"))&&tape[i].value("callback_anchor",size_t(0))==callback){
            if(callback==0)reject("Ambiguous slice2 query before unmatched initialization write");
            auto entry=timeline_.at(callback).at("entry");if(may_precede_query(authority_graph_,tape[i].at("site"),site,entry))reject("Ambiguous slice2 query state point crosses unmatched world write");
        }
        auto output=query_snapshot(name,values,timeline_.at(state_point_).at("state"));event["state_point"]=state_point_;event["result"]=output;event["anchor_kind"]=timeline_[state_point_].at("kind");event["proof"]="unique_callback_frontier_without_unmatched_predecessor_write";query_anchors_.push_back(event);world_calls_.push_back(event);
        bridge_.label_service_result("authority_reference:"+std::to_string(trace_epoch_)+":state:"+std::to_string(state_point_));return Json::array({output});
    }
    if(site.value("ambiguous",true))reject("Ambiguous slice2 consumer loop context");std::vector<size_t> candidates;
    for(size_t i=0;i<tape.size();++i)if(!matched_[i]&&tape[i].at("op")==name&&tape[i].value("callback_anchor",size_t(0))==callback&&role(tape[i].at("site"))==role(site))candidates.push_back(i);
    if(candidates.size()>1)reject("Ambiguous slice2 authority consumer");
    if(candidates.empty()){
        if(std::none_of(values.begin(),values.end(),[](const Json& v){return v.is_object();})){auto validation=*world_;validation.call(name,values);event["matched"]=false;suppressed.push_back(event);world_calls_.push_back(event);return Json::array({nullptr});}
        reject("Unmatched slice2 world contribution");
    }
    auto index=candidates[0];const auto& expected=tape[index];if(values.size()!=expected.at("args").size()||(name=="Player.AddCoins"&&values[0]!=expected.at("args")[0]))reject("Slice2 world target mismatch");
    for(size_t n=0;n<values.size();++n){auto pending=Json::parse(slice_.pending(bridge_.shadow(),static_cast<int>(n)+3));if(!pending.is_null()){
        Json owner;try{owner=authority_owner(authority_graph_,expected.at("argument_value_ids")[n],pending.at("owner"),expected.at("args")[n]);}catch(const std::exception& e){reject(e.what());}
        auto evidence=Json{{"value",expected.at("args")[n]},{"authority_event",index},{"authority_value_id",expected.at("argument_value_ids")[n]},{"authority_owner_version",owner},{"personal_expression_id",pending.at("expression")},{"personal_owner",pending.at("owner")},{"operation",name},{"argument",n},{"authority_site",expected.at("site")},{"personal_site",site},{"state_point_before",expected.at("state_before_id")},{"state_point_after",expected.at("state_after_id")},{"binding_kind","storage_version_and_consumer_reference"}};
        auto text=evidence.dump();auto answer=Json::parse(slice_.bind(bridge_.shadow(),pending.at("expression"),text.c_str()));if(!answer.at("ok").get<bool>())reject(answer.at("error").get<std::string>());projection_.push_back(evidence);
    }else if(slice3_mode(mode_)&&!(name=="Player.AddCoins"&&n==0)){auto id=slice_.value(bridge_.shadow(),static_cast<int>(n)+3);auto evidence=Json{{"value",expected.at("args")[n]},{"authority_event",index},{"authority_value_id",expected.at("argument_value_ids")[n]},{"operation",name},{"argument",n},{"authority_site",expected.at("site")},{"personal_site",site},{"state_point_before",expected.at("state_before_id")},{"state_point_after",expected.at("state_after_id")},{"binding_kind","unique_world_consumer_dual_view"}};auto text=evidence.dump();auto answer=Json::parse(slice_.view_bind(bridge_.shadow(),id,text.c_str()));if(!answer.at("ok").get<bool>())reject(answer.at("error").get<std::string>());evidence["personal_version"]=answer.at("producer");projection_.push_back(evidence);}else if(values[n]!=expected.at("args")[n])ambiguous_draw_roots_.push_back(slice_.value(bridge_.shadow(),static_cast<int>(n)+3));}
    matched_[index]=true;state_point_=expected.at("state_after_id");event["authority_event"]=index;event["state_point"]=state_point_;suppressed.push_back(event);world_calls_.push_back(event);return Json::array({nullptr});
}
std::unique_ptr<NativeModContext> NativeModSession::rebuild_personal_slice2(unsigned limit,unsigned& cost){
    cost=0;
    auto context=std::make_unique<NativeModContext>(api_,host_,bootstrap_,mods_,false,initial_options_.at(1),true,ui_mode(mode_));context->store=initial_stores_.at(1);context->load_enums(enums_);
    if(slice3_mode(mode_))cost=context->startup_instructions_slice3();
    if(cost>=limit)throw std::runtime_error("Slice3 initialization instruction budget exceeded");
    auto execute=[&](auto fn){try{fn();}catch(...){cost+=context->branches_slice2().at("instructions").get<unsigned>();throw;}cost+=context->branches_slice2().at("instructions").get<unsigned>();};
    NativeWorldModel scratch;context->begin(&scratch,&initial_tape_,mode_);context->configure_slice2(initial_timeline_,initial_graph_,Json::array(),false,limit-cost);execute([&]{for(size_t n=0;n<mods_.size();++n)context->load_mod(n);context->check();});
    for(const auto& accepted:history_){
        if(cost>=limit)throw std::runtime_error("Slice2 reconstruction instruction budget exceeded");
        const auto& output=accepted.at("output");scratch.frame=accepted.at("frame");scratch.time_ms=accepted.at("time_ms");context->input=accepted.at("inputs")[1];context->begin(&scratch,&output.at("transcript"),mode_);const auto& host=output.at("execution_dependencies")[0];context->configure_slice2(host.at("state_timeline"),host.at("value_graph"),output.at("branch_search").at("selected_choices"),true,limit-cost);
        execute([&]{context->dispatch(1);context->dispatch(2);if(slice3_mode(mode_))context->branch_purposes_slice3(output.at("branch_search").at("branch_purposes"));auto proof=context->finish_slice2();if(!proof.at("resolved").get<bool>()||!proof.at("consistent").get<bool>())throw std::runtime_error("Slice2 accepted history branch recovery failed");context->check();});
        auto expected=output.at("execution_dependencies")[1],actual=context->trace_report();expected.erase("runtime");actual.erase("runtime");
        if(context->store!=output.at("stores")[1]||context->personal_options()!=output.at("personal_options")[1]||context->draws!=output.at("draws")[1]||actual!=expected)throw std::runtime_error("Slice2 private history reconstruction diverged");}
    return context;
}
void NativeModSession::project_personal_slice2(NativeWorldModel& candidate,const Json& inputs){
    auto host=contexts_[0]->trace_report();std::deque<Json> pending{Json::array()};Json attempts=Json::array();std::unique_ptr<NativeModContext> selected;Json selected_choices;unsigned instructions{};bool unresolved=false;
    branch_search_={{"attempts",attempts},{"total_instructions",0},{"selected_choices",nullptr},{"host_execution_count",1},{"staged_committed",false},{"path_limit",32},{"guard_limit",8},{"instruction_limit",2000000}};
    while(!pending.empty()){
        if(attempts.size()>=32){branch_search_["failure"]="path_budget";throw std::runtime_error("Slice2 exploration path budget exceeded");}
        if(instructions>=2000000){branch_search_["failure"]="instruction_budget";throw std::runtime_error("Slice2 exploration instruction budget exceeded");}
        auto choices=pending.front();pending.pop_front();unsigned reconstruction{};std::unique_ptr<NativeModContext> context;
        try{context=rebuild_personal_slice2(2000000-instructions,reconstruction);}catch(const std::exception& e){instructions+=reconstruction;attempts.push_back({{"choices",choices},{"instructions",reconstruction},{"reconstruction_instructions",reconstruction},{"frame_instructions",0},{"outcome","reconstruction_refused"},{"error",e.what()}});branch_search_["attempts"]=attempts;branch_search_["total_instructions"]=instructions;branch_search_["failure"]=e.what();throw;}
        instructions+=reconstruction;
        if(instructions>=2000000){attempts.push_back({{"choices",choices},{"instructions",reconstruction},{"reconstruction_instructions",reconstruction},{"frame_instructions",0},{"outcome","instruction_budget"}});branch_search_["attempts"]=attempts;branch_search_["total_instructions"]=instructions;throw std::runtime_error("Slice2 exploration instruction budget exceeded");}
        context->input=inputs[1];context->begin(&candidate,&contexts_[0]->tape,mode_);context->configure_slice2(host.at("state_timeline"),host.at("value_graph"),choices,true,2000000-instructions);
        std::string error;try{context->dispatch(1);context->dispatch(2);}catch(const std::exception& e){error=e.what();}
        auto status=context->branches_slice2();auto frame_cost=status.at("instructions").get<unsigned>();instructions+=frame_cost;Json attempt={{"choices",choices},{"instructions",reconstruction+frame_cost},{"reconstruction_instructions",reconstruction},{"frame_instructions",frame_cost},{"guards",status.at("guards")}};
        if(status.at("needs_choice").get<bool>()){
            if(choices.size()>=8)throw std::runtime_error("Slice2 unresolved branch budget exceeded");for(bool value:{true,false}){auto next=choices;next.push_back(value);pending.push_front(next);}attempt["outcome"]="needs_choice";
        }else{
            auto proof=context->finish_slice2();attempt["proof"]=proof;if(proof.at("resolved").get<bool>()&&!proof.at("consistent").get<bool>())attempt["outcome"]="inconsistent";
            else if(!error.empty()||!proof.at("resolved").get<bool>()){attempt["outcome"]="unresolved";attempt["error"]=error.empty()?proof.value("error",std::string{}):error;unresolved=true;}
            else{try{context->check();if(selected)throw std::runtime_error("Ambiguous slice2 multiple consistent branches");selected_choices=choices;selected=std::move(context);attempt["outcome"]="consistent";}catch(const std::exception& e){attempt["outcome"]="unresolved";attempt["error"]=e.what();unresolved=true;}}
        }
        if(slice3_mode(mode_)){auto evaluated=context?context->branches_slice2():selected->branches_slice2();auto extra=evaluated.at("instructions").get<unsigned>()-frame_cost;instructions+=extra;attempt["projection_instructions"]=extra;attempt["instructions"]=attempt.at("instructions").get<unsigned>()+extra;attempt["frame_instructions"]=frame_cost+extra;}
        if(context)attempt["staged_discarded"]=context->staged_slice2();
        attempts.push_back(attempt);branch_search_["attempts"]=attempts;branch_search_["total_instructions"]=instructions;branch_search_["selected_choices"]=selected_choices;
        if(error.find("budget exceeded")!=std::string::npos){branch_search_["failure"]=error;throw std::runtime_error(error);}
        if(instructions>=2000000&&!pending.empty())throw std::runtime_error("Slice2 exploration instruction budget exceeded");
    }
    if(unresolved||!selected){std::string reason="Slice2 unresolved or nonunique path";for(const auto& a:attempts)if(a.contains("error")){reason+=": "+a.at("error").get<std::string>();break;}throw std::runtime_error(reason);}
    contexts_[1]=std::move(selected);branch_search_["staged_committed"]=true;
}
}
