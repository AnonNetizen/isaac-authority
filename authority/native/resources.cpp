#include "resources.hpp"
#include "resource_catalog.hpp"
#include <algorithm>
#include <cwctype>
#include <memory>
namespace ia {
namespace {
std::wstring folded(std::wstring text) {std::transform(text.begin(),text.end(),text.begin(),[](wchar_t c){return static_cast<wchar_t>(std::towlower(c));});return text;}
std::string text(const Json& value) {
    if(value.at("t")!="string")throw std::runtime_error("Resource string argument required");
    const auto hex=value.at("hex").get<std::string>();std::string result;
    auto digit=[](char c){if(c>='0'&&c<='9')return c-'0';if(c>='a'&&c<='f')return c-'a'+10;throw std::runtime_error("Invalid resource string hex");};
    if(hex.size()%2||hex.size()>8192)throw std::runtime_error("Resource path/string limit");
    for(size_t i=0;i<hex.size();i+=2)result+=static_cast<char>((digit(hex[i])<<4)|digit(hex[i+1]));
    if(result.find('\0')!=std::string::npos)throw std::runtime_error("NUL in resource string");return result;
}
Json wire(const std::string& value) {constexpr char digits[]="0123456789abcdef";std::string hex;for(unsigned char b:value){hex+=digits[b>>4];hex+=digits[b&15];}return {{"t","string"},{"hex",hex}};}
void count(const std::vector<Json>& args,size_t low,size_t high) {if(args.size()<low||args.size()>high)throw std::runtime_error("Unverified resource call signature");}
void optional_boolean(const std::vector<Json>& args,size_t index) {
    if(args.size()>index&&args[index].at("t")!="boolean"&&args[index].at("t")!="nil")throw std::runtime_error("Resource boolean argument required");
}
}
class ResourceVerificationEnvironment {
    struct Archive {HANDLE handle{};std::string hash;};
    std::map<std::wstring,Archive> archives_;
    size_t hits_{};uint64_t bytes_{},elapsed_{};
public:
    ~ResourceVerificationEnvironment(){for(const auto& [path,archive]:archives_){(void)path;CloseHandle(archive.handle);}}
    void verify(const std::filesystem::path& path,const std::string& expected) {
        auto key=folded(path.generic_wstring());auto found=archives_.find(key);
        if(found!=archives_.end()) {
            if(found->second.hash!=expected)throw std::runtime_error("Conflicting shared archive hash");++hits_;return;
        }
        auto handle=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
        if(handle==INVALID_HANDLE_VALUE)throw std::runtime_error("Cannot pin packed archive");
        try {
            auto begin=GetTickCount64();auto actual=sha256_file(path);elapsed_+=GetTickCount64()-begin;
            if(actual!=expected)throw std::runtime_error("Changed resource dependency: "+utf8(path.filename().wstring()));
            bytes_+=std::filesystem::file_size(path);archives_.emplace(key,Archive{handle,actual});
        }catch(...){CloseHandle(handle);throw;}
    }
    Json statistics() const {return {{"archives_hashed",archives_.size()},{"archive_cache_hits",hits_},{"bytes_hashed",bytes_},{"hash_elapsed_ms",elapsed_},{"read_pins_held",archives_.size()}};}
};
namespace {thread_local std::shared_ptr<ResourceVerificationEnvironment> active_verification;}
ResourceVerificationScope::ResourceVerificationScope():previous_(active_verification),environment_(previous_?previous_:std::make_shared<ResourceVerificationEnvironment>()) {active_verification=environment_;}
ResourceVerificationScope::~ResourceVerificationScope(){active_verification=previous_;}
Json ResourceVerificationScope::statistics() const {return environment_->statistics();}
std::filesystem::path ResourceCapabilities::path(const std::string& name) const {
    if(name.empty()||name.find('\0')!=std::string::npos)throw std::runtime_error("Invalid resource path");
    auto requested=std::filesystem::path(wide(name));
    auto absolute=(requested.is_absolute()?requested:game_/requested).lexically_normal();
    auto relative=absolute.lexically_relative(game_);
    if(relative.empty()||relative.is_absolute()||relative.begin()->wstring()==L".."||absolute.wstring().find(':',3)!=std::wstring::npos)
        throw std::runtime_error("Resource outside game root");
    return absolute;
}
ResourceCapabilities::ResourceCapabilities(const std::filesystem::path& game,Json catalog):game_(std::filesystem::absolute(game).lexically_normal()),catalog_(std::move(catalog)),verification_(active_verification?active_verification:std::make_shared<ResourceVerificationEnvironment>()) {
    if(catalog_.at("schema")!=1||catalog_.at("resources").empty()||catalog_.at("resources").size()>256)throw std::runtime_error("Invalid resource catalog");
    size_t i{};
    for(const auto& resource:catalog_.at("resources")) {
        const auto file=resource.at("path").get<std::string>();const auto key=folded(path(file).generic_wstring());
        if(!paths_.emplace(key,i).second)throw std::runtime_error("Duplicate catalog resource");
        if(resource.at("kind")!="font"&&resource.at("kind")!="sprite"&&resource.at("kind")!="image")throw std::runtime_error("Unknown resource kind");
        const auto storage=resource.value("storage",std::string("loose"));
        if(storage!="loose"&&storage!="packed")throw std::runtime_error("Unknown resource storage");
        if(resource.at("files").empty()||resource.at("files").size()>64)throw std::runtime_error("Resource dependency limit");
        bool has_main{};
        for(const auto& dependency:resource.at("files")) {
            const auto dep=dependency.at("path").get<std::string>();path(dep);has_main|=dep==file;
            const auto hash=dependency.at("sha256").get<std::string>();
            if(hash.size()!=64||hash.find_first_not_of("0123456789abcdef")!=std::string::npos)throw std::runtime_error("Invalid resource dependency hash");
        }
        if(storage=="loose"&&!has_main)throw std::runtime_error("Resource main file not hashed");
        if(storage=="packed") {
            const auto logical=resource.at("engine_path").get<std::string>();
            if(!logical.starts_with("gfx/")||logical.find("..")!=std::string::npos||logical.find('\\')!=std::string::npos||file!="resources/"+logical)
                throw std::runtime_error("Invalid packed engine path");
            path(logical);
            if(!catalog_.contains("packed_environment")||catalog_.at("packed_environment").empty()||catalog_.at("packed_environment").size()>64)
                throw std::runtime_error("Missing packed environment");
            for(const auto& dependency:resource.at("files")) {
                bool pinned{};for(const auto& archive:catalog_.at("packed_environment"))pinned|=archive==dependency;
                if(!pinned)throw std::runtime_error("Packed archive not in frozen environment");
            }
            const auto& entries=resource.at("packed_entries");bool packed_main{};
            if(!entries.is_array()||entries.empty()||entries.size()>64)throw std::runtime_error("Invalid packed entry catalog");
            for(const auto& entry:entries) {
                const auto name=entry.at("entry").get<std::string>();path(name);
                if(!name.starts_with("resources/gfx/")||name.find("..")!=std::string::npos||name.find('\\')!=std::string::npos)throw std::runtime_error("Invalid packed dependency entry");
                packed_main|=name==file;
                bool pinned{};for(const auto& dependency:resource.at("files"))pinned|=dependency.at("path")=="resources/packed/"+entry.at("archive").get<std::string>()&&dependency.at("sha256")==entry.at("archive_sha256");
                if(!pinned)throw std::runtime_error("Packed entry provider not hashed");
                if(!entry.at("bytes").is_number_integer()||entry.at("bytes").get<int64_t>()<1||entry.at("bytes").get<int64_t>()>4*1024*1024||!entry.at("offset").is_number_integer()||entry.at("offset").get<int64_t>()<14)throw std::runtime_error("Invalid packed entry bounds");
                const auto hash=entry.at("sha256").get<std::string>();if(hash.size()!=64||hash.find_first_not_of("0123456789abcdef")!=std::string::npos)throw std::runtime_error("Invalid packed entry hash");
            }
            if(!packed_main)throw std::runtime_error("Packed resource main entry missing");
        }
        if(resource.at("kind")=="sprite") {
            const auto& frames=resource.at("animations");
            if(!frames.is_object()||frames.empty()||frames.size()>4096)throw std::runtime_error("Invalid sprite animation catalog");
            for(auto it=frames.begin();it!=frames.end();++it)if(it.key().empty()||it.key().size()>256||!it.value().is_number_integer()||it.value().get<int64_t>()<1||it.value().get<int64_t>()>100000)throw std::runtime_error("Invalid animation frame count");
            animation(i,resource.at("default_animation"));
            const auto layers=resource.value("layers",Json::array());std::vector<int64_t> seen;
            if(!layers.is_array()||layers.size()>4096)throw std::runtime_error("Invalid sprite layers");
            for(const auto& layer:layers){if(!layer.is_number_integer()||layer.get<int64_t>()<0||layer.get<int64_t>()>4095||std::find(seen.begin(),seen.end(),layer.get<int64_t>())!=seen.end())throw std::runtime_error("Invalid sprite layers");seen.push_back(layer.get<int64_t>());}
        }
        for(const auto& alias:resource.at("aliases")) {
            auto normalized=std::filesystem::path(wide(alias.get<std::string>())).lexically_normal();path(utf8(normalized.wstring()));
            if(normalized.has_root_path()||!aliases_.emplace(folded(normalized.generic_wstring()),i).second)throw std::runtime_error("Ambiguous resource alias");
        }
        ++i;
    }
}
ResourceCapabilities::~ResourceCapabilities()=default;
Json ResourceCapabilities::compiled_catalog() {return Json::parse(resource_catalog_source);}
size_t ResourceCapabilities::resolve(const std::string& requested,const char* kind) const {
    const auto absolute=path(requested);auto found=paths_.find(folded(absolute.generic_wstring()));size_t index{};
    if(found!=paths_.end())index=found->second;
    else {
        auto relative=std::filesystem::path(wide(requested));
        if(relative.has_root_path())throw std::runtime_error("Unverified native resource: "+requested);
        auto alias=aliases_.find(folded(relative.lexically_normal().generic_wstring()));
        if(alias==aliases_.end())throw std::runtime_error("Unverified native resource: "+requested);index=alias->second;
    }
    if(catalog_.at("resources").at(index).at("kind")!=kind)throw std::runtime_error("Native resource kind mismatch");return index;
}
void ResourceCapabilities::verify_file(const Json& file) const {
        auto absolute=path(file.at("path"));auto current=game_;
        auto attributes=GetFileAttributesW(current.c_str());
        if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_REPARSE_POINT))throw std::runtime_error("Reparse/missing game resource root");
        for(const auto& part:absolute.lexically_relative(game_)) {
            current/=part;attributes=GetFileAttributesW(current.c_str());
            if(attributes==INVALID_FILE_ATTRIBUTES||(attributes&FILE_ATTRIBUTE_REPARSE_POINT))throw std::runtime_error("Reparse/missing resource dependency");
        }
        if(!std::filesystem::is_regular_file(absolute))throw std::runtime_error("Changed resource dependency: "+file.at("path").get<std::string>());
        if(absolute.extension()==L".a"&&absolute.parent_path()==game_/L"resources/packed")verification_->verify(absolute,file.at("sha256").get<std::string>());
        else if(sha256_file(absolute)!=file.at("sha256").get<std::string>())throw std::runtime_error("Changed resource dependency: "+file.at("path").get<std::string>());
}
void ResourceCapabilities::verify_packed_environment() {
    std::vector<std::wstring> expected,actual;
    for(const auto& entry:catalog_.at("packed_environment")) {
        auto absolute=path(entry.at("path"));
        if(absolute.parent_path()!=game_/L"resources/packed"||absolute.extension()!=L".a")throw std::runtime_error("Invalid packed environment archive");
        if(!packed_verified_) {
            verify_file(entry);
        }
        expected.push_back(folded(absolute.filename().wstring()));
    }
    for(const auto& item:std::filesystem::directory_iterator(game_/L"resources/packed"))if(folded(item.path().extension().wstring())==L".a")actual.push_back(folded(item.path().filename().wstring()));
    std::sort(expected.begin(),expected.end());std::sort(actual.begin(),actual.end());
    if(actual!=expected)throw std::runtime_error("Changed packed archive inventory");packed_verified_=true;
}
void ResourceCapabilities::verify(size_t index) {
    const auto& resource=catalog_.at("resources").at(index);
    if(resource.value("storage",std::string("loose"))!="packed") {for(const auto& file:resource.at("files"))verify_file(file);return;}
    verify_packed_environment();
    // Engine resolution remains logical for packed assets. Refuse a loose
    // override instead of claiming to know an unverified resolver priority.
    for(const auto& entry:resource.at("packed_entries")) {
        auto logical=entry.at("entry").get<std::string>();
        if(!logical.starts_with("resources/gfx/")||logical.find("..")!=std::string::npos)throw std::runtime_error("Invalid packed dependency entry");
        auto relative=wide(logical.substr(10));path(utf8(relative));
        if(std::filesystem::exists(game_/relative))throw std::runtime_error("Loose override of packed resource");
        std::vector<std::filesystem::path> roots={game_};
        if(std::filesystem::exists(game_/L"mods"))for(const auto& mod:std::filesystem::directory_iterator(game_/L"mods"))if(mod.is_directory())roots.push_back(mod.path());
        for(const auto& root:roots)for(const auto& folder:std::filesystem::directory_iterator(root))
            if(folder.is_directory()&&folder.path().filename().wstring().starts_with(L"resources")&&std::filesystem::exists(folder.path()/relative))throw std::runtime_error("Loose override of packed resource");
    }
}
std::string ResourceCapabilities::load_path(size_t index) const {
    const auto& resource=catalog_.at("resources").at(index);
    return resource.value("storage",std::string("loose"))=="packed"?resource.at("engine_path").get<std::string>():utf8(path(resource.at("path")).generic_wstring());
}
std::pair<uint64_t,uint64_t> ResourceCapabilities::receiver(const std::vector<Json>& args) const {
    if(args.empty()||args[0].at("t")!="ref"||args[0].at("kind")!="userdata")throw std::runtime_error("Resource object receiver required");return {args[0].at("scope"),args[0].at("id")};
}
void ResourceCapabilities::animation(size_t index,const std::string& name,const Json* frame) const {
    const auto& frames=catalog_.at("resources").at(index).at("animations");
    if(!frames.contains(name))throw std::runtime_error("Unverified sprite animation: "+name);
    if(frame&& (frame->at("t")!="integer"||frame->at("v").get<int64_t>()<0||frame->at("v").get<int64_t>()>=frames.at(name).get<int64_t>()))throw std::runtime_error("Sprite frame outside verified animation");
}
void ResourceCapabilities::prepare(const std::string& label,const std::string& operation,std::vector<Json>& args) {
    if(operation!="call")return;
    if(label=="Sprite.Load"||label=="Font.Load") {
        count(args,2,3);receiver(args);
        if(label=="Sprite.Load")optional_boolean(args,2);
        else if(args.size()==3&&text(args[2])!="")throw std::runtime_error("Only empty Font.Load compatibility argument verified");
        auto index=resolve(text(args[1]),label=="Sprite.Load"?"sprite":"font");verify(index);
        // A failed reload can leave an unknown native animation state. Revoke
        // the old capability before invoking Load; completion alone restores it.
        if(label=="Sprite.Load")sprites_.erase(receiver(args));
        else fonts_.erase(receiver(args));
        // Pin engine resolution to the catalog file, including legacy ../ paths.
        args[1]=wire(load_path(index));return;
    }
    if(label.starts_with("Font.")) {
        if(!fonts_.contains(receiver(args)))throw std::runtime_error("Font resource has not loaded successfully");
        if(label=="Font.GetStringWidth") {count(args,2,2);if(args[1].at("t")!="string"||args[1].at("hex").get_ref<const std::string&>().size()>131072)throw std::runtime_error("Font measurement string limit");}
        else if(label=="Font.IsLoaded")count(args,1,1);
        else if(label=="Font.SetMissingCharacter") {count(args,2,2);if(args[1].at("t")!="integer"||args[1].at("v").get<int64_t>()<0||args[1].at("v").get<int64_t>()>65535)throw std::runtime_error("Unverified missing character range");}
        else throw std::runtime_error("Unverified font operation: "+label);
        return;
    }
    if(!label.starts_with("Sprite."))return;
    auto found=sprites_.find(receiver(args));if(found==sprites_.end())throw std::runtime_error("Sprite resource has not loaded successfully");
    auto& state=found->second;
    if(!state.valid)throw std::runtime_error("Sprite resource state invalid after incomplete native call");
    if(label=="Sprite.Play") {count(args,2,3);optional_boolean(args,2);animation(state.resource,text(args[1]));}
    else if(label=="Sprite.SetFrame") {
        count(args,2,3);
        if(args.size()==2)animation(state.resource,state.animation,&args[1]);
        else animation(state.resource,text(args[1]),&args[2]);
    }
    else if(label=="Sprite.GetFrame"||label=="Sprite.GetAnimation"||label=="Sprite.GetFilename")count(args,1,1);
    else if(label=="Sprite.ReplaceSpritesheet") {
        count(args,3,3);const auto& layers=catalog_.at("resources").at(state.resource).at("layers");
        if(args[1].at("t")!="integer"||std::find(layers.begin(),layers.end(),args[1].at("v"))==layers.end())throw std::runtime_error("Unverified sprite layer");
        auto image=resolve(text(args[2]),"image");verify(image);args[2]=wire(load_path(image));state.valid=false;
    }
    else if(label=="Sprite.LoadGraphics") {
        count(args,1,1);verify(state.resource);for(const auto& replacement:state.replacements)verify(replacement.second);state.valid=false;
    }
    else throw std::runtime_error("Unverified sprite operation: "+label);
}
void ResourceCapabilities::completed(const std::string& label,const std::string& operation,const std::vector<Json>& args,const std::vector<Json>&) {
    if(operation!="call")return;
    if(label=="Sprite.Load")sprites_[receiver(args)]={resolve(text(args[1]),"sprite"),"",true,{}};
    else if(label=="Font.Load")fonts_[receiver(args)]=resolve(text(args[1]),"font");
    else if(label=="Sprite.Play"||(label=="Sprite.SetFrame"&&args.size()==3))sprites_.at(receiver(args)).animation=text(args[1]);
    else if(label=="Sprite.ReplaceSpritesheet") {auto& state=sprites_.at(receiver(args));state.replacements[args[1].at("v").get<int64_t>()]=resolve(text(args[2]),"image");state.valid=true;}
    else if(label=="Sprite.LoadGraphics")sprites_.at(receiver(args)).valid=true;
}
Json ResourceCapabilities::inventory() const {return catalog_;}
void install_resource_capabilities(LuaObjectBridge& bridge,const std::filesystem::path& game) {
    auto resources=std::make_shared<ResourceCapabilities>(game,ResourceCapabilities::compiled_catalog());
    bridge.set_call_adapter([resources](const auto& label,const auto& op,auto& args){resources->prepare(label,op,args);},
        [resources](const auto& label,const auto& op,const auto& args,const auto& results){resources->completed(label,op,args,results);});
}
}
