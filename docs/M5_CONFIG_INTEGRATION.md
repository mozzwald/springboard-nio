# Milestone 5 — NIO Config five-PRC Springboard package

**GO for controlled remote hardware testing; no M5 physical test performed.**
Built 2026-11-05. No flash, Palm install/reset/reinsertion, service restart or
physical measurement was performed by the agent. M3 R2 remains the known-good
hardware fallback. This checkpoint qualifies software and packaging only.

## Source and contents

- `nio-config`, branch `feat/palmos-config`, base upstream master
  `2a760f6b50d6702d7dc04eba89497fdc58196471` (origin verified read-only).
  Application implementation commit **c15cedc**.
  New Palm-only UI/build/tests documented in that repo's `docs/palmos-config.md`.
- `fujinet-nio-lib`, unchanged branch `feat/palmos-shared-niolib`, revision
  `6190125ca4063142fb9b1ad360a1cfca6dc6ad60`. M4 software-verification PASS.
  No new API or source changes required for M5.
- This worktree `/home/mozzwald/nio/springboard-niolib-m3`, branch
  `feat/palmos-shared-apps`, extends hardware checkpoint `e376198`.
  No change to firmware sources, PIO, pin mapping, read/write ABI, clocks, bridge,
  USB descriptors, backend services or the source apps in fujinet-palm.

| RAM database | Type / creator | Bytes |
| --- | --- | ---: |
| NioLib | libr / NiL1 | 18,824 |
| NioLibTest | appl / NiT1 | 8,898 |
| ISS Tracker | appl / NBFI | 11,404 |
| Weather | appl / NBFW | 16,032 |
| NIO Config | appl / NiC1 | 3,810 |

All app builds consume the same ABI 1.2 header and client archive from
`fujinet-nio-lib/build/palmos-shared-m5`. NioConfig requires transport, Clock and
client capabilities; existing ABI 1.1 apps retain compatibility. The library and
test PRC resources are byte-identical to the software-verified M4 resources;
container timestamps change outer PRC hashes. No NIO common core or physical
transport is linked into any of the three client applications.

## Installer change and upgrade behavior

The R2 source compiles with `NIOLIB_M5` to install five resources, adding
`nPRC/1004` and expected `appl/NiC1`. Without this define the original four-PRC
behavior remains. The R2 `MemHandleNew(n)` → lock → copy complete PRC to chunk
base → `DmCreateDatabaseFromImage()` → unlock/free sequence is unchanged.

Preserved policy:

- Validate embedded length, CRC, resource directory and exact type/creator.
- Reuse identical resource databases, including an identical loaded library.
- Refuse foreign same-name identities and differing open databases.
- Refuse replacement of a differing library registered in SysLibFind.
- Update an idle, matching-identity database, then verify installed resources.
- Retain RAM applications when the module is removed.
- Stop at first error; earlier installed PRCs remain. This is incremental,
  not a five-database atomic transaction. If an idle replacement fails after
  deleting the old version, that database may be absent until retry. A later
  discovery retry reuses completed identical databases and installs missing ones.
  It does not erase or repair unrelated Palm databases.

The package uses a separate `NioLib M5 Setup` HsSU/HsCd database. Use fresh
module insertion for discovery; a seated soft reset is not a reliable promise
that PalmOS will rediscover changed Setup databases. Closing clients before
upgrade is required; the installer never force-removes a loaded library.

## Build and verification

Build only, from this worktree:

```sh
./tools/build-config-uf2.sh > build/m5/build.log 2>&1
```

Create `build/m5` first when redirecting shell output. The script builds the
unchanged library into a new M5 directory, NioConfig, matching ISS/Weather RAM
PRCs, a new Setup/ROM, then a separate UF2. Existing M3/M4 outputs are preserved.
It uses `fujinet-palm-springboard-tools` with network disabled and the pinned
existing pico-sdk/apio/toolchain. No device or service action exists in it.
Environment overrides: NIOLIB_ROOT, NIO_CONFIG_ROOT, PALM_IMAGE, SBNIO_ABI_DIR,
SBNIO_DEPS, PICO_SDK_PATH, PICOTOOL_DIR.

Relevant verification commands (workspace absolute paths avoid cwd ambiguity):

