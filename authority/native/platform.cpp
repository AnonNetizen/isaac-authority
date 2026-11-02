#include "platform.hpp"
#include <bcrypt.h>
#include <array>
#include <iomanip>
#include <sstream>
#include <stdexcept>
namespace ia {
std::string sha256_bytes(const std::string& bytes) {
    BCRYPT_ALG_HANDLE algorithm{};BCRYPT_HASH_HANDLE hash{};DWORD used{},count{};
    if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0)throw std::runtime_error("SHA256 unavailable");
    if(BCryptGetProperty(algorithm,BCRYPT_OBJECT_LENGTH,reinterpret_cast<PUCHAR>(&count),sizeof(count),&used,0)<0){BCryptCloseAlgorithmProvider(algorithm,0);throw std::runtime_error("SHA256 object size unavailable");}
    std::vector<UCHAR> object(count);std::array<UCHAR,32> result{};
    bool ok=BCryptCreateHash(algorithm,&hash,object.data(),count,nullptr,0,0)>=0;
    for(size_t offset=0;ok&&offset<bytes.size();) {
        auto chunk=static_cast<ULONG>(std::min<size_t>(bytes.size()-offset,65536));
        ok=BCryptHashData(hash,reinterpret_cast<PUCHAR>(const_cast<char*>(bytes.data()+offset)),chunk,0)>=0;offset+=chunk;
    }
    if(ok)ok=BCryptFinishHash(hash,result.data(),static_cast<ULONG>(result.size()),0)>=0;
    if(hash)BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);
    if(!ok)throw std::runtime_error("SHA256 bytes failed");
    std::ostringstream out;out<<std::hex<<std::setfill('0');for(auto b:result)out<<std::setw(2)<<unsigned(b);return out.str();
}
std::string sha256_file(const std::filesystem::path& path) {
    BCRYPT_ALG_HANDLE algorithm{}; BCRYPT_HASH_HANDLE hash{};
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) throw std::runtime_error("SHA256 unavailable");
    DWORD bytes{}, object_bytes{};
    BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&object_bytes), sizeof(object_bytes), &bytes, 0);
    std::vector<UCHAR> object(object_bytes); std::array<UCHAR, 32> result{};
    if (BCryptCreateHash(algorithm, &hash, object.data(), object_bytes, nullptr, 0, 0) < 0) {
        BCryptCloseAlgorithmProvider(algorithm, 0); throw std::runtime_error("SHA256 creation failed");
    }
    std::ifstream file(path, std::ios::binary); std::array<char, 65536> buffer{};
    bool ok = file.is_open();
    while (file.read(buffer.data(), buffer.size()) || file.gcount())
        if (BCryptHashData(hash, reinterpret_cast<PUCHAR>(buffer.data()), static_cast<ULONG>(file.gcount()), 0) < 0) ok = false;
    if (!file.eof()) ok = false;
    if (BCryptFinishHash(hash, result.data(), static_cast<ULONG>(result.size()), 0) < 0) ok = false;
    BCryptDestroyHash(hash); BCryptCloseAlgorithmProvider(algorithm, 0);
    if (!ok) throw std::runtime_error("Could not hash game file");
    std::ostringstream out; out << std::hex << std::setfill('0'); for (auto b : result) out << std::setw(2) << unsigned(b); return out.str();
}
bool supported_game(const std::filesystem::path& path) {
    auto hash = sha256_file(path);
    return hash == "210cade2a1de98550cef52d012174108189d1a0d3926a22c3a1ec12fb3ae4831" ||
           hash == "7122ac28779925b24e23e2416f231322b1470388bd25e2c08665ad8d53b3ea4f";
}
std::string utf8(const std::wstring& s) {
    if (s.empty()) return {};
    int n = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), nullptr, 0, nullptr, nullptr);
    if (!n) throw std::runtime_error("Invalid UTF16");
    std::string result(n, '\0'); WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), result.data(), n, nullptr, nullptr); return result;
}
std::wstring wide(const std::string& s) {
    if (s.empty()) return {};
    int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), nullptr, 0);
    if (!n) throw std::runtime_error("Invalid UTF8");
    std::wstring result(n, L'\0'); MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), result.data(), n); return result;
}
void Log::open(const std::filesystem::path& path) {
    std::filesystem::create_directories(path.parent_path()); file_.open(path, std::ios::app);
    if (!file_) throw std::runtime_error("Could not open observation log");
}
void Log::write(const std::string& event, Json data) {
    std::lock_guard lock(mutex_);
    if (!file_) return;
    try { file_ << Json({{"event", event}, {"time_ms", GetTickCount64()}, {"data", std::move(data)}}).dump(-1, ' ', false, Json::error_handler_t::replace) << '\n'; file_.flush(); }
    catch (...) {} // Observer logging must never unwind through the game.
}
}
