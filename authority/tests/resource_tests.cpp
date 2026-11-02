#include "resources.hpp"
#include <iostream>
namespace {
using namespace ia;
void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
Json string(const std::string& value){constexpr char digits[]="0123456789abcdef";std::string hex;for(unsigned char b:value){hex+=digits[b>>4];hex+=digits[b&15];}return {{"t","string"},{"hex",hex}};}
Json object(uint64_t id=1,uint64_t scope=1){return {{"t","ref"},{"scope",scope},{"id",id},{"kind","userdata"}};}
Json number(int64_t n){return {{"t","integer"},{"v",n}};}
void write(const std::filesystem::path& path,const std::string& data){std::ofstream file(path,std::ios::binary);file<<data;if(!file)throw std::runtime_error("Write resource fixture");}
}
int wmain(){
    using namespace ia;std::filesystem::path temporary;
    try {
        temporary=std::filesystem::temp_directory_path()/(L"isaac-resource-tests-"+std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64()));
        std::filesystem::create_directories(temporary/L"mods/fixture/resources/gfx");
        auto file=temporary/L"mods/fixture/resources/gfx/test.anm2",image=temporary/L"mods/fixture/resources/gfx/test.png";
        write(file,"frozen animation fixture");write(image,"frozen image fixture");
        Json record={{"kind","sprite"},{"path","mods/fixture/resources/gfx/test.anm2"},{"aliases",Json::array({"gfx/test.anm2"})},
            {"default_animation","Idle"},{"animations",{{"Idle",1},{"Cursor",5}}},{"layers",Json::array({0,1})},
            {"files",Json::array({Json{{"path","mods/fixture/resources/gfx/test.anm2"},{"sha256",sha256_file(file)}},Json{{"path","mods/fixture/resources/gfx/test.png"},{"sha256",sha256_file(image)}}})}};
        auto image_record=Json{{"kind","image"},{"path","mods/fixture/resources/gfx/test.png"},{"aliases",Json::array({"gfx/test.png"})},{"files",Json::array({Json{{"path","mods/fixture/resources/gfx/test.png"},{"sha256",sha256_file(image)}}})}};
        auto font=temporary/L"mods/fixture/resources/test.fnt";write(font,"frozen font fixture");
        auto font_record=Json{{"kind","font"},{"path","mods/fixture/resources/test.fnt"},{"aliases",Json::array({"font/test.fnt"})},{"files",Json::array({Json{{"path","mods/fixture/resources/test.fnt"},{"sha256",sha256_file(font)}}})}};
        Json catalog={{"schema",1},{"resources",Json::array({record,image_record,font_record})}};ResourceCapabilities resources(temporary,catalog);unsigned passed{};
        auto test=[&](auto body){body();++passed;};
        auto reject=[&](auto body,const char* reason){bool refused{};try{body();}catch(const std::exception& e){refused=std::string(e.what()).find(reason)!=std::string::npos;}check(refused,reason);++passed;};
        auto prepare=[&](const char* label,std::vector<Json> args){resources.prepare(label,"call",args);return args;};
        test([&]{auto args=prepare("Font.Load",{object(10),string("font/test.fnt"),string("")});check(args[1]==string(utf8(font.generic_wstring()))&&args[2]==string(""),"Font compatibility argument preserves pinned path");resources.completed("Font.Load","call",args,{});prepare("Font.IsLoaded",{object(10)});prepare("Font.SetMissingCharacter",{object(10),number(2)});prepare("Font.GetStringWidth",{object(10),string("text")});});
        reject([&]{prepare("Font.Load",{object(10),string("font/test.fnt"),string("extra")});},"Only empty Font.Load");
        reject([&]{prepare("Font.IsLoaded",{object(11)});},"not loaded successfully");
        reject([&]{prepare("Font.IsLoaded",{object(10,2)});},"not loaded successfully");
        reject([&]{prepare("Font.SetMissingCharacter",{object(10),number(-1)});},"missing character range");
        reject([&]{prepare("Font.SetMissingCharacter",{object(10),number(65536)});},"missing character range");
        reject([&]{prepare("Font.GetStringWidth",{object(10),number(3)});},"Font measurement string limit");
        test([&]{prepare("Font.Load",{object(10),string("font/test.fnt")});reject([&]{prepare("Font.IsLoaded",{object(10)});},"not loaded successfully");});
        test([&]{auto args=prepare("Sprite.Load",{object(),string("gfx/./test.anm2")});check(args[1]==string(utf8(file.generic_wstring())),"Pinned absolute path/default graphics");resources.completed("Sprite.Load","call",args,{});});
        test([&]{auto args=prepare("Sprite.Load",{object(2),string(utf8((temporary/L"mods/fixture/main.lua/../resources/gfx/test.anm2").generic_wstring())),Json{{"t","boolean"},{"v",false}}});check(args[1]==string(utf8(file.generic_wstring())),"Legacy source-relative path normalized");resources.completed("Sprite.Load","call",args,{});});
        test([&]{auto args=prepare("Sprite.SetFrame",{object(),string("Cursor"),number(4)});resources.completed("Sprite.SetFrame","call",args,{});prepare("Sprite.SetFrame",{object(),number(0)});});
        reject([&]{prepare("Sprite.SetFrame",{object(),string("Cursor"),number(5)});},"outside verified animation");
        reject([&]{prepare("Sprite.SetFrame",{object(),number(-1)});},"outside verified animation");
        reject([&]{prepare("Sprite.SetFrame",{object(),string("missing"),number(0)});},"Unverified sprite animation");
        reject([&]{prepare("Sprite.SetFrame",{object(2),number(0)});},"Unverified sprite animation");
        reject([&]{prepare("Sprite.GetFrame",{object(3)});},"not loaded successfully");
        reject([&]{prepare("Sprite.GetFrame",{object(1,2)});},"not loaded successfully");
        test([&]{auto args=prepare("Sprite.Load",{object(3),string("gfx/test.anm2")});reject([&]{prepare("Sprite.GetFrame",{object(3)});},"not loaded successfully");});
        test([&]{auto args=prepare("Sprite.Play",{object(2),string("Idle")});resources.completed("Sprite.Play","call",args,{});prepare("Sprite.SetFrame",{object(2),number(0)});prepare("Sprite.SetFrame",{object(),number(4)});});
        test([&]{auto args=prepare("Sprite.Load",{object(2),string("gfx/test.anm2")});bool revoked{};try{prepare("Sprite.GetFrame",{object(2)});}catch(const std::exception& e){revoked=std::string(e.what()).find("not loaded successfully")!=std::string::npos;}check(revoked,"Failed reload cannot reuse old sprite capability");resources.completed("Sprite.Load","call",args,{});});
        reject([&]{prepare("Sprite.Load",{object(),string("../outside.anm2")});},"outside game root");
        reject([&]{prepare("Sprite.Load",{object(),string("gfx/missing.anm2")});},"Unverified native resource");
        reject([&]{prepare("Sprite.Load",{object(),string("gfx/test.anm2:extra")});},"outside game root");
        reject([&]{prepare("Sprite.Load",{object(),string(std::string("gfx/test.anm2\0bad",17))});},"NUL");
        reject([&]{prepare("Font.Load",{object(),string("gfx/test.anm2")});},"kind mismatch");
        reject([&]{prepare("Sprite.Load",{object(),string("gfx/test.anm2"),number(1)});},"boolean argument");
        reject([&]{prepare("Sprite.Play",{object(),string("Cursor"),string("invalid")});},"boolean argument");
        reject([&]{prepare("Sprite.GetFrame",{object(),number(1)});},"call signature");
        test([&]{write(image,"changed image fixture");reject([&]{prepare("Sprite.Load",{object(),string("gfx/test.anm2")});},"Changed resource dependency");write(image,"frozen image fixture");});
        reject([&]{auto other=catalog;other["resources"].push_back(record);ResourceCapabilities invalid(temporary,other);},"Duplicate catalog resource");
        reject([&]{auto other=catalog;other["resources"][0]["files"].erase(0);ResourceCapabilities invalid(temporary,other);},"main file not hashed");
        reject([&]{auto other=catalog;other["resources"][0]["animations"]["Idle"]=0;ResourceCapabilities invalid(temporary,other);},"frame count");
        reject([&]{prepare("Sprite.ReplaceSpritesheet",{object(),number(99),string("gfx/test.png")});},"Unverified sprite layer");
        reject([&]{prepare("Sprite.ReplaceSpritesheet",{object(),number(1),string("gfx/missing.png")});},"Unverified native resource");
        reject([&]{prepare("Sprite.ReplaceSpritesheet",{object(),number(1),string("gfx/test.anm2")});},"kind mismatch");
        test([&]{auto args=prepare("Sprite.ReplaceSpritesheet",{object(),number(1),string("gfx/test.png")});check(args[2]==string(utf8(image.generic_wstring())),"Replacement pinned to verified image");resources.completed("Sprite.ReplaceSpritesheet","call",args,{});auto graphics=prepare("Sprite.LoadGraphics",{object()});resources.completed("Sprite.LoadGraphics","call",graphics,{});prepare("Sprite.GetFrame",{object()});});
        test([&]{prepare("Sprite.ReplaceSpritesheet",{object(),number(1),string("gfx/test.png")});reject([&]{prepare("Sprite.Play",{object(),string("Idle")});},"state invalid");auto reload=prepare("Sprite.Load",{object(),string("gfx/test.anm2")});resources.completed("Sprite.Load","call",reload,{});});
        test([&]{prepare("Sprite.LoadGraphics",{object()});reject([&]{prepare("Sprite.GetFrame",{object()});},"state invalid");auto reload=prepare("Sprite.Load",{object(),string("gfx/test.anm2")});resources.completed("Sprite.Load","call",reload,{});});
        reject([&]{auto other=catalog;other["resources"][0]["layers"]=Json::array({1,1});ResourceCapabilities invalid(temporary,other);},"Invalid sprite layers");
        std::filesystem::create_directories(temporary/L"resources/packed");auto archive=temporary/L"resources/packed/fixture.a";write(archive,"synthetic packed provider");
        auto packed=record;packed["storage"]="packed";packed["path"]="resources/gfx/packed.anm2";packed["engine_path"]="gfx/packed.anm2";packed["aliases"]=Json::array({"gfx/packed.anm2"});
        packed["files"]=Json::array({Json{{"path","resources/packed/fixture.a"},{"sha256",sha256_file(archive)}}});packed["packed_entries"]=Json::array({Json{{"entry","resources/gfx/packed.anm2"},{"archive","fixture.a"},{"archive_sha256",sha256_file(archive)},{"sha256",sha256_bytes("synthetic entry")},{"offset",14},{"bytes",1}}});
        auto packed_image=image_record;packed_image["storage"]="packed";packed_image["path"]="resources/gfx/packed.png";packed_image["engine_path"]="gfx/packed.png";packed_image["aliases"]=Json::array({"gfx/packed.png"});packed_image["files"]=packed["files"];packed_image["packed_entries"]=packed["packed_entries"];packed_image["packed_entries"][0]["entry"]="resources/gfx/packed.png";
        Json packed_catalog={{"schema",1},{"resources",Json::array({packed,packed_image})},{"packed_environment",packed["files"]}};
        {
            ResourceCapabilities guarded(temporary,packed_catalog);
            test([&]{std::vector<Json> args={object(),string("gfx/packed.anm2")};guarded.prepare("Sprite.Load","call",args);check(args[1]==string("gfx/packed.anm2"),"Packed engine logical path preserved");guarded.completed("Sprite.Load","call",args,{});});
            test([&]{auto handle=CreateFileW(archive.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);check(handle==INVALID_HANDLE_VALUE&&GetLastError()==ERROR_SHARING_VIOLATION,"Pinned archive cannot be overwritten");});
            test([&]{std::vector<Json> args={object(),number(1),string("gfx/packed.png")};guarded.prepare("Sprite.ReplaceSpritesheet","call",args);check(args[2]==string("gfx/packed.png"),"Packed replacement logical path preserved");guarded.completed("Sprite.ReplaceSpritesheet","call",args,{});std::vector<Json> graphics={object()};guarded.prepare("Sprite.LoadGraphics","call",graphics);guarded.completed("Sprite.LoadGraphics","call",graphics,{});});
            test([&]{auto extra=temporary/L"resources/packed/extra.a";write(extra,"extra archive");reject([&]{std::vector<Json> args={object(),string("gfx/packed.anm2")};guarded.prepare("Sprite.Load","call",args);},"Changed packed archive inventory");std::filesystem::remove(extra);});
            test([&]{auto loose=temporary/L"mods/fixture/resources/gfx/packed.anm2";write(loose,"override");reject([&]{std::vector<Json> args={object(),string("gfx/packed.anm2")};guarded.prepare("Sprite.Load","call",args);},"Loose override");std::filesystem::remove(loose);});
        }
        test([&]{auto handle=CreateFileW(archive.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);check(handle!=INVALID_HANDLE_VALUE,"Packed handles released after context lifetime");CloseHandle(handle);});
        {
            ResourceVerificationScope shared;
            test([&]{
                {ResourceCapabilities first(temporary,packed_catalog);std::vector<Json> args={object(),string("gfx/packed.anm2")};first.prepare("Sprite.Load","call",args);}
                check(shared.statistics().at("archives_hashed")==1,"One shared archive hash");
                ResourceCapabilities second(temporary,packed_catalog);std::vector<Json> args={object(),string("gfx/packed.anm2")};second.prepare("Sprite.Load","call",args);
                check(shared.statistics().at("archives_hashed")==1&&shared.statistics().at("archive_cache_hits")==1,"Fresh context shares verification without sharing sprite state");
                bool refused{};try{std::vector<Json> getter={object()};second.prepare("Sprite.GetFrame","call",getter);}catch(const std::exception&){refused=true;}check(refused,"Shared environment does not grant another context's sprite state");
            });
            test([&]{auto handle=CreateFileW(archive.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);check(handle==INVALID_HANDLE_VALUE&&GetLastError()==ERROR_SHARING_VIOLATION,"Shared pins outlive individual contexts");});
            reject([&]{auto bad=packed_catalog;bad["packed_environment"][0]["sha256"]=sha256_bytes("different");bad["resources"][0]["files"]=bad["packed_environment"];bad["resources"][1]["files"]=bad["packed_environment"];for(auto& resource:bad["resources"])resource["packed_entries"][0]["archive_sha256"]=bad["packed_environment"][0]["sha256"];ResourceCapabilities invalid(temporary,bad);std::vector<Json> args={object(),string("gfx/packed.anm2")};invalid.prepare("Sprite.Load","call",args);},"Conflicting shared archive hash");
        }
        test([&]{auto handle=CreateFileW(archive.c_str(),GENERIC_WRITE,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);check(handle!=INVALID_HANDLE_VALUE,"Shared pins released at diagnostic end");CloseHandle(handle);});
        reject([&]{auto bad=packed_catalog;bad["packed_environment"]=Json::array();ResourceCapabilities invalid(temporary,bad);},"Missing packed environment");
        reject([&]{auto bad=packed_catalog;bad["resources"][0]["engine_path"]="gfx/../escape.anm2";ResourceCapabilities invalid(temporary,bad);},"Invalid packed engine path");
        reject([&]{auto bad=packed_catalog;bad["resources"][0]["packed_entries"][0]["entry"]="resources/gfx/missing.anm2";ResourceCapabilities invalid(temporary,bad);},"main entry missing");
        reject([&]{auto bad=packed_catalog;bad["resources"][0]["packed_entries"][0]["archive"]="unhashed.a";ResourceCapabilities invalid(temporary,bad);},"provider not hashed");
        // Only our newly created, resolved temporary tree is removed.
        auto resolved=std::filesystem::canonical(temporary),parent=std::filesystem::canonical(std::filesystem::temp_directory_path());
        check(resolved.parent_path()==parent&&resolved.filename().wstring().starts_with(L"isaac-resource-tests-"),"Temporary cleanup target verified");std::filesystem::remove_all(resolved);
        std::cout<<Json({{"passed",passed},{"native_game_used",false},{"resource_boundaries",true},{"playable",false}}).dump()<<'\n';return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
