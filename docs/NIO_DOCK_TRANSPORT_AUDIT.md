# NIO master: Palm dock transport audit — 2026-11-04

## Revisions and preservation

The user's pending `fujinet-nio` visor changes were committed first:
`f0cd3e01882e3d197185affb9eaf7508ef30310c`, 88 source/documentation files.
All 14 native bridge CTest cases passed in a fresh Release build; Python syntax
and whitespace checks passed. These historical experimental files are preserved
as-is; this commit does not promote their hardware qualification. No push.

Fetched the user's synced origin/master and inspected it read-only in detached
worktree `/home/mozzwald/nio/fujinet-nio-master-review`, revision
`09c96f9bd7a497a7a527887261bb1cd694a3e13e`. The original visor checkout remains
on visor, now clean. Local master was behind origin/master; it was not reset or
merged. The running Linux backend and RP2350 firmware were not replaced.

## What exists

| Path | Finding | Source in reviewed NIO master |
| --- | --- | --- |
| Palm serial cradle to NIO on PC | SerialPort backend with SLIP FujiBus framing; configurable serial port and baud. Fits serial-cradle app transport with an NIO-compatible Palm client. | `src/lib/build_profile/amiga_rs232.cpp`, `src/platform/posix/serial_channel.cpp`, preset `fujibus-rs232-debug` |
| Palm serial cradle to NIO on FN-RS232 hardware | UART FujiBus backend; documentation explicitly describes Palm cradle wiring through a null-modem adapter, no RTS/CTS. | `docs/hotsync.md` section Cradle; `src/platform/esp32/uart_channel.cpp`; `pio-build/ini/platforms/platformio-fujibus-gpio-rs232-*.ini` |
| Shared serial-cradle HotSync | Implemented line arbiter/coordinator switches between app FujiBus and HotSync rates; optional, disabled in configuration until enabled. | `include/fujinet/hotsync/cradle_coordinator.h`, `src/lib/hotsync/`, `docs/hotsync.md` |
| Generic USB CDC transport | Implemented on ESP32-S3 as USB **device**, with separate FujiBus and log interfaces. SLIP and PacketLink build variants exist. | `src/platform/esp32/usb_cdc_channel.cpp`, `tinyusb_cdc.cpp`, `build_profile.cpp:43–59`; USB PlatformIO profiles |
| PacketLink over PC serial/USB serial | Implemented upstream, including the serial build profile we separately added to the older Diller branch. | `src/lib/build_profile/fujibus_link_serial.cpp`, `docs/packet_link.md`, preset `fujibus-link-serial-debug` |
| Direct stock Visor USB cradle into ESP32 USB host | No Visor-specific USB-host backend found in this NIO revision. The USB CDC device profiles above do not implement this physical topology. | Reviewed `src/platform/esp32`, channel factory, TinyUSB setup, build profiles; no Visor host driver/vendor handshake |

The main Palm-related changes include:

- `72e8d82`: Palm HotSync over NetSync and serial cradle (#19). This includes
  real serial app-line coordination, but HotSync/DLP itself is not the app's
  ordinary NIO network transport.
- `15935b0`: PacketLink over serial (#24).
- `4cab67c`: packaged RP2350 Springboard bridge (#25).
- `57296d2`: separate USB CDC FujiBus traffic from logs.

USB device mode is useful, but it is not synonymous with a USB-host driver
for the stock Visor cradle. The working topology described by fujinet-palm
has the PC or ESP32 acting as USB host to the Visor. Reuse of an OS serial
adapter/driver or external USB bridge is another possible topology; generic
NIO serial support alone does not prove its Visor endpoint setup works.

## Existing Palm-side code to reuse

The current `fujinet-palm` checkout already contains the relevant Palm APIs:

- `palm/transport_ser.c`, `palm/transport_ser.h`: old Serial Manager binding,
  `SysLibFind`/`SysLibLoad`, `SerOpen`, configurable baud, 8N1/no flow control,
  RX buffering and the Handspring keyboard-daemon release for serial UART.
- Named libraries: `USB Library` (`HsUs`), `BuiltIn SerLib`, `Serial Library`.
- `README.md` sections Running on a Visor over USB and Real FujiNet hardware:
  the PC bridge `tools/visorbridge.js` handles Visor-specific USB discovery/
  connection-info/endpoints. The existing `fujiversal-palm` firmware uses
  `lib/hardware/VisorChannel` in fujinet-firmware, with ESP32 as USB host.
- `palm/netshim` already provides a separate NetLib replacement. Reuse and
  compatibility deserve review when designing the proposed shared driver;
  this audit does not change or install it.

The **currently checked-out** NIO library branch,
`feat/palmos-springboard` at `361c164`, selects CS1 in
`src/platform/palmos/fn_transport.c`. It is not currently a runtime-selectable
CS1/USB/serial driver. Its existence does not make the classic serial apps
NIO-compatible automatically: keep NIO packet construction/semantics and reuse
physical Serial Manager bindings underneath them. Fetching Diller's library
master for cross-reference did not alter the active library branch.

## Consequence for the proposed common Palm library

Serial does not require a new NIO server transport. The shared Palm library
can use an NIO byte-stream/SLIP backend over the existing serial binding, plus
its CS1 backend, while apps retain one public API. USB has reusable Palm and
FujiNet-PC/Fujiversal host-side code; a complete NIO deployment still needs the
appropriate Visor USB-host adapter/bridge. Select framing deliberately:
serial-cradle SLIP and the current Springboard's USB PacketLink are different
links carrying the same NIO raw packet semantics.

Runtime mode selection, shared-library packaging, request ownership, and
nonblocking Palm APIs remain integration work. Do not select a USB CDC device
profile and assume it can host the Visor cradle or the RP2350 USB device.
No firmware or Palm app was modified or tested on hardware in this audit.

## Checks performed

- Fresh visor Release native build and CTest: 14/14 passed.
- All 83 newly tracked historical text files inspected for file type/size;
  all new Python files parse; git whitespace check passed.
- Master source/doc review at the exact revision above.
- Master's `py/tests/test_usb_cdc_profiles.py`: passed, checking interface 0
  for FujiBus and interface 1 for logs across all three selected profiles.
- No full master rebuild, physical dock serial test, physical dock USB test,
  flash, Palm reset, mode switch or HotSync was performed.
