import itertools
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from connectivity_vln.benchmark.constrained_route import lexicographic_route, optimal_route
from connectivity_vln.benchmark.single_floor import distances
from solve_objectnav_rssi_graph import edge_on_floor


def graphs(n, edges):
    adjacency = [[] for _ in range(n)]
    length_graph = [[] for _ in range(n)]
    costs = []
    for index, (a, b, cost) in enumerate(edges):
        adjacency[a].append((b, index))
        adjacency[b].append((a, index))
        length_graph[a].append((b, cost[2]))
        length_graph[b].append((a, cost[2]))
        costs.append(cost)
    return adjacency, costs, distances(length_graph, n - 1)


class OptimalRouteTests(unittest.TestCase):
    def test_floor_guard_rejects_flat_waypoints_over_a_raised_surface(self):
        def snap(point):
            x, y, z = point
            return x, .5 if .09 < x < .20 else y, z

        self.assertFalse(edge_on_floor([[0, 0, 0], [.30, 0, 0]], snap, 0, .28))
        self.assertTrue(edge_on_floor([[0, 0, 0], [.30, 0, 0]], lambda point: point, 0, .28))

    def test_severe_weak_exposure_takes_priority_over_weak_distance(self):
        # Each edge stores (severe weak distance, all weak distance, length).
        edges = [(0, 1, (0, 2, 3)), (1, 2, (0, 0, 1)), (0, 2, (1, 1, 3))]
        adjacency, costs, _ = graphs(3, edges)
        path, cost = lexicographic_route(adjacency, costs, 0, 2)
        self.assertEqual([destination for _, destination, _ in path], [1, 2])
        self.assertEqual(cost, (0, 2, 4))

    def test_unbounded_prefers_clean_detour_outside_old_cap(self):
        edges = [(0, 2, (1, 0, 10)), (0, 1, (0, 0, 7)), (1, 2, (0, 0, 7))]
        adjacency, costs, bounds = graphs(3, edges)
        self.assertEqual(optimal_route(adjacency, costs, 0, 2, 12, bounds)[1], (1, 0, 10))
        self.assertEqual(lexicographic_route(adjacency, costs, 0, 2)[1], (0, 0, 14))

    def test_retain_two_prefixes_at_same_node_when_cheaper_one_is_longer(self):
        edges = [(0, 1, (0, 0, 8)), (0, 2, (1, 0, 2)), (2, 1, (1, 1, 3)),
                 (1, 3, (1, 0, 4))]
        adjacency, costs, bounds = graphs(4, edges)
        path, cost = optimal_route(adjacency, costs, 0, 3, 10, bounds)
        self.assertEqual([edge[1] for edge in path], [2, 1, 3])
        self.assertEqual(cost, (3, 1, 9))

    def test_matches_exhaustive_simple_path_search(self):
        rng = random.Random(61)
        for _ in range(50):
            edges = []
            for a, b in itertools.combinations(range(6), 2):
                if rng.random() < .55:
                    length = rng.randint(1, 10)
                    weak = rng.randint(0, length)
                    edges.append((a, b, (weak, rng.randint(0, weak), length)))
            adjacency, costs, bounds = graphs(6, edges)
            cap = rng.randint(4, 30)

            def brute(node, seen, cost, limit):
                if node == 5:
                    yield cost
                    return
                for neighbor, edge in adjacency[node]:
                    new = tuple(a + b for a, b in zip(cost, costs[edge]))
                    if neighbor not in seen and new[2] <= limit:
                        yield from brute(neighbor, seen | {neighbor}, new, limit)

            expected = min(brute(0, {0}, (0, 0, 0), cap), default=None)
            if expected is None:
                with self.assertRaises(ValueError):
                    optimal_route(adjacency, costs, 0, 5, cap, bounds)
            else:
                path, actual = optimal_route(adjacency, costs, 0, 5, cap, bounds)
                self.assertEqual(actual, expected)
                self.assertEqual(tuple(sum(costs[edge][i] for _, _, edge in path) for i in range(3)), actual)
            unbounded = min(brute(0, {0}, (0, 0, 0), float("inf")), default=None)
            if unbounded is None:
                with self.assertRaises(ValueError):
                    lexicographic_route(adjacency, costs, 0, 5)
            else:
                self.assertEqual(lexicographic_route(adjacency, costs, 0, 5)[1], unbounded)
