# Sandbox image in which a coding agent writes autoware_carla_scenario scenarios.
#
# Everything the agent needs is baked in at build time, because the OpenShell
# policy gives the running sandbox no WAN at all:
#   * the framework (PyPI autoware-carla-scenario, pinned) in a pre-synced venv,
#     including typesafe-carla's prebuilt client and the Codon toolchain that
#     `scenario-check` compiles with;
#   * the Nishishinjuku Lanelet2/OpenDRIVE map that `scenario-expand` reads;
#   * a warm uv cache (uv_build, pytest), so `uv pip install -e <pkg>` of a
#     freshly scaffolded package resolves offline;
#   * the pi coding agent (the harness) and its model config.
# The only egress the sandbox gets is the LLM endpoint, granted by an attached
# OpenShell provider (see ../policy/).

ARG NODE_IMAGE=node:22-bookworm-slim

FROM ${NODE_IMAGE} AS pi
ARG PI_VERSION=0.73.1
RUN npm install --prefix /opt/pi --omit=dev --no-audit --no-fund \
      @mariozechner/pi-coding-agent@${PI_VERSION}

FROM ubuntu:24.04

ARG UV_VERSION=0.9.17
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    UV_PYTHON_INSTALL_DIR=/usr/local/share/uv/python \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/sandbox/.cache/uv \
    TYPESAFE_CARLA_PYCARLA_BUILD=0

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git git-lfs less ripgrep jq procps build-essential \
    && rm -rf /var/lib/apt/lists/*

# uv (static binary) + node (for pi), both on /usr/local so the sandbox's
# baseline read-only /usr grant covers them.
COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /uvx /usr/local/bin/
COPY --from=pi /usr/local/bin/node /usr/local/bin/node
COPY --from=pi /opt/pi /usr/local/lib/pi
RUN ln -s /usr/local/lib/pi/node_modules/@mariozechner/pi-coding-agent/dist/cli.js /usr/local/bin/pi \
    && chmod +x /usr/local/lib/pi/node_modules/@mariozechner/pi-coding-agent/dist/cli.js

# Non-root sandbox user (OpenShell's Docker driver rejects a root USER).
RUN usermod -l sandbox -d /sandbox -m ubuntu && groupmod -n sandbox ubuntu \
    && mkdir -p /sandbox && chown -R sandbox:sandbox /sandbox \
    && mkdir -p ${UV_PYTHON_INSTALL_DIR} && chown sandbox:sandbox ${UV_PYTHON_INSTALL_DIR}

USER sandbox
WORKDIR /sandbox/workspace

ARG AUTOWARE_CARLA_SCENARIO_VERSION=29.3.11
COPY --chown=sandbox:sandbox workspace/ /sandbox/workspace/
RUN sed -i "s/@AUTOWARE_CARLA_SCENARIO_VERSION@/${AUTOWARE_CARLA_SCENARIO_VERSION}/" pyproject.toml AGENTS.md \
    && uv python install 3.12 && uv sync --python 3.12 \
    # typesafe-carla must import from its prebuilt client (no 15-50 min build).
    && uv run python -c "import typesafe_carla.carla as c; print('typesafe_carla ok')"

# Town10HD_Opt (CARLA 0.10): the framework clones its Autoware map from the
# HuggingFace dataset on first use. Do it now, at the commit the framework
# pins, so the offline sandbox resolves it from the cache.
ENV AUTOWARE_DATA_DIR=/sandbox/autoware_data
RUN git lfs install --skip-repo \
    && uv run python -c "import yaml, autoware_carla_scenario as a, pathlib; \
from autoware_carla_scenario.maps.resolver import resolve_map; \
src = yaml.safe_load((pathlib.Path(a.__file__).parent / 'examples/conf/map/town10hd_opt.yaml').read_text())['map']['source']; \
print(resolve_map(src).lanelet2_path)"

# Warm the uv cache and the Codon path with a throwaway scaffolded package, so
# that the agent's `scenario-new` + `uv pip install -e` + `scenario-check`
# work with UV_OFFLINE=1.
RUN uv run scenario-new warmup_pkg --scenario warmup -o /tmp/warm \
    && uv pip install -e /tmp/warm/warmup_pkg \
    && uv run scenario-check scenario='warmup/*' \
    && uv pip uninstall warmup_pkg && rm -rf /tmp/warm

# Warm the Scenario IR path (export_package -> offline editable install -> tests)
# with a throwaway document, so that `validate-ir` works with UV_OFFLINE=1.
COPY --chown=sandbox:sandbox irwarm.yaml /tmp/irwarm.yaml
RUN SCENARIO_MAP=town10hd_opt IR_PACKAGES_DIR=/tmp/irwarm UV_OFFLINE=1 \
       uv run python tools/validate_ir.py /tmp/irwarm.yaml \
    && uv pip uninstall irwarm-scenario && rm -rf /tmp/irwarm /tmp/irwarm.yaml

COPY --chown=sandbox:sandbox pi/ /sandbox/.pi/agent/

# The CARLA server runs on the host, reached as host.openshell.internal
# (policy rule `carla`). The skills' commands say plain `uv run scenario ...`,
# so the server host comes from the environment instead of the command line.
RUN sed -i 's/^  host: localhost$/  host: ${oc.env:CARLA_HOST,localhost}/' \
      .venv/lib/python3.12/site-packages/autoware_carla_scenario/examples/conf/server/localhost.yaml \
    && grep -q 'oc.env:CARLA_HOST' .venv/lib/python3.12/site-packages/autoware_carla_scenario/examples/conf/server/localhost.yaml

# Agent Skills shipped by the framework (pi discovers .agents/skills/), plus
# the two sandbox helpers on PATH.
RUN mkdir -p .agents && cp -r .venv/lib/python3.12/site-packages/autoware_carla_scenario/agent/skills .agents/skills \
    && mkdir -p bin \
    && printf '#!/bin/sh\nexec /sandbox/workspace/.venv/bin/python /sandbox/workspace/tools/lanelet_info.py "$@"\n' > bin/lanelet-info \
    && printf '#!/bin/sh\nexec /sandbox/workspace/.venv/bin/python /sandbox/workspace/tools/validate_scenario.py "$@"\n' > bin/validate-scenario \
    && printf '#!/bin/sh\nexec /sandbox/workspace/.venv/bin/python /sandbox/workspace/tools/carla_status.py "$@"\n' > bin/carla-status \
    && printf '#!/bin/sh\nexec /sandbox/workspace/.venv/bin/python /sandbox/workspace/tools/validate_ir.py "$@"\n' > bin/validate-ir \
    && printf '#!/bin/sh\nexec /sandbox/workspace/.venv/bin/python /sandbox/workspace/tools/ir_catalog.py "$@"\n' > bin/ir-catalog \
    && mkdir -p ir \
    && chmod +x bin/* && git config --global user.email sandbox@localhost && git config --global user.name sandbox \
    && git init -q && printf '.venv/\ndata/\n__pycache__/\n' > .gitignore && git add -A && git commit -qm "sandbox baseline"

# OpenShell hands the workload only PATH from the image ENV, and runs
# `sandbox exec` as a login shell with HOME=/sandbox/workspace: the runtime
# environment therefore lives in a file that .profile/.bashrc source.
RUN printf '%s\n' \
      'export UV_OFFLINE=1 UV_NO_SYNC=1 UV_LINK_MODE=copy' \
      'export UV_CACHE_DIR=/sandbox/.cache/uv UV_PYTHON_INSTALL_DIR=/usr/local/share/uv/python' \
      'export TYPESAFE_CARLA_PYCARLA_BUILD=0' \
      'export PI_CODING_AGENT_DIR=/sandbox/.pi/agent GIT_CONFIG_GLOBAL=/sandbox/.gitconfig' \
      'export NISHISHINJUKU_XODR_PATH=/sandbox/workspace/data/nishishinjuku_carla.xodr' \
      'export NISHISHINJUKU_LANELET2_PATH=/sandbox/workspace/data/nishishinjuku.osm' \
      'export AUTOWARE_DATA_DIR=/sandbox/autoware_data SCENARIO_MAP=town10hd_opt' \
      'export CARLA_HOST=host.openshell.internal TYPESAFE_CARLA_CARLA_REF=1.0' \
      'export FW=/sandbox/workspace/.venv/lib/python3.12/site-packages/autoware_carla_scenario' \
      'export PATH=/sandbox/workspace/bin:/sandbox/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin' \
      'cd /sandbox/workspace 2>/dev/null || true' \
      > /sandbox/sandbox.env \
    && echo '. /sandbox/sandbox.env' > /sandbox/workspace/.profile \
    && echo '. /sandbox/sandbox.env' > /sandbox/workspace/.bashrc \
    && echo '. /sandbox/sandbox.env' >> /sandbox/.bashrc \
    && printf '.venv/\ndata/\ndocs/\nir_packages/\noutputs/\nmultirun/\n__pycache__/\n.cache/\n.pi/\n.profile\n.bashrc\n' > .gitignore && git commit -qam "ignore env files" || true

ENV PATH=/sandbox/workspace/bin:/sandbox/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin \
    UV_OFFLINE=1 \
    PI_CODING_AGENT_DIR=/sandbox/.pi/agent \
    NISHISHINJUKU_XODR_PATH=/sandbox/workspace/data/nishishinjuku_carla.xodr \
    NISHISHINJUKU_LANELET2_PATH=/sandbox/workspace/data/nishishinjuku.osm
