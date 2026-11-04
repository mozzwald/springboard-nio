#!/usr/bin/env python3
"""Talk to the springboard-nio firmware console.

  sbcon.py                  print console output until Ctrl-C
  sbcon.py status regs      send commands, print what comes back, exit
  sbcon.py -t 30 trace on   ...and keep listening for 30 seconds

The port is found by its USB interface name ("Console"); SBNIO_CONSOLE
overrides it.
"""
import argparse
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import termios
import time


def board_serial():
    """The RP2350 to use when several run this firmware: SBNIO_SERIAL, else
    host/board.serial, else whichever Springboard NIO device comes first."""
    serial = os.environ.get("SBNIO_SERIAL")
    if not serial:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board.local.serial")
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board.serial")
        if os.path.exists(path):
            serial = open(path).read().strip()
    return serial or None


def session_id_macos():
    """USB session of the selected board; it changes every time it enumerates."""
    tree = subprocess.run(["ioreg", "-r", "-n", "Springboard NIO", "-l", "-w0"],
                          capture_output=True, text=True).stdout
    wanted = board_serial()
    for device in re.split(r"(?m)^\+-o ", tree)[1:]:
        m = re.search(r'"USB Serial Number" = "([^"]+)"', device)
        if wanted and (not m or m.group(1) != wanted):
            continue
        m = re.search(r'"sessionID" = (\d+)', device)
        return m.group(1) if m else None
    return None


def find_port_macos(name):
    """Map a CDC port's interface name ("NIO link", "Console") on the
    Springboard NIO device to its /dev/cu.* path. The name is on the control
    interface; the serial device hangs off the data interface after it."""
    tree = subprocess.run(["ioreg", "-r", "-n", "Springboard NIO", "-l", "-w0"],
                          capture_output=True, text=True).stdout
    wanted = board_serial()
    for device in re.split(r"(?m)^\+-o ", tree)[1:]:
        m = re.search(r'"USB Serial Number" = "([^"]+)"', device)
        if wanted and (not m or m.group(1) != wanted):
            continue
        current = None
        for line in device.splitlines():
            m = re.search(r'"kUSBString" = "([^"]+)"', line)
            if m:
                current = m.group(1)
            m = re.search(r'"IOCalloutDevice" = "([^"]+)"', line)
            if m and current == name:
                return m.group(1)
    return None


LINUX_INTERFACES = {"NIO link": "00", "Console": "02"}


def linux_ports(sys_tty=Path("/sys/class/tty")):
    """Discover both CDC interfaces by USB identity, never by ttyACM number."""
    wanted = board_serial()
    for tty in sorted(sys_tty.glob("ttyACM*")):
        device = (tty / "device").resolve()
        interface = next((p for p in (device, *device.parents)
                          if (p / "bInterfaceNumber").is_file()), None)
        usb = next((p for p in (device, *device.parents)
                    if (p / "idVendor").is_file()), None)
        if interface is None or usb is None:
            continue
        def read(name):
            try:
                return (usb / name).read_text().strip()
            except OSError:
                return ""
        serial = read("serial")
        if (read("idVendor"), read("idProduct"), read("product")) != (
                "2e8a", "0009", "Springboard NIO"):
            continue
        if wanted and serial != wanted:
            continue
        number = (interface / "bInterfaceNumber").read_text().strip()
        yield number, "/dev/" + tty.name, serial + ":" + read("busnum") + ":" + read("devnum")


def find_port(name):
    override = os.environ.get("SBNIO_CONSOLE" if name == "Console" else "SBNIO_LINK")
    if override:
        return override
    if sys.platform == "darwin":
        return find_port_macos(name)
    return next((port for number, port, _ in linux_ports()
                 if number == LINUX_INTERFACES[name]), None)


def session_id():
    if sys.platform == "darwin":
        return session_id_macos()
    return next((session for _, _, session in linux_ports()), None)


def open_port(path):
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = attrs[1] = attrs[3] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return fd


def reopen():
    while True:
        time.sleep(1)
        path = os.environ.get("SBNIO_CONSOLE") or find_port("Console")
        if path:
            try:
                fd = open_port(path)
                sys.stdout.write("[console reconnected]\n")
                sys.stdout.flush()
                return fd
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-t", "--time", type=float, help="seconds to listen (default: forever, or 1.5 after commands)")
    parser.add_argument("--port", metavar="NAME", help='print the device for a port ("NIO link" or "Console") and exit')
    parser.add_argument("--session", action="store_true", help="print the board's USB session ID and exit")
    parser.add_argument("command", nargs="*", help="console commands; multi-word ones need quotes")
    args = parser.parse_args()
    if args.session:
        print(session_id() or "")
        return
    if args.port:
        path = find_port(args.port)
        if not path:
            sys.exit(f"no Springboard NIO {args.port!r} port found")
        print(path)
        return
    path = os.environ.get("SBNIO_CONSOLE") or find_port("Console")
    if not path:
        sys.exit("no Springboard NIO console port found")
    fd = open_port(path)
    for command in args.command:
        os.write(fd, command.encode() + b"\n")
        time.sleep(0.05)
    limit = args.time if args.time is not None else (1.5 if args.command else None)
    end = time.time() + limit if limit else None
    try:
        while end is None or time.time() < end:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if not ready:
                continue
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                continue
            except OSError:
                # The board re-enumerated (flash or reset): follow it when listening forever.
                os.close(fd)
                if end is not None:
                    return
                fd = reopen()
                continue
            sys.stdout.write(data.decode(errors="replace"))
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    os.close(fd)


if __name__ == "__main__":
    main()
