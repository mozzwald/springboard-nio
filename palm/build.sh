#!/bin/sh
# Build the Palm app and Springboard ROM in the sbnio-palm container.
#   palm/build.sh            # build/sbnio.prc and build/sbnio.rom
#   palm/build.sh clean
set -e
PALM=$(cd "$(dirname "$0")" && pwd)
ROOT=$(dirname "$PALM")
IMAGE=${PALM_IMAGE:-sbnio-palm}
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker build --platform linux/amd64 -t "$IMAGE" "$PALM/docker"
fi
exec docker run --rm --platform linux/amd64 --user "$(id -u):$(id -g)" -v "$(dirname "$ROOT")":"$(dirname "$ROOT")" -w "$PALM" "$IMAGE" make "$@"
