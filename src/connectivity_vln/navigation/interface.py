"""Bounded navigation interface helpers, independent of simulator and goal data."""
import json
import math


def parse_object(text):
    if not isinstance(text, str):
        raise ValueError("Expected a JSON string")
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("Unclosed JSON fence")
        value = "\n".join(lines[1:-1])
    item = json.loads(value)
    if not isinstance(item, dict):
        raise ValueError("Expected a JSON object")
    return item


def validate_tool(text, candidates, *, version="v0", allow_stop=True):
    item = parse_object(text)
    tool = item.get("tool")
    if tool not in ("waypoint", "look", "stop"):
        raise ValueError("Expected a waypoint/look/stop object")
    if tool == "stop" and not allow_stop:
        raise ValueError("STOP was not confirmed; choose waypoint or look")
    if tool == "waypoint":
        value = item.get("candidate_id")
        if type(value) is not int or value not in {c["id"] for c in candidates}:
            raise ValueError("Choose an integer candidate_id from the current candidate list")
    if tool == "look":
        value = item.get("degrees")
        if (type(value) not in (int, float) or not 15 <= abs(value) <= 90
                or abs(value / 15 - round(value / 15)) > 1e-6):
            raise ValueError("Look angle must be a nonzero multiple of 15 in [-90,90]")
    for key in ("reason", "memory"):
        value = item.get(key, "")
        if version == "v0":
            if not isinstance(value, str) or len(value) > 600:
                raise ValueError(f"Invalid or oversized {key}")
        else:
            # Full original output is retained in the request/response log.
            item[key] = value[:600] if isinstance(value, str) else ""
    return item


def stop_review(text):
    item = parse_object(text)
    verdict = item.get("verdict")
    if verdict not in ("confirm", "reject", "uncertain"):
        raise ValueError("Expected confirm, reject or uncertain")
    evidence = item.get("evidence")
    if not isinstance(evidence, str) or (verdict != "uncertain" and not evidence.strip()):
        raise ValueError("Expected visual evidence for a decisive verdict")
    return {"verdict": verdict, "evidence": evidence[:600]}


class ProgressGuard:
    """Credit new camera headings at a fixed location without resetting strikes."""

    def __init__(self, pose, turn_degrees):
        self.anchor = pose["position"]
        self.views = [pose["rotation_xyzw"]]
        self.min_view_angle = math.radians(turn_degrees * 0.8)
        self.stalled = 0

    def update(self, pose, feedback):
        position = pose["position"]
        rotation = pose["rotation_xyzw"]
        if math.hypot(position[0]-self.anchor[0], position[2]-self.anchor[2]) >= 0.25:
            self.anchor = position
            self.views = [rotation]
            self.stalled = 0
            return "translation"
        if feedback["tool"] == "look" and feedback["executed_actions"] and not feedback["collision"]:
            # q and -q denote the same orientation.
            distances = [2 * math.acos(min(1.0, abs(sum(a*b for a, b in zip(rotation, seen)))))
                         for seen in self.views]
            if all(distance >= self.min_view_angle for distance in distances):
                self.views.append(rotation)
                return "new_view"
        self.stalled += 1
        return "stalled"