```sh
# library repo
make test-palmos-shared PALMOS_SHARED_BUILD=build/palmos-shared-m5 \
  PALMOS_SHARED_PYTHON=build/palmos-shared/venv/bin/python
# config repo
PALMOS_SHARED_BUILD=/home/mozzwald/nio/fujinet-nio-lib/build/palmos-shared-m5 \
  make test-palmos PALMOS_PYTHON=../fujinet-nio-lib/build/palmos-shared/venv/bin/python
# this worktree
PALMOS_SHARED_BUILD=/home/mozzwald/nio/fujinet-nio-lib/build/palmos-shared-m5 \
PALMOS_APPS_BUILD=/home/mozzwald/nio/springboard-niolib-m3/palm/build/m5 \
  ../fujinet-nio-lib/build/palmos-shared/venv/bin/python -m unittest discover -s tests -v
```

| Verification actually performed | Result |
| --- | --- |
| Native Palm app, library, test, matching client apps, Setup and firmware builds | PASS |
| Compiled m68k NioConfig + real ABI 1.2 library, mock OS/peer | **15/15 PASS** |
| Full shared library M1/M2/M4 compiled/native regression suite | **41/41 PASS** |
| This worktree's original and five-PRC installer/app tests | **8/8 PASS** |
| Installer CRC/identity, R2 chunk-base/lock/allocation contract | PASS |
| Loaded library and open app rejection; idle upgrade; fifth-PRC partial failure/retry | PASS |
| Idempotence/removal retains apps; independently parsed five resources/ROM metadata | PASS |
| New ISS/Weather compiled apps: repeated handoff, two handles, error cleanup | PASS |
| Original static Palm serial and CS1 builds in new M5 output | PASS |
| nio-config original Linux build | PASS |
| nio-config Amiga host tests and FileService parser | **1,315 checks, zero failures**, parser PASS |
| Firmware source diff vs M3 hardware checkpoint | Empty |
| Linked persistent ARM responder and PIO initializer | Byte/address-identical to M3 |
| ROM embedded once in ELF; UF2 payload equals BIN; RP2350 family marker | PASS |
| M3 rollback UF2 hash unchanged | PASS |
| M5 actual Prism or serial hardware | **NOT TESTED** |

Full emulator-driven Atari/BBC suites and unrelated cross-toolchains were not
run for this Palm-only addition. M4's documented unrelated stream-wake signature
and missing Amiga-driver-header failures remain outside this change; no claim
of a clean all-platform full test run is made.

Evidence: `build/m5/{build.log,tests.log,firmware-differential.json,library-m4-differential.json,SHA256SUMS,BUILD_ID.json}`;
`palm/build/m5/verification.json`; `nio-config/build/palmos/{tests.log,
linux-build.log,amiga-tests.log}`; `fujinet-nio-lib/build/palmos-shared-m5/`
contains audits, disassembly, test/static-build logs. Build outputs are ignored;
the identities below and this checkpoint are committed.

### Timing preservation

No timing measurement was requested or performed. The linked instructions at:

- `sb_persistent_reply`: **0x20080000**, 314 bytes,
  SHA256 `9452a573533a56c6ad172606ad64e1049c2cf076fca99ead3f5cc92dcf8c384f`.
- `sb_pio_rearm_program_init`: **0x20002604**, 1,020 bytes,
  SHA256 `c28e058c8cb087af6bce3b85f4c4e51c730b7da4d9217ba5b90fe67aef2df099`.

are byte-identical to the M3 linked ELF. The startup `main`, Core1 C service,
pin setup, input write capture initialization and Core1 launch **opcodes** also
compare identical at unchanged instruction addresses. Trailing literal pools
change only as the larger ROM relocates ordinary SRAM objects. The backing
table moves from **0x20028000** to **0x20030000**; both preserve the established
16-byte alignment and word-table offset +8. Main RAM ends at **0x2005d118**,
leaving 143,080 bytes before the main-RAM limit; the SCRATCH_X responder and
Core1 stack remain separate and unchanged. This relocation is recorded rather
than claiming every firmware byte or SRAM address is identical.

Firmware sources/build configuration
are unchanged, with clock 150 MHz and ROM HsAT token 330 ns. No new physical
sampling or setup/hold margin is claimed.

## Artifacts and hashes

Final UF2 (265,216 bytes):
`build/m5/niolib-m5-config.uf2`

SHA256: `445abdf3dc8ee5543677fffebff1be810e04392cb49a563f59db819150c1eac8`

