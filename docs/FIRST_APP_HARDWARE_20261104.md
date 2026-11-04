# First Linux-backed real-app checkpoint — 2026-11-04

## Observed success

User removed the prototype from the Prism and entered RP2350 BOOTSEL. The
engineer verified USB serial D2510D4E47DAC885 and copied the prebuilt candidate
without rebuilding or changing ROM contents. The user then inserted once.
ISS Tracker and Weather appeared in the launcher. ISS fetched a position and
plotted it on the map. Weather identified the user's location and displayed
current weather. These are actual end-to-end application observations.

Firmware UF2 SHA256:
`5c7169697f85cffb1aa757780468899d004ed88672e812114fb408f66587fe2b`.
ROM: 51,544 bytes, runtime CRC32 `1da7bf43`, HsAT 330 ns.
Sources: springboard-nio `6adc84f`, Linux NIO `aeba1b6`, library `361c164`.
The apps execute from CS0 ROM and exchange requests/replies through CS1 and
USB PacketLink to the Linux NIO backend. No HotSync or diagnostic read/write
campaign was used for acceptance. No scope/LA measurements were made.

## Captured counters and limitations

At uptime 526 s:

- Bus active, runs 1, fault 0; CS0 cycles 25,098,378; CS1 cycles 835,142.
- 1,897 requests / 1,897 answers; zero refused, unanswered, timeout, resend,
  corrupt or TX-dropped PacketLink outcomes. The console log independently
  contains 1,897 `reply ok` lines.
- Link ready, generation 7, idle, loopback off.
- Seven initial sync attempts, six unanswered, preceded the stable backend
  launch. They are recorded in the pre-insertion snapshot and are not six
  failed Palm requests.
- Write snapshots 28,882, unknown decoded register IDs 573, DMA ring peak 38
  of 8,192 words. Unknown snapshots are not explained by this experiment;
  no claim of perfectly qualified writes follows from correct app results.
- WE meter: 28,310 samples, minimum 340 ns, last 366 ns, maximum 20,093,153 ns.
  The unusually large maximum is unexplained; this coarse PIO meter is not
  independent electrical timing evidence. No scope test is requested now.

Logs, flash record, exact UF2/ROM identities and immutable success snapshot:
`build/bench/20261104-first-app/`. Raw logs include location-dependent network
requests and remain local/ignored rather than committed to a public repository.
Snapshot: `success-snapshot/{console.log,nio.log,result.json}`.
Build identities and rollback image: `build/artifacts/`.

The console collector and NIO backend remain running for the bench session.
An initial shell-launched NIO exited when its tool session ended; it was
restarted in a detached session before insertion. The stable PIDs recorded
for this run are console 243092 and NIO 243390. Check process identity before
later stopping/reusing any PID; PIDs are not permanent identities.

## User-observed responsiveness issue

Both apps become unresponsive until their initial data fetch finishes.
This agrees with the synchronous software call path:

- ISS `MainFormHandleEvent(frmOpenEvent)` draws then calls `DoRefresh`, which
  calls `FetchIss` and performs consecutive blocking JSON queries.
- Weather's same event calls `FullRefresh`, which gets location and weather
  before returning to the event loop.
- `palm/common/sbn_client.c:sbn_exchange` submits a request and busy-polls
  RESP_SEQ with a 35-second per-exchange timeout. It does not return to the
  Palm event loop while waiting.
- `palm/compat/fn_classic.c` waits for NIO readiness inside network_open,
  network_read and network_json_query_n. `SysTaskDelay(5)` yields CPU time,
  but does not dispatch the app's queued UI events.
- Each translated JSON query opens another NIO HTTP operation. A multi-field
  refresh therefore compounds the blocking calls. Network `NotReady` replies
  are normal intermediate protocol results, not PacketLink failures.
- The Linux backend also reports a 50 ms idle delay without transport wait;
  many individual replies take about 49 ms. Reducing that overhead would not
  itself restore Palm UI event processing.

The evidence supports application/transport blocking as the explanation for
UI unresponsiveness. It does not establish physical bus timing margins or
resolve the unrelated write-meter observations.

## Next software requirement

Preserve this successful image as the regression checkpoint. Make a separate
app-side experiment with bounded submit/poll/collect operations and a fetch
state machine progressed from normal Palm events. The UI must show loading,
continue repainting and handling controls, and support cancellation/form exit.

Preserve one outstanding exchange and response ownership. A cancelled network
operation may have run already: do not replay it blindly. Drain/abort or
invalidate an old result before starting a new request. Keep the existing
synchronous API for compatibility; do not recursively pump arbitrary UI events
from deep inside it, which could reenter code sharing transport/session globals.

Splitting only the transport polling loop is insufficient: callers and the
compatibility readiness loops must also return control between fetch stages.
Ordinary CS1 accesses stay short; do not change the PIO responder to solve UI
scheduling. No application, firmware or protocol code was changed in this
checkpoint capture.

## Follow-up: taps queued during the first ISS fetch

The user clarified that the first ISS launch was unresponsive, so they tapped
Refresh and then Home. Once the position arrived, the map appeared and the
launcher opened immediately. They reopened ISS and waited for its map to load.

This is consistent with input queued while frmOpenEvent's synchronous refresh
was running, then processed after it returned. The queued Home action explains
the immediate launcher transition; queued Refresh may also have scheduled
additional legitimate fetches, but its exact handling was not independently
traced. This is not evidence of a reset or crash.

Extra legitimate refresh requests can increase ordinary traffic. They do not,
by themselves, explain the unknown-write counter: that counter increments only
when a captured high-address register ID is outside the defined DATA/BEGIN/
CHECK/DOORBELL/CONTROL/LOG/ECHO set. No per-unknown snapshot/timestamp evidence
was recorded to associate those decodes with the taps or launcher transition.
Do not attribute the 573 unknown decodes or the long WE-meter maximum to user
input without further evidence. The initial app success and the UI event-loop
follow-up remain valid; no firmware change or extra hardware test was made.
