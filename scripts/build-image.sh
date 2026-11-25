#!/usr/bin/env bash
# Build the scenario-authoring sandbox image on the host Docker daemon (the one
# the local OpenShell gateway's Docker driver launches sandboxes from).
#
#   scripts/build-image.sh                                        # default version (scripts/env.sh)
#   AUTOWARE_CARLA_SCENARIO_VERSION=29.3.11 scripts/build-image.sh
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
ver="$AUTOWARE_CARLA_SCENARIO_VERSION"
ref="v$ver"

# The map data and the docs the skills cite (docs/<page>.md) are in the
# framework repo, not in the PyPI wheel: take them from the matching tag.
src="$AUTOWARE_CARLA_SCENARIO_SRC"
if [ -z "$src" ]; then
  src="$here/.cache/autoware_carla_scenario-$ver"
  [ -d "$src/.git" ] || git clone -q --depth 1 --branch "$ref" "$AUTOWARE_CARLA_SCENARIO_REPO" "$src"
fi
mkdir -p "$here/image/workspace/data"
for f in nishishinjuku.osm nishishinjuku_carla.xodr; do
  git -C "$src" show "$ref:data/$f" > "$here/image/workspace/data/$f"
done
rm -rf "$here/image/workspace/docs.tmp" && mkdir -p "$here/image/workspace/docs.tmp"
git -C "$src" archive "$ref" autoware_carla_scenario/docs | tar -x -C "$here/image/workspace/docs.tmp"
rm -rf "$here/image/workspace/docs" && mv "$here/image/workspace/docs.tmp/autoware_carla_scenario/docs" "$here/image/workspace/docs"
rmdir -p "$here/image/workspace/docs.tmp/autoware_carla_scenario" 2>/dev/null || true

docker build --build-arg AUTOWARE_CARLA_SCENARIO_VERSION="$ver" -t "$SANDBOX_IMAGE" "$here/image"
echo "built $SANDBOX_IMAGE"
