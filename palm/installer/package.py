#!/usr/bin/env python3
"""Build and independently verify the RAM PRC, RAM-installing Setup ROM."""
import binascii
import hashlib
import json
import re
import struct
import sys
from pathlib import Path


def resources(data):
    assert len(data) >= 78 and struct.unpack_from('>H', data, 32)[0] & 1
    count = struct.unpack_from('>H', data, 76)[0]
    rows = [struct.unpack_from('>4sHI', data, 78+10*i) for i in range(count)]
    assert count and rows[0][2] >= 78+10*count
    assert all(rows[i][2] <= rows[i+1][2] for i in range(count-1))
    assert rows[-1][2] <= len(data)
    return {(typ, ident): data[start:rows[i+1][2] if i+1<count else len(data)]
            for i, (typ, ident, start) in enumerate(rows)}


def verify(b, lib, test, config=None):
    prcs = [lib, test, b/'isstracker.prc', b/'weather.prc']
    if config: prcs.append(config)
    setup = (b/'installer.prc').read_bytes()
    assert setup[60:68] == b'HsSUHsCd'
    src = resources(setup)
    result = {'hardware_qualified': False, 'applications': {}}
    for i, p in enumerate(prcs):
        data = p.read_bytes()
        payload = src[b'nPRC', 1000+i]
        size, crc = struct.unpack_from('>II', payload)
        assert payload[8:] == data and size == len(data) and crc == binascii.crc32(data)
        assert data[60:68] == [b'librNiL1', b'applNiT1', b'applNBFI', b'applNBFW', b'applNiC1'][i]
        resources(data)
        result['applications'][p.name] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    for name in ['isstracker', 'weather']:
        symbols = (b/name/(name+'.symbols')).read_text()
        for forbidden in ['fn_packet_', 'fn_palmos_', 'fn_transport_', 'sbn_exchange', 'fn_sessions', 'nl_original_exchange']:
            assert forbidden not in symbols, (name, forbidden)
        for expected in ['fn_init', 'fn_shutdown', 'fn_open_translated', 'fuji_palmos_close']:
            assert re.search(r'\b'+expected+r'$', symbols, re.M), (name, expected)
        dis = (b/name/(name+'.dis')).read_text()
        assert 'a80b' in dis.lower() and 'a809' in dis.lower()
    rom = (b/('niolib-m5.rom' if config else 'niolib-m3.rom')).read_bytes()
    u16 = lambda off: struct.unpack_from('>H', rom, off)[0]
    u32 = lambda off: struct.unpack_from('>I', rom, off)[0]
    ptr = lambda off: u32(off)-0x08000000
    assert 512 <= len(rom) <= 65536 and len(rom)%2 == 0
    assert u32(8) == 0xfeedbeef and u32(256) == 0xfeedface
    assert u32(108) == len(rom)
    assert binascii.crc_hqx(rom[114:], binascii.crc_hqx(rom[:112], 0)) == u16(112)
    token = ptr(100)
    assert rom[token:token+9] == b'HsAT\0\x03330'
    directory = ptr(316)
    assert u32(directory) == 0 and u16(directory+4) == 1
    db = ptr(directory+6)
    assert rom[db:db+32] == setup[:32] and rom[db+60:db+68] == b'HsSUHsCd'
    assert u16(db+32)&3 == 3 and u16(db+76) == len(src)
    for i in range(len(src)):
        pos = db+78+10*i
        key = (rom[pos:pos+4], u16(pos+4))
        off = ptr(pos+6)
        header = u32(off-8)
        assert not header & 0x80000000
        size = (header & 0xffffff)-8-((header>>24)&15)
        assert 0 <= off <= off+size <= len(rom)
        assert rom[off:off+size] == src.pop(key)
    assert not src
    result['rom'] = {'size': len(rom), 'sha256': hashlib.sha256(rom).hexdigest(), 'crc16': hex(u16(112)), 'access_ns': 330}
    (b/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    action, dest, *args = sys.argv[1:]
    dest = Path(dest)
    if action == 'resources':
        for i, name in enumerate(args):
            data = Path(name).read_bytes()
            resources(data)
            (dest/f'nPRC{1000+i:04x}.bin').write_bytes(struct.pack('>II', len(data), binascii.crc32(data))+data)
    elif action == 'setup':
        data = bytearray(dest.read_bytes())
        assert data[60:68] == b'applHsCd'
        struct.pack_into('>HH', data, 32, 1, 3)
        data[36:52] = bytes(16)
        data[60:68] = b'HsSUHsCd'
        Path(args[0]).write_bytes(data)
    elif action == 'verify':
        verify(dest, *map(Path, args))
    else:
        raise SystemExit('unknown action')
