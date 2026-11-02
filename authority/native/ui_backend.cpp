#include "ui_backend.hpp"
#include <cmath>
#include <set>
#include <algorithm>
namespace ia {
namespace {constexpr int registry=-1001000;const char* meta="IsaacAuthority.StandaloneUiValue.v1";thread_local Json resources;
std::string string(const BridgeLuaApi& api,BridgeLuaState* s,int i){size_t n{};auto p=api.string(s,i,&n);if(!p)throw std::runtime_error("UI string required");return {p,n};}
std::string bytes(const Json& x){std::string out;auto h=x.get<std::string>();for(size_t i=0;i<h.size();i+=2)out+=static_cast<char>(std::stoi(h.substr(i,2),nullptr,16));return out;}
}
thread_local std::map<BridgeLuaState*,StandaloneUiBackend*> StandaloneUiBackend::active_;
StandaloneUiBackend::StandaloneUiBackend(const BridgeLuaApi& api,BridgeLuaState* s):api_(api),state_(s){
    active_[s]=this;api_.newmetatable(s,meta);
    for(auto pair:std::initializer_list<std::pair<const char*,BridgeLuaFunction>>{{"__index",get},{"__newindex",set}}){api_.pushclosure(s,pair.second,0);api_.setfield(s,-2,pair.first);}
    for(auto name:{"__add","__sub","__mul","__div","__unm","__eq","__len","__tostring","__band","__bor","__bxor"}){
        api_.pushstring(s,name,strlen(name));api_.pushclosure(s,operation,1);api_.setfield(s,-2,name);
    }
    api_.pushstring(s,"Standalone UI Value",19);api_.setfield(s,-2,"__metatable");api_.settop(s,0);
    api_.pushclosure(s,make,0);api_.setglobal(s,"__authority_ui_userdata");
    if(api_.trace.allow){api_.trace.allow(s,make,"authority.ui.make");api_.trace.allow(s,get,"authority.ui.get");api_.trace.allow(s,set,"authority.ui.set");api_.trace.allow(s,operation,"authority.ui.operator");}
}
StandaloneUiBackend::~StandaloneUiBackend(){active_.erase(state_);}
int __cdecl StandaloneUiBackend::make(BridgeLuaState* s){return dispatch(s,0);}
int __cdecl StandaloneUiBackend::get(BridgeLuaState* s){return dispatch(s,1);}
int __cdecl StandaloneUiBackend::set(BridgeLuaState* s){return dispatch(s,2);}
int __cdecl StandaloneUiBackend::operation(BridgeLuaState* s){return dispatch(s,3);}
int StandaloneUiBackend::dispatch(BridgeLuaState* s,int op){
    auto self=active_.at(s);auto& api=self->api_;std::string error;int returns{};
    try{
        if(op==0){
            auto label=string(api,s,1);const std::set<std::string> allowed={"Vector","Color","KColor","Font","Sprite","FontRenderSettings","BitSet128"};
            if(!allowed.contains(label)||api.type(s,2)!=5)throw std::runtime_error("Unregistered UI userdata class");
            if(self->sequence_>=2048)throw std::runtime_error("UI object budget exceeded");
            api.pushvalue(s,2);int ref=api.reference(s,registry);auto h=static_cast<Handle*>(api.newuserdata(s,sizeof(Handle)));*h={++self->sequence_,ref};self->labels_[h->id]=label;
            api.getfield(s,registry,meta);api.setmetatable(s,-2);
            if(api.slice.ui_register)api.slice.ui_register(s,-1,label.c_str(),h->id);
            api.pushvalue(s,-1);api.reference(s,registry);returns=1;
        }else{
            auto h=static_cast<Handle*>(api.testuserdata(s,1,meta));if(!h&&op==3)h=static_cast<Handle*>(api.testuserdata(s,2,meta));if(!h||!self->labels_.contains(h->id))throw std::runtime_error("Foreign UI userdata receiver");
            int count=api.gettop(s);api.rawgeti(s,registry,h->reference);
            if(op==1){api.pushvalue(s,2);api.gettable(s,-2);returns=1;}
            else if(op==2){api.pushvalue(s,2);api.pushvalue(s,3);api.settable(s,-3);}
            else {auto name=string(api,s,registry-1);api.getfield(s,-1,name.c_str());if(api.type(s,-1)!=6)throw std::runtime_error("Unregistered UI operator: "+name);
                for(int i=1;i<=count;++i)api.pushvalue(s,i);int status=api.pcall(s,count,1,0,0,nullptr);if(status)throw std::runtime_error(string(api,s,-1));returns=1;}
        }
    }catch(const std::exception& e){error=e.what();}
    if(!error.empty()){api.pushstring(s,error.data(),error.size());return api.error(s);}return returns;
}
UiResourceScope::UiResourceScope(Json value):previous_(std::move(resources)){resources=std::move(value);}
UiResourceScope::~UiResourceScope(){resources=std::move(previous_);}
Json ui_resource_call(const std::string& op,const Json& args){
    if(resources.is_null())throw std::runtime_error("Missing frozen UI resource scope");
    if(op=="ui.resource"){
        if(args.size()!=2||!args[0].is_string()||!args[1].is_string())throw std::runtime_error("UI resource signature");
        auto requested=args[1].get<std::string>();std::replace(requested.begin(),requested.end(),'\\','/');
        auto marker=requested.find("/mods/");if(marker!=std::string::npos)requested=requested.substr(marker+1);
        auto normalized=std::filesystem::path(requested).lexically_normal().generic_string();if(normalized.starts_with("../mods/"))normalized.erase(0,3);
        const Json* found=nullptr;
        for(const auto& item:resources.at("resources"))if(item.at("kind")==args[0]&&(item.at("path")==normalized||std::find(item.at("aliases").begin(),item.at("aliases").end(),normalized)!=item.at("aliases").end())){
            if(found)throw std::runtime_error("Ambiguous frozen UI resource alias");found=&item;
        }
        if(!found)throw std::runtime_error("Unsupported frozen UI resource: "+requested);
        Json output={{"id",found->at("path")}};for(auto key:{"animations","default_animation","layers"})if(found->contains(key))output[key]=found->at(key);
        return Json::array({output});
    }
    if(op=="ui.font.width"){
        if(args.size()!=3)throw std::runtime_error("UI font width signature");const Json* found=nullptr;for(const auto& item:resources.at("resources"))if(item.at("path")==args[0])found=&item;
        if(!found||!found->contains("metrics"))throw std::runtime_error("Unregistered font metrics");auto text=bytes(args[1]);auto missing=args[2].get<int>();int64_t total{};unsigned previous{};
        for(size_t i=0;i<text.size();){unsigned c=static_cast<unsigned char>(text[i++]);if(c>=128){unsigned extra=c<224?1:c<240?2:3;if(c<194||c>244||i+extra>text.size())throw std::runtime_error("Unregistered invalid UTF8 width semantics");c&=(1u<<(6-extra))-1;while(extra--){unsigned x=static_cast<unsigned char>(text[i++]);if((x&192)!=128)throw std::runtime_error("Invalid UTF8 width");c=(c<<6)|(x&63);}}
            const auto& m=found->at("metrics");auto key=std::to_string(c);if(!m.at("advances").contains(key)){key=std::to_string(missing);if(!m.at("advances").contains(key))throw std::runtime_error("Unregistered missing glyph behavior");}
            auto pair=std::to_string(previous)+":"+std::to_string(c);if(m.at("kerning").contains(pair))total+=m.at("kerning").at(pair).get<int>();total+=m.at("advances").at(key).get<int>();previous=c;
        }return Json::array({total});
    }
    throw std::runtime_error("Unsupported standalone UI service: "+op);
}
}
