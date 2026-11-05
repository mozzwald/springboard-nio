#!/usr/bin/env python3
"""Verify actual linked bus code against the proven ELF and UF2 payload vs BIN."""
import argparse
import hashlib
import json
import re
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

def verify(root,baseline,build_dir=None,rom_path=None,report_path=None):
    build=build_dir or root/'build/m3/firmware';candidate=build/'sbnio.elf'
    result={}
    for name in ['sb_persistent_reply','sb_pio_rearm_program_init']:
        a,x=function(baseline,name);b,y=function(candidate,name)
        assert a==b and x==y,(name,'bus-code regression')
        result[name]={'address':hex(b),'bytes':len(y),'byte_identical_to_baseline':True,'sha256':hashlib.sha256(y).hexdigest()}
    # Larger embedded ROM relocates ordinary SRAM globals. Compare actual
    # startup/service opcodes separately from their trailing literal pools.
    for name in ['main','core1_service','bus_pins_init','bus_write_capture_init','bus_launch_core1']:
        a,x=function(baseline,name);b,y=function(candidate,name)
        dis=subprocess.check_output(['arm-none-eabi-objdump','-d','--disassemble='+name,str(candidate)],text=True)
        literals=re.findall(r'^([0-9a-f]+):\s+[^\n]*\.word',dis,re.M)
        length=int(literals[0],16)-b if literals else len(y)
        assert a==b and len(x)==len(y) and x[:length]==y[:length],(name,'instruction regression')
        result[name]={'address':hex(b),'opcode_bytes':length,'opcodes_identical':True,
                      'literal_pool_changed':x[length:]!=y[length:]}
    def symbol(path,name):
        rows=subprocess.check_output(['arm-none-eabi-nm','-S',str(path)],text=True).splitlines()
        row=next(l.split() for l in rows if l.split()[-1]==name)
        return int(row[0],16)
    old_table=symbol(baseline,'table_backing');new_table=symbol(candidate,'table_backing')
    ram_end=symbol(candidate,'__end__')
    assert old_table%16==new_table%16==0 and new_table+0x20010<=ram_end<=0x20080000
    result['sram']={'baseline_table':hex(old_table),'candidate_table':hex(new_table),
                    'word_table_mod16':8,'main_ram_end':hex(ram_end),
                    'main_ram_remaining':0x20080000-ram_end}
    rom=(rom_path or root/'palm/build/shared/niolib-m3.rom').read_bytes()
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
    (report_path or root/'build/m3/firmware-differential.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True,type=Path)
    parser.add_argument('--build',type=Path)
    parser.add_argument('--rom',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    verify(Path(__file__).resolve().parents[1],args.baseline,args.build,args.rom,args.report)
