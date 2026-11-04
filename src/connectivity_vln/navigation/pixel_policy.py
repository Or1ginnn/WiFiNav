"""Provisional pixel-subgoal VLM baseline, without goal or reference access."""
import base64
import io
import json
import math
import time
import urllib.request

import habitat_sim
import numpy as np
from PIL import Image
from habitat.utils.geometry_utils import quaternion_rotate_vector

SYSTEM = """You navigate an indoor robot using its front camera and an instruction.
Follow the instruction in order; explore if the next doorway or landmark is out of view.
Images are chronological, with the CURRENT image last. You cannot see behind walls.
Choose one high-level tool. Return ONLY a single JSON object with a short reason and
an updated memory (max 600 characters) of observed progress, rooms and planned next step.
Tools:
1. {"tool":"waypoint","candidate_id":3,"reason":"...","memory":"..."}
Select one numbered visible floor candidate from the CURRENT image and candidate list.
Candidates are derived from current depth only, without goal or global map information.
They are NOT guaranteed collision-free: furniture and narrow doorways can block execution.
Choose a point towards the next doorway/landmark, not an object. The local controller
moves at most 1.5m before requesting another observation. Candidate IDs change each view.
2. {"tool":"look","degrees":60,"reason":"...","memory":"..."}
Rotate in place: positive = left, negative = right, multiples of 15, at most 90 degrees.
Use this to inspect unseen space; use a different view if no floor path is visible.
3. {"tool":"stop","reason":"...","memory":"..."}
Stop only when the instruction's destination is visually reached. There is no goal oracle.
A collision means the previous motion failed; inspect and choose a different reachable point.
Never invent a visual observation. Do not repeat a failed motion without new evidence.
"""


def validate_tool(text, candidates):
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    item = json.loads(value)
    if not isinstance(item, dict) or item.get("tool") not in {"waypoint", "look", "stop"}:
        raise ValueError("Expected a waypoint/look/stop object")
    if item["tool"] == "waypoint":
        value = item.get("candidate_id")
        if type(value) is not int or value not in {c["id"] for c in candidates}:
            raise ValueError("Choose an integer candidate_id from the current candidate list")
    if item["tool"] == "look":
        value = item.get("degrees")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 15 <= abs(value) <= 90 or abs(value / 15 - round(value / 15)) > 1e-6:
            raise ValueError("Look angle must be a nonzero multiple of 15 in [-90,90]")
    for key, limit in (("reason", 600), ("memory", 600)):
        if not isinstance(item.get(key, ""), str) or len(item.get(key, "")) > limit:
            raise ValueError(f"Invalid or oversized {key}")
    return item


