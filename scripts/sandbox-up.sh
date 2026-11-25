#!/usr/bin/env bash
# Register the Strata provider with the OpenShell gateway and create the
# scenario-authoring sandbox from the locally built image.
#
#   scripts/sandbox-up.sh [name]          (default name: scenario-author)
#   openshell sandbox connect scenario-author # then run `pi` inside
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
NAME="${1:-scenario-author}"

if ! openshell provider profile list 2>/dev/null | grep -q "^strata-local "; then
  openshell provider profile import -f "$here/policy/strata-profile.yaml"
fi
if ! openshell provider list 2>/dev/null | grep -q "^strata "; then
  # The real key goes to the gateway only; the sandbox sees a placeholder.
  STRATA_API_KEY="$(cat "$here/.secrets/strata_api_key")" \
    openshell provider create --name strata --type strata-local --from-existing
fi
openshell sandbox create --name "$NAME" --from "$SANDBOX_IMAGE" \
  --policy "$here/policy/sandbox-policy.yaml" \
  --provider strata --no-auto-providers --no-tty --detach
openshell sandbox list
