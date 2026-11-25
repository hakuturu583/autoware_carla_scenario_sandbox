"""lanelet-info: look up real Lanelet2 IDs of the sandbox map (SCENARIO_MAP, default town10hd_opt), offline.

A scenario must name lanelets that exist (ego.spawn_lanelet_id, goal lanelets,
NPC lanelets) and an `s` that is inside the lanelet's length. This tool answers
those questions from the map file, with the framework's own CARLA-free loader.

  lanelet-info show 242 460            # length, neighbours, successors, turn direction
  lanelet-info route 242 265           # shortest drivable lanelet sequence from A to B
  lanelet-info ahead 242 --meters 150  # lanelets reached driving straight on for N m
  lanelet-info list --min-length 60 --limit 20   # long road lanelets (good spawn candidates)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import lanelet2
import lanelet2.routing
import lanelet2.traffic_rules
from autoware_carla_scenario.sweeper.map_loader import load_lanelet2_map

MAP_NAME = os.environ.get("SCENARIO_MAP", "town10hd_opt")


def _map_conf() -> dict:
    import pathlib

    import autoware_carla_scenario
    import yaml

    conf = pathlib.Path(autoware_carla_scenario.__file__).parent / f"examples/conf/map/{MAP_NAME}.yaml"
    return yaml.safe_load(conf.read_text())["map"]


def _map_files() -> tuple[str, str | None]:
    """(lanelet2 .osm, xodr or None) of the selected map. A git-sourced map
    (town10hd_opt) resolves from the cache baked into the image, offline."""
    conf = _map_conf()
    if conf.get("source"):
        from autoware_carla_scenario.maps.resolver import resolve_map

        resolved = resolve_map(conf["source"])
        return str(resolved.lanelet2_path), None
    return (os.environ.get("NISHISHINJUKU_LANELET2_PATH", "data/nishishinjuku.osm"),
            os.environ.get("NISHISHINJUKU_XODR_PATH", "data/nishishinjuku_carla.xodr"))


NO_3D = set(_map_conf().get("no_3d_model_lanelet_ids") or [])


def _load():
    lanelet2_path, xodr_path = _map_files()
    lmap = load_lanelet2_map(lanelet2_path, xodr_path)
    rules = lanelet2.traffic_rules.create(
        lanelet2.traffic_rules.Locations.Germany, lanelet2.traffic_rules.Participants.Vehicle
    )
    return lmap, lanelet2.routing.RoutingGraph(lmap, rules)


def _is_road(ll) -> bool:
    return ll.attributes["subtype"] == "road" if "subtype" in ll.attributes else False


def _info(ll, graph) -> dict:
    attrs = {k: ll.attributes[k] for k in ("subtype", "turn_direction", "speed_limit") if k in ll.attributes}
    left, right = graph.left(ll), graph.right(ll)
    regs = sorted({type(r).__name__ for r in ll.regulatoryElements})
    return {
        "id": ll.id,
        "length_m": round(lanelet2.geometry.length2d(ll), 2),
        **attrs,
        "left_lane_change_to": left.id if left else None,
        "right_lane_change_to": right.id if right else None,
        "successors": [s.id for s in graph.following(ll)],
        "predecessors": [p.id for p in graph.previous(ll)],
        "regulatory_elements": regs,
        "usable_for_spawn": ll.id not in NO_3D,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lanelet-info", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("show"); p.add_argument("ids", type=int, nargs="+")
    p = sub.add_parser("route"); p.add_argument("start", type=int); p.add_argument("goal", type=int)
    p = sub.add_parser("ahead"); p.add_argument("start", type=int); p.add_argument("--meters", type=float, default=100.0)
    p = sub.add_parser("list"); p.add_argument("--min-length", type=float, default=50.0); p.add_argument("--limit", type=int, default=20)
    args = ap.parse_args(argv)

    lmap, graph = _load()

    def get(i: int):
        try:
            return lmap.laneletLayer[i]
        except Exception:
            print(json.dumps({"error": f"lanelet {i} does not exist in this map"}))
            sys.exit(1)

    if args.cmd == "show":
        print(json.dumps([_info(get(i), graph) for i in args.ids], indent=1))
    elif args.cmd == "route":
        route = graph.getRoute(get(args.start), get(args.goal))
        if route is None:
            print(json.dumps({"error": f"no drivable route from {args.start} to {args.goal}"}))
            return 1
        path = route.shortestPath()
        ids = [ll.id for ll in path]
        total = sum(lanelet2.geometry.length2d(ll) for ll in path)
        print(json.dumps({"lanelets": ids, "length_m": round(total, 1),
                          "note": "consecutive ids that are not successors are lane changes"}))
    elif args.cmd == "ahead":
        ll, out, dist = get(args.start), [], 0.0
        while ll is not None and dist < args.meters:
            length = lanelet2.geometry.length2d(ll)
            out.append({"id": ll.id, "length_m": round(length, 1), "at_m": round(dist, 1),
                        "turn_direction": ll.attributes["turn_direction"] if "turn_direction" in ll.attributes else None})
            dist += length
            nxt = graph.following(ll)
            straight = [n for n in nxt if "turn_direction" not in n.attributes or n.attributes["turn_direction"] == "straight"]
            ll = (straight or nxt or [None])[0]
        print(json.dumps(out, indent=1))
    elif args.cmd == "list":
        rows = [(lanelet2.geometry.length2d(ll), ll) for ll in lmap.laneletLayer if _is_road(ll) and ll.id not in NO_3D]
        rows = sorted((r for r in rows if r[0] >= args.min_length), key=lambda r: -r[0])[: args.limit]
        print(json.dumps([{"id": ll.id, "length_m": round(n, 1), "successors": [s.id for s in graph.following(ll)]}
                          for n, ll in rows], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
