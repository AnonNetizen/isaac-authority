"""Read selected archive entries; never extract into the game installation.

Adapted Python implementation of Gibbed.Rebirth's ArchiveFile/ArchiveEntry.
https://github.com/gibbed/Gibbed.Rebirth (2017 Rick); this is an altered version.
Only Bogocrypt1 and MiniZ entries are supported. Other modes fail.
"""
# Copyright (c) 2017 Rick (rick 'at' gibbed 'dot' us)
# This software is provided 'as-is', without any express or implied warranty.
# In no event will the authors be held liable for any damages arising from
# the use of this software.
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would
#    be appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not
#    be misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.
import hashlib
import struct
import zlib

MASK = 0xffffffff
LIMIT = 4 * 1024 * 1024


def isaac_words(high):
    seed = (high << 32) | ((high ^ ((high ^ (high << 15)) << 8) ^ (high >> 9)) & MASK)
    values = []
    for _ in range(256):
        part, shift = ((seed >> 27) ^ (seed >> 45)) & MASK, seed >> 59
        values.append(((part >> shift) | (part << ((-shift) & 31))) & MASK)
        seed = (seed * 6364136223846793005 + 127) & 0xffffffffffffffff

    def mix(v):
        for i, shift in enumerate((11, -2, 8, -16, 10, -4, 8, -9)):
            j, k, l = (i + 1) % 8, (i + 3) % 8, (i + 2) % 8
            v[i] = (v[i] ^ (v[j] << shift if shift > 0 else v[j] >> -shift)) & MASK
            v[k] = (v[k] + v[i]) & MASK
            v[j] = (v[j] + v[l]) & MASK

    v = [0x9e3779b9] * 8
    for _ in range(4):
        mix(v)
    state = [0] * 256
    for source in (values, state):
        for i in range(0, 256, 8):
            v = [(a + b) & MASK for a, b in zip(v, source[i:i + 8])]
            mix(v)
            state[i:i + 8] = v
    a = b = c = 0
    while True:
        c = (c + 1) & MASK
        b = (b + c) & MASK
        result = []
        for i in range(256):
            x = state[i]
            shift = (13, -6, 2, -16)[i % 4]
            a = (a ^ (a << shift if shift > 0 else a >> -shift)) & MASK
            a = (a + state[(i + 128) % 256]) & MASK
            y = (state[(x >> 2) & 255] + a + b) & MASK
            state[i] = y
            b = (state[(y >> 10) & 255] + x) & MASK
            result.append(b)
        yield from result


def name_hash(name):
    a, b = 5381, 0x5bb2220e
    for c in name.lower().encode("ascii"):
        a = (a * 33 + c) & MASK
        b = ((b ^ c) * 0x1000193) & MASK
    return a, b


def checksum(data):
    block, value = bytearray(512), 0xababeb98
    for offset in range(0, len(data), 512):
        part = data[offset:offset + 512]
        block[:len(part)] = part  # The format retains final-word padding.
        for word in range(0, (len(part) + 3) // 4 * 4, 4):
            value = ((value >> 1) + (value << 31) + struct.unpack_from("<I", block, word)[0]) & MASK
    return value


class Archive:
    def __init__(self, path):
        self.path, self.size = path, path.stat().st_size
        with path.open("rb") as source:
            header = source.read(14)
            if len(header) != 14:
                raise ValueError("Truncated archive header")
            magic, self.mode, offset, count = struct.unpack("<7sBIH", header)
            if magic != b"ARCH000" or offset < 14 or offset + count * 20 > self.size:
                raise ValueError("Invalid archive index bounds")
            source.seek(offset)
            self.entries = {}
            for entry in struct.iter_unpack("<IIIII", source.read(count * 20)):
                key = entry[:2]
                if key in self.entries or entry[2] < 14 or entry[2] >= self.size:
                    raise ValueError("Invalid/duplicate archive entry")
                self.entries[key] = entry
        self.sha256 = None

    def read(self, name):
        entry = self.entries[name_hash(name)]
        _, high, offset, length, expected = entry
        if not 0 < length <= LIMIT:
            raise ValueError("Packed entry size limit")
        with self.path.open("rb") as source:
            source.seek(offset)

            def exact(count):
                value = source.read(count)
                if len(value) != count:
                    raise ValueError("Truncated packed entry")
                return value

            if self.mode == 0:
                data = bytearray(exact((length + 3) & ~3))
                key = (high ^ 0xf9524287) | 1
                for word in range(0, len(data), 4):
                    for byte in range(4):
                        data[word + byte] ^= (key >> (8 * byte)) & 255
                    swap = {2: (3, 2, 1, 0), 9: (1, 0, 3, 2), 13: (2, 3, 0, 1)}.get(key & 15)
                    if swap:
                        part = data[word:word + 4]
                        data[word:word + 4] = bytes(part[i] for i in swap)
                    left = (key << 8) & MASK
                    middle = (key ^ left) >> 9
                    key = (key ^ middle ^ left ^ ((middle ^ key ^ left) << 23)) & MASK
                data = bytes(data[:length])
            elif self.mode == 2:
                result = bytearray()
                words, raw = None, False
                for _ in range((length + 1023) // 1024):
                    flags, = struct.unpack("<I", exact(4))
                    count, last = flags & 0x7fffffff, bool(flags >> 31)
                    if not 0 < count <= 2048:
                        raise ValueError("Invalid MiniZ block")
                    block = exact(count)
                    expected_size = min(1024, length - len(result))
                    if raw or (count == 1024 and not last):
                        raw = True
                        if words is None:
                            words = isaac_words(high)
                        decoded = bytearray(block)
                        for offset in range(0, count, 4):
                            word = next(words)
                            for byte in range(min(4, count - offset)):
                                decoded[offset + byte] ^= (word >> (8 * byte)) & 255
                        if count != expected_size:
                            raise ValueError("Invalid MiniZ raw block length")
                    else:
                        decoder = zlib.decompressobj(-15)
                        decoded = decoder.decompress(block, expected_size + 1)
                        if len(decoded) != expected_size or decoder.unconsumed_tail or decoder.unused_data:
                            raise ValueError("Invalid MiniZ decoded block")
                    result.extend(decoded)
                    if last:
                        if len(result) != length or (not raw and not decoder.eof):
                            raise ValueError("Invalid MiniZ final block")
                        break
                else:
                    raise ValueError("Missing MiniZ final block")
                data = bytes(result)
            else:
                raise ValueError("Unsupported archive compression mode")
        if checksum(data) != expected:
            raise ValueError("Packed entry checksum mismatch")
        if self.sha256 is None:
            with self.path.open("rb") as source:
                self.sha256 = hashlib.file_digest(source, "sha256").hexdigest()
        return data, {"archive": self.path.name, "entry": name, "offset": offset, "bytes": length,
                      "checksum": expected, "sha256": hashlib.sha256(data).hexdigest(), "archive_sha256": self.sha256}
