"""validate-ir: check a Scenario IR document (ScenarioDocument YAML) and build its package, offline.

  validate-ir <document.yaml>        # e.g. validate-ir ir/stop_behind.yaml

Steps (stops at the first failing one, prints PASS/FAIL per step):
  1. load      parse the YAML into a ScenarioDocument (unknown keys, wrong types)
  2. validate  the framework's validate_document (unknown action/condition types, missing
               fields, references to unknown entities, ...)
  3. compile   the framework's compile_document (the plan the runtime would build)
  4. lanelets  every lanelet id in the document exists in the map, and fixed spawn `s` values
               are inside their lanelet
  5. export    export_package -> /sandbox/workspace/ir_packages/<id>_scenario (no lock: offline)
  6. install   `uv pip install --offline -e` of that package (registers the scenario)
  7. pytest    the exported package's own tests

A passing document runs on CARLA with
`uv run scenario scenario=<id> map=<id>_map` (the package's own map group).
"""

from __future__ import annotations

import importlib.metadata
import os
import pathlib
import subprocess
import sys

OUT = pathlib.Path(os.environ.get("IR_PACKAGES_DIR", "/sandbox/workspace/ir_packages"))


def _head(step: str, what: str) -> None:
    print(f"\n=== [{step}] {what}", flush=True)


def _done(step: str, ok: bool) -> bool:
    print(f"=== [{step}] {'PASS' if ok else 'FAIL'}", flush=True)
    return ok


def _run(step: str, cmd: list[str], cwd: pathlib.Path | None = None) -> bool:
    _head(step, "$ " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = proc.stdout.strip().splitlines()
    if len(out) > 60:
        out = out[:25] + [f"... ({len(out) - 50} lines omitted) ..."] + out[-25:]
    print("\n".join(out))
    return _done(step, proc.returncode == 0)


def _lanelet_refs(node, path=""):
    """Yield (path, id) for every lanelet id in the document (spawns, goals, params)."""
    keys = ("lanelet_id", "lanelet_ids", "lanes", "goal_lanelet_ids")
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else str(k)
            if str(k) in keys or str(k).endswith("_lanelet_id"):
                for i in v if isinstance(v, list) else [v]:
                    if isinstance(i, int) and not isinstance(i, bool) and i != 0:
                        yield p, i
            else:
                yield from _lanelet_refs(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _lanelet_refs(v, f"{path}[{i}]")


def _check_lanelets(doc) -> bool:
    _head("lanelets", "every lanelet id exists in the map")
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import lanelet2
    import lanelet_info

    lmap, _ = lanelet_info._load()

    def length(i: int) -> float | None:
        try:
            return lanelet2.geometry.length2d(lmap.laneletLayer[int(i)])
        except Exception:
            return None

    ok = True
    for p, i in _lanelet_refs(doc.model_dump(mode="python", by_alias=True)):
        if length(i) is None:
            print(f"FAIL {p}: lanelet {i} does not exist in the map (use `lanelet-info list` / `lanelet-info ahead <id>`)")
            ok = False
        elif i in lanelet_info.NO_3D:
            print(f"FAIL {p}: lanelet {i} has no 3D model in CARLA (spawns fail); pick another")
            ok = False
    for e in doc.entities:
        sp = e.spawn
        if sp is None or sp.mode != "fixed" or not sp.lanelet_id:
            continue
        n = length(sp.lanelet_id)
        s = sp.s.value if sp.s is not None else 0.0
        if n is not None and s is not None and not (0.0 <= float(s) < n):
            print(f"FAIL entities[{e.id}].spawn.s={s} is outside lanelet {sp.lanelet_id} (length {n:.1f} m)")
            ok = False
    return _done("lanelets", ok)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    path = pathlib.Path(argv[0]).resolve()
    from autoware_carla_scenario.authoring import (
        compile_document,
        export_package,
        load_document,
        validate_document,
    )

    def result(ok: bool) -> int:
        print("\nRESULT:", "PASS - all offline checks passed" if ok else "FAIL - fix the first FAIL above and run again")
        return 0 if ok else 1

    _head("load", str(path))
    try:
        doc = load_document(path)
    except Exception as exc:  # pydantic ValidationError, YAML errors
        print(str(exc)[:3000])
        return result(_done("load", False))
    _done("load", True)

    _head("validate", "validate_document")
    report = validate_document(doc)
    for i in report.issues:
        print(f"{i.severity.upper()} {i.path}: {i.message}")
    if not _done("validate", report.ok):
        return result(False)

    _head("compile", "compile_document")
    try:
        compiled = compile_document(doc)
        print(f"ego + {len(compiled.npcs)} npc(s), {len(compiled.actions)} action(s), "
              f"{len(compiled.pass_conditions)} pass / {len(compiled.fail_conditions)} fail condition(s)")
        for w in compiled.warnings:
            print("WARNING", w)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}"[:3000])
        return result(_done("compile", False))
    _done("compile", True)

    if not _check_lanelets(doc):
        return result(False)

    _head("export", f"export_package -> {OUT}")
    os.environ.setdefault("SCENARIO_EXPORT_FRAMEWORK_VERSION", importlib.metadata.version("autoware-carla-scenario"))
    try:
        res = export_package(doc, OUT, lock=False, verify=False, run_tests=False, pin_uv_version=False, force=True)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}"[:3000])
        return result(_done("export", False))
    pkg = res.root
    print(f"package: {pkg}")
    _done("export", True)

    ok = _run("install", ["uv", "pip", "install", "--offline", "-q", "-e", str(pkg)])
    if ok and (pkg / "tests").is_dir():
        ok = _run("pytest", [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=pkg)
    if ok:
        print(f"\nRun it on CARLA: uv run scenario scenario={doc.id} map={doc.id}_map")
    return result(ok)


if __name__ == "__main__":
    raise SystemExit(main())
