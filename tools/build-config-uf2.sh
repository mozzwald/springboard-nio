#!/bin/sh
# M5 build only. No flash, USB device, backend, or Palm action.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORKSPACE=$(dirname "$ROOT")
LIB=${NIOLIB_ROOT:-$WORKSPACE/fujinet-nio-lib}
CONFIG=${NIO_CONFIG_ROOT:-$WORKSPACE/nio-config}
IMAGE=${PALM_IMAGE:-fujinet-palm-springboard-tools}
ABI=${SBNIO_ABI_DIR:-$WORKSPACE/fujinet-nio-master-review/bridges/rp2350-springboard/include}
# New library output: retain the software-verified M4 and hardware M3 outputs.
docker run --rm --network none --user "$(id -u):$(id -g)" \
 -v "$WORKSPACE:$WORKSPACE" -w "$LIB" "$IMAGE" \
 make palmos-shared PALMOS_SHARED_BUILD=build/palmos-shared-m5 "SBNIO_ABI_INCLUDE=-I$ABI"
docker run --rm --network none --user "$(id -u):$(id -g)" \
 -v "$WORKSPACE:$WORKSPACE" -w "$CONFIG" "$IMAGE" \
 make palmos "FUJINET_NIO_LIB=$LIB" "NIOLIB_BUILD=$LIB/build/palmos-shared-m5"
docker run --rm --network none --user "$(id -u):$(id -g)" \
 -v "$WORKSPACE:$WORKSPACE" -w "$ROOT/palm" "$IMAGE" \
 make -f Makefile.config "LIB=$LIB" "CONFIG_ROOT=$CONFIG" \
 "CLIENT=$LIB/build/palmos-shared-m5/libniolib-client.a" \
 "LIBPRC=$LIB/build/palmos-shared-m5/NioLib.prc" \
 "TESTPRC=$LIB/build/palmos-shared-m5/NioLibTest.prc"
cmake -S "$ROOT/firmware" -B "$ROOT/build/m5/firmware" -G Ninja \
 -DCMAKE_BUILD_TYPE=Release \
 "-DSBNIO_DEPS=${SBNIO_DEPS:-$WORKSPACE/springboard-nio/build/deps}" \
 "-DPICO_SDK_PATH=${PICO_SDK_PATH:-$WORKSPACE/springboard-nio/build/deps/pico-sdk}" \
 "-Dpicotool_DIR=${PICOTOOL_DIR:-$WORKSPACE/fujinet-nio/bridges/rp2350-springboard/build/persistent-reply/picotool-host/picotool}" \
 "-DSBNIO_ROM=$ROOT/palm/build/m5/niolib-m5.rom"
cmake --build "$ROOT/build/m5/firmware"
python3 "$ROOT/tools/verify-shared-uf2.py" \
 --baseline "$ROOT/build/m3/firmware/sbnio.elf" \
 --build "$ROOT/build/m5/firmware" --rom "$ROOT/palm/build/m5/niolib-m5.rom" \
 --report "$ROOT/build/m5/firmware-differential.json"
cp "$ROOT/build/m5/firmware/sbnio.uf2" "$ROOT/build/m5/niolib-m5-config.uf2"
mkdir -p "$ROOT/build/m5/install"
cp "$ROOT/palm/build/m5/isstracker.prc" "$ROOT/palm/build/m5/weather.prc" \
 "$LIB/build/palmos-shared-m5/NioLib.prc" "$LIB/build/palmos-shared-m5/NioLibTest.prc" \
 "$CONFIG/build/palmos/NioConfig.prc" "$ROOT/build/m5/install/"
(cd "$ROOT/build/m5" && sha256sum niolib-m5-config.uf2 install/*.prc > SHA256SUMS)
printf '%s\n' "Built $ROOT/build/m5/niolib-m5-config.uf2 (not flashed)."
