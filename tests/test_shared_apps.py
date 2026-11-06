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
from test_palmos_shared_json import CachedJSONPeer
from unicorn.m68k_const import UC_M68K_REG_A0, UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_PC

class AppMachine(net.NetworkMachine):
    def __init__(self):
        self.missing_library = self.incompatible = False
        self.alerts = []
        super().__init__()

    def hook(self, uc, pc, size, context):
        if bytes(uc.mem_read(pc, 2)) == b'\x4e\x4f':
            trap, sp = self.read16(pc+2), uc.reg_read(UC_M68K_REG_A7)
            if trap == 0xa0a0:  # bounded NotReady polling delay
                self.now += self.read32(sp)
                uc.reg_write(UC_M68K_REG_D0,0); uc.reg_write(UC_M68K_REG_PC,pc+4)
                return
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
        path = Path(os.environ.get('PALMOS_APPS_BUILD',ROOT/'palm/build/shared'))/name/name
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
            # The document handle now lives until the caller's JSON Close.
            self.assertEqual(len(m.sessions),1)
            m.client('network_close',struct.pack('>I',0x9100))
            self.assertFalse(m.sessions)
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

class CachedAppMachine(CachedJSONPeer, AppMachine):
    def string(self,address):
        data=bytearray()
        while self.uc.mem_read(address+len(data),1)[0]: data+=self.uc.mem_read(address+len(data),1)
        return data.decode()

    def hook(self,uc,pc,size,ctx):
        # SDK ROM string helpers needed by the actual Weather fetch routines;
        # all networking, packet construction and field access stay real code.
        if bytes(uc.mem_read(pc,2))==b'\x4e\x4f':
            trap,sp=self.read16(pc+2),uc.reg_read(UC_M68K_REG_A7)
            if trap in (0xa0c8,0xa2d6,0xa2de):
                target,source=self.read32(sp),self.read32(sp+4)
                if trap==0xa0c8:
                    a,b=self.string(target),self.string(source)
                    result=0 if a==b else 1 if a>b else 0xffff
                else:
                    if trap==0xa2d6:
                        text=(self.string(target)+self.string(source))[:max(0,self.read16(sp+8)-1)]
                        result=target;uc.reg_write(UC_M68K_REG_A0,target)
                    else:
                        # Only the app's single-Int16 daily-index formats.
                        argument=self.read16(sp+8)
                        if argument>=0x8000:argument-=0x10000
                        text=self.string(source)%argument;result=len(text)
                    uc.mem_write(target,text.encode()+b'\0')
                uc.reg_write(UC_M68K_REG_D0,result);uc.reg_write(UC_M68K_REG_PC,pc+4);return
        super().hook(uc,pc,size,ctx)


