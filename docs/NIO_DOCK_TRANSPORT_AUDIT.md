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

At the initial audit, the checked-out NIO library branch,
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


## Library master verification after the user switched branches

Verified `fujinet-nio-lib` master at
`ba872988a4e25e26f50217b54b6362bd18b77bf4`, clean and matching origin/master:

- `a589e40`: Palm OS cradle serial target merged (#7).
- `ba87298`: Palm OS Springboard CS1 target merged (#6).
- `make palmos-serial` and `make palmos-springboard` both cross-built with
  the existing Palm Docker toolchain and the reviewed master bridge ABI header.
  Outputs are `fujinet-nio-lib/build/fujinet-nio-palmos-{serial,springboard}.a`.
- `make test-palmos-transport`: PASS; `make test-raw-transport-retry`: PASS.
- `make test-stream-wake`: compile FAIL at `tests/stream_wake_test.c:42`.
  The test calls `fn_slip_decode` with three arguments, but the current bounded
  decoder requires `out_max` as its fourth argument. This is an upstream test
  source mismatch; no test or library source was changed to bypass it.

Against the previously used library branch `361c164`, all existing files in
`src/platform/palmos/` are unchanged; `fn_channel_serial.c` is newly added.
The serial backend selects SrmOpen(serPortCradlePort) when the New Serial
Manager is present, otherwise SerOpen through `Serial Library`, at 115200 baud
by default. It uses the common SLIP stream transport and idle-line reclaim.
It does not offer the Visor-specific `USB Library` / `BuiltIn SerLib` runtime
selection that the classic Palm transport has. Defaults and Handspring UART
ownership/flow-control behavior still need hardware-specific review before
claiming the generic serial target works unchanged on this Prism.

These are separate static build targets exposing the same high-level NIO API,
not a shared Palm system library with runtime mode selection. The CS1 exchange
is still blocking; the asynchronous UI work remains necessary. The checked-out
library master, app sources and running firmware/backend were not modified.
This follow-up supersedes the earlier checked-out-branch observation; the NIO
USB host/device role distinction above is unchanged.
