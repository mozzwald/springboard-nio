"""Native tests of the actual installer C policy; Palm APIs are small mocks."""
import subprocess
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class InstallerTests(unittest.TestCase):
    def test_install_idempotence_loaded_library_corruption_and_failure(self):
        out=ROOT/'build/m3/test-installer'
        out.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-multichar',
            '-fpack-struct=2','-Itests/installer-mocks','tests/installer-mocks/test_installer.c',
            '-o',str(out)],cwd=ROOT,check=True)
        subprocess.run([str(out)]+[str(ROOT/f'palm/build/shared/installer/nPRC{i:04x}.bin')
            for i in range(1000,1004)],cwd=ROOT,check=True)
