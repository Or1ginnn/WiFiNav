"""Shared geometry/risk graph planner; no task goals or reference paths."""
import heapq
import math
import time

import numpy as np


def shortest_path(adjacency, start, goal, risk, weight):
    """Dijkstra with nonnegative length * (1 + lambda * mean endpoint risk)."""
    if not math.isfinite(weight) or weight < 0:
        raise ValueError("Risk weight must be finite and nonnegative")
    costs = {start: 0.0}
    previous = {}
    queue = [(0.0, start)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != costs[node]:
            continue
        if node == goal:
            path = [node]
            while node != start:
                node = previous[node]
                path.append(node)
            return path[::-1], cost
        for other, length in adjacency[node]:
            # lambda=0 does not access a radio field, including risk callbacks.
            penalty = (risk(node) + risk(other)) / 2 if weight else 0.0
            if not math.isfinite(penalty) or penalty < 0 or not math.isfinite(length) or length < 0:
                raise ValueError("Graph lengths and risks must be finite and nonnegative")
            candidate = cost + length * (1 + weight * penalty)
            if candidate < costs.get(other, math.inf):
                costs[other] = candidate
                previous[other] = node
                heapq.heappush(queue, (candidate, other))
    raise ValueError("No shared-grid route to selected local target")


class NavmeshRiskPlanner:
    """Known geometry, single floor grid shared by NoSignal and StaticMap.

    Each edge is checked by navmesh try_step in both directions. Disconnected
    locations never receive a shortest-path or risk-based fallback. The floor
    limitation is explicit and is not a staircase implementation.
    """

    def __init__(self, pathfinder, floor_y, *, resolution=0.25, floor_tolerance=0.20):
        self.pathfinder = pathfinder
        self.resolution = resolution
        self.floor_y = floor_y
        self.floor_tolerance = floor_tolerance
        self.points = []
        self.cells = {}
        self.edges = []
        low, high = pathfinder.get_bounds()
        started = time.perf_counter()
        for ix, x in enumerate(np.arange(low[0], high[0] + resolution / 2, resolution)):
            for iz, z in enumerate(np.arange(low[2], high[2] + resolution / 2, resolution)):
                requested = np.array([x, floor_y, z], dtype=np.float32)
                snapped = pathfinder.snap_point(requested)
                if (not np.isfinite(snapped).all() or abs(float(snapped[1])-floor_y) > floor_tolerance
                        or np.linalg.norm((snapped-requested)[[0, 2]]) > 0.03):
                    continue
                self.cells[ix, iz] = len(self.points)
                self.points.append(np.asarray(snapped))
                self.edges.append([])
        for (ix, iz), node in self.cells.items():
            for dx, dz in [(0, 1), (1, -1), (1, 0), (1, 1)]:
                other = self.cells.get((ix+dx, iz+dz))
                if other is not None and self._clear(self.points[node], self.points[other]):
                    length = float(np.linalg.norm(self.points[node]-self.points[other]))
                    self.edges[node].append((other, length))
                    self.edges[other].append((node, length))
        self.positions = np.asarray(self.points)
        if not self.points:
            raise ValueError("No grid nodes on this floor")
        self.build_seconds = time.perf_counter()-started
        self.risks = {}

    def _clear(self, start, end):
        if abs(float(start[1]-end[1])) > 0.20:
            return False
        # Test the midpoint as well as both endpoints; no corner cutting.
        middle = (start+end)/2
        for a, b in [(start, middle), (middle, end), (end, middle), (middle, start)]:
            reached = self.pathfinder.try_step(a, b)
            if not np.isfinite(reached).all() or np.linalg.norm(reached-b) > 0.025:
                return False
        return True

    def _attach(self, point):
        distances = np.linalg.norm(self.positions-point, axis=1)
        nodes = np.flatnonzero(distances <= self.resolution*2)
        return [(int(n), float(distances[n])) for n in nodes if self._clear(point, self.points[n])]

    def discrete_action(self, position, forward, waypoint, *, step_m, turn_degrees):
        """Choose a realizable heading, not just an ideal graph edge.

        Geometry only: a complete forward action must avoid clipping, stay on
        this floor, and retain graph access. At most 45 degrees departure from
        the requested path tangent is allowed. Never extend a step across an
        unsupported stair simply because its ideal waypoint is on the boundary.
        """
        position = np.asarray(position, dtype=np.float32)
        forward = np.asarray(forward, dtype=np.float64)
        forward[1] = 0
        forward /= np.linalg.norm(forward)
        delta = np.asarray(waypoint)-position
        desired = math.degrees(math.atan2(forward[2]*delta[0]-forward[0]*delta[2],
                                         forward[0]*delta[0]+forward[2]*delta[2]))
        options = []
        rejected = {"clipping": 0, "floor": 0, "attachment": 0}
        for k in range(-round(180/turn_degrees), round(180/turn_degrees)+1):
            angle = k*turn_degrees
            error = abs((desired-angle+180) % 360-180)
            if error > 45:
                continue
            rad = math.radians(angle)
            direction = np.array([math.cos(rad)*forward[0]+math.sin(rad)*forward[2], 0.,
                                  -math.sin(rad)*forward[0]+math.cos(rad)*forward[2]])
            endpoint = position+step_m*direction
            reached = np.asarray(self.pathfinder.try_step(position, endpoint))
            if not np.isfinite(reached).all() or np.linalg.norm((reached-endpoint)[[0, 2]]) > .001:
                rejected["clipping"] += 1
                continue
            if abs(float(reached[1])-self.floor_y) > self.floor_tolerance+1e-5:
                rejected["floor"] += 1
                continue
            if not self._attach(reached):
                rejected["attachment"] += 1
                continue
            options.append((error, abs(k), k, reached))
        if not options:
            raise ValueError("No safe discrete forward heading on shared floor grid: " + str(rejected))
        error, _, k, reached = min(options, key=lambda x: x[:3])
        action = "move_forward" if k == 0 else ("turn_left" if k > 0 else "turn_right")
        return action, {"desired_heading_degrees": desired,
                        "selected_heading_offset_degrees": k*turn_degrees,
                        "heading_error_degrees": error, "predicted_forward_position": reached.tolist(),
                        "rejected_headings": rejected, "clipping_tolerance_m": .001}

    @staticmethod
    def signal_risk(field, point):
        # 0 at/above weak threshold, 1 at/below outage. Oracle reads static
        # latent truth, never the sample-index-dependent measurement noise.
        rssi = field.query(point, 0)["rssi_truth_dbm"]
        config = field.config
        return min(1.0, max(0.0, (config["weak_threshold_dbm"]-rssi) /
                            (config["weak_threshold_dbm"]-config["outage_threshold_dbm"])))

    def plan(self, start, target, *, weight=0.0, field=None):
        stamp = time.perf_counter()
        start = np.asarray(start, dtype=np.float32)
        target = self.pathfinder.snap_point(np.asarray(target, dtype=np.float32))
        if not np.isfinite(target).all():
            raise ValueError("Local target cannot be snapped")
        if weight and field is None:
            raise ValueError("StaticMap requires a field")
        n = len(self.points)
        # Only two new adjacency lists are created; existing graph is immutable.
        start_edges, target_edges = self._attach(start), self._attach(target)
        if not start_edges or not target_edges:
            raise ValueError("Local endpoint cannot attach to shared floor grid")
        extra = {n: start_edges, n+1: target_edges}
        attachments = {}
        for endpoint, edges in extra.items():
            for node, length in edges:
                attachments.setdefault(node, []).append((endpoint, length))
        class Adjacency:
            def __getitem__(_, node):
                return extra[node] if node >= n else self.edges[node] + attachments.get(node, [])
        points = self.points + [start, target]
        # Keep endpoint-to-endpoint direct edge only for <=one grid diagonal,
        # so risk integration is never skipped across a long free-space chord.
        direct = float(np.linalg.norm(start-target))
        if direct <= self.resolution*math.sqrt(2) and self._clear(start, target):
            extra[n].append((n+1, direct)); extra[n+1].append((n, direct))
        def risk(node):
            if node >= n:
                return self.signal_risk(field, points[node])
            key = (field, node)
            if key not in self.risks:
                self.risks[key] = self.signal_risk(field, points[node])
            return self.risks[key]
        route, objective = shortest_path(Adjacency(), n, n+1, risk, weight)
        path = [points[node].tolist() for node in route]
        length = sum(float(np.linalg.norm(np.asarray(a)-b)) for a, b in zip(path, path[1:]))
        return path, {"planner": "navmesh_grid_dijkstra_v0", "lambda": weight,
                      "resolution_m": self.resolution, "grid_nodes": n,
                      "grid_build_seconds": self.build_seconds, "plan_seconds": time.perf_counter()-stamp,
                      "snapped_target": target.tolist(), "path_points": path,
                      "path_length_m": length, "weighted_objective": objective}
