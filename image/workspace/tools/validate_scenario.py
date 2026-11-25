"""validate-scenario: every offline check a scenario package must pass, in one command.

  validate-scenario <package_dir>            # e.g. validate-scenario stop_sign_pkg

Steps (stops at the first failing one, prints PASS/FAIL per step):
  1. install    `uv pip install -e <package_dir>` (offline; registers the entry point)
  2. static     `scenario-check scenario='<name>/*' map=$SCENARIO_MAP` for every conf/scenario/<name>/ (Codon type check
                of the class with the YAML's values: type errors, unknown config keys, bad values)
  3. lanelets   every *lanelet_id / *lanelet_ids value under `ego:` and `scenario:` in the YAML
                exists in the map, is usable for spawning, and every spawn `s` is inside the lanelet
  4. pytest     the package's own tests (tests/test_typecheck.py from scenario-new)

No CARLA server is involved; a passing package is ready to be run on one with
`uv run scenario scenario=<name>/<variant>`.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import yaml


def _run(step: str, cmd: list[str], cwd: pathlib.Path | None = None) -> bool:
    print(f"\n=== [{step}] $ {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = proc.stdout.strip().splitlines()
    # keep the output short for a small-context model: head + tail
    if len(out) > 60:
        out = out[:25] + [f"... ({len(out) - 50} lines omitted) ..."] + out[-25:]
    print("\n".join(out))
    print(f"=== [{step}] {'PASS' if proc.returncode == 0 else 'FAIL'} (exit {proc.returncode})", flush=True)
    return proc.returncode == 0


def _lanelet_values(node, path=""):
    """Yield (yaml_path, key, value) for every key ending in lanelet_id(s)."""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else str(k)
            if str(k).endswith(("lanelet_id", "lanelet_ids")) and not isinstance(v, (dict, str)):
                yield p, str(k), v
            else:
                yield from _lanelet_values(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _lanelet_values(v, f"{path}[{i}]")


def _check_lanelets(yaml_files: list[pathlib.Path]) -> bool:
    print("\n=== [lanelets] checking lanelet ids in", ", ".join(str(f) for f in yaml_files), flush=True)
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import lanelet2  # noqa: F401
    import lanelet_info

    lmap, _ = lanelet_info._load()
    ok = True

    def length(i: int) -> float | None:
        try:
            return lanelet2.geometry.length2d(lmap.laneletLayer[int(i)])
        except Exception:
            return None

    for f in yaml_files:
        doc = yaml.safe_load(f.read_text()) or {}
        for section in ("ego", "scenario"):
            for p, key, v in _lanelet_values(doc.get(section, {}), section):
                for i in v if isinstance(v, list) else [v]:
                    n = length(i)
                    if n is None:
                        print(f"FAIL {f.name}: {p}: lanelet {i} does not exist in the map "
                              f"(use `lanelet-info list` / `lanelet-info ahead <id>`)")
                        ok = False
                    elif int(i) in lanelet_info.NO_3D:
                        print(f"FAIL {f.name}: {p}: lanelet {i} has no 3D model in CARLA (spawns fail); pick another")
                        ok = False
        ego = doc.get("ego", {}) or {}
        if "spawn_lanelet_id" in ego and "spawn_s" in ego:
            n = length(ego["spawn_lanelet_id"])
            if n is not None and not (0.0 <= float(ego["spawn_s"]) < n):
                print(f"FAIL {f.name}: ego.spawn_s={ego['spawn_s']} is outside lanelet "
                      f"{ego['spawn_lanelet_id']} (length {n:.1f} m)")
                ok = False
    print(f"=== [lanelets] {'PASS' if ok else 'FAIL'}", flush=True)
    return ok


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    pkg = pathlib.Path(argv[0]).resolve()
    if not (pkg / "pyproject.toml").is_file():
        print(f"FAIL: {pkg} has no pyproject.toml (create the package with `scenario-new`)")
        return 1
    conf_dirs = sorted(p for p in pkg.glob("src/*/conf/scenario/*") if p.is_dir())
    if not conf_dirs:
        print(f"FAIL: no src/<package>/conf/scenario/<name>/ directory in {pkg}")
        return 1

    steps_ok = _run("install", ["uv", "pip", "install", "--offline", "-q", "-e", str(pkg)])
    for d in conf_dirs:
        if not steps_ok:
            break
        steps_ok = _run("static", ["scenario-check", f"scenario={d.name}/*",
                                    f"map={os.environ.get('SCENARIO_MAP', 'town10hd_opt')}"])
    if steps_ok:
        steps_ok = _check_lanelets(sorted(f for d in conf_dirs for f in d.glob("*.yaml")))
    if steps_ok and (pkg / "tests").is_dir():
        steps_ok = _run("pytest", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=pkg)

    print("\nRESULT:", "PASS - all offline checks passed" if steps_ok else "FAIL - fix the first FAIL above and run again")
    return 0 if steps_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
