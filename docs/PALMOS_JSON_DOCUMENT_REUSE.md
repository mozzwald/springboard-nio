# ISS and Weather — reuse the open JSON response

Scope: remove repeated HTTP GETs only. Native forms, synchronous app handlers,
polling/backoff, transports, RP2350 firmware, ROM and installer are unchanged.
Application source in `fujinet-palm` is unchanged: both apps already use the same
classic compatibility shim in `palm/compat/fn_classic.c`.

The shared build now retains the original network handle during
`network_json_parse()`. Each `network_json_query_n()` uses
`fn_json_query(handle, selector)` then reads at offset zero; `network_close()`
releases the document. The NIO host caches the completed body and changes its
JSON selector using its existing TranslateConfigure command, with no new GET.
A first-body NotReady is followed by Read polling, not configuration replay.

Expected successful fetches:

| Operation | Before | New |
| --- | ---: | ---: |
| ISS position refresh | 4 GETs | 1 GET |
| Weather startup, IP location | 42 GETs | 4 GETs |

Weather still uses its original location URL and three separate weather URLs.
This change does not combine endpoints, cache location between launches or make
UI/networking asynchronous. Legacy static app builds are preserved.

## Required library

These PRCs require **NioLib ABI 1.4**, capability **0x40**, exposing cached JSON
selection at appended trap **0xA816**. The NIO host already supports the command,
including the preserved Springboard backend revision `aeba1b6c`; no host update
is required. The Palm library/client needed this small exposure; the generic
public fn_json_query signature already existed for BBC.

The new shim reports an understandable dependency error on an older library;
it does not refetch once per field as a fallback. Existing old apps remain
compatible with NioLib 1.4. See sibling library
`docs/palmos-shared-library.md` for the ABI and ownership details.

## Build only — no ROM, UF2 or installation

First build the library separately into `build/palmos-shared-json-reuse` with
`fujinet-palm-springboard-tools`, using its documented Handspring/ABI mounts.
Then, in the same existing Docker image with repositories mounted at their
normal locations, run from `springboard-nio/palm`:

```sh
make -f Makefile.shared apps B=build/shared-json-reuse \
  LIB=/path/to/fujinet-nio-lib \
  FNPALM=/path/to/fujinet-palm/palm/apps \
  CLIENT=/path/to/fujinet-nio-lib/build/palmos-shared-json-reuse/libniolib-client.a
```

Outputs: `palm/build/shared-json-reuse/isstracker.prc` and `weather.prc`, with
linked COFF, symbols and disassembly alongside. The old app artifacts and frozen
pre-upstream ABI 1.3 test bundle are not overwritten.

## Automated evidence

Using the library's existing Unicorn venv:

```sh
NIOLIB_ROOT=/path/to/fujinet-nio-lib \
PALMOS_SHARED_BUILD=/path/to/fujinet-nio-lib/build/palmos-shared-json-reuse \
PALMOS_APPS_BUILD=/path/to/springboard-nio/palm/build/shared-json-reuse \
  /path/to/fujinet-nio-lib/build/palmos-shared/venv/bin/python -B \
  -m unittest discover -s tests -p test_shared_apps.py -v
```

The tests execute actual compiled FetchIss, GetIpLocation and GetWeather, asserting
one/four Opens and three/38 selector commands. Other checks cover field values,
reused handles, normal cleanup/handoff, missing dependencies, errors and first-body
NotReady without replaying configuration. Palm ROM helpers/peers are mocked;
these are not physical timing measurements. The separate shared-library tests
cover CS1/serial/USB and request/response validation. Neither app embeds the NIO
core or a physical transport implementation.

## Later physical test

**First perform the already-prepared code-review hardware regression using its
frozen ABI 1.3 bundle.** This app change is a separate follow-up.

After that passes, use the same safe idle-library/HotSync procedure to install
ABI 1.4 NioLib plus these ISS/Weather PRCs into RAM. The freshly built NioLibTest
is optional. Keep NioConfig, backend configuration and module firmware unchanged.
Launch ISS, then Weather and confirm correct fields/fresh data; compare backend
GET/Open counts with one/four. Existing synchronous UI waiting remains expected.
No installation, backend restart, USB claim or physical testing was performed
while preparing these candidates.


## Hardware checkpoint — 2026-11-06

The user tested the updated NioLib, ISS Tracker and Weather with these JSON fixes
on the Visor Prism and reports that all work perfectly. This follows the separate
successful pre-upstream USB and CS1 acceptance session.

The app implementation is committed as
`5bf75ebef471c17f53ac1c029f708a5c9ce7f7ce` on `feat/palmos-shared-apps`.
Its matching NioLib ABI 1.4 support is
`421fa27d2a34b9b98766bf29f6b57fb8c80a8c45` on
`fujinet-nio-lib:feat/palmos-shared-niolib`. No host, firmware or ROM update is
required for this change.

This is user-reported physical application success. No additional host trace,
GET-count measurement or elapsed-time measurement was collected, and the transport
for this particular app test was not specified. The automated evidence above
remains the source for exact one/four GET assertions. The earlier preparation-only
and pending-test statements are retained as historical context.
