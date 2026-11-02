"""Read exception registers and module-relative stack addresses from an x86 minidump.

Does not export memory contents, strings, or module paths. Stack scan hits are
candidates, not a symbolized stack. Crash dumps themselves stay outside bundles.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def inspect(path):
    data = path.read_bytes()
    def unpack(fmt, offset):
        return struct.unpack_from('<' + fmt, data, offset)
    if data[:4] != b'MDMP':
        raise ValueError('Not a minidump')
    count, directory = unpack('II', 8)
    streams = {}
    for i in range(count):
        kind, size, offset = unpack('III', directory + i * 12)
        streams[kind] = (size, offset)
    modules = []
    _, offset = streams[4]
    for i in range(unpack('I', offset)[0]):
        p = offset + 4 + i * 108
        base, size, _, _, name = unpack('QIIII', p)
        n = unpack('I', name)[0]
        filename = data[name + 4:name + 4 + n].decode('utf-16-le').replace('\\', '/').rsplit('/', 1)[-1]
        modules.append((base, size, filename))
    def location(address):
        for base, size, name in modules:
            if base <= address < base + size:
                return {'module': name, 'rva': hex(address - base)}
        return {'mapped_module': False}
    memory = []
    if 5 in streams:
        _, p = streams[5]
        for i in range(unpack('I', p)[0]):
            address, size, rva = unpack('QII', p + 4 + i * 16)
            memory.append((address, size, rva))
    if 9 in streams:
        _, p = streams[9]
        n, rva = unpack('QQ', p)
        for i in range(n):
            address, size = unpack('QQ', p + 16 + i * 16)
            memory.append((address, size, rva))
            rva += size
    if 3 in streams:
        _, p = streams[3]
        for i in range(unpack('I', p)[0]):
            address, size, rva = unpack('QII', p + 4 + i * 48 + 24)
            memory.append((address, size, rva))
    def read(address, size):
        for start, length, rva in memory:
            if start <= address and address + size <= start + length:
                return data[rva + address - start:rva + address - start + size]
        return None
    _, p = streams[6]
    thread = unpack('I', p)[0]
    code, flags, record, address, n = unpack('IIQQI', p + 8)
    parameters = unpack('Q' * min(n, 15), p + 40)
    context_size, context = unpack('II', p + 160)
    if context_size < 204 or not (unpack('I', context)[0] & 0x10000):
        raise ValueError('Not an x86 context')
    registers = {name: unpack('I', context + off)[0] for name, off in
                 [('edi', 156), ('esi', 160), ('ebx', 164), ('edx', 168), ('ecx', 172),
                  ('eax', 176), ('ebp', 180), ('eip', 184), ('esp', 196)]}
    frames, seen = [], set()
    bp = registers['ebp']
    for _ in range(32):
        raw = read(bp, 8)
        if not raw or bp in seen:
            break
        seen.add(bp)
        following, ret = struct.unpack('<II', raw)
        frames.append(location(ret))
        if following <= bp or following - bp > 1024 * 1024:
            break
        bp = following
    candidates = []
    for off in range(0, 2048, 4):
        raw = read(registers['esp'] + off, 4)
        if not raw:
            break
        loc = location(struct.unpack('<I', raw)[0])
        if 'module' in loc:
            candidates.append({'stack_offset': off, **loc})
        if len(candidates) >= 40:
            break
    result = {'dump_sha256': hashlib.sha256(data).hexdigest(), 'thread_id': thread,
              'exception_code': hex(code), 'fault': location(address),
              'exception_parameters': [hex(x) for x in parameters],
              'registers': {k: hex(v) for k, v in registers.items()},
              'ebp_chain_unsymbolized': frames, 'stack_scan_candidates': candidates,
              'stack_scan_is_not_verified_call_stack': True}
    raw = read(address, 32)
    if raw:
        try:
            from capstone import Cs, CS_ARCH_X86, CS_MODE_32
            result['fault_instructions'] = [{'offset_from_fault': x.address - address,
                'instruction': x.mnemonic + ' ' + x.op_str}
                for x in list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(raw, address))[:6]]
        except ImportError:
            result['disassembler_available'] = False
    # The first Sprite.Load crash has a known instruction boundary in its first
    # caller. Report only this small code span and its single global pointer.
    # No debug symbols are available, so the global's semantic type is unknown.
    if result['dump_sha256'] == '30d3595203131739006571160fdc50e5e2826dd4aa5086a7e66e37f416b48f39':
        base = next(base for base, _, name in modules if name == 'isaac-ng.exe')
        caller = read(base + 0xed95, 34)
        if caller:
            try:
                from capstone import Cs, CS_ARCH_X86, CS_MODE_32
                instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(caller, base + 0xed95))
                evidence = {'caller_instructions': [{'rva': hex(x.address - base),
                    'instruction': x.mnemonic + ' ' + x.op_str} for x in instructions],
                    'global_semantic_type_known': False}
                if caller[:2] == b'\x8b\x0d':
                    address = struct.unpack_from('<I', caller, 2)[0]
                    pointer = read(address, 4)
                    if pointer:
                        value = struct.unpack('<I', pointer)[0]
                        evidence.update(global_pointer_rva=hex(address-base),
                                        global_pointer_value=hex(value),
                                        global_pointer_is_null=value == 0)
                result['first_sprite_crash_caller_evidence'] = evidence
            except ImportError:
                pass
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dump', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = inspect(args.dump)
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf-8')
    print(text)
