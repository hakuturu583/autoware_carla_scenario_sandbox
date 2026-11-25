#!/usr/bin/env bash
# Run a sandbox-written scenario package on the host CARLA server and record it.
#
#   scripts/run-in-carla.sh <package_dir> <scenario_name> <out_dir> [extra hydra overrides...]
#
# Needs a CARLA server on localhost:2000 (scripts/carla-up.sh) -- and the GPU
# free of Strata (scripts/strata-down.sh), since the two do not fit together.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
pkg="$(realpath "$1")"; name="$2"; out="$(realpath -m "$3")"; shift 3
mkdir -p "$out/frames"
export TYPESAFE_CARLA_CARLA_REF=1.0 TYPESAFE_CARLA_PYCARLA_BUILD=0
# One host venv per framework version (AUTOWARE_CARLA_SCENARIO_VERSION).
venv="$here/runner/.venv-$AUTOWARE_CARLA_SCENARIO_VERSION"
if [ ! -x "$venv/bin/scenario" ]; then
  uv venv -q --python 3.12 "$venv"
  VIRTUAL_ENV="$venv" uv pip install -q "autoware-carla-scenario==$AUTOWARE_CARLA_SCENARIO_VERSION" opencv-python-headless
fi
export VIRTUAL_ENV="$venv" PATH="$venv/bin:$PATH"
cd "$here/runner"
uv pip install -q -e "$pkg"

python chase_cam.py "$out/frames" 120 > "$out/chase_cam.log" 2>&1 &
cam=$!
set +e
scenario "scenario=${name}/default" map=town10hd_opt \
  server.max_tick_rate_hz=20 "hydra.run.dir=$out/run" "$@" > "$out/scenario.log" 2>&1
rc=$?
set -e
sleep 3; kill "$cam" 2>/dev/null || true; wait "$cam" 2>/dev/null || true
n=$(ls "$out/frames" | wc -l)
if [ "$n" -gt 0 ]; then
  ffmpeg -y -loglevel error -framerate 10 -pattern_type glob -i "$out/frames/*.jpg" \
    -c:v libx264 -pix_fmt yuv420p -crf 23 -movflags +faststart "$out/carla.mp4"
fi
echo "scenario exit=$rc frames=$n video=$out/carla.mp4"
grep -E -i "PASS|FAIL|verdict|result" "$out/scenario.log" | tail -5 || true
