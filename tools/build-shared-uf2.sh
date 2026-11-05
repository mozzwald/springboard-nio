#!/bin/sh
# Build a separate UF2 using the unchanged working bus/USB firmware.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORKSPACE=$(dirname "$ROOT")
"$ROOT/palm/build-shared.sh"
cmake -S "$ROOT/firmware" -B "$ROOT/build/m3/firmware" -G Ninja \
 -DCMAKE_BUILD_TYPE=Release \
 "-DSBNIO_DEPS=${SBNIO_DEPS:-$WORKSPACE/springboard-nio/build/deps}" \
 "-DPICO_SDK_PATH=${PICO_SDK_PATH:-$WORKSPACE/springboard-nio/build/deps/pico-sdk}" \
 "-Dpicotool_DIR=${PICOTOOL_DIR:-$WORKSPACE/fujinet-nio/bridges/rp2350-springboard/build/persistent-reply/picotool-host/picotool}" \
 "-DSBNIO_ROM=$ROOT/palm/build/shared/niolib-m3.rom"
cmake --build "$ROOT/build/m3/firmware"
python3 "$ROOT/tools/verify-shared-uf2.py" --baseline "${BASELINE_ELF:-$WORKSPACE/springboard-nio/build/artifacts/sbnio-linux-apps.elf}"
cp "$ROOT/build/m3/firmware/sbnio.uf2" "$ROOT/build/m3/niolib-m3-r2.uf2"
mkdir -p "$ROOT/build/m3/install"
cp "$ROOT/palm/build/shared/isstracker.prc" "$ROOT/palm/build/shared/weather.prc" "$ROOT/build/m3/install/"
LIB=${NIOLIB_ROOT:-$(cd "$ROOT/repos/fujinet-nio-lib" && pwd -P)}
cp "$LIB/build/palmos-shared-m3/NioLib.prc" "$LIB/build/palmos-shared-m3/NioLibTest.prc" "$ROOT/build/m3/install/"
printf '%s\n' "Built $ROOT/build/m3/niolib-m3-r2.uf2 (not flashed)."
