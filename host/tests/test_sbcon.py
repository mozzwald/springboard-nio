"""USB selection tests use fake sysfs and ioreg; never open a real port."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sbcon', Path(__file__).parents[1] / 'sbcon.py')
sbcon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sbcon)


class Discovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tty = self.root / 'tty'
        self.tty.mkdir()

    def board(self, serial, devnum, first):
        usb = self.root / serial
        usb.mkdir()
        for key, value in dict(serial=serial, busnum='1', devnum=str(devnum),
                               idVendor='2e8a', idProduct='0009', product='Springboard NIO').items():
            (usb / key).write_text(value)
        for i, number in enumerate(('00', '02')):
            iface = usb / ('interface' + number)
            iface.mkdir()
            (iface / 'bInterfaceNumber').write_text(number)
            tty = self.tty / ('ttyACM' + str(first + i))
            tty.mkdir()
            (tty / 'device').symlink_to(iface)
        return usb

    def test_linux_interfaces_serial_and_reenumeration(self):
        self.board('OTHER', 7, 0)
        selected = self.board('OURS', 8, 2)
        with patch.object(sbcon, 'board_serial', return_value='OURS'):
            found = list(sbcon.linux_ports(self.tty))
            self.assertEqual(found, [('00', '/dev/ttyACM2', 'OURS:1:8'),
                                     ('02', '/dev/ttyACM3', 'OURS:1:8')])
            (selected / 'devnum').write_text('9')
            self.assertEqual(list(sbcon.linux_ports(self.tty))[0][2], 'OURS:1:9')

    def test_linux_wrong_product_rejected(self):
        usb = self.board('OURS', 8, 0)
        (usb / 'product').write_text('Other Pico')
        with patch.object(sbcon, 'board_serial', return_value='OURS'):
            self.assertEqual(list(sbcon.linux_ports(self.tty)), [])

    def test_port_and_session_routing(self):
        with patch.object(sbcon.sys, 'platform', 'linux'), patch.object(sbcon, 'linux_ports',
                return_value=iter([('02', '/dev/ttyACM9', 'OURS:1:3')])):
            self.assertEqual(sbcon.find_port('Console'), '/dev/ttyACM9')
        with patch.object(sbcon.sys, 'platform', 'linux'), patch.object(sbcon, 'linux_ports',
                return_value=iter([('00', '/dev/ttyACM8', 'OURS:1:3')])):
            self.assertEqual(sbcon.session_id(), 'OURS:1:3')

    def test_explicit_port_overrides(self):
        with patch.dict(sbcon.os.environ, {'SBNIO_CONSOLE': '/tmp/console', 'SBNIO_LINK': '/tmp/link'}):
            self.assertEqual(sbcon.find_port('Console'), '/tmp/console')
            self.assertEqual(sbcon.find_port('NIO link'), '/tmp/link')

    def test_macos_discovery_unchanged(self):
        tree = '''+-o RP2350
          "USB Serial Number" = "OURS"
          "sessionID" = 123
          "kUSBString" = "NIO link"
          "IOCalloutDevice" = "/dev/cu.usbmodem01"
          "kUSBString" = "Console"
          "IOCalloutDevice" = "/dev/cu.usbmodem03"
'''
        with patch.object(sbcon, 'board_serial', return_value='OURS'), patch.object(
                sbcon.subprocess, 'run') as run, patch.object(sbcon.sys, 'platform', 'darwin'):
            run.return_value.stdout = tree
            self.assertEqual(sbcon.find_port('Console'), '/dev/cu.usbmodem03')
            self.assertEqual(sbcon.find_port('NIO link'), '/dev/cu.usbmodem01')
            self.assertEqual(sbcon.session_id(), '123')


if __name__ == '__main__':
    unittest.main()
