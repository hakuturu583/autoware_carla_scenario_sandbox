"""Scenario-writing tasks for the local-LLM evaluation.

Each task names the package and scenario so the grader can find them, and
lists `must_use`: framework classes the solution has to use somewhere in the
scenario module (a cheap semantic check on top of validate-scenario), and
`yaml_expect`: YAML values the solution has to set.
"""

AUTONOMY = (
    "Work autonomously: do not ask me questions, make reasonable choices yourself. "
    "Read AGENTS.md first. You are done only when `validate-scenario {pkg}` prints `RESULT: PASS`."
)

TASKS = [
    {
        "id": "t1_reach_goal",
        "pkg": "route_pkg",
        "scenario": "straight_route",
        "prompt": (
            "Create a scenario package `route_pkg` with a scenario `straight_route`: the ego spawns on "
            "lanelet 242 at s=5 m with an initial speed of 10 km/h and must drive straight through the "
            "junction ahead onto lanelet 265. It fails if that takes more than 40 seconds."
        ),
        "must_use": ["TimeoutCondition", "EntityLanePositionCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 242, "ego.spawn_s": 5.0, "ego.initial_speed_kmh": 10.0},
    },
    {
        "id": "t2_speed_limit",
        "pkg": "speed_pkg",
        "scenario": "speed_cap",
        "prompt": (
            "Create a scenario package `speed_pkg` with a scenario `speed_cap`: the ego spawns on lanelet 242 "
            "at s=5 m and must reach lanelet 265. The scenario FAILS if the ego's speed ever exceeds a "
            "configurable limit `max_speed_kmh` (default 40.0 km/h), or after a 60 second timeout. "
            "Use the framework's SpeedCondition for the speed check (read its constructor first)."
        ),
        "must_use": ["SpeedCondition", "TimeoutCondition"],
        "yaml_expect": {"scenario.max_speed_kmh": 40.0},
    },
    {
        "id": "t3_parked_npc",
        "pkg": "obstacle_pkg",
        "scenario": "parked_car",
        "prompt": (
            "Create a scenario package `obstacle_pkg` with a scenario `parked_car`: the ego spawns on lanelet "
            "249 at s=10 m. A stationary NPC vehicle (vehicle.toyota.prius) is parked in the ego's lane on the "
            "same lanelet, `npc_gap_m` metres (default 40.0) ahead of the ego spawn. The ego must not collide "
            "with anything (fail condition, use CollisionCondition) and the scenario passes when the ego has "
            "come to a standstill (StandstillCondition) behind the NPC. Add a 60 second timeout fail "
            "condition. Follow the NPC spawn pattern of $FW/examples/cut_in.py."
        ),
        "must_use": ["CollisionCondition", "StandstillCondition", "VehicleEntity", "TimeoutCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 249, "scenario.npc_gap_m": 40.0},
    },
    {
        "id": "t4_cut_in",
        "pkg": "cutin_pkg",
        "scenario": "right_cut_in",
        "prompt": (
            "Create a scenario package `cutin_pkg` with a scenario `right_cut_in`: the ego spawns on lanelet 231 "
            "at s=20 m with an initial speed of 30 km/h. An NPC vehicle (vehicle.toyota.prius) spawns on the lane "
            "to the ego's right, lanelet `npc_lanelet_id` (default 232), at `npc_s` (default 35.0 m), and is held "
            "at `npc_speed_kmh` (default 35.0 km/h) with SetSpeedAction. After `cut_in_after_seconds` (default 3.0) "
            "the NPC changes lane to the LEFT into the ego's lane (LaneChangeAction triggered by an "
            "ElapsedTimeCondition). The scenario passes once the NPC is on lanelet 231, fails on any ego "
            "collision (CollisionCondition) or after a 40 second timeout. Base it on $FW/examples/cut_in.py "
            "but keep it simple: fixed positions from the config, no gap solving."
        ),
        "must_use": ["VehicleEntity", "LaneChangeAction", "ElapsedTimeCondition", "SetSpeedAction",
                     "CollisionCondition", "TimeoutCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 231, "scenario.npc_lanelet_id": 232,
                        "scenario.cut_in_after_seconds": 3.0, "scenario.npc_s": 35.0},
    },
]

# --- Town10HD_Opt (CARLA 0.10): runnable on the host CARLA server ---------
# Lanelets 1281 (103.6 m) and 1172 (98.9 m, the lane to 1281's right) are a
# straight two-lane stretch with no junction, so the TrafficManager-driven ego
# behaves predictably. CARLA 0.10 has no vehicle.toyota.prius.
TOWN10_TASKS = [
    {
        "id": "w1_parked_car",
        "pkg": "t10_parked_pkg",
        "scenario": "parked_car",
        "prompt": (
            "Create a scenario package `t10_parked_pkg` with a scenario `parked_car` for the Town10HD_Opt map: "
            "the ego spawns on lanelet 1281 at s=5 m with an initial speed of 20 km/h. A stationary NPC vehicle "
            "(vehicle.lincoln.mkz) is parked in the ego's lane on the same lanelet, `npc_gap_m` metres "
            "(default 45.0) ahead of the ego spawn. The scenario passes when the ego has come to a standstill "
            "for 2 seconds (StandstillCondition) behind the NPC, fails on any ego collision (CollisionCondition) "
            "or after a 40 second timeout. Follow the NPC spawn pattern of $FW/examples/cut_in.py."
        ),
        "must_use": ["CollisionCondition", "StandstillCondition", "VehicleEntity", "TimeoutCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 1281, "scenario.npc_gap_m": 45.0},
    },
    {
        "id": "w2_cut_in",
        "pkg": "t10_cutin_pkg",
        "scenario": "left_cut_in",
        "prompt": (
            "Create a scenario package `t10_cutin_pkg` with a scenario `left_cut_in` for the Town10HD_Opt map: "
            "the ego spawns on lanelet 1172 at s=5 m with an initial speed of 20 km/h. An NPC vehicle "
            "(vehicle.lincoln.mkz) spawns on the lane to the ego's LEFT, lanelet `npc_lanelet_id` (default 1281), "
            "at `npc_s` (default 20.0 m), and is held at `npc_speed_kmh` (default 30.0 km/h) with SetSpeedAction. "
            "After `cut_in_after_seconds` (default 3.0) the NPC changes lane to the RIGHT into the ego's lane "
            "(LaneChangeAction triggered by an ElapsedTimeCondition). The scenario passes once the NPC is on "
            "lanelet 1172, fails on any ego collision (CollisionCondition) or after a 30 second timeout. Base it "
            "on $FW/examples/cut_in.py but keep it simple: fixed positions from the config, no gap solving."
        ),
        "must_use": ["VehicleEntity", "LaneChangeAction", "ElapsedTimeCondition", "SetSpeedAction",
                     "CollisionCondition", "TimeoutCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 1172, "scenario.npc_lanelet_id": 1281,
                        "scenario.cut_in_after_seconds": 3.0, "scenario.npc_s": 20.0},
    },
    {
        "id": "w3_speed_cap",
        "pkg": "t10_speed_pkg",
        "scenario": "speed_cap",
        "prompt": (
            "Create a scenario package `t10_speed_pkg` with a scenario `speed_cap` for the Town10HD_Opt map: "
            "the ego spawns on lanelet 1281 at s=5 m and must reach lanelet 1764 (straight on, through the "
            "junction ahead). The scenario FAILS if the ego's speed ever exceeds a configurable limit "
            "`max_speed_kmh` (default 50.0 km/h), or after a 40 second timeout. Use SpeedCondition for the "
            "speed check (read its constructor first: mind its units)."
        ),
        "must_use": ["SpeedCondition", "TimeoutCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 1281, "scenario.max_speed_kmh": 50.0},
    },
]

# --- Japanese instructions --------------------------------------------------
AUTONOMY_JA = (
    "私に質問せず、自分で判断して最後まで進めてください。最初に AGENTS.md を読んでください。"
    "`validate-scenario {pkg}` が `RESULT: PASS` を出したら完了です。"
)

JA_TASKS = [
    {
        "id": "j1_parked_car",
        "pkg": "t10_parked_pkg",
        "scenario": "parked_car",
        "prompt": (
            "Town10HD_Opt マップ用のシナリオパッケージ `t10_parked_pkg` を作り、シナリオ名は `parked_car` に"
            "してください。自車（ego）は lanelet 1281 の s=5 m に初速 20 km/h で出現します。自車と同じ車線・同じ "
            "lanelet 上、自車の出現位置から `npc_gap_m` メートル（既定値 45.0）前方に、停車した NPC 車両"
            "（vehicle.lincoln.mkz）を置きます。自車が NPC の手前で 2 秒間停止したら合格"
            "（StandstillCondition）、自車が何かに衝突したら不合格（CollisionCondition）、40 秒で"
            "タイムアウトしたら不合格です。NPC の出し方は $FW/examples/cut_in.py に倣ってください。"
        ),
        "must_use": ["CollisionCondition", "StandstillCondition", "VehicleEntity", "TimeoutCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 1281, "scenario.npc_gap_m": 45.0},
    },
    {
        "id": "j2_cut_in",
        "pkg": "t10_cutin_pkg",
        "scenario": "left_cut_in",
        "prompt": (
            "Town10HD_Opt マップ用のシナリオパッケージ `t10_cutin_pkg` を作り、シナリオ名は `left_cut_in` に"
            "してください。自車は lanelet 1172 の s=5 m に初速 20 km/h で出現します。NPC 車両"
            "（vehicle.lincoln.mkz）は自車の左隣の車線、lanelet `npc_lanelet_id`（既定値 1281）の `npc_s`"
            "（既定値 20.0 m）に出現し、SetSpeedAction で `npc_speed_kmh`（既定値 30.0 km/h）に保ちます。"
            "`cut_in_after_seconds`（既定値 3.0）秒後に NPC は右へ車線変更して自車の車線に割り込みます"
            "（ElapsedTimeCondition をきっかけにした LaneChangeAction）。NPC が lanelet 1172 に入ったら合格、"
            "自車の衝突（CollisionCondition）か 30 秒のタイムアウトで不合格です。$FW/examples/cut_in.py を"
            "参考にしつつ、ギャップ計算はせず設定値の固定位置を使う簡単な形にしてください。"
        ),
        "must_use": ["VehicleEntity", "LaneChangeAction", "ElapsedTimeCondition", "SetSpeedAction",
                     "CollisionCondition", "TimeoutCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 1172, "scenario.npc_lanelet_id": 1281,
                        "scenario.cut_in_after_seconds": 3.0, "scenario.npc_s": 20.0},
    },
    {
        "id": "j3_speed_cap",
        "pkg": "t10_speed_pkg",
        "scenario": "speed_cap",
        "prompt": (
            "Town10HD_Opt マップ用のシナリオパッケージ `t10_speed_pkg` を作り、シナリオ名は `speed_cap` に"
            "してください。自車は lanelet 1281 の s=5 m に出現し、前方の交差点を直進して lanelet 1764 に"
            "到達しなければなりません。自車の速度が設定可能な上限 `max_speed_kmh`（既定値 50.0 km/h）を一度でも"
            "超えたら不合格、40 秒でタイムアウトしても不合格です。速度の判定には SpeedCondition を使って"
            "ください（先にコンストラクタを読み、単位に注意すること）。"
        ),
        "must_use": ["SpeedCondition", "TimeoutCondition"],
        "yaml_expect": {"ego.spawn_lanelet_id": 1281, "scenario.max_speed_kmh": 50.0},
    },
]

# --- Skill-driven closed loop: write -> run in CARLA -> debug ----------------
# Needs CARLA reachable from the sandbox (scripts/carla-up.sh, CARLA_RENDER=0
# next to Strata). Graded on validate-scenario AND the CARLA verdict of the
# agent's own last run (outputs/**/_result.json).
SKILL_TASKS = [
    {
        "id": "s1_ja_skill_loop",
        "lang": "ja",
        "carla": True,
        "pkg": "stop_pkg",
        "scenario": "stop_behind",
        "prompt": (
            "/skill:write-scenario Town10HD_Opt で、自車が前方に停まっている車の手前できちんと止まれるかを"
            "確かめるシナリオを作りたいです。パッケージ名は `stop_pkg`、シナリオ名は `stop_behind`。自車は "
            "lanelet 1281 の s=5 m から 20 km/h で出発し、40 m 先に停車車両（vehicle.lincoln.mkz）を置いて"
            "ください。衝突したら不合格です。\n\n"
            "このスキルの Stage 1〜4 まで進めてください。Stage 4 では debug-concrete-scenario スキルに従って "
            "CARLA で実際に `uv run scenario scenario=stop_behind/default map=town10hd_opt` を実行し、"
            "PASSED になるまで修正を繰り返してください。Stage 5 以降（スイープ）は不要です。"
            "私への確認は不要で、自分で判断して進めてください。"
        ),
        "must_use": ["CollisionCondition", "VehicleEntity"],
        "yaml_expect": {"ego.spawn_lanelet_id": 1281},
    },
    {
        "id": "s2_en_skill_loop",
        "lang": "en",
        "carla": True,
        "pkg": "stop_pkg",
        "scenario": "stop_behind",
        "prompt": (
            "/skill:write-scenario On Town10HD_Opt I want a scenario that checks the ego stops properly behind a "
            "car standing in its lane. Package `stop_pkg`, scenario `stop_behind`. The ego starts on lanelet 1281 "
            "at s=5 m at 20 km/h; put a stopped vehicle (vehicle.lincoln.mkz) 40 m ahead. A collision fails it.\n\n"
            "Go through Stages 1-4 of the skill. In Stage 4 follow the debug-concrete-scenario skill: actually run "
            "`uv run scenario scenario=stop_behind/default map=town10hd_opt` in CARLA and fix until it PASSES. "
            "Skip Stage 5 onwards (sweeps). Do not ask me to confirm anything; decide yourself."
        ),
        "must_use": ["CollisionCondition", "VehicleEntity"],
        "yaml_expect": {"ego.spawn_lanelet_id": 1281},
    },
]

# --- Scenario IR (declarative) versions of w1-w3 -----------------------------
# Same scenarios, written as a ScenarioDocument YAML instead of a Python package.
# Graded by `validate-ir`, the condition/action types used, a few values, and a
# CARLA run of the exported package done by the grader (not by the agent).
AUTONOMY_IR = (
    "Work autonomously: do not ask me questions, make reasonable choices yourself. Read AGENTS.md first "
    "(section \"Scenario IR\"). Do not write Python and do not run scenario-new. You are done only when "
    "`validate-ir {doc}` prints `RESULT: PASS`."
)

IR_TASKS = [
    {
        "id": "i1_parked_car",
        "doc": "ir/ir_parked_car.yaml",
        "prompt": (
            "Write a Scenario IR document `ir/ir_parked_car.yaml` with id `ir_parked_car` for the Town10HD_Opt map: "
            "the ego spawns on lanelet 1281 at s=5 m with an initial speed of 20 km/h, goal lanelet 1764. A "
            "stationary NPC vehicle (vehicle.lincoln.mkz) is parked in the ego's lane on the same lanelet, 45 m "
            "ahead of the ego spawn. The scenario passes when the ego has come to a standstill for 2 seconds behind "
            "the NPC, fails on any ego collision or after a 40 second timeout."
        ),
        "must_types": ["standstill", "collision", "timeout"],
        "expect": {"ego.spawn.lanelet_id": 1281, "ego.spawn.s": 5.0, "npc.spawn.lanelet_id": 1281, "npc.spawn.s": 50.0},
    },
    {
        "id": "i2_cut_in",
        "doc": "ir/ir_left_cut_in.yaml",
        "prompt": (
            "Write a Scenario IR document `ir/ir_left_cut_in.yaml` with id `ir_left_cut_in` for the Town10HD_Opt "
            "map: the ego spawns on lanelet 1172 at s=5 m with an initial speed of 20 km/h; its goal is lanelet 1172 "
            "at s=90 m. An NPC vehicle (vehicle.lincoln.mkz) spawns on the lane to the ego's LEFT, lanelet 1281, at "
            "s=20 m, and is held at 30 km/h (set_speed). 3 seconds after the start (elapsed_time trigger) the NPC "
            "changes lane to the RIGHT into the ego's lane. The scenario passes once the NPC is on lanelet 1172, "
            "fails on any ego collision or after a 30 second timeout."
        ),
        "must_types": ["set_speed", "lane_change", "elapsed_time", "entity_lane_position", "collision", "timeout"],
        "expect": {"ego.spawn.lanelet_id": 1172, "npc.spawn.lanelet_id": 1281, "npc.spawn.s": 20.0},
    },
    {
        "id": "i3_speed_cap",
        "doc": "ir/ir_speed_cap.yaml",
        "prompt": (
            "Write a Scenario IR document `ir/ir_speed_cap.yaml` with id `ir_speed_cap` for the Town10HD_Opt map: "
            "the ego spawns on lanelet 1281 at s=5 m and must reach lanelet 1764 (straight on, through the junction "
            "ahead); the scenario passes when the ego is on lanelet 1764. It FAILS if the ego's speed ever exceeds "
            "50 km/h, or after a 40 second timeout. Check the units of the speed condition with ir-catalog."
        ),
        "must_types": ["speed", "timeout"],
        "expect": {"ego.spawn.lanelet_id": 1281, "speed.value_mps": 13.89},
    },
]
