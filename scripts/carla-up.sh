#!/usr/bin/env bash
# CARLA 1.0 nightly (shipping package) on :2000, offscreen, Town10HD_Opt.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
PKG="${CARLA_PKG:?set CARLA_PKG to the CARLA 1.0 package dir (contains CarlaUnreal.sh), e.g. in local.env}"
cd "$PKG"
# CARLA_RENDER=0: -nullrhi (no GPU rendering, ~no VRAM) so the server fits next to
# Strata/SQ-20 for the agent's debug loop (TrafficManager ego, no sensors).
# CARLA_RENDER=1 (default): offscreen rendering, needed for the chase-cam video.
if [ "${CARLA_RENDER:-1}" = "0" ]; then render=(-nullrhi); else render=(-RenderOffScreen -quality-level="${CARLA_QUALITY:-Epic}"); fi
nohup ./CarlaUnreal.sh "${render[@]}" -carla-rpc-port=2000 \
  > "${CARLA_LOG:-$here/runner/carla.log}" 2>&1 &
echo "CARLA pid $!; waiting for :2000"
for i in $(seq 120); do (echo > /dev/tcp/127.0.0.1/2000) 2>/dev/null && { echo up; exit 0; }; sleep 2; done
echo "CARLA did not come up" >&2; exit 1
