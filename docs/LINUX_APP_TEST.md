# Linux/macOS preparation for a real app test

## Source selection

Reviewed 2026-11-04. `diller/two-way-cs` is commit `4ccd971`; it is an
ancestor of our original `master` commit `1be0895`. It already changed the
Springboard bus to two-way CS1. Master retains that work and subsequently
replaces USB SLIP with NIO PacketLink. Do not downgrade to the older branch.

The request bytes are written through CS1; reply registers/data are read
through CS1. CS0 carries only the ROM. BEGIN/DATA/CHECK/DOORBELL and response
buffering still form the transport contract; direct CS1 does not mean removing
packet assembly, sequence ownership or asynchronous processing.

Repositories used locally:

| Repository | Branch / upstream starting commit | Location |
| --- | --- | --- |
| springboard-nio | feat/linux-macos-host / 1be0895 | /home/mozzwald/nio/springboard-nio |
| fujinet-nio | feat/linux-springboard-host / 4ae9dee | /home/mozzwald/nio/fujinet-nio-springboard |
| fujinet-nio-lib | feat/palmos-springboard / 361c164bd98694731f5d52f5de847b11009fe6a9 | /home/mozzwald/nio/fujinet-nio-lib |

Both NIO and Springboard repositories now have the explicitly requested
`diller` remote. The original dirty NIO `visor` checkout was left untouched;
the fetched NIO branch has its own worktree. No library source change was needed.

## Changes

No firmware bus, PIO, ARM service, register ABI, Palm app or ROM construction
source changed in springboard-nio.

- USB discovery retains the macOS `ioreg` path and adds Linux sysfs identity
  and interface selection (00=NIO, 02=console). Linux session identity includes
  bus/device numbers so the supervisor notices re-enumeration.
- `SBNIO_SERIAL` overrides an ignored `host/board.local.serial`, then the
  original checked-in Mac `host/board.serial`. The local file selects
  D2510D4E47DAC885. `SBNIO_CONSOLE` / `SBNIO_LINK` allow explicit port paths.
- Palm Docker builds accept `PALM_IMAGE`, mount the parent directory for
  sibling dependencies, and write files as the invoking UID/GID. The original
  sbnio-palm default and Darwin toolchain discovery are retained.
- `host/flash.sh --build-only` never accesses hardware or starts/stops NIO.
  `SBNIO_DEPS` and `PICOTOOL_DIR` select existing dependency/tool installations.
  Without --build-only this script **does flash**; do not run it during review.
- The isolated NIO branch adds the missing `fujibus-link-serial-debug` preset
  and native-packet/SerialPort/PacketLink profile using existing channel code.
  The old SLIP/Amiga profile is unchanged. CURL's public-header dependency is
  propagated to consumers, fixing builds with non-system libcurl headers.

## Local dependencies and build

Ignored `repos/` links point at the three sibling repositories above (and
fujinet-palm). `build/deps/` links reuse the already pinned SDK 2.3.1,
apio 0.3.0 and epio 0.2.1 sources. No baseline files were overwritten.

From springboard-nio:

```sh
PALM_IMAGE=fujinet-palm-springboard-tools ./palm/build.sh
SBNIO_DEPS="$PWD/build/deps" \
PICOTOOL_DIR=/home/mozzwald/nio/fujinet-nio/bridges/rp2350-springboard/build/persistent-reply/picotool-host/picotool \
  ./host/flash.sh --build-only
python3 -m unittest discover -s host/tests -v
```

Firmware compiler available here: Arm GCC 13.2.1, matching the compiler used
in our preceding experiments. Diller documented Arm GCC 14.2 on his Mac;
this is not a byte-identical reproduction of his UF2. Pico SDK is pinned to
2.3.1, RP2350 clock remains 150 MHz and ROM HsAT remains 330 ns.

From fujinet-nio-springboard:

```sh
cmake --preset fujibus-link-serial-debug
cmake --build build/fujibus-link-serial-debug --parallel 6
ctest --test-dir build/fujibus-link-serial-debug --output-on-failure
./scripts/run-python-tests
```

