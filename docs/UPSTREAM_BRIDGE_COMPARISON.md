# Upstream RP2350 bridge versus tested Diller implementation

Compared 2026-11-04; no hardware or runtime changes made.

## Exact comparison points

| Source | Revision | Role |
| --- | --- | --- |
| springboard-nio | `6adc84feed589d07364883c3c53b2451c8898e56` | Actual four-app firmware source used for successful ISS and Weather run |
| Diller NIO branch | `4ae9dee6dd0d9f2cf0009255ae32fa6610e66781` | `diller/feat/rp2350-springboard`; packaged bridge used as source reference and Linux backend base |
| Our NIO host branch | `aeba1b6cfd3fa2ffd19c95cd6983ebdbdcb44c16` | Adds host serial PacketLink profile; does not change bridge firmware |
| Synced upstream master | `09c96f9bd7a497a7a527887261bb1cd694a3e13e` | Reviewed in detached `fujinet-nio-master-review` worktree |

The physical firmware is the standalone springboard-nio build, not a firmware
build from the NIO worktree. Its UF2 SHA256 remains
`5c7169697f85cffb1aa757780468899d004ed88672e812114fb408f66587fe2b`.

## Finding

Upstream is the same two-way CS1 bridge architecture with two specific
PacketLink ownership/completion fixes. It is not another bus engine.

From Diller's packaged bridge to current master, exactly six files differ:

1. `README.md`: documents the request snapshot RAM cost.
2. `docs/sbnio-link.md`: describes disconnect outcomes and request ownership.
3. `include/sbnio.h`: clarifies the existing UNANSWERED result comment.
4. `src/packet_link.c`: implements the two fixes.
5. `src/packet_link.h`: replaces the request pointer with an owned array.
6. `tests/test_packet_link.c`: adds disconnect and source-buffer-reuse checks.

The functional changes are from upstream commit
`e11f65be8df4f2c7853282efb6cc4878beeff363`, "Protect Springboard packet
completion and retries". `4cc174e` subsequently documents the RAM cost.

## What is unchanged

Diller-to-master byte comparisons confirm unchanged:

- `src/pio_rearm_program.c`: PIO CS0/CS1 reader, qualification and clamps.
- `src/persistent_reply.S`: Core1 SRAM read/reply/completion loop in SCRATCH_X.
- `src/bus.c`: write snapshot/DMA capture, ROM/register tables, startup and ownership.
- `src/link.c`: CS1 command assembly, request checks, register publication.
- `src/main.c`: initialization and Core0 task loop.
- `src/usb_descriptors.c`: USB identity, interfaces and endpoints.

All other bridge files except the six listed are also unchanged between those
packaged revisions. Clock, pins, drive configuration, write-settle default,
startup, completion guards and the firmware CMake configuration are unchanged.

Standalone-to-packaged differences are mostly formatting, include ordering,
provenance comments, split string literals, and a shorter startup banner
(`springboard-nio` becomes `sbnio`). The actual PIO program is byte-identical
across all three sources. The standalone/published ARM assembly token stream
is identical after comments and whitespace are excluded. No new CS0 or CS1
lookup operation was found in the port.

The standalone project bundles Palm app/ROM building and host scripts. The
packaged bridge instead has pinned dependency/bootstrap tooling, host tests,
board validation and a separate host/firmware CMake mode. It takes an external
ROM through `SPRINGBOARD_ROM`; omitting that input embeds an erased placeholder
that cannot enumerate apps. A move to it must explicitly reuse our verified
51,544-byte ROM. The upstream bridge does not package the four apps by itself.

## The two real behavior changes

**Disconnect outcome:** previously `pl_close` returned NO_PEER for any pending
request. If the request had already been sent, NIO may have executed it before
USB disconnected. Upstream reports UNANSWERED in that case and increments its
counter; a pending request not yet sent still returns NO_PEER. The existing
SBN_RES_UNANSWERED code carries that distinction to the Palm. This avoids
misrepresenting an uncertain completion as a command that could not have run.

**Owned request snapshot:** previously PacketLink retained a pointer to the
mutable request-assembly buffer. A later Palm BEGIN/DATA sequence could change
those bytes before an initial delayed send or an allowed retry. Upstream copies
the validated request into `pl_link.req[8192]` at submission. Delayed sends and
retries retain the original bytes even if the assembly buffer is reused.

These fixes do not change the wire framing, register offsets, checksums,
sequence rules or ABI version 4. Comparing C-preprocessor output finds all
43 SBN macro definitions identical. Existing compiled Palm apps should remain
ABI-compatible; that is a source/ABI conclusion, not a completed hardware test.

## Resource and timing implications

The new request array replaces a 4-byte pointer on RP2350, adding 8,188 static
bytes. Upstream documents comparable-build BSS increasing from 219,688 to
227,876 bytes; those are build-specific figures, not a fresh measurement of
our exact ROM build. Submission adds one memcpy of at most 8,192 bytes on
Core0, once per accepted request. No such copy occurs inside Core1's live
ROM read path.

Unchanged bus source does not prove identical hardware timing: static SRAM
placement and Core0 SRAM traffic can affect response behavior. Do not claim
instruction-timing or electrical equivalence of a newly linked firmware until
checked. Preserve the working UF2 and run the same real-app regression before
adopting a new build.

## Checks actually run

- Original standalone PacketLink test + original implementation: PASS.
- Upstream expanded PacketLink test + upstream implementation: PASS.
- Upstream expanded test + original implementation: expected FAIL at three
  assertions: in-flight disconnect, mutated retry payload, mutated deferred
  first-send payload. This demonstrates the fixes cover real missing cases.
- Upstream full native bridge Release suite: 7/7 PASS, including PIO read,
  write decoding, ABI, PacketLink, setup/tooling and PIO policy checks.
- Shared SBN macro comparison: 43/43 identical.
- Source byte/token and revision comparisons as described above.

Evidence: `build/comparison-20261104/{comparison.json,*.log}` in this repository;
full native log in the master review worktree under
`bridges/rp2350-springboard/build/compare-host/Testing/Temporary/LastTest.log`.
These are host tests; no new firmware UF2 was built, flashed or hardware-tested.

## Recommendation

Use upstream as the preferred basis for the next deliberate bridge build,
with our exact current ROM and a preserved rollback image, rather than
maintaining another permanent copy. It carries useful error-path fixes while
retaining the proven bus engine. A short ISS/Weather regression is still needed
for that newly linked image.

Neither fix addresses Palm blocking fetches, unknown write-register decodes,
or the unusually long WE-meter sample from our first app run: their relevant
paths are unchanged. Keep those issues separate. The installed successful
firmware, current Linux NIO backend and console collector remain unchanged.
