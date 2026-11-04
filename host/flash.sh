#!/bin/sh
# Build the RP2350 firmware, flash it through picotool's reset interface and
# restart fujinet-nio on the new USB port.
#   host/flash.sh             # firmware with the current ROM
#   host/flash.sh --palm      # rebuild the Palm app and ROM first
set -eu
HOST=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$HOST")
# Preserve the original Mac toolchain discovery; Linux uses PATH or PICO_TOOLCHAIN_PATH.
MAC_TOOLCHAIN="$HOME/opt/arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi/bin"
if [ "$(uname -s)" = Darwin ] && [ -d "$MAC_TOOLCHAIN" ]; then
    export PATH="$MAC_TOOLCHAIN:$PATH"
fi
BUILD_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --palm) "$ROOT/palm/build.sh" ;;
        --build-only) BUILD_ONLY=1 ;;
        *) echo "usage: $0 [--palm] [--build-only]" >&2; exit 2 ;;
    esac
done
set -- -S "$ROOT/firmware" -B "$ROOT/firmware/build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DSBNIO_DEPS="${SBNIO_DEPS:-$ROOT/repos/fujinet-nio/bridges/rp2350-springboard/.deps}" \
    -DSBNIO_ROM="$ROOT/palm/build/sbnio.rom"
if [ -n "${PICOTOOL_DIR:-}" ]; then
    set -- "$@" "-Dpicotool_DIR=$PICOTOOL_DIR"
fi
cmake "$@" >/dev/null
cmake --build "$ROOT/firmware/build"
[ "$BUILD_ONLY" = 0 ] || exit 0
# Flash only the Springboard board, by serial, even with other RP2350s attached.
SERIAL=${SBNIO_SERIAL:-$(cat "$HOST/board.local.serial" 2>/dev/null || cat "$HOST/board.serial" 2>/dev/null)}
[ -n "$SERIAL" ] || { echo "set SBNIO_SERIAL or write host/board.serial" >&2; exit 1; }
"$HOST/nio.sh" stop
picotool load -x "$ROOT/firmware/build/sbnio.uf2" --ser "$SERIAL" -f
sleep 2
"$HOST/nio.sh" start