HTTP requires libcurl development headers/library; HTTPS also uses the platform
trust store. Locally, the Ubuntu libcurl4-openssl-dev package was downloaded and
extracted under `build/curl-dev/`, without installing system packages. Configure
used these cache overrides:

```sh
-DCURL_INCLUDE_DIR="$PWD/build/curl-dev/root/usr/include/x86_64-linux-gnu" \
-DCURL_LIBRARY_RELEASE=/usr/lib/x86_64-linux-gnu/libcurl.so.4
```

Both CURL and OpenSSL are enabled. A local `build/.venv` contains pyserial 3.5
for the existing Python tests. Tests needing loopback sockets require host
network permissions in the Codex sandbox.

## Actual checks

- All four Palm apps and ROM built with the existing Docker image.
- Independent header/store signatures, whole-ROM CRC16, 330 ns HsAT and
  all 52 resources across four databases checked against the generated PRCs.
  Database order is not assumed to match the MakeROM input order.
- RP2350 ELF/BIN/UF2 built; Core1 reply loop at 0x20080000 in SCRATCH_X,
  size 314 bytes; Core1's 2 KiB stack reservation and code fit the 4 KiB bank.
  BSS end 0x20055118 is below stacks/scratch. Table backing is 128 KiB + 16.
- Packaged upstream bridge native suite: 7/7 passed (including actual PIO
  source, write snapshot decoding, PacketLink and setup/tooling tests).
- New Linux/macOS USB-discovery tests: 5/5 passed using synthetic sysfs and
  mocked ioreg. No physical Mac test was performed.
- NIO native suite: 644/644 passed with loopback permissions; default sandbox
  initially prevented 12 socket tests from opening local servers.
- NIO Python suite: 79/79 passed in the local pyserial environment; the first
  CTest run used a Python without pyserial and failed imports.
- Physical app/USB/bus compatibility on this Prism remains untested.

Candidate and hashes: `build/artifacts/BUILD_ID.json`.
Working outputs: `firmware/build/sbnio.uf2`, `palm/build/sbnio.rom`.
The old single-database `host/tools/verify-rom.py` was left untouched; its
single-app assumption does not apply to this four-database image.

## First hardware test: ISS Tracker

The engineer handles flashing, backend selection and logs; the user handles
only the agreed module/Prism actions and app buttons. No Echo, Loop or raw
read/write campaign is required first. No scope or logic analyzer is needed.

1. Before authorization to flash, record the currently installed firmware and
   retain its matching rollback UF2. Keep all previous experiment images.
2. With the app closed and module removed, user enters RP2350 BOOTSEL when cued.
   Engineer flashes the exact candidate, then identifies its two USB interfaces.
   This firmware embeds its ROM and has **no MSC ROM drive**: no ROM-file copy.
3. Engineer starts NIO (`host/nio.sh start`) and console logging, checks backend
   process health and PacketLink synchronization. NIO runs on the Linux PC,
   which needs working internet/DNS; the module needs no Wi-Fi credentials.
4. Engineer cues one careful insertion for fresh recognition. User opens
   **ISS Tracker** directly from the module. It fetches on opening; Refresh
   can be used if requested. These apps execute from ROM, not an auto-installed
   RAM clone. Do not reset/reflash RP2350 while an app is running.
5. Accept fresh position/time on the Prism, correlated with successful NIO
   network requests and clean firmware link status. Preserve both logs and
   the displayed outcome. Weather is the next optional real-app test.

If a remote API fails, keep the transport outcome distinct from endpoint
availability; do not infer a bus fault from an HTTP/server error alone.
Record isolated MemoryMgr alerts and recover manually; stop after two
consecutive startup alerts. Do not bypass Palm initialization guards.

Nothing in this preparation flashed, reset or opened the hardware serial ports.
No runtime backend/collector is left running yet. Future bench actions require
explicit authorization; the user's next physical test is the real app above.
