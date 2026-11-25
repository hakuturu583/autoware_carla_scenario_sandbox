# Shared settings for the scripts. Source it; every value can be overridden
# from the environment or from a git-ignored ./local.env (machine paths).
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$here/local.env" ] && . "$here/local.env"

# The autoware_carla_scenario release the sandbox is built for. It selects the
# PyPI version installed in the image and on the host runner, and the git tag
# (v<version>) the map data and the skills' docs are taken from.
AUTOWARE_CARLA_SCENARIO_VERSION="${AUTOWARE_CARLA_SCENARIO_VERSION:-29.3.11}"
AUTOWARE_CARLA_SCENARIO_REPO="${AUTOWARE_CARLA_SCENARIO_REPO:-https://github.com/autowarefoundation/autoware_carla_scenario.git}"
# Optional local clone to read the tag from instead of cloning from GitHub.
AUTOWARE_CARLA_SCENARIO_SRC="${AUTOWARE_CARLA_SCENARIO_SRC:-}"
SANDBOX_IMAGE="${SANDBOX_IMAGE:-autoware-carla-scenario-sandbox:${AUTOWARE_CARLA_SCENARIO_VERSION}}"
export AUTOWARE_CARLA_SCENARIO_VERSION SANDBOX_IMAGE