Standalone config: `../nio-config/build/palmos/NioConfig.prc` and
`build/m5/install/NioConfig.prc` (identical).

SHA256: `8c8955072720b7f579c785e30e0a778e957c42f081e6a68ed6eb93e6553907b6`

ROM: `palm/build/m5/niolib-m5.rom`, **61,854 bytes**, 3,682 bytes remain within
unchanged 64-KiB mapping. No compression/mapping/timing workaround was needed.
SHA256: `78c8ae1a22f3e11a369759bd6ee5cb87f0394af5e94b65e7e5ca2b6a36deb617`.

All five deployable PRCs are under `build/m5/install/`; SHA256SUMS and BUILD_ID
record each byte length/hash. Preserve these exact files for remote testing;
rebuilding build-prc containers may change timestamp-dependent hashes.

## Minimal remote Prism test

1. Exit NioLibTest, ISS, Weather and any NIO client to Home/Launcher. No active
   module ROM execution or networking should remain. Safely remove the module
   with the sled; leave the Prism at Launcher. Do not hold Prism Reset.
2. Put only the RP2350 into BOOTSEL. Copy **niolib-m5-config.uf2** to RPI-RP2;
   wait for the drive to disappear and normal module USB interfaces to return.
   No additional SPRINGBD.ROM copy is required for this embedded-ROM firmware.
3. Reconnect the Linux NIO process to the module's **NIO-link** CDC interface,
   not the debug console. If the existing process exited during reflash, run
   the existing built PacketLink-enabled binary on that interface, e.g.:

   ```sh
   FN_SERIAL_PORT=/dev/ttyACM0 ./fujinet-nio 2>&1 | tee m5-test.log
   ```

   Substitute the actual NIO-link path if enumeration changes. Do not run a
   second process against an already-owned serial interface. No new host build
   or protocol setting is required compared with successful M3 testing.
4. Carefully reinsert once for Setup discovery. Confirm **NIO Config** appears.
   The installer upgrades idle matching databases and keeps identical ones.
5. Open NIO Config. Springboard should be selected unless a valid older saved
   selection exists. If necessary select Springboard, tap Save and confirm
   **Saved and verified**. Do not test Serial without the proper cable/peer.
6. Tap Test. Expected **Clock reply: PASS**, Palm/NIO error zero. Test closes its
   foreground session. Save the CS1 configuration, exit and reopen NIO Config
   to confirm it persists. Leave Springboard selected for app regression.
7. Run NioLibTest's foundation/network checks, then **ISS → Weather → ISS** with
   successful fresh reads, returning Home between applications. Report results
   and preserve the NIO log. No further reinsertion campaign is needed.

Configuration inspection/save works without the module or backend. Test is
synchronous and can wait up to the library's 35-second exchange deadline; a
network timeout is not proof of a Palm crash. No serial physical result or USB
transport support is claimed. USB remains an unavailable reserved ID for M6.

### Non-destructive recovery and rollback

If installation stops, do not delete unrelated apps or hard-reset the Prism.
Close all NIO clients first; a registered/active library is intentionally not
replaced. Retry discovery later after normal clean shutdown. Report the exact
screen/error if the app is absent or the library is incompatible.

For a Fatal Alert record text, remove the module if necessary, and use one
ordinary soft reset to recover. Follow the existing policy: stop after two
consecutive startup alerts; do not repeatedly reset or erase Palm RAM.

Rollback, module out: BOOTSEL-flash the retained
`build/m3/niolib-m3-r2.uf2` (SHA256
`9058447b8c623d38c63b2a3d3fdbedaa367233754e6f6114012dd0ee72387361`),
then reinsert for fresh discovery. Idle M4 RAM library/apps may be replaced by
the older R2 package; close all clients first. NioConfig may remain installed
but needs ABI 1.2, so it will report an incompatible older library. No automatic
firmware or preference rollback occurs. M3 artifacts and the immutable hardware
success snapshot remain untouched.

## Next steps

Hardware qualification should establish the new installer/UI and CS1 regression
on the Prism. Serial physical qualification is deferred to a developer with a
serial cradle/cable. Future Hosts/Devices screens can use Palm RAM applications
as device entries; no fake entries or speculative commands exist in M5. USB
cradle support is M6 and requires its own transport/device-role investigation;
this UI reserves USB without claiming that the current dock supports it.
