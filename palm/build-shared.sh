#!/bin/sh
# Build only: RAM PRCs + installer ROM. No USB/HotSync/service actions.
set -eu
PALM=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname "$PALM")
WORKSPACE=$(dirname "$ROOT")
LIB=${NIOLIB_ROOT:-$(cd "$ROOT/repos/fujinet-nio-lib" && pwd -P)}
ABI=${SBNIO_ABI_DIR:-$WORKSPACE/fujinet-nio-master-review/bridges/rp2350-springboard/include}
IMAGE=${PALM_IMAGE:-fujinet-palm-springboard-tools}
docker run --rm --network none --user "$(id -u):$(id -g)" \
 -v "$WORKSPACE:$WORKSPACE" -w "$LIB" "$IMAGE" \
 make -f makefiles/palmos-shared.mk B=build/palmos-shared-m3 "SBNIO_ABI_INCLUDE=-I$ABI"
exec docker run --rm --network none --user "$(id -u):$(id -g)" \
 -v "$WORKSPACE:$WORKSPACE" -w "$PALM" "$IMAGE" \
 make -f Makefile.shared "LIB=$LIB" "$@"
