# Scenario-authoring sandbox (autoware_carla_scenario @AUTOWARE_CARLA_SCENARIO_VERSION@)

You write CARLA test scenarios for Autoware with the `autoware_carla_scenario` framework.
You are in an isolated sandbox with **no internet**: do not try to download anything. Everything is installed.
Writing a scenario is done when `validate-scenario <package>` prints `RESULT: PASS`. A CARLA server may be
running on the host; check with `carla-status`. When it is up you may also run scenarios (see "Running in CARLA").

## Facts

- Working directory: `/sandbox/workspace`. Create packages here.
- Map: **Town10HD_Opt** (CARLA 0.10), selected with `map=town10hd_opt` (the validator does this for you).
  Positions are ALWAYS Lanelet2: `lanelet_id` + `s` (metres from the lanelet start).
- CARLA 0.10 vehicle blueprints: use `vehicle.lincoln.mkz` or `vehicle.mini.cooper` (there is NO `vehicle.toyota.prius`).
- The ego is driven by CARLA's TrafficManager autopilot (it keeps its lane, follows the car ahead and stops behind
  obstacles; at junctions it may turn).
- Framework source (read it to learn the API): `$FW` = `/sandbox/workspace/.venv/lib/python3.12/site-packages/autoware_carla_scenario`
  - built-in scenarios to copy patterns from: `$FW/examples/*.py`, their YAML: `$FW/examples/conf/scenario/<name>/*.yaml`, configs: `$FW/examples/configs.py`
  - conditions: `$FW/conditions/`, actions: `$FW/actions/`, public API list: `$FW/__init__.py` (`__all__`)
- Framework docs: `docs/<page>.md` in skills = `/sandbox/workspace/docs/<page>.md` (e.g. `docs/typecheck.md`, `docs/usage.md`).
- `<framework>/` in skills = `$FW/`. `uv run <cmd>` in skills works as written (offline venv).

## Skills (`.agents/skills/`, all six from the framework)

| Skill | Use it to |
|---|---|
| `write-scenario` | create a scenario end to end (stages 1-7) |
| `scenario-writing` (+ `references/`) | domain knowledge: patterns, code-generation rules, sweep constraints |
| `debug-concrete-scenario` | run a concrete scenario in CARLA, read the result, fix until it passes |
| `scenario-debugging` | domain knowledge for reading run outputs and failures |
| `review-scenario` | review a scenario's parameter design before adding a sweep |
| `scenario-review` | domain knowledge for that review (orthogonality, bindings) |

Load a skill by reading its `SKILL.md` (pi also accepts `/skill:<name>`). The skills ask you to confirm with
the user at each stage; when the user said to work autonomously, decide yourself and keep going.

## Running in CARLA (only when `carla-status` says UP)

- `uv run scenario scenario=<name>/<variant> map=town10hd_opt` runs one concrete scenario (the server host is
  preconfigured). Results: `outputs/<date>/<time>/` (`*_result.json`, `*.trajectory.jsonl`, the log).
- `uv run scenario --multirun scenario=<name>/<variant> map=town10hd_opt hydra/sweeper=lanelet_constraint` runs a sweep.
- `uv run scenario-expand scenario=<name>/<variant> map=town10hd_opt` previews a sweep without CARLA.

## Workflow (follow in order)

1. Scaffold: `scenario-new <package> --scenario <name>` (names: `^[a-z][a-z0-9_]*$`, package e.g. `stop_sign_pkg`).
   It creates `<package>/src/<package>/{__init__.py,configs.py,<name>.py,conf/scenario/<name>/default.yaml}` and `tests/`.
   The template is a working "reach goal" scenario: modify it, do not start from an empty file.
2. Read the closest built-in example in `$FW/examples/` (e.g. `temporary_stop.py`, `cut_in.py`, `traffic_light_compliance.py`).
3. Pick real lanelets with `lanelet-info` (never invent IDs):
   - `lanelet-info list --min-length 60` long road lanelets usable for spawning
   - `lanelet-info ahead <id> --meters 150` the lanelets the ego reaches driving on
   - `lanelet-info route <from> <to>`, `lanelet-info show <id> ...` (length, successors, lane-change neighbours, traffic lights)
4. Edit three files: `configs.py` (dataclass), `<name>.py` (scenario class), `conf/scenario/<name>/default.yaml`.
5. Run `validate-scenario <package>`. Fix the FIRST failure it reports, run it again. Repeat until `RESULT: PASS`.

## Rules the static check (Codon) enforces

- Declare every attribute you set on `self` at class level: `_config: MyConfig`, `_npc_pose: Lanelet2Pose`.
- No list comprehensions / generator expressions / `x if c else y` where the value must be a base type.
  Build lists explicitly: `conds: list[BaseCondition] = []` then `conds.append(...)`.
- Annotate a variable that can hold different condition classes: `cond: BaseCondition`.
- Do not read the base class's private attributes (e.g. the spawn pose): store what you need yourself in
  `__init__` (`self._ego_spawn = spawn_pose`, declared `_ego_spawn: Lanelet2Pose` at class level).
- No `getattr(self, name)` with a variable name: write each check out explicitly.
- Import everything from `autoware_carla_scenario` (top level), CARLA as `import typesafe_carla.carla as carla`.
- Config dataclass fields need defaults; validate values in `__post_init__` (raise `ValueError`).
- Every key under `scenario:` in the YAML must be a field of the config dataclass (typos fail the check).

## Scenario rules

- `setup()` calls `self._setup_ego_spawn()` first, then `register_init(...)`, `register_pass_condition(...)`, `register_fail_condition(...)`.
- Always register a `TimeoutCondition(seconds, label="scenario_timeout")` as a fail condition. `is_done()` returns `False`.
- The scenario PASSES as soon as ANY pass condition is true. To require several things, use one `AndCondition([...])`
  and wrap one-time events in `StickyCondition(...)`.
- Give every condition/action a `label="..."`.
- NPCs: copy the pattern from `$FW/examples/cut_in.py` (around `npc = VehicleEntity(`): `snap_to_carla_road(Lanelet2Pose(...), world,
  ground_projection=self._ground_projection)` -> `VehicleEntity(VehicleEntityConfig(role_name=..., spawn_location=SpawnTransform(...)))`
  -> `npc.spawn(world)` -> `self.register_entity(npc)`; then drive it with `register_pre_tick(SetSpeedAction(...))` etc.

## Minimal YAML shape (`conf/scenario/<name>/default.yaml`)

```yaml
# @package _global_
scenario:
  name: <name>
  goal_lanelet_ids: [7066, 1764]
  timeout_seconds: 30.0
ego:
  initial_speed_kmh: 5.0
  spawn_lanelet_id: 1281
  spawn_s: 10.0
```
