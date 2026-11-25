#!/usr/bin/env bash
# Serve Inkling 2 Mini with Strata (official container) for the sandbox.
#  * 127.0.0.1:18080  -> host-side tests
#  * 172.17.0.1:18080 -> docker0 bridge = host.openshell.internal for sandboxes
# The gateway already owns :8080, hence 18080.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
IMAGE="${STRATA_IMAGE:-ghcr.io/niko1221/strata:0.2.21-cuda13}"
MODEL="${STRATA_MODEL:-SQ-20}"
CONTEXT="${STRATA_CONTEXT:-32k}"
DATA="${STRATA_DATA:-$here/.strata-data}"   # ~19 GB of weights
BRIDGE_IP="$(ip -4 -o addr show docker0 | awk '{print $4}' | cut -d/ -f1)"
docker rm -f strata >/dev/null 2>&1 || true
docker run -d --name strata --gpus all \
  -p 127.0.0.1:18080:8080 -p "${BRIDGE_IP}:18080:8080" \
  --ulimit memlock=-1:-1 --shm-size 2g --stop-timeout 120 \
  -v "${DATA}:/data" \
  -e FAMILY=inkling-2-mini -e MODEL="${MODEL}" -e CONTEXT="${CONTEXT}" \
  -e PARALLEL=1 -e VISION=off \
  -e API_KEY_FILE=/run/secrets/strata_api_key \
  -v "$here/.secrets/strata_api_key:/run/secrets/strata_api_key:ro" \
  ${STRATA_SET:+-e STRATA_SET="$STRATA_SET"} \
  "$IMAGE"
echo "started; follow with: docker logs -f strata"
