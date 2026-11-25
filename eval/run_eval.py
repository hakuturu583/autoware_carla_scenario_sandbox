"""Run the scenario-writing tasks with pi + a local model inside fresh OpenShell sandboxes.

  python3 eval/run_eval.py [--tasks t1_reach_goal,t2_speed_limit] [--trials 1] [--timeout 1800]
                           [--thinking low] [--keep]

Per trial: create a sandbox from the image -> run `pi -p` with the task prompt
(JSON event stream saved) -> grade inside the sandbox (validate-scenario +
must_use + yaml_expect) -> download the package -> delete the sandbox.
Results: eval/results/<timestamp>/{summary.json, <task>-<n>/...}.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from tasks import AUTONOMY, AUTONOMY_JA, JA_TASKS, SKILL_TASKS, TASKS, TOWN10_TASKS  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERSION = os.environ.get("AUTOWARE_CARLA_SCENARIO_VERSION", "29.3.11")
IMAGE = os.environ.get("SANDBOX_IMAGE", f"autoware-carla-scenario-sandbox:{VERSION}")

GRADER = r'''
import json, pathlib, re, subprocess, sys, yaml
pkg, scen, must_use, expect = sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), json.loads(sys.argv[4])
r = {"package_exists": pathlib.Path(pkg, "pyproject.toml").is_file()}
v = subprocess.run(["validate-scenario", pkg], capture_output=True, text=True)
r["validate_pass"] = v.returncode == 0
r["validate_tail"] = v.stdout.strip().splitlines()[-12:]
mod = pathlib.Path(pkg, "src", pkg, scen + ".py")
src = mod.read_text() if mod.is_file() else ""
r["must_use_missing"] = [c for c in must_use if not re.search(r"\b" + c + r"\b", src)]
ymls = sorted(pathlib.Path(pkg, "src", pkg, "conf", "scenario", scen).glob("*.yaml"))
doc = yaml.safe_load(ymls[0].read_text()) if ymls else {}
bad = {}
for k, want in expect.items():
    cur = doc or {}
    for part in k.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    try:
        ok = cur is not None and float(cur) == float(want)
    except (TypeError, ValueError):
        ok = False
    if not ok:
        bad[k] = cur
r["yaml_mismatch"] = bad
r["success"] = r["validate_pass"] and not r["must_use_missing"] and not bad
results = sorted(pathlib.Path("outputs").glob("*/*/*_result.json"), key=lambda p: p.stat().st_mtime)
r["carla_runs"] = len(results)
if results:
    last = json.loads(results[-1].read_text())
    r["carla_last_passed"] = bool(last.get("passed"))
    r["carla_last_message"] = str(last.get("message"))[:200]
if len(sys.argv) > 5 and sys.argv[5] == "carla":
    r["success"] = r["success"] and r.get("carla_last_passed", False)
print(json.dumps(r))
'''


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def exec_in(name: str, script: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    return sh(["openshell", "sandbox", "exec", "--name", name, "--", "bash", "-lc", script], timeout=timeout)


def summarize_events(path: pathlib.Path) -> dict:
    """Count turns / tool calls / errors from pi's --mode json stream."""
    tools: dict[str, int] = {}
    turns = 0
    errors = 0
    out_tokens = 0
    scenario_runs = 0
    skills_read: set[str] = set()
    for line in path.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        if t == "turn_end":
            turns += 1
        elif t == "tool_execution_start":
            tools[ev.get("toolName", "?")] = tools.get(ev.get("toolName", "?"), 0) + 1
            a = json.dumps(ev.get("args") or {})
            if "scenario scenario=" in a and "scenario-" not in a.split("scenario scenario=")[0][-10:]:
                scenario_runs += 1
            for sk in re.findall(r"skills/([a-z-]+)/SKILL\.md", a):
                skills_read.add(sk)
        elif t == "tool_execution_end" and ev.get("isError"):
            errors += 1
        elif t == "message_end":
            usage = (ev.get("message") or {}).get("usage") or {}
            out_tokens += int(usage.get("output", 0) or 0)
    return {"turns": turns, "tool_calls": tools, "tool_errors": errors, "output_tokens": out_tokens,
            "scenario_run_cmds": scenario_runs, "skills_read": sorted(skills_read)}


