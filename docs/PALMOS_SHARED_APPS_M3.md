# Milestone 3: RAM applications using the installed NioLib

Status: **Milestone 3 normal-use hardware qualification PASS, 2026-11-05**:
R2 installation and NioLibTest → ISS → Weather → rerun ISS all succeeded. See
[M3_HARDWARE_20261105.md](M3_HARDWARE_20261105.md) for the separate user and log
evidence. The first candidate's Fatal Exception remains recorded below.
The agent did not flash, reset, insert, HotSync, or restart hardware/services.
The user subsequently performed the successful physical test recorded above.
The separate UF2 is a packaging option requested for remote testing; the bus,
USB and backend implementations are unchanged.

## Source ownership and branches

- Shared library: `fujinet-nio-lib`, `feat/palmos-shared-niolib`, M2 implementation
  `a1f16a7d14cfa55ed061c0ccbada8853c98c37d4`, physical checkpoint `73d08d4`.
- Application integration: this isolated worktree
  `/home/mozzwald/nio/springboard-niolib-m3`, branch `feat/palmos-shared-apps`,
  based on `springboard-nio` `9bd9f15`.
- Authoritative app UI/resource source: `fujinet-palm/palm/apps/{isstracker,weather}`,
  commit `2703ef555f3859a4d1d1f9ca08ccea94795209f4`, read-only inputs. That
  checkout/branch and its unrelated untracked files were not changed.
- `palm/compat/fn_classic.c` is the already working classic-API adaptation used
  in the original Springboard app builds. It is reused by both apps. No copy
  of either app's UI or JSON helper implementation was forked.

The original `springboard-nio` checkout remains on `feat/linux-macos-host` with
its pre-existing untracked audit/photo preserved. No merge or push occurred.

## Changes and lifetime

`palm/Makefile.shared` links the same app sources/resources and `compat/fnapp.c`
with `NIO_SHARED_CLIENT` and **only `libniolib-client.a`**. Existing static
`palm/Makefile` targets remain available. The shared shim includes
`NioLibClient.h`, preserving the required stdbool-before-PalmOS include order.
The original app names/creators remain ISS Tracker / `NBFI` and Weather / `NBFW`.

No new trap, capability, library identity or ABI version is needed. Both apps
use ABI 1.1 and its existing `fn_init`, `fn_open`, `fn_info`, `fn_read`,
`fn_open_translated`, `fn_close`, `fn_shutdown` client operations. Each bounded
JSON Pointer query still uses the existing NIO JSON translation service. There
is no app-side physical transport, packet parser, service core or CS1 address.

Initialization is lazy on the first classic network call. The client checks
ABI/capabilities, balances one Open/Begin, and owns handles for that foreground
application only. The existing apps already call `fuji_palmos_close` after the
`appStopEvent` loop; it closes classic handles and calls `fn_shutdown` to close
any remaining tracked remote handles, EndClient, Close and safe removal.
Shared-mode failed Open/Info/Read/translated query paths also end the owner.
An Info error cannot be incorrectly reported as a successful Open. The static
mode retains its prior session-end policy; Info errors are now rejected in
both builds rather than being misreported as successful Open. The classic slot table is
cleared at shutdown. Missing/incompatible library or missing module produces
an understandable existing GeneralAlert (9000), rather than a transport call
through an invalid library.

Networking and UI remain synchronous. No caching, endpoint change, JSON
protocol change, event pumping, background work or automatic retry of ambiguous
requests was added. M2 timeout/stale-reply safeguards and cleanup limits remain.
A fatal OS crash is not a normal shutdown; remote cleanup cannot be promised.

## Builds and artifacts

Local ignored `repos/` symlinks point to the existing sibling checkouts. On a
new worktree create them as documented in the original README. With the current
workspace layout:

```sh
cd /home/mozzwald/nio/springboard-niolib-m3
./palm/build-shared.sh       # PRCs + verified installer ROM only
./tools/build-shared-uf2.sh  # includes the above, then separate UF2; never flashes
```

Both use the installed `fujinet-palm-springboard-tools` Docker image. The latter
uses native CMake/Ninja, ARM GCC 13.2.1 and the same pinned Pico SDK/apio as the
working build. Override `NIOLIB_ROOT`, `SBNIO_ABI_DIR`, `PALM_IMAGE`, `SBNIO_DEPS`,
`PICO_SDK_PATH`, `PICOTOOL_DIR`, `BASELINE_ELF` when building elsewhere. All mounted
inputs must be inside the workspace bind mount. No dependency download or image
build is performed automatically. The initial `sbnio-palm` image was absent;
the existing approved toolchain image was used instead. A first SDK configure
tried fetching picotool; the successful build explicitly uses the installed
matching picotool package. No production source was changed for these issues.

