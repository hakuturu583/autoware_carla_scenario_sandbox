"""Record one real pi + Inkling run in a fresh sandbox, with host-side timestamps.

  python3 eval/record_demo.py t3_parked_npc out_dir/

Writes out_dir/events.jsonl: one {"t": seconds_since_start, "ev": <pi json event>}
per line, plus out_dir/validate.txt (a final `validate-scenario` run, also
timestamped into the stream as a synthetic event so the video can show it).
"""

from __future__ import annotations

import json
import pathlib
import shlex
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from run_eval import IMAGE, ROOT  # noqa: E402
from tasks import AUTONOMY, TASKS, TOWN10_TASKS  # noqa: E402


def main() -> int:
    task = next(t for t in TASKS + TOWN10_TASKS if t["id"] == sys.argv[1])
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    name = f"demo-{task['id'][:2]}-{int(time.time()) % 10000}"
    subprocess.run(["openshell", "sandbox", "create", "--name", name, "--from", IMAGE,
                    "--policy", str(ROOT / "policy/sandbox-policy.yaml"), "--provider", "strata",
                    "--no-auto-providers", "--no-tty", "--detach"], check=True, capture_output=True)
    prompt = task["prompt"] + "\n\n" + AUTONOMY.format(pkg=task["pkg"])
    pi = (f"pi --provider strata --model inkling-2-mini-sq-20 --thinking low --mode json "
          f"-p {shlex.quote(prompt)} 2>/dev/null")
    events = (out / "events.jsonl").open("w")
    t0 = time.monotonic()
    events.write(json.dumps({"t": 0.0, "ev": {"type": "demo_prompt", "text": prompt, "sandbox": name}}) + "\n")
    try:
        proc = subprocess.Popen(["openshell", "sandbox", "exec", "--name", name, "--", "bash", "-lc", pi],
                                stdout=subprocess.PIPE, text=True, bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.write(json.dumps({"t": round(time.monotonic() - t0, 3), "ev": ev}) + "\n")
        proc.wait()
        v = subprocess.run(["openshell", "sandbox", "exec", "--name", name, "--", "bash", "-lc",
                            f"validate-scenario {task['pkg']} 2>&1 | grep -E '^===|RESULT|FAIL|\\[ok\\]'"],
                           capture_output=True, text=True)
        (out / "validate.txt").write_text(v.stdout)
        events.write(json.dumps({"t": round(time.monotonic() - t0, 3),
                                 "ev": {"type": "demo_validate", "text": v.stdout}}) + "\n")
        (out / "package").mkdir(exist_ok=True)
        subprocess.run(["openshell", "sandbox", "download", name, f"/sandbox/workspace/{task['pkg']}",
                        str(out / "package")], capture_output=True)
    finally:
        events.close()
        subprocess.run(["openshell", "sandbox", "delete", name], capture_output=True)
    print(f"recorded {out}/events.jsonl ({time.monotonic() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