class CachedJSONAppTests(unittest.TestCase):
    def document(self,m,url,paths):
        m.uc.mem_write(0x9100,url.encode()+b'\0')
        spec=struct.pack('>I',0x9100)
        self.assertEqual(m.client('network_open',struct.pack('>IBxBx',0x9100,4,0)),0)
        self.assertEqual(m.client('network_json_parse',spec),0)
        original_handles=set(m.sessions)
        self.assertEqual(len(original_handles),1)
        answers=[]
        for path in paths:
            m.uc.mem_write(0x9300,path.encode()+b'\0')
            result=m.call('network_json_query_n',struct.pack('>IIIH',0x9100,0x9300,0x9400,32),app=True,a5=m.app_a5)
            self.assertLess(result,0x8000)
            answers.append(bytes(m.uc.mem_read(0x9400,result)).decode())
            self.assertEqual(set(m.sessions),original_handles)
        m.client('network_close',spec)
        self.assertFalse(m.sessions);self.assertFalse(m.documents)
        return answers

    def test_iss_three_fields_share_one_http_get_and_snapshot(self):
        m=CachedAppMachine();m.load_app('isstracker',101)
        values=self.document(m,'N:http://example.com/iss',
            ['/timestamp','/iss_position/latitude','/iss_position/longitude','/fetch'])
        self.assertEqual(values,['1234567890','12.34','56.78','1'])
        self.assertEqual(m.http_opens,1)
        self.assertEqual(sum(p[:2]==b'\xfd\x01' for p in m.requests),1)
        m.client('fuji_palmos_close');self.assertFalse(m.globals)

    def test_actual_iss_fetch_uses_one_get(self):
        m=CachedAppMachine();m.load_app('isstracker',101)
        self.assertEqual(m.call('FetchIss',struct.pack('>I',0x8800),app=True,a5=m.app_a5),1)
        self.assertEqual(m.http_opens,1)
        self.assertEqual(m.read32(m.app_data+m.app_symbols['gTimestamp']),1234567890)
        self.assertEqual([p[13:] for p in m.requests if p[:2]==b'\xfd\x07'],
                         [b'/timestamp',b'/iss_position/latitude',b'/iss_position/longitude'])
        self.assertFalse(m.sessions);self.assertFalse(m.documents)
        m.client('fuji_palmos_close');self.assertFalse(m.globals)

    def test_weather_startup_field_sequence_uses_four_documents(self):
        m=CachedAppMachine();m.load_app('weather',202)
        location=['/status','/city','/regionName','/countryCode','/lat','/lon']
        current=['/current/'+key for key in ('temperature_2m','apparent_temperature','wind_speed_10m','wind_direction_10m')]
        extras=['/current/relative_humidity_2m','/current/surface_pressure','/current/weather_code',
                '/utc_offset_seconds','/daily/sunrise/0','/daily/sunset/0']
        forecast=['/daily/temperature_2m_max/0','/daily/temperature_2m_min/0']
        forecast += ['/daily/%s/%d'%(key,i) for i in range(1,6)
                     for key in ('time','temperature_2m_max','temperature_2m_min','weather_code')]
        for n,paths in enumerate((location,current,extras,forecast)):
            values=self.document(m,'N:http://example.com/weather%d'%n,paths)
            self.assertTrue(all(values))
        self.assertEqual(m.http_opens,4)
        self.assertEqual(sum(p[:2]==b'\xfd\x07' for p in m.requests),38)
        self.assertEqual(sum(p[:2]==b'\xfd\x04' for p in m.requests),4)
        m.client('fuji_palmos_close')
        self.assertFalse(m.globals);self.assertFalse(m.registered)
        self.assertEqual(len(m.allocations),len(m.frees))

    def test_actual_weather_fetch_uses_four_gets(self):
        m=CachedAppMachine();m.load_app('weather',202)
        self.assertEqual(m.call('GetIpLocation',b'',app=True,a5=m.app_a5,budget=6000000),1)
        self.assertEqual(m.call('GetWeather',b'',app=True,a5=m.app_a5,budget=6000000),1)
        self.assertEqual(m.http_opens,4)
        self.assertEqual(sum(p[:2]==b'\xfd\x07' for p in m.requests),38)
        self.assertEqual(sum(p[:2]==b'\xfd\x04' for p in m.requests),4)
        self.assertFalse(m.sessions);self.assertFalse(m.documents)
        m.client('fuji_palmos_close');self.assertFalse(m.globals)

    def test_older_library_reports_dependency_without_refetch_fallback(self):
        class OlderApps(CachedAppMachine):
            def hook(self,uc,pc,size,ctx):
                if bytes(uc.mem_read(pc,2))==b'\x4e\x4f':
                    trap,sp=self.read16(pc+2),uc.reg_read(UC_M68K_REG_A7)
                    if trap==0xa816:raise AssertionError('new trap called on old library')
                    if trap==0xa805:
                        uc.mem_write(self.read32(sp+2),struct.pack('>4H',8,1,3,6))
                        uc.reg_write(UC_M68K_REG_D0,0);uc.reg_write(UC_M68K_REG_PC,pc+4);return
                super().hook(uc,pc,size,ctx)
        for name in ('isstracker','weather'):
            m=OlderApps();m.load_app(name,101)
            self.assertEqual(m.open_url(),0)
            self.assertEqual(m.client('network_json_parse',struct.pack('>I',0x9100)),0)
            self.assertGreaterEqual(m.query(),0x8000)
            self.assertEqual(m.alerts,[9000]);self.assertEqual(m.http_opens,1)
            self.assertFalse(m.globals);self.assertFalse(m.sessions)

    def test_first_pending_body_polls_read_without_reconfiguring(self):
        for name in ('isstracker','weather'):
            m=CachedAppMachine();m.load_app(name,101)
            m.json_pending_config=1;m.json_pending_reads=2
            values=self.document(m,'N:http://example.com/json',['/value','/other'])
            self.assertEqual(values,['first','second'])
            self.assertEqual(m.http_opens,1)
            self.assertEqual(sum(p[:2]==b'\xfd\x07' for p in m.requests),2)
            self.assertEqual(m.json_pending_reads,0)
            m.client('fuji_palmos_close');self.assertFalse(m.globals)

if __name__=='__main__':unittest.main()