Artifacts:

- `build/m3/niolib-m3-r2.uf2` — single experimental firmware package.
- `build/m3/install/{NioLib,NioLibTest,isstracker,weather}.prc` — standalone
  HotSync-installable alternatives; exactly the same files embedded in the ROM.
- `palm/build/shared/{installer.prc,niolib-m3.rom,verification.json}`.
- `palm/build/shared/{isstracker,weather}/` — linked code, maps, symbols, disassembly.
- `../fujinet-nio-lib/build/palmos-shared-m3/` — library, permanent test app,
  client archive and unchanged ABI/A4 audit.
- `build/m3/{build.log,app-tests.log,firmware-differential.json}`.
- `build/m3/rollback/` — original static PRCs and original working Springboard
  UF2; original source artifacts are also untouched in `springboard-nio`.

The rebuilt NioLib and NioLibTest resources match the M2 hardware-tested PRCs
byte for byte; their outer PRC creation timestamps differ. Library code remains
13,724 bytes, owned globals 2,248 bytes. No M2 production library source changed.

### Size comparison

Same UI/resources, compiler and optimization; static baseline built before shim
changes from the current common core:

| PRC | Static baseline | Shared client | Reduction |
| --- | ---: | ---: | ---: |
| ISS Tracker | 14,492 | 11,404 | 3,088 bytes (21.3%) |
| Weather | 19,120 | 16,032 | 3,088 bytes (16.2%) |

These are per-app disk reductions, not a claim that installing only two apps
plus the 13,876-byte shared library saves total storage. The 7,414-byte test app
is additional diagnostic storage. Maps/symbols show that the migrated apps have
client entry points and traps A80B/A809 but **no `fn_packet_*`, `fn_palmos_*`,
`fn_transport_*`, `sbn_exchange`, or session-core symbols**.

## All-in-one Setup ROM

`palm/installer/installer.c` is a separate Handspring `HsSU` / `HsCd` Setup,
version 3, named `NioLib M3 Setup`. Handspring's normal mechanism copies Setup
to RAM and invokes Install (`0x8000`). The audited 10-byte parameter layout and
setupCardNo==0 are checked. It does not execute network requests or retain
callbacks. Remove (`0x8001`) leaves the standalone RAM software installed.

Four `nPRC` resources contain complete PRCs with bounded length and CRC32. The
installer validates those and expected type/creator, then uses
`DmCreateDatabaseFromImage` to create each DB in internal RAM. It compares all
installed resources, rather than asserting success from a filename. Identical
DBs are reused. A foreign same-name identity is rejected. A different loaded
library or open database is rejected rather than replaced. A different idle
matching DB can be replaced. Replacement is not atomic across four DBs: an OS
allocation/create failure can leave a partial installation; a subsequent install
rechecks and completes it. No preferences/user data are deleted. Keep enough
free RAM for the ~51 KiB copied Setup plus installed PRCs and temporary OS work.
The exact peak Palm heap/storage cost is not established by native mocks.

`package.py` independently validates every embedded PRC resource, identities,
ROM directory/chunks, full ROM CRC16 and HsAT 330 token. The R2 ROM is **51,558
bytes**, below 65,536. Nothing changes the clock, wait states or electrical
settings. `verify-shared-uf2.py` verifies UF2 framing, the unchanged RP2350
compatibility marker, program blocks against the generated BIN, exact ROM in
the ELF, and two critical linked functions against the physically proven ELF:

| Function | Address in both | Length | Byte comparison |
| --- | --- | ---: | --- |
| `sb_persistent_reply` | `20080000` | 314 | identical |
| `sb_pio_rearm_program_init` | `20002604` | 1,020 | identical |

All tracked firmware sources/CMake files are unchanged. This proves code
preservation, not that the new Setup installer is physically qualified.
ROM activation and PalmOS discovery remain separate: resetting RP2350 or Prism
alone does not guarantee discovery of changed ROM databases.

## Tests performed

