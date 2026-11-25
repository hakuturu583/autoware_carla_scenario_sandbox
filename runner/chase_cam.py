"""Attach a chase camera to the scenario's ego and save its frames (JPEG, named by sim time)."""
import os
import sys
import time

os.environ.setdefault("TYPESAFE_CARLA_CARLA_REF", "1.0")
import cv2
import numpy as np
import typesafe_carla.carla as carla

OUT = sys.argv[1]
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 300.0
os.makedirs(OUT, exist_ok=True)
client = carla.Client("localhost", 2000)
client.set_timeout(30.0)
world = client.get_world()

ego = None
deadline = time.time() + DURATION
while ego is None and time.time() < deadline:
    for actor in world.get_actors():
        if actor.type_id.startswith("vehicle.") and actor.attributes.get("role_name") in ("ego", "Ego", "hero"):
            ego = actor
            break
    time.sleep(0.5)
if ego is None:
    sys.exit("no ego appeared")
print(f"ego {ego.id}", flush=True)

bp = world.get_blueprint_library().find("sensor.camera.rgb")
for key, value in (("image_size_x", "1280"), ("image_size_y", "720"), ("fov", "90"), ("sensor_tick", "0.1")):
    bp.set_attribute(key, value)
camera = world.spawn_actor(
    bp, carla.Transform(carla.Location(x=-7.0, z=3.2), carla.Rotation(pitch=-12.0)), attach_to=ego
).as_sensor()


errors = []


def save(data):
    try:
        _save(data)
    except Exception as e:  # noqa: BLE001 - a callback must not die silently
        if len(errors) < 3:
            errors.append(repr(e))
            print("callback error:", repr(e), flush=True)


def _save(data):
    image = data.as_image() if isinstance(data, carla.SensorData) else data
    frame = np.frombuffer(bytes(image.raw_data), dtype=np.uint8).reshape(image.height, image.width, 4)[:, :, :3]
    cv2.imwrite(os.path.join(OUT, f"{image.timestamp:010.3f}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])


camera.listen(save)
try:
    ego_id = ego.id
    while time.time() < deadline:
        time.sleep(2.0)
        if not any(a.id == ego_id for a in world.get_actors()):
            break
finally:
    camera.stop()
    camera.destroy()
print(f"frames: {len(os.listdir(OUT))}", flush=True)
