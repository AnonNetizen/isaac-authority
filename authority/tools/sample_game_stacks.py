"""Read-only stack sampler for the running x86 game process.

Suspends each thread for a few microseconds, reads EIP/EBP/ESP and a bounded stack
window, keeps only addresses that fall inside the module's .text section, then resumes
the thread. It never writes target memory, never injects a DLL and does not use a
debugger interface. Samples are anonymous module-relative RVAs; no strings, no heap
contents and no save data are captured.

Use it while the game is in a normal single-player run, then analyze the JSONL with
analyze_game_stacks.py.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import struct
import sys
import time
from pathlib import Path

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
THREAD_SUSPEND_RESUME = 0x0002
THREAD_GET_CONTEXT = 0x0008
THREAD_QUERY_INFORMATION = 0x0040
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPTHREAD = 0x00000004
LIST_MODULES_32BIT = 0x01
CONTEXT_I386 = 0x00010000
CONTEXT_CONTROL = CONTEXT_I386 | 0x0001
CONTEXT_INTEGER = CONTEXT_I386 | 0x0002
CONTEXT_FULL_X86 = CONTEXT_CONTROL | CONTEXT_INTEGER
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
STILL_ACTIVE = 259


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", wt.LONG),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ThreadID", wt.DWORD),
        ("th32OwnerProcessID", wt.DWORD),
        ("tpBasePri", wt.LONG),
        ("tpDeltaPri", wt.LONG),
        ("dwFlags", wt.DWORD),
    ]


class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ("lpBaseOfDll", ctypes.c_void_p),
        ("SizeOfImage", wt.DWORD),
        ("EntryPoint", ctypes.c_void_p),
    ]


class CONTEXT(ctypes.Structure):
    _fields_ = [
        ("ContextFlags", wt.DWORD),
        ("Dr0", wt.DWORD), ("Dr1", wt.DWORD), ("Dr2", wt.DWORD), ("Dr3", wt.DWORD),
        ("Dr6", wt.DWORD), ("Dr7", wt.DWORD),
        ("FloatSave", ctypes.c_byte * 112),
        ("SegGs", wt.DWORD), ("SegFs", wt.DWORD), ("SegEs", wt.DWORD), ("SegDs", wt.DWORD),
        ("Edi", wt.DWORD), ("Esi", wt.DWORD), ("Ebx", wt.DWORD), ("Edx", wt.DWORD),
        ("Ecx", wt.DWORD), ("Eax", wt.DWORD), ("Ebp", wt.DWORD), ("Eip", wt.DWORD),
        ("SegCs", wt.DWORD), ("EFlags", wt.DWORD), ("Esp", wt.DWORD), ("SegSs", wt.DWORD),
        ("ExtendedRegisters", ctypes.c_byte * 512),
    ]


kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenThread.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenThread.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL
kernel32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wt.BOOL
kernel32.SuspendThread.argtypes = [wt.HANDLE]
kernel32.SuspendThread.restype = wt.DWORD
kernel32.ResumeThread.argtypes = [wt.HANDLE]
kernel32.ResumeThread.restype = wt.DWORD
kernel32.GetThreadContext.argtypes = [wt.HANDLE, ctypes.POINTER(CONTEXT)]
kernel32.GetThreadContext.restype = wt.BOOL
kernel32.Wow64SuspendThread.argtypes = [wt.HANDLE]
kernel32.Wow64SuspendThread.restype = wt.DWORD
kernel32.Wow64GetThreadContext.argtypes = [wt.HANDLE, ctypes.c_void_p]
kernel32.Wow64GetThreadContext.restype = wt.BOOL
kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
kernel32.Thread32First.argtypes = [wt.HANDLE, ctypes.POINTER(THREADENTRY32)]
kernel32.Thread32First.restype = wt.BOOL
kernel32.Thread32Next.argtypes = [wt.HANDLE, ctypes.POINTER(THREADENTRY32)]
kernel32.Thread32Next.restype = wt.BOOL
kernel32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wt.BOOL
kernel32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wt.BOOL
kernel32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
kernel32.GetExitCodeProcess.restype = wt.BOOL
psapi.EnumProcessModulesEx.argtypes = [wt.HANDLE, ctypes.POINTER(wt.HMODULE), wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD]
psapi.EnumProcessModulesEx.restype = wt.BOOL
psapi.GetModuleInformation.argtypes = [wt.HANDLE, wt.HMODULE, ctypes.POINTER(MODULEINFO), wt.DWORD]
psapi.GetModuleInformation.restype = wt.BOOL
psapi.GetModuleBaseNameW.argtypes = [wt.HANDLE, wt.HMODULE, wt.LPWSTR, wt.DWORD]
psapi.GetModuleBaseNameW.restype = wt.DWORD


def find_process(name: str = "isaac-ng.exe") -> int | None:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return None
        while True:
            if entry.szExeFile.lower() == name.lower():
                return int(entry.th32ProcessID)
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                return None
    finally:
        kernel32.CloseHandle(snapshot)


def process_alive(handle) -> bool:
    code = wt.DWORD()
    if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
        return False
    return code.value == STILL_ACTIVE


def read_memory(handle, address: int, size: int) -> bytes:
    buffer = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(got)):
        return buffer.raw[:got.value]
    return b""


def module_text_range(handle, module_base: int):
    header = read_memory(handle, module_base, 0x1000)
    if len(header) < 0x40 or header[:2] != b"MZ":
        raise RuntimeError("Could not read module PE header")
    pe = struct.unpack_from("<I", header, 0x3C)[0]
    nt = read_memory(handle, module_base + pe, 0x400)
    if len(nt) < 0x108 or nt[:4] != b"PE\0\0":
        raise RuntimeError("Could not read module NT header")
    section_count = struct.unpack_from("<H", nt, 6)[0]
    optional_size = struct.unpack_from("<H", nt, 20)[0]
    table = 24 + optional_size
    section_table = read_memory(handle, module_base + pe + table, section_count * 40)
    for index in range(section_count):
        at = index * 40
        name, virtual_size, virtual_address, raw_size, _ = struct.unpack_from("<8sIIII", section_table, at)
        if name.rstrip(b"\0") == b".text":
            size = max(virtual_size, raw_size)
            return module_base + virtual_address, size
    raise RuntimeError("No .text section in module")


def find_game_module(handle) -> tuple[int, int]:
    modules = (wt.HMODULE * 1024)()
    needed = wt.DWORD()
    if not psapi.EnumProcessModulesEx(handle, modules, ctypes.sizeof(modules), ctypes.byref(needed), LIST_MODULES_32BIT):
        raise OSError(ctypes.get_last_error(), "EnumProcessModulesEx failed")
    count = needed.value // ctypes.sizeof(wt.HMODULE)
    for index in range(count):
        module = modules[index]
        info = MODULEINFO()
        if not psapi.GetModuleInformation(handle, module, ctypes.byref(info), ctypes.sizeof(info)):
            continue
        name = ctypes.create_unicode_buffer(260)
        psapi.GetModuleBaseNameW(handle, module, name, 260)
        if name.value.lower() == "isaac-ng.exe":
            return int(info.lpBaseOfDll), int(info.SizeOfImage)
    raise RuntimeError("isaac-ng.exe module not found in process")


def enumerate_threads(pid: int) -> list[int]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot threads failed")
    result = []
    try:
        entry = THREADENTRY32()
        entry.dwSize = ctypes.sizeof(THREADENTRY32)
        if not kernel32.Thread32First(snapshot, ctypes.byref(entry)):
            return result
        while True:
            if entry.th32OwnerProcessID == pid:
                result.append(int(entry.th32ThreadID))
            if not kernel32.Thread32Next(snapshot, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snapshot)
    return result


def sample_thread(handle, thread_id: int, module_base: int, text_start: int, text_size: int, stack_bytes: int) -> dict | None:
    thread = kernel32.OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, False, thread_id)
    if not thread:
        return None
    try:
        wow64 = ctypes.sizeof(ctypes.c_void_p) == 8
        if wow64:
            if kernel32.Wow64SuspendThread(thread) == 0xFFFFFFFF:
                return None
        else:
            if kernel32.SuspendThread(thread) == 0xFFFFFFFF:
                return None
        try:
            if wow64:
                buffer = ctypes.create_string_buffer(2048)
                struct.pack_into("<I", buffer, 0, CONTEXT_FULL_X86)
                if not kernel32.Wow64GetThreadContext(thread, buffer):
                    return None
                raw = buffer.raw
                # WOW64_CONTEXT on this build starts the integer block 4 bytes earlier
                # than the 32-bit CONTEXT: ECX=172, EBP=180, EIP=184, ESP=196.
                ecx = struct.unpack_from("<I", raw, 172)[0]
                ebp = struct.unpack_from("<I", raw, 180)[0]
                eip = struct.unpack_from("<I", raw, 184)[0]
                esp = struct.unpack_from("<I", raw, 196)[0]
            else:
                context = CONTEXT()
                context.ContextFlags = CONTEXT_FULL_X86
                if not kernel32.GetThreadContext(thread, ctypes.byref(context)):
                    return None
                ecx = int(context.Ecx)
                ebp = int(context.Ebp)
                eip = int(context.Eip)
                esp = int(context.Esp)
            rvas = []
            offset = 0
            while offset < stack_bytes:
                chunk_size = min(0x100, stack_bytes - offset)
                chunk = read_memory(handle, esp + offset, chunk_size)
                if not chunk:
                    offset += 0x100
                    continue
                for position in range(0, len(chunk) - 3, 4):
                    value = struct.unpack_from("<I", chunk, position)[0]
                    if text_start <= value < text_start + text_size:
                        rva = value - module_base
                        if rva not in rvas:
                            rvas.append(rva)
                offset += len(chunk)
            return {
                "tid": thread_id,
                "eip_rva": eip - module_base if text_start <= eip < text_start + text_size else None,
                "ebp_rva": ebp - module_base if text_start <= ebp < text_start + text_size else None,
                "ecx": ecx,
                "esp": esp,
                "stack_rvas": rvas,
            }
        finally:
            if wow64:
                kernel32.ResumeThread(thread)
            else:
                kernel32.ResumeThread(thread)
    finally:
        kernel32.CloseHandle(thread)


def sample_once(handle, pid: int, module_base: int, text_start: int, text_size: int, stack_bytes: int) -> dict:
    threads = []
    for thread_id in enumerate_threads(pid):
        result = sample_thread(handle, thread_id, module_base, text_start, text_size, stack_bytes)
        if result:
            threads.append(result)
    return {"threads": threads}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process-id", type=int, help="isaac-ng.exe process id (auto-detected when omitted)")
    parser.add_argument("--wait", action="store_true", help="wait for isaac-ng.exe to start")
    parser.add_argument("--wait-timeout", type=float, default=300.0)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--interval-ms", type=float, default=20.0)
    parser.add_argument("--stack-bytes", type=int, default=0x1000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    pid = args.process_id
    deadline = time.monotonic() + args.wait_timeout
    while pid is None:
        pid = find_process()
        if pid is not None:
            break
        if not args.wait or time.monotonic() > deadline:
            print("isaac-ng.exe is not running; start the game (in a run) and pass --process-id or --wait.", file=sys.stderr)
            return 2
        time.sleep(0.5)

    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        print(f"OpenProcess({pid}) failed: {ctypes.get_last_error()}", file=sys.stderr)
        return 2
    try:
        module_base, module_size = find_game_module(handle)
        text_start, text_size = module_text_range(handle, module_base)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as stream:
            header = {
                "kind": "header",
                "pid": pid,
                "module_base": module_base,
                "module_size": module_size,
                "text_start": text_start,
                "text_size": text_size,
                "stack_bytes": args.stack_bytes,
            }
            stream.write(json.dumps(header) + "\n")
            written = 0
            for index in range(args.samples):
                if not process_alive(handle):
                    print("game process exited", file=sys.stderr)
                    break
                record = sample_once(handle, pid, module_base, text_start, text_size, args.stack_bytes)
                record.update({"kind": "sample", "index": index, "time": time.time()})
                stream.write(json.dumps(record) + "\n")
                written += 1
                time.sleep(args.interval_ms / 1000.0)
        print(json.dumps({"pid": pid, "samples": written, "output": str(args.output)}))
        return 0
    finally:
        kernel32.CloseHandle(handle)


if __name__ == "__main__":
    raise SystemExit(main())