def run_trial(task: dict, n: int, outdir: pathlib.Path, args) -> dict:
    name = f"ev-{task['id'][:2]}-{n}-{int(time.time()) % 100000}"  # <= 19 chars
    tdir = outdir / f"{task['id']}-{n}"
    tdir.mkdir(parents=True)
    print(f"[{task['id']} #{n}] creating sandbox {name}", flush=True)
    c = sh(["openshell", "sandbox", "create", "--name", name, "--from", IMAGE,
            "--policy", str(ROOT / "policy/sandbox-policy.yaml"), "--provider", "strata",
            "--no-auto-providers", "--no-tty", "--detach"])
    if c.returncode != 0:
        return {"task": task["id"], "trial": n, "error": "sandbox create failed: " + c.stderr[-500:]}
    try:
        if task.get("carla"):
            prompt = task["prompt"]
        elif task["id"].startswith("j"):
            prompt = task["prompt"] + "\n\n" + AUTONOMY_JA.format(pkg=task["pkg"])
        else:
            prompt = task["prompt"] + "\n\n" + AUTONOMY.format(pkg=task["pkg"])
        seed_env = (f"env PI_SAMPLING_SEED={args.seed_base + n} PI_SAMPLING_TEMPERATURE={args.temperature} "
                    if args.seed_base else "")
        pi = (f"{seed_env}pi --provider strata --model inkling-2-mini-sq-20 --thinking {shlex.quote(args.thinking)} "
              f"--mode json -p {shlex.quote(prompt)} > /sandbox/workspace/_eval/pi_events.jsonl 2> /sandbox/workspace/_eval/pi_stderr.txt")
        t0 = time.monotonic()
        try:
            p = exec_in(name, f"mkdir -p _eval; timeout {args.timeout} {pi}; echo exit=$?", timeout=args.timeout + 120)
            pi_exit = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else f"exec rc={p.returncode}"
        except subprocess.TimeoutExpired:
            pi_exit = "host timeout"
        wall = time.monotonic() - t0
        print(f"[{task['id']} #{n}] pi finished ({pi_exit}) in {wall:.0f}s; grading", flush=True)
        g = exec_in(name, "python - " + " ".join(shlex.quote(a) for a in [
            task["pkg"], task["scenario"], json.dumps(task["must_use"]), json.dumps(task["yaml_expect"]),
            "carla" if task.get("carla") else "-"])
            + " <<'PYEOF'\n" + GRADER + "\nPYEOF", timeout=600)
        try:
            grade = json.loads(g.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            grade = {"success": False, "grader_error": (g.stdout + g.stderr)[-1500:]}
        (tdir / "logs").mkdir()
        (tdir / "package").mkdir()
        sh(["openshell", "sandbox", "download", name, "/sandbox/workspace/_eval", str(tdir / "logs")])
        sh(["openshell", "sandbox", "download", name, f"/sandbox/workspace/{task['pkg']}", str(tdir / "package")])
        ev = next(tdir.joinpath("logs").rglob("pi_events.jsonl"), tdir / "missing")
        stats = summarize_events(ev) if ev.is_file() else {}
        res = {"task": task["id"], "trial": n, "pi_exit": pi_exit, "wall_s": round(wall), **stats, **grade}
        (tdir / "result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        print(f"[{task['id']} #{n}] success={res.get('success')} validate={res.get('validate_pass')} "
              f"missing={res.get('must_use_missing')} yaml={res.get('yaml_mismatch')} "
              f"turns={stats.get('turns')} tools={stats.get('tool_calls')} "
              f"carla_runs={res.get('carla_runs')} carla_last={res.get('carla_last_passed')} "
              f"skills={stats.get('skills_read')}", flush=True)
        return res
    finally:
        if not args.keep:
            sh(["openshell", "sandbox", "delete", name])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", choices=["nishishinjuku", "town10", "town10-ja", "skills"], default="town10")
    ap.add_argument("--tasks", default="")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=1800, help="seconds per pi run")
    ap.add_argument("--thinking", default="low")
    ap.add_argument("--seed-base", type=int, default=0,
                    help="sample with temperature + per-trial seed (0 = Strata's deterministic decoding)")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--keep", action="store_true", help="keep sandboxes for inspection")
    args = ap.parse_args()
    outdir = ROOT / "eval/results" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True)
    suite = {"town10": TOWN10_TASKS, "nishishinjuku": TASKS, "town10-ja": JA_TASKS,
             "skills": SKILL_TASKS}[args.suite]
    wanted = args.tasks.split(",") if args.tasks else [t["id"] for t in suite]
    results = [run_trial(t, n, outdir, args) for t in suite if t["id"] in wanted for n in range(1, args.trials + 1)]
    (outdir / "summary.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    ok = sum(1 for r in results if r.get("success"))
    print(f"\n{ok}/{len(results)} trials succeeded -> {outdir}/summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