| Test | Actual result |
| --- | --- |
| Shared library/test builds, metadata, A4, relocations, original ABI | PASS; unchanged M2 resource contents |
| M1/M2 compiled library/client and image regression suite | 26/26 PASS with Unicorn and mocked OS/CS1/NIO |
| Actual compiled ISS/Weather shim/client/library | 4/4 PASS; nine ISS→Weather→ISS lifetimes, distinct current app identity, translated JSON, two handles per app, all opens matched by closes, balanced modeled allocations |
| Missing/wrong library, absent module | PASS for each app; GeneralAlert, no doorbells or retained owner/allocation |
| Failed translated read and Open/Info | PASS for each app; errors, immediate owner cleanup, no stale JSON success |
| Native actual installer C with small Palm API mocks | PASS: four DBs, idempotent install, loaded-library refusal, foreign identity, CRC corruption, create failure/retry, removal persistence and parameter validation |
| ROM and linked app audit | PASS; all four embedded PRCs byte exact; no duplicate core/transport |
| Existing static Palm targets | Both fresh `-B palmos-springboard palmos-serial` builds PASS with external `SBNIO_ABI_INCLUDE` |
| Linux/native API, session, CS1, replay guard, Open, translation, Ready, partial Write and large Read | 9 regression targets PASS |
| Linked ARM / UF2 differential | PASS as above |
| Physical automatic install and first app fetch | **R2 PASS, 2026-11-05**; see the hardware checkpoint |
| Complete ISS→Weather→ISS re-entry | **PASS, user confirmed 2026-11-05** |
| Quantitative Palm heap / extended repeated switching | Not measured; additional coverage |

Host test commands:

```sh
# From this worktree, after build:
../fujinet-nio-lib/build/palmos-shared/venv/bin/python -m unittest discover -s tests -v
# From fujinet-nio-lib:
PALMOS_SHARED_BUILD=build/palmos-shared-m3 make test-palmos-shared \
 PALMOS_SHARED_PYTHON=build/palmos-shared/venv/bin/python
make linux test-library-link test-session test-palmos-transport \
 test-raw-transport-retry test-open-ext test-open-wire test-ready-wire \
 test-write-partial test-large-read \
 SBNIO_ABI_INCLUDE=-I/home/mozzwald/nio/fujinet-nio-master-review/bridges/rp2350-springboard/include
```

Native installer mocks compile the actual installer C with two-byte struct
packing; they do not emulate Palm's database allocator or automatic Setup
launch. The compiled app tests exercise real classic adapter/client/service
instructions, not GUI events or real endpoints. Their mock code-cache is flushed
when replacing one app's code with the next, and application relocations permit
odd-address text strings without relaxing the production library serializer.
The full cross-platform suite was not rerun: previously recorded cc65/toolchain
and `test-stream-wake` signature failures remain unrelated, unresolved limits.

## Minimal Prism procedure (manual; no automatic actions)

Choose **one** installation path:

**Single UF2, no HotSync:** close network apps, return Home, remove the module,
enter RP2350 BOOTSEL, copy `build/m3/niolib-m3-r2.uf2`, then let it enumerate. Start
NIO using the command below, then insert the module once. The ROM Setup should
install NioLib (a hidden system library), NioLibTest, ISS Tracker and Weather
into RAM. Do not run the old static ROM apps as a substitute. This candidate ROM
contains only Setup; the visible ISS/Weather apps are the installed RAM copies.
Do not flash with an app executing from the module.

**Existing firmware, HotSync:** the engineer queues all four files in
`build/m3/install/` using the established serial palm-sync workflow. No ROM or
firmware change is needed for this path. Exit apps first; do not replace a
loaded library during active networking. We have not queued HotSync now.

After a flash, the old PC process may retain the disconnected USB port. The
operator can explicitly restart the existing Linux backend with:

```sh
NIO=/home/mozzwald/nio/fujinet-nio-springboard/build/fujibus-link-serial-debug/fujinet-nio \
 /home/mozzwald/nio/springboard-nio/host/nio.sh restart
/home/mozzwald/nio/springboard-nio/host/nio.sh status
```

This selects the **NIO link** ACM interface via board discovery, runs in the
existing `host/nio-run` configuration directory and logs to
`/home/mozzwald/nio/springboard-nio/host/nio-run/nio.log`. No Wi-Fi credentials
are needed in the module; the Linux host needs working network access. For an
interactive foreground launch with no backend already owning that port, use
`NIO=... /home/mozzwald/nio/springboard-nio/host/run-nio.sh` instead. Do not run
two copies. These commands were documented, not executed during this task.

Test only this sequence initially:

1. Open NioLibTest; expect the original offline 81-check PASS. Network → Run
   should still show Clock + two HTTP PASS. Return **Home** normally.