class PixelPolicy:
    def __init__(self, model_config, settings):
        self.model = model_config
        self.settings = settings
        self.memory = ""
        self.history = []
        self.feedback = []
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def decide(self, instruction, frame, candidates, directory):
        content = []
        frames = self.history[-self.settings["max_history_images"]:] + [str(frame)]
        for i, name in enumerate(frames):
            content.append({"type": "text", "text": "CURRENT image:" if i == len(frames)-1 else "Previous image:"})
            content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(open(name, "rb").read()).decode()}})
        content.append({"type": "text", "text": json.dumps({
            "instruction": instruction, "memory": self.memory, "current_floor_candidates": candidates,
            "recent_controller_feedback": self.feedback[-6:],
        }, ensure_ascii=False)})
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
        for attempt in range(self.settings["max_parse_attempts"]):
            payload = {"model": self.model["served_model_name"], "messages": messages,
                       "temperature": 0, "max_tokens": self.settings["model_output_tokens"],
                       "chat_template_kwargs": {"enable_thinking": False}}
            # Exact request is retained in ignored runtime; frame paths are also indexed.
            (directory / f"request_{attempt}.json").write_text(json.dumps(payload) + "\n")
            request = urllib.request.Request(f'http://127.0.0.1:{self.model["port"]}/v1/chat/completions',
                        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            started = time.perf_counter()
            with self.opener.open(request, timeout=self.settings["request_timeout_seconds"]) as response:
                raw = json.load(response)
            raw["wall_seconds"] = time.perf_counter() - started
            (directory / f"response_{attempt}.json").write_text(json.dumps(raw, indent=2) + "\n")
            text = raw["choices"][0]["message"]["content"]
            try:
                if raw["choices"][0].get("finish_reason") != "stop":
                    raise ValueError("Model output was truncated or did not finish normally")
                choice = validate_tool(text, candidates)
            except (ValueError, TypeError) as error:
                (directory / f"parse_error_{attempt}.txt").write_text(str(error))
                messages += [{"role": "assistant", "content": text},
                             {"role": "user", "content": "Invalid tool JSON: " + str(error) + ". Return one valid tool object."}]
                continue
            self.memory = choice.get("memory", "")
            self.history.append(str(frame))
            self.history = self.history[-self.settings["max_history_images"]:]
            return choice, {"frames": frames, "attempts": attempt + 1,
                            "wall_seconds": raw["wall_seconds"], "usage": raw.get("usage")}
        raise RuntimeError("Model failed bounded tool parsing attempts")

    def observe_feedback(self, feedback):
        self.feedback.append(feedback)
        self.feedback = self.feedback[-6:]


def pixel_subgoal(env, depth, choice, settings):
    """Backproject measured depth; no pathfinder/map/goal queries are made here."""
    h, w = depth.shape[:2]
    col = int(round(choice["u"] * (w - 1)))
    row = int(round(choice["v"] * (h - 1)))
    distance = float(depth[row, col].item())
    if not math.isfinite(distance) or distance <= 0 or distance >= settings["depth_max_m"] - 1e-4:
        raise ValueError("Selected pixel has invalid or clipped depth")
    focal = w / (2 * math.tan(math.radians(settings["hfov_degrees"] / 2)))
    camera = np.array([(col + 0.5 - w / 2) * distance / focal,
                       -(row + 0.5 - h / 2) * distance / focal, -distance])
    state = env.sim.get_agent_state()
    sensor = state.sensor_states["depth"]
    point = np.asarray(sensor.position) + quaternion_rotate_vector(sensor.rotation, camera)
    # Visible floor must be near the current walking level. Stairs require a later adapter.
    if abs(float(point[1] - state.position[1])) > 0.40:
        raise ValueError("Selected pixel is not near the current floor height")
    delta = point - state.position
    delta[1] = 0
    norm = float(np.linalg.norm(delta))
    if norm < settings["forward_step_m"] / 2:
        raise ValueError("Subgoal too close for a forward action")
    if norm > settings["max_subgoal_distance_m"]:
        point = state.position + delta / norm * settings["max_subgoal_distance_m"]
    point[1] = state.position[1]
    return point.tolist(), {"pixel": [col, row], "measured_depth_m": distance,
                            "backprojected_point": (np.asarray(sensor.position) + quaternion_rotate_vector(sensor.rotation, camera)).tolist()}


def heading_error(env, target):
    state = env.sim.get_agent_state()
    forward = quaternion_rotate_vector(state.rotation, np.array([0.0, 0.0, -1.0]))
    delta = np.array(target) - state.position
    return math.degrees(math.atan2(forward[2] * delta[0] - forward[0] * delta[2],
                                  forward[0] * delta[0] + forward[2] * delta[2]))


def local_navmesh_waypoint(env, target):
    """Return the next navmesh point toward a VLM-selected local target.

    This query only receives the current pose and local target. It never sees the
    R2R task goal, reference path, shortest-path sensor, or evaluation metrics.
    """
    pathfinder = env.sim.pathfinder
    snapped = pathfinder.snap_point(np.asarray(target, dtype=np.float32))
    if not np.isfinite(snapped).all():
        raise ValueError("Local target cannot be snapped to the navigation mesh")
    query = habitat_sim.ShortestPath()
    query.requested_start = env.sim.get_agent_state().position
    query.requested_end = snapped
    if not pathfinder.find_path(query) or not math.isfinite(query.geodesic_distance):
        raise ValueError("No navigation-mesh path to the selected local target")
    position = env.sim.get_agent_state().position
    points = [np.asarray(point) for point in query.points]
    next_point = next(
        (point for point in points[1:] if np.linalg.norm((point - position)[[0, 2]]) > 0.12),
        snapped,
    )
    return next_point.tolist(), {
        "snapped_target": snapped.tolist(),
        "remaining_geodesic_m": float(query.geodesic_distance),
        "path_points": [point.tolist() for point in points],
    }


def floor_candidates(env, depth, settings, rgb, output):
    """Sample measured floor points and annotate RGB; no map/GT is queried."""
    from PIL import ImageDraw
    candidates = []
    for u in np.linspace(0.10, 0.90, 9):
        valid = []
        for v in np.linspace(0.95, 0.55, 17):
            try:
                target, projection = pixel_subgoal(env, depth, {"u":float(u),"v":float(v)}, settings)
            except ValueError:
                continue
            raw = projection["backprojected_point"]
            position = env.sim.get_agent_state().position
            distance = float(np.linalg.norm(np.array(raw)[[0,2]] - position[[0,2]]))
            if abs(raw[1]-position[1]) <= 0.20 and 0.5 <= distance <= 4.0:
                valid.append({"u":float(u),"v":float(v),"distance_m":distance})
        if valid:
            candidates.append(max(valid,key=lambda c:c["distance_m"]))
    image = Image.fromarray(rgb[..., :3]).copy()
    draw = ImageDraw.Draw(image)
    for i, candidate in enumerate(candidates):
        candidate["id"] = i
        x,y = round(candidate["u"]*(image.width-1)),round(candidate["v"]*(image.height-1))
        draw.ellipse((x-10,y-10,x+10,y+10),fill="yellow",outline="black",width=2)
        draw.text((x-3,y-5),str(i),fill="black")
    image.save(output)
    return candidates
