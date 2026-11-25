"""carla-status: is the host CARLA server reachable from this sandbox? Prints UP/DOWN and the map."""
import os
import sys

os.environ.setdefault("TYPESAFE_CARLA_CARLA_REF", "1.0")
host = os.environ.get("CARLA_HOST", "localhost")
try:
    import typesafe_carla.carla as carla

    client = carla.Client(host, 2000)
    client.set_timeout(10.0)
    print(f"UP {host}:2000 map={client.get_world().get_map().name} server={client.get_server_version()}")
except Exception as exc:  # noqa: BLE001
    print(f"DOWN {host}:2000 ({type(exc).__name__}: {str(exc)[:120]})")
    sys.exit(1)
