#include "mod_runtime.hpp"
#include <deque>
#include <set>
namespace ia {
void NativeModContext::branch_purposes_slice3(const Json& keys){auto text=Json{{"action","branch_roles"},{"keys",keys}}.dump();auto result=Json::parse(slice_.purpose(bridge_.shadow(),text.c_str()));if(!result.at("ok").get<bool>())throw std::runtime_error(result.at("error").get<std::string>());}
void NativeModContext::limit_slice3(unsigned remaining){auto text=Json{{"action","remaining_budget"},{"remaining",remaining}}.dump();auto result=Json::parse(slice_.purpose(bridge_.shadow(),text.c_str()));if(!result.at("ok").get<bool>())throw std::runtime_error(result.at("error").get<std::string>());}
void NativeModSession::project_personal_slice3(NativeWorldModel& candidate,const Json& inputs){
    struct Path {std::unique_ptr<NativeModContext> context;size_t attempt;std::string error;unsigned charged;};
    auto host=contexts_[0]->trace_report();std::deque<Json> pending{Json::array()};Json attempts=Json::array(),role_proofs=Json::array();std::vector<Path> complete;std::set<std::string> roles;unsigned instructions{};
    branch_search_={{"attempts",attempts},{"total_instructions",0},{"selected_choices",nullptr},{"branch_purposes",Json::array()},{"host_execution_count",1},{"staged_committed",false},{"path_limit",32},{"guard_limit",8},{"instruction_limit",2000000},{"view_rule","personal-settings-authority-hud-v1"}};
    auto publish=[&]{branch_search_["attempts"]=attempts;branch_search_["total_instructions"]=instructions;branch_search_["branch_purposes"]=roles;branch_search_["branch_purpose_proofs"]=role_proofs;};
    while(!pending.empty()){
        if(attempts.size()>=32){publish();throw std::runtime_error("Slice3 exploration path budget exceeded");}
        if(instructions>=2000000){publish();throw std::runtime_error("Slice3 exploration instruction budget exceeded");}
        auto choices=pending.front();pending.pop_front();unsigned reconstruction{};std::unique_ptr<NativeModContext> context;
        try{context=rebuild_personal_slice2(2000000-instructions,reconstruction);}catch(const std::exception& e){instructions+=reconstruction;attempts.push_back({{"choices",choices},{"instructions",reconstruction},{"outcome","reconstruction_refused"},{"error",e.what()}});publish();throw;}
        instructions+=reconstruction;if(instructions>=2000000){publish();throw std::runtime_error("Slice3 exploration instruction budget exceeded");}
        context->input=inputs[1];context->begin(&candidate,&contexts_[0]->tape,mode_);context->configure_slice2(host.at("state_timeline"),host.at("value_graph"),choices,true,2000000-instructions);
        std::string error;try{context->dispatch(1);context->dispatch(2);}catch(const std::exception& e){error=e.what();}
        auto status=context->branches_slice2();auto frame_cost=status.at("instructions").get<unsigned>();instructions+=frame_cost;size_t index=attempts.size();
        Json attempt={{"choices",choices},{"instructions",reconstruction+frame_cost},{"reconstruction_instructions",reconstruction},{"startup_instructions",context->startup_instructions_slice3()},{"frame_instructions",frame_cost},{"guards",status.at("guards")}};
        for(auto proof:status.at("hud_branch_keys")){roles.insert(proof.at("key").get<std::string>());proof["candidate"]=index;role_proofs.push_back(proof);}
        if(status.at("needs_choice").get<bool>()){
            if(choices.size()>=8){publish();throw std::runtime_error("Slice3 unresolved branch budget exceeded");}
            for(bool value:{true,false}){auto next=choices;next.push_back(value);pending.push_front(next);}attempt["outcome"]="needs_choice";attempt["staged_discarded"]=context->staged_slice2();
        }else{attempt["outcome"]="awaiting_use_proof";complete.push_back({std::move(context),index,error,frame_cost});}
        attempts.push_back(attempt);publish();
        if(error.find("budget exceeded")!=std::string::npos)throw std::runtime_error(error);
    }
    std::unique_ptr<NativeModContext> selected;Json selected_choices;bool unresolved=false;std::string first_error;
    for(auto& path:complete){
        auto& attempt=attempts[path.attempt];if(instructions>=2000000){publish();throw std::runtime_error("Slice3 exploration instruction budget exceeded");}path.context->limit_slice3(2000000-instructions);path.context->branch_purposes_slice3(roles);auto proof=path.context->finish_slice2();attempt["proof"]=proof;
        if(proof.at("resolved").get<bool>()&&!proof.at("consistent").get<bool>())attempt["outcome"]="inconsistent";
        else if(!path.error.empty()||!proof.at("resolved").get<bool>()){attempt["outcome"]="unresolved";attempt["error"]=path.error.empty()?proof.value("error",std::string{}):path.error;unresolved=true;}
        else{try{path.context->check();attempt["outcome"]="consistent";if(selected)throw std::runtime_error("Ambiguous slice3 multiple consistent branches");selected_choices=attempt.at("choices");}
            catch(const std::exception& e){attempt["outcome"]="unresolved";attempt["error"]=e.what();unresolved=true;}}
        auto final_cost=path.context->branches_slice2().at("instructions").get<unsigned>();auto extra=final_cost-path.charged;instructions+=extra;attempt["projection_instructions"]=extra;attempt["instructions"]=attempt.at("instructions").get<unsigned>()+extra;attempt["frame_instructions"]=final_cost;
        if(attempt.at("outcome")=="consistent")selected=std::move(path.context);else attempt["staged_discarded"]=path.context->staged_slice2();
        if(attempt.contains("error")&&first_error.empty())first_error=attempt.at("error").get<std::string>();publish();
        if(instructions>2000000)throw std::runtime_error("Slice3 exploration instruction budget exceeded");
    }
    if(unresolved||!selected)throw std::runtime_error("Slice3 unresolved or nonunique path: "+first_error);
    contexts_[1]=std::move(selected);branch_search_["selected_choices"]=selected_choices;branch_search_["staged_committed"]=true;publish();
}
}
