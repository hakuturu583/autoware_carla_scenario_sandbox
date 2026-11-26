"""Print the Scenario IR building blocks the installed framework registers.

  ir-catalog                 # every action / condition / spawn constraint / binding, one line each
  ir-catalog <type_id> ...   # full field list of those types (name, kind, default, unit, options, help)

Generated from autoware_carla_scenario.authoring's registry, so it always
matches the installed version.
"""

from __future__ import annotations

import sys

from autoware_carla_scenario.authoring import action_specs, binding_specs, condition_specs, constraint_specs


def _groups():
    return [("action", list(action_specs())), ("condition", list(condition_specs())),
            ("constraint", list(constraint_specs())), ("binding", list(binding_specs()))]


def _first_line(text: str) -> str:
    return " ".join((text or "").split())[:110]


def _field(f, indent: str = "    ") -> list[str]:
    bits = [f"{f.name}: {f.kind}"]
    if f.default is not None:
        bits.append(f"default={f.default!r}")
    if f.unit:
        bits.append(f"unit={f.unit}")
    if not f.required:
        bits.append("optional")
    if f.options:
        bits.append("options=" + "|".join(str(o.value) for o in f.options))
    out = [indent + "  ".join(bits) + (f"  # {_first_line(f.help)}" if f.help else "")]
    for sub in f.item_fields:
        out += _field(sub, indent + "    ")
    return out


def main() -> int:
    wanted = set(sys.argv[1:])
    for group, specs in _groups():
        for s in specs:
            if wanted and s.type_id not in wanted:
                continue
            extra = ""
            if group == "condition":
                extra = f" kind={s.kind}" + (f" children={s.min_children}..{s.max_children}" if s.kind != "leaf" else "")
            if group == "action":
                extra = f" scope={s.scope} actors={','.join(s.actor_kinds)} phase={s.default_phase}"
            if group == "constraint":
                extra = f" kind={s.kind}"
            print(f"[{group}] {s.type_id}: {s.title}{extra}  -- {_first_line(getattr(s, 'description', ''))}")
            if wanted:
                for f in s.fields:
                    print("\n".join(_field(f)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
