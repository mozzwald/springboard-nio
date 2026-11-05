#!/usr/bin/env python3
"""Verify actual linked bus code against the proven ELF and UF2 payload vs BIN."""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

def sections(path):
    blob=path.read_bytes()
    assert blob[:6]==b'\x7fELF\x01\x01'
    off=struct.unpack_from('<I',blob,32)[0]
    size,n,shstr=struct.unpack_from('<3H',blob,46)
    rows=[struct.unpack_from('<10I',blob,off+i*size) for i in range(n)]
    names=rows[shstr];strings=blob[names[4]:names[4]+names[5]]
    return {strings[r[0]:].split(b'\0')[0].decode():(r[3],blob[r[4]:r[4]+r[5]]) for r in rows if r[1]!=8}

def function(path,name):
    symbols=subprocess.check_output(['arm-none-eabi-nm','-S',str(path)],text=True)
    row=next(l.split() for l in symbols.splitlines() if l.split()[-1]==name)
    address,length=int(row[0],16)&~1,int(row[1],16)
    for start,blob in sections(path).values():
        if start<=address and address+length<=start+len(blob):return address,blob[address-start:address-start+length]
    raise AssertionError(name)

def verify(root,baseline):
    build=root/'build/m3/firmware';candidate=build/'sbnio.elf'
    result={}
    for name in ['sb_persistent_reply','sb_pio_rearm_program_init']:
        a,x=function(baseline,name);b,y=function(candidate,name)
        assert a==b and x==y,(name,'bus-code regression')
        result[name]={'address':hex(b),'bytes':len(y),'byte_identical_to_baseline':True,'sha256':hashlib.sha256(y).hexdigest()}
    rom=(root/'palm/build/shared/niolib-m3.rom').read_bytes()
    assert candidate.read_bytes().count(rom)==1
    binary=(build/'sbnio.bin').read_bytes();uf2=(build/'sbnio.uf2').read_bytes()
    assert len(uf2)%512==0
    chunks={};count=len(uf2)//512
    baseline_uf2=baseline.with_suffix('.uf2').read_bytes()
    main_count=None;markers=0
    for i in range(count):
        block=uf2[i*512:(i+1)*512]
        magic1,magic2,flags,addr,size,seq,total,family=struct.unpack_from('<8I',block)
        assert (magic1,magic2)==(0x0a324655,0x9e5d5157)
        assert struct.unpack_from('<I',block,508)[0]==0x0ab16f30
        assert size==256 and flags&0x2000
        if flags&0x8000: # RP2350 picotool compatibility marker, not program data
            assert block==baseline_uf2[i*512:(i+1)*512]
            markers+=1
            continue
        assert seq==len(chunks) and (main_count is None or main_count==total)
        main_count=total
        assert addr not in chunks
        chunks[addr]=block[32:32+size]
    assert markers==1 and len(chunks)==main_count
    start=min(chunks)
    assert start==0x10000000
    joined=b''.join(chunks[a] for a in range(start,start+main_count*256,256))
    assert joined[:len(binary)]==binary
    result.update({'embedded_rom_byte_exact':True,'uf2_matches_binary':True,'uf2_blocks':count,'uf2_family':hex(family),'hardware_qualified':False})
    (root/'build/m3/firmware-differential.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True,type=Path)
    args=parser.parse_args()
    verify(Path(__file__).resolve().parents[1],args.baseline)
