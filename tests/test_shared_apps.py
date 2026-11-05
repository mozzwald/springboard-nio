"""Execute real app classic shim + client + shared library, mocked OS/NIO only.

Run with the library's Unicorn venv. Does not emulate GUI or claim hardware
qualification. Reuses the M2 harness rather than introducing a Palm emulator.
"""
import os
import re
import struct
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LIB = Path(os.environ.get('NIOLIB_ROOT', ROOT/'repos/fujinet-nio-lib')).resolve()
os.environ.setdefault('PALMOS_SHARED_BUILD', str(LIB/'build/palmos-shared-m3'))
sys.path.insert(0, str(LIB/'tests'))
import test_palmos_shared_network as net
from unicorn.m68k_const import UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_PC

class AppMachine(net.NetworkMachine):
    def __init__(self):
        self.missing_library = self.incompatible = False
        self.alerts = []
        super().__init__()

    def hook(self, uc, pc, size, context):
        if bytes(uc.mem_read(pc, 2)) == b'\x4e\x4f':
            trap, sp = self.read16(pc+2), uc.reg_read(UC_M68K_REG_A7)
            if trap == 0xa2ac and self.missing_library:
                uc.reg_write(UC_M68K_REG_D0, 1)
                uc.reg_write(UC_M68K_REG_PC, pc+4)
                return
            if trap == 0xa805 and self.incompatible:
                uc.mem_write(self.read32(sp+2), struct.pack('>4H', 8, 2, 0, 0))
                uc.reg_write(UC_M68K_REG_D0, 0)
                uc.reg_write(UC_M68K_REG_PC, pc+4)
                return
            if trap == 0xa194:  # FrmCustomAlert: preserved app GeneralAlert 9000
                self.alerts.append(self.read16(sp))
                uc.reg_write(UC_M68K_REG_D0, 0)
                uc.reg_write(UC_M68K_REG_PC, pc+4)
                return
        super().hook(uc, pc, size, context)

    def load_app(self, name, identity):
        assert not self.globals and not self.registered and not self.sessions
        path = ROOT/'palm/build/shared'/name/name
        blob = path.read_bytes()
        sections = net.foundation.image.coff_sections(blob)
        code = next(s['data'] for s in sections if s['name']=='.text')
        by_name={s['name']:s for s in sections}
        d,b=by_name['.data'],by_name['.bss']
        assert b['address']==d['size']
        data=bytearray(d['data'])+bytearray(b['size'])
        # Normal application .text also contains string literals, including
        # odd byte addresses; the strict library function-pointer serializer
        # deliberately does not support those. Model standard app relocations
        # here, without relaxing the production library serializer.
        reloc=by_name.get('.reloc',{}).get('data',b'')
        for off in range(0,len(reloc),12):
            kind,source,pos,target,reserved=struct.unpack_from('>HHIHH',reloc,off)
            assert kind==1 and reserved==0 and sections[source]['name']=='.data'
            target_name=sections[target]['name']
            assert target_name in ('.text','.data','.bss')
            value=struct.unpack_from('>I',data,pos)[0]
            struct.pack_into('>I',data,pos,value+(self.APP if target_name=='.text' else self.app_data))
        self.uc.mem_write(self.APP, b'\0'*0x8000)
        self.uc.mem_write(self.APP, code)
        self.uc.ctl_remove_cache(self.APP,self.APP+0x8000)
        self.uc.mem_write(self.app_data, bytes(data))
        self.app_symbols = {n:int(a,16) for a,_,n in re.findall(
            r'^([0-9a-f]+)\s+(\S)\s+(\S+)$',path.with_suffix('.symbols').read_text(),re.M)}
        self.app_a5 = self.app_data+self.app_symbols['edata']
        self.current_app = identity

    def open_url(self):
        self.uc.mem_write(0x9100,b'N:http://example.com/\0')
        return self.client('network_open',struct.pack('>IBxBx',0x9100,4,0))

    def query(self):
        self.uc.mem_write(0x9300,b'/value\0')
        return self.call('network_json_query_n',struct.pack('>IIIH',0x9100,0x9300,0x9400,32),app=True,a5=self.app_a5)

class SharedAppsTests(unittest.TestCase):
    def test_iss_weather_iss_handoff_and_repeated_lifetime(self):
        m=AppMachine()
        for name,identity in [('isstracker',101),('weather',202),('isstracker',101)]*3:
            m.load_app(name,identity)
            self.assertEqual(m.open_url(),0)
            self.assertEqual(m.client('network_json_parse',struct.pack('>I',0x9100)),0)
            self.assertGreater(m.query(),0)
            self.assertTrue(bytes(m.uc.mem_read(0x9400,5)).startswith(b'body-'))
            # Two app-owned handles; shutdown closes both without explicit close.
            for suffix in [b'a',b'b']:
                m.uc.mem_write(0x9200,b'N:http://example.com/'+suffix+b'\0')
                self.assertEqual(m.client('network_open',struct.pack('>IBxBx',0x9200,4,0)),0)
            self.assertEqual(len(m.sessions),2)
            m.client('fuji_palmos_close')
            self.assertFalse(m.sessions)
            self.assertFalse(m.registered)
            self.assertFalse(m.globals)
            self.assertEqual(len(m.allocations),len(m.frees))
        opens=sum(p[:2]==b'\xfd\x01' for p in m.requests)
        closes=sum(p[:2]==b'\xfd\x04' for p in m.requests)
        self.assertEqual(opens,closes)

    def test_missing_incompatible_and_missing_module(self):
        for name in ['isstracker','weather']:
            for failure in ['missing_library','incompatible','no_module']:
                m=AppMachine();m.load_app(name,101)
                if failure=='no_module':m.present=False
                else:setattr(m,failure,True)
                self.assertNotEqual(m.open_url(),0)
                self.assertEqual(m.alerts,[9000])
                m.client('fuji_palmos_close')
                self.assertFalse(m.globals)
                self.assertFalse(m.registered)
                self.assertFalse(m.sessions)
                self.assertEqual(m.doorbells,0)

    def test_failed_query_and_normal_exit_cleanup(self):
        for name in ['isstracker','weather']:
            m=AppMachine();m.load_app(name,101)
            self.assertEqual(m.open_url(),0)
            m.client('network_json_parse',struct.pack('>I',0x9100))
            m.wrong_handle=True
            self.assertGreaterEqual(m.query(),0x8000) # Int16 error, not stale JSON
            self.assertFalse(m.globals) # error path ended the owner immediately
            m.client('fuji_palmos_close')
            self.assertFalse(m.sessions)
            self.assertFalse(m.globals)
            self.assertFalse(m.registered)

    def test_open_info_failure_cannot_report_success_or_retain_owner(self):
        for name in ['isstracker','weather']:
            m=AppMachine();m.load_app(name,101)
            original=m.execute
            def info_failure(request):
                if request[:2]==b'\xfd\x05':
                    m.requests.append(request)
                    return net.reply(0xfd,5,status=0x44)
                return original(request)
            m.execute=info_failure
            self.assertNotEqual(m.open_url(),0)
            self.assertFalse(m.sessions)
            self.assertFalse(m.globals)
            self.assertFalse(m.registered)

if __name__=='__main__':unittest.main()
