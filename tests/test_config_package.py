"""Five-PRC installer, unchanged R2 allocation contract, no hardware access."""
import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parent
LIB=WORKSPACE/'fujinet-nio-lib'
CONFIG=WORKSPACE/'nio-config'
B=ROOT/'palm/build/m5'
spec=importlib.util.spec_from_file_location('package',ROOT/'palm/installer/package.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)

class ConfigPackageTests(unittest.TestCase):
    def test_five_prcs_rom_metadata_and_resources(self):
        package.verify(B,LIB/'build/palmos-shared-m5/NioLib.prc',
                       LIB/'build/palmos-shared-m5/NioLibTest.prc',CONFIG/'build/palmos/NioConfig.prc')
        resources=package.resources((B/'installer.prc').read_bytes())
        self.assertEqual(sum(k[0]==b'nPRC' for k in resources),5)
        names=[]
        for i in range(5):
            p=resources[b'nPRC',1000+i][8:]
            names.append(p[:32].split(b'\0')[0])
        self.assertEqual(len(set(names)),5)
        self.assertEqual(names[-1],b'NIO Config')
        v=json.loads((LIB/'build/palmos-shared-m5/verification.json').read_text())
        self.assertIn('NioLibGetConfig',v['dispatch'])
        for name in ('isstracker','weather'):
            symbols=(B/name/(name+'.symbols')).read_text()
            self.assertNotIn('fn_transport_',symbols)
            self.assertIn('fn_init',symbols)

    def test_actual_installer_c_upgrade_loaded_open_crc_retry_and_chunk_base(self):
        out=ROOT/'build/m5/test-installer'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-multichar',
            '-fpack-struct=2','-DNIOLIB_M5','-Itests/installer-mocks',
            'tests/installer-mocks/test_installer.c','-o',str(out)],cwd=ROOT,check=True)
        subprocess.run([str(out)]+[str(B/f'installer/nPRC{i:04x}.bin') for i in range(1000,1005)],check=True)

    def test_firmware_sources_and_linked_responder_unchanged(self):
        diff=subprocess.check_output(['git','diff','e376198','--','firmware','include'],cwd=ROOT)
        self.assertEqual(diff,b'')
        report=json.loads((ROOT/'build/m5/firmware-differential.json').read_text())
        self.assertTrue(report['embedded_rom_byte_exact'])
        self.assertTrue(report['uf2_matches_binary'])
        for name in ('sb_persistent_reply','sb_pio_rearm_program_init'):
            self.assertTrue(report[name]['byte_identical_to_baseline'])
        for name in ('main','core1_service','bus_pins_init','bus_write_capture_init','bus_launch_core1'):
            self.assertTrue(report[name]['opcodes_identical'])
        self.assertEqual(report['sram']['word_table_mod16'],8)
        self.assertGreater(report['sram']['main_ram_remaining'],0)
        # Proven R2 artifacts are untouched, not regenerated in M5 directories.
        rollback=ROOT/'build/m3/niolib-m3-r2.uf2'
        self.assertEqual(hashlib.sha256(rollback.read_bytes()).hexdigest(),
            '9058447b8c623d38c63b2a3d3fdbedaa367233754e6f6114012dd0ee72387361')

if __name__=='__main__':unittest.main()
