#pragma once
#include "core.hpp"
#include <filesystem>
#include <mutex>
#include <fstream>
#include <windows.h>
namespace ia {
std::string sha256_file(const std::filesystem::path& path);
std::string sha256_bytes(const std::string& bytes);
bool supported_game(const std::filesystem::path& path);
std::string utf8(const std::wstring& value);
std::wstring wide(const std::string& value);
class Log {
    std::ofstream file_;
    std::mutex mutex_;
public:
    void open(const std::filesystem::path& path);
    void write(const std::string& event, Json data = Json::object());
};
}
