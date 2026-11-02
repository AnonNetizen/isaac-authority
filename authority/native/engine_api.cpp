#include "engine_api.hpp"
#include "resources.hpp"
#include <algorithm>
namespace ia {
namespace {
Json canonical_frames(const BridgeLuaApi& api,BridgeLuaState* host,const std::string& file,const std::string& name,int last) {
    const int top=api.gettop(host);
    const auto source="local s=Sprite();s:Load("+Json(file).dump()+",true);s:SetFrame("+Json(name).dump()+","+std::to_string(last)+");local named=s:GetFrame();s:SetFrame("+std::to_string(last)+");return named,s:GetFrame()";
    try {
        int status=api.loadbuffer(host,source.data(),source.size(),"@authority-canonical-frame-control","t");
        if(!status)status=api.pcall(host,0,2,0,0,nullptr);
        if(status){size_t n{};auto message=api.string(host,-1,&n);throw std::runtime_error(message?std::string(message,n):"Canonical frame control failed");}
        if(!api.isinteger(host,-2)||!api.isinteger(host,-1))throw std::runtime_error("Noninteger canonical frame result");
        Json frames=Json::array({api.integer(host,-2,nullptr),api.integer(host,-1,nullptr)});api.settop(host,top);return frames;
    }catch(...){api.settop(host,top);throw;}
}
}
void expose_item_metadata(LuaObjectBridge& bridge) {
    bridge.expose_readonly_getter("__authority_item_config","Isaac","GetItemConfig","ItemConfig.Config");
    for(auto method:{"GetCollectible","GetTrinket","GetCard","GetPillEffect"})
        bridge.allow_readonly_method("ItemConfig.Config",method,"ItemConfig.Item");
}
Json probe_engine_api(const BridgeLuaApi& api,BridgeLuaState* host,const std::filesystem::path& game,const std::filesystem::path& output) {
    Json report={{"native_game_used",true},{"playable",false},{"generic_mod_compatibility_passed",false},
        {"probe_passed",false},{"checks",Json::object()},{"timing","on game thread after canonical MCM/EID late loading markers exist"}};
    const auto sprite=game/L"mods/mod_config_menu_cn_2494192799/resources/gfx/ui/modconfig/menu.anm2";
    const auto font=game/L"mods/mod_config_menu_cn_2494192799/resources/mcm_cn_font/pftempestasevencondensed.fnt";
    auto stage=[&](const std::string& name){
        report["stage"]=name;
        auto progress=report;progress["status"]="before_call";
        std::ofstream trace(output/L"engine-api-trace.jsonl",std::ios::app);trace<<progress.dump()<<'\n';trace.flush();
        if(!trace)throw std::runtime_error("Cannot persist engine API call trace");
    };
    try {
        report["assets_sha256"]={{"mcm_menu_anm2",sha256_file(sprite)},{"mcm_default_font",sha256_file(font)}};
        const auto catalog=ResourceCapabilities::compiled_catalog();
        report["resource_catalog_sha256"]=sha256_bytes(catalog.dump());
        report["resource_inventory"]=catalog;
        const auto absolute=Json(utf8(sprite.wstring())).dump(),font_path=Json(utf8(font.wstring())).dump();
        stage("canonical_sprite_load_absolute_without_graphics");
        api.execute(host,"local s=Sprite();s:Load("+absolute+",false);s:Play('Idle',true);assert(s:GetAnimation()=='Idle')","@authority-canonical-sprite-control");
        report["checks"]["canonical_absolute_sprite_without_graphics"]=true;
        stage("canonical_sprite_load_relative_with_graphics");
        api.execute(host,"local s=Sprite();s:Load('gfx/ui/modconfig/menu.anm2',true);s:Play('Idle',true);assert(s:GetAnimation()=='Idle')","@authority-canonical-sprite-graphics-control");
        report["checks"]["canonical_relative_sprite_with_graphics"]=true;
        {
            LuaObjectBridge first(api,host),second(api,host);
            for(auto* bridge:{&first,&second}) {
                for(auto name:{"Sprite","Vector","Font"})bridge->expose(name);
                expose_item_metadata(*bridge);
                install_resource_capabilities(*bridge,game);
                bridge->set_policy([](const std::string& label,const std::string& op,const std::vector<Json>&){
                    if(op!="call")return;
                    const std::vector<std::string> allowed={"Sprite","Vector","Font","Sprite.Load","Sprite.Play","Sprite.SetFrame","Sprite.GetFrame","Sprite.GetAnimation","Sprite.GetFilename","Sprite.ReplaceSpritesheet","Sprite.LoadGraphics",
                        "Font.Load","Font.GetStringWidth","Font.IsLoaded","Font.SetMissingCharacter","Isaac.GetItemConfig","ItemConfig.Config.GetCollectible","ItemConfig.Config.GetTrinket","ItemConfig.Config.GetCard","ItemConfig.Config.GetPillEffect"};
                    if(std::find(allowed.begin(),allowed.end(),label)==allowed.end())throw std::runtime_error("Unverified engine API: "+label);
                });
            }
            stage("private_sprite_load_absolute_with_graphics");
            first.run("s=Sprite();s:Load("+absolute+",true);s:Play('Idle',true);s.Scale=Vector(1.25,1.5);assert(s:GetAnimation()=='Idle' and s:GetFilename()~='')");
            report["checks"]["private_absolute_sprite_with_graphics"]=true;
            stage("second_private_sprite_load_relative_with_graphics");
            second.run("s=Sprite();s:Load('gfx/ui/modconfig/menu.anm2',true);s:Play('Idle',true);s.Scale=Vector(2,3);assert(s:GetAnimation()=='Idle' and s.Scale.X==2)");
            first.run("assert(s.Scale.X==1.25 and s.Scale.Y==1.5)");
            report["checks"]["private_relative_sprite_and_independent_state"]=true;
            stage("private_mcm_font_load_absolute");
            auto width=first.run("f=Font();f:Load("+font_path+");cachedWidth=f.GetStringWidth;local n=cachedWidth(f,'native bridge');assert(n>0);return n");
            report["mcm_font_width"]=width[0].at("v");report["checks"]["private_mcm_font_load_measure"]=true;
            stage("eid_font_legacy_load_and_missing_character");
            const auto eid_font_path=Json(utf8((game/L"mods/external item descriptions_836319872/resources/font/eid_default.fnt").generic_wstring())).dump();
            api.execute(host,"local f=Font();f:Load("+eid_font_path+",'');f:SetMissingCharacter(2);assert(f:IsLoaded() and f:GetStringWidth('native bridge')==65)","@authority-canonical-legacy-font-load");
            for(auto* bridge:{&first,&second})bridge->run("eidFont=Font();eidFont:Load("+eid_font_path+",'');cachedMissing=eidFont.SetMissingCharacter;cachedLoaded=eidFont.IsLoaded;cachedMissing(eidFont,2);assert(cachedLoaded(eidFont) and eidFont:GetStringWidth('native bridge')==65)");
            report["checks"]["canonical_and_two_private_legacy_font_load_missing_character"]=true;
            stage("invalid_font_compatibility_argument_and_missing_character_refused");
            for(auto source:{"eidFont:Load("+eid_font_path+",'unverified')",std::string("eidFont:SetMissingCharacter(65536)")}) {
                bool refused{};try{first.run(source);}catch(const std::exception& error){refused=std::string(error.what()).find("verified")!=std::string::npos;}
                if(!refused)throw std::runtime_error("Unverified font arguments accepted");
            }
            report["checks"]["invalid_font_compatibility_argument_and_missing_character_refused"]=true;
            size_t resource_index{};
            for(const auto& resource:catalog.at("resources")) {
                if(resource.at("kind")=="image"){++resource_index;continue;}
                const auto alias=Json(resource.at("aliases")[0]).dump();
                const auto native_path=resource.value("storage",std::string("loose"))=="packed"?resource.at("engine_path").get<std::string>():utf8((game/wide(resource.at("path"))).generic_wstring());
                const auto full=Json(native_path).dump();
                const auto key=resource.at("path").get<std::string>();
                stage("catalog_resource_"+std::to_string(resource_index));
                if(resource.at("kind")=="sprite") {
                    first.run("asset=Sprite();asset:Load("+alias+");cachedSetFrame=asset.SetFrame;cachedGetFrame=asset.GetFrame;asset:Play("+Json(resource.at("default_animation")).dump()+",false)");
                    second.run("asset=Sprite();asset:Load("+full+",true);asset:Play("+Json(resource.at("default_animation")).dump()+")");
                    Json measurements=Json::array();
                    for(auto it=resource.at("animations").begin();it!=resource.at("animations").end();++it) {
                        const auto name=Json(it.key()).dump(),last=std::to_string(it.value().get<int>()-1);
                        stage("animation_"+std::to_string(resource_index)+"_"+it.key());
                        auto canonical=canonical_frames(api,host,native_path,it.key(),it.value().get<int>()-1);
                        auto private_frames=first.run("cachedSetFrame(asset,"+name+","+last+");local named=cachedGetFrame(asset);asset:SetFrame("+last+");assert(asset:GetAnimation()=="+name+");return named,cachedGetFrame(asset)");
                        if(private_frames[0].at("v")!=canonical[0]||private_frames[1].at("v")!=canonical[1])throw std::runtime_error("Private/canonical frame overload results diverged");
                        second.run("asset:SetFrame("+name+",0);assert(asset:GetAnimation()=="+name+" and asset:GetFrame()==0)");
                        first.run("assert(cachedGetFrame(asset)=="+canonical[1].dump()+")");
                        measurements.push_back({{"animation",it.key()},{"selectable_frame_limit",it.value()},{"declared_frames",resource.at("declared_frames").at(it.key())},
                            {"requested_last_frame",it.value().get<int>()-1},{"first_named_frame",private_frames[0].at("v")},{"first_numeric_frame",private_frames[1].at("v")},{"canonical_frames",canonical},{"second_frame",0}});
                    }
                    report["sprite_roundtrips"].push_back({{"path",key},{"animations",measurements}});
                    report["checks"]["catalog_sprite_"+std::to_string(resource_index)]=true;
                }else {
                    Json measured=Json::array();
                    for(auto* bridge:{&first,&second}) {
                        auto measured_width=bridge->run("assetFont=Font();assetFont:Load("+full+");local measure=assetFont.GetStringWidth;local n=measure(assetFont,'native bridge');assert(n>0);return n");
                        measured.push_back(measured_width[0].at("v"));
                    }
                    if(measured[0]!=measured[1])throw std::runtime_error("Private font measurements diverged");
                    report["font_roundtrips"].push_back({{"path",key},{"widths",measured}});
                    report["checks"]["catalog_font_"+std::to_string(resource_index)]=true;
                }
                ++resource_index;
            }
            stage("packed_questionmark_replacement_and_graphics");
            api.execute(host,"local s=Sprite();s:Load('gfx/005.100_collectible.anm2',true);s:ReplaceSpritesheet(1,'gfx/items/collectibles/questionmark.png');s:LoadGraphics();s:SetFrame('Idle',0);assert(s:GetAnimation()=='Idle')","@authority-canonical-questionmark");
            for(auto* bridge:{&first,&second})bridge->run("question=Sprite();question:Load('gfx/005.100_collectible.anm2',true);cachedReplace=question.ReplaceSpritesheet;cachedGraphics=question.LoadGraphics;cachedReplace(question,1,'gfx/items/collectibles/questionmark.png');cachedGraphics(question);question:SetFrame('Idle',0);assert(question:GetAnimation()=='Idle')");
            second.run("question:SetFrame('ShopIdle',0)");first.run("assert(question:GetAnimation()=='Idle')");
            report["checks"]["packed_replacement_cached_calls_two_contexts_and_canonical_control"]=true;
            stage("unverified_sprite_layer_and_replacement_image_refused");
            for(auto source:{"question:ReplaceSpritesheet(999,'gfx/items/collectibles/questionmark.png')","question:ReplaceSpritesheet(1,'gfx/unverified.png')"}) {
                bool refused{};try{first.run(source);}catch(const std::exception& error){refused=std::string(error.what()).find("Unverified")!=std::string::npos;}
                if(!refused)throw std::runtime_error("Unverified replacement accepted");
            }
            report["checks"]["unverified_layer_and_image_refused"]=true;
            stage("legacy_source_relative_font_path");
            const auto legacy=Json(utf8((game/L"mods/mod_config_menu_cn_2494192799/scripts/modconfig.lua/../../resources/mcm_cn_font/pftempestasevencondensed.fnt").generic_wstring())).dump();
            first.run("local f=Font();f:Load("+legacy+");assert(f:GetStringWidth('native bridge')==67)");
            report["checks"]["legacy_source_relative_font_path_normalized"]=true;
            stage("invalid_animation_and_unloaded_sprite_refused");
            auto refuse_resource=[&](const char* source,const char* expected){bool refused{};try{first.run(source);}catch(const std::exception& e){refused=std::string(e.what()).find(expected)!=std::string::npos;}if(!refused)throw std::runtime_error("Expected resource refusal missing");};
            refuse_resource("pcall(function()asset:SetFrame('missing-authority-animation',0)end)","Unverified sprite animation");
            refuse_resource("pcall(function()Sprite():GetFrame()end)","not loaded successfully");
            report["checks"]["unknown_animation_and_unloaded_sprite_refused"]=true;
            stage("private_readonly_item_metadata");
            for(auto* bridge:{&first,&second}) {
                auto data=bridge->run("config=__authority_item_config();cachedItem=config.GetCollectible;item=cachedItem(config,1);assert(item.ID==1 and type(item.Name)=='string');assert(config:GetTrinket(1).ID==1 and config:GetCard(1).ID==1 and config:GetPillEffect(0).ID==0);return item.ID,item.Name,item.Quality");
                report["metadata_contexts"].push_back(data);
            }
            report["checks"]["two_private_contexts_cached_readonly_metadata"]=true;
            stage("readonly_metadata_write_and_unknown_method_refused");
            auto reject=[&](const char* code,const char* expected){bool refused{};try{first.run(code);}catch(const std::exception& e){refused=std::string(e.what()).find(expected)!=std::string::npos;}if(!refused)throw std::runtime_error("Expected metadata refusal missing");};
            reject("pcall(function()item.Quality=99 end)","Borrowed host objects");
            reject("pcall(function()item:IsAvailable()end)","Unverified engine API");
            first.run("assert(cachedItem(config,1).Quality==item.Quality)");
            report["checks"]["metadata_readonly_and_progress_query_refused"]=true;
            report["bridges"]=Json::array({first.statistics(),second.statistics()});
        }
        stage("private_contexts_destroyed_then_new_sprite");
        {
            LuaObjectBridge rebuilt(api,host);rebuilt.expose("Sprite");
            install_resource_capabilities(rebuilt,game);
            rebuilt.run("local s=Sprite();s:Load('gfx/ui/modconfig/menu.anm2',true);s:Play('Idle',true);assert(s:GetAnimation()=='Idle')");
        }
        report["checks"]["sprite_after_context_lifetime_cleanup"]=true;
        stage("complete");report["probe_passed"]=true;
    }catch(const std::exception& error){report["error"]=error.what();}
    return report;
}
}