2. Open ISS Tracker; wait for a position/map, then return **Home** normally.
3. Open Weather; wait for location/current weather, then return **Home**.
4. Reopen ISS Tracker; verify another successful fetch. Return **Home**.

Report displayed results/errors. The engineer correlates backend opens/closes
and library ownership; repeat switching and Palm free-heap checks can follow if
this minimum sequence succeeds. No synchronous responsiveness improvement is
claimed. If Setup did not install the apps, stop and report that separately;
no repeated reset/insertion campaign. A loaded-library collision requires
normal app exit/cleanup before retry; do not delete an active library. Record
isolated MemoryMgr alerts; stop after two consecutive startup alerts.

Rollback: with apps closed and module removed, flash
`build/m3/rollback/sbnio-linux-apps.uf2` (SHA256
`5c7169697f85cffb1aa757780468899d004ed88672e812114fb408f66587fe2b`), restart NIO
manually if the USB connection changed, and reinsert once. Keep standalone
static PRCs for serial HotSync rollback; avoid running static clients while a
shared-library transaction is unresolved. Nothing here clears M2's fail-closed
pending-response metadata or claims unknown remote handles are cleaned up.

The implementation was initially ready for hardware qualification. The later
R2 checkpoint now qualifies installation and the complete minimum app-handoff
sequence. Quantitative heap and extended stress/fault coverage remain additional
work rather than measured guarantees.
Milestone 4 serial integration, configuration and asynchronous networking have
not begun.


## Startup failure and installer R2 — 2026-11-05

User reports a Fatal Exception with only Reset during module detection on
insertion. The user confirmed `niolib-m3.uf2` was flashed and this was its first
insertion. The alert has no filename or line number; no exception PC/stack is
available. Treat this
as a startup failure report, not proof of a particular ROM bus or networking
failure. No automatic reset or flash was initiated; no app test had run at that failure
point. The subsequent successful R2 test is recorded in the hardware checkpoint.

Source review identified a concrete call-site problem: the original installer
locked an `nPRC` resource, skipped the 8-byte length/CRC envelope, then passed
that interior pointer to `DmCreateDatabaseFromImage`. The SDK API describes its
input as a pointer to a locked resource containing the database image
([Palm API reference](https://palm.wiki/development/docs/601/PalmOSReference/DataAndResourceManager.html)).
The old native mock accepted arbitrary interior pointers and did not model
allocation boundaries. There is no real Palm exception trace proving this was
the crashing operation; that causal link remains a hypothesis.

R2 copies the complete validated PRC into a new `MemHandleNew(n)` allocation,
locks it and calls the OS with that allocation's base pointer. It unlocks and
frees the temporary image on success or create failure; allocation/lock failure
returns an error. The source resource remains locked during validation/use.
This removes the interior-pointer dependency and provides the exact image
length as the chunk size. Peak extra temporary allocation is one PRC at a time
(maximum 16,032 bytes), plus handle/OS overhead. It does not alter any app,
library, protocol, PIO, ARM reply or USB source.

The native mock now requires the API argument to equal the base of the new
locked image allocation, copies database contents independently (no retained
pointer to a freed image), and checks allocation failure and final zero live
image/lock counts. The original committed installer **fails** that tightened
check; R2 passes. This reproduces a violated modeled precondition, not the
Prism's actual exception. The compiled installer and complete ROM packaging
were rebuilt and audited. All five app/installer host methods pass. The linked
critical ARM/PIO byte comparisons and UF2/BIN validation still pass. The
unchanged library/network code's prior 26-test result remains applicable; it
was not needlessly rerun for this installer-only change.

Original candidate and identity files remain in
`build/m3-failure-20261105/`; the original named UF2 also remains in `build/m3/`.
Use **`build/m3/niolib-m3-r2.uf2`** for an explicitly agreed next attempt. R2
was initially unflashed; its subsequent successful hardware run is recorded in
the linked checkpoint. Keep the working rollback UF2 available.
Do not repeatedly reset the current alert. Confirm recovery/test details with
the operator before another hardware action.


R2 UF2 SHA256: `9058447b8c623d38c63b2a3d3fdbedaa367233754e6f6114012dd0ee72387361`.
R2 ROM SHA256: `953b9ebb97fb9fcf7f953889983c5a24c0cc071f80e2cb7ad5ce968571f6d3bc`.
The four application/library PRCs are unchanged. For recovery after recording
the alert, remove the module and soft-reset the Prism once, keeping the module
out before any explicitly agreed R2 flash/reinsert. No hard reset or data erase
is requested. If an exception repeats, stop rather than cycling resets.
