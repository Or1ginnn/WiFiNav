"""Exact lexicographic shortest paths on a finite graph."""
import heapq


def lexicographic_route(adjacency, edge_costs, start, goal):
    """Dijkstra with nonnegative additive (weak, severe, length) edge costs."""
    costs = {start: (0, 0, 0)}
    previous = {}
    queue = [(costs[start], start)]
    while queue:
        cost, node = heapq.heappop(queue)
        if cost != costs[node]:
            continue
        if node == goal:
            path = []
            while node != start:
                origin, edge = previous[node]
                path.append((origin, node, edge))
                node = origin
            return path[::-1], cost
        for other, edge in adjacency[node]:
            weak, severe, length = edge_costs[edge]
            new = (cost[0] + weak, cost[1] + severe, cost[2] + length)
            if other not in costs or new < costs[other]:
                costs[other] = new
                previous[other] = (node, edge)
                heapq.heappush(queue, (new, other))
    raise ValueError("No route in the navigation graph")


def optimal_route(adjacency, edge_costs, start, goal, max_length, remaining_length):
    """Minimize (weak distance, severe distance, length), with an integer length cap.

    An adjacency item is (next node, edge index). Edge costs are nonnegative
    integer triples. remaining_length is a lower bound on length to the goal.
    """
    labels = [[] for _ in adjacency]
    costs = [(0, 0, 0)]
    parent = [(start, None, None)]
    active = [True]
    labels[start].append(0)
    queue = [((0, 0, 0), 0)]
    while queue:
        cost, state = heapq.heappop(queue)
        if not active[state]:
            continue
        node = parent[state][0]
        if node == goal:
            path = []
            while parent[state][1] is not None:
                node, previous, edge = parent[state]
                path.append((parent[previous][0], node, edge))
                state = previous
            return path[::-1], cost
        for other, edge in adjacency[node]:
            weak, severe, length = edge_costs[edge]
            new_cost = (cost[0] + weak, cost[1] + severe, cost[2] + length)
            if new_cost[2] + remaining_length[other] > max_length:
                continue
            # Retain a costlier prefix when it is shorter and can still fit a
            # continuation that would exceed the budget for the cheaper prefix.
            frontier = labels[other]
            if any(costs[i][2] <= new_cost[2] and costs[i] <= new_cost for i in frontier):
                continue
            survivors = []
            for i in frontier:
                if new_cost[2] <= costs[i][2] and new_cost <= costs[i]:
                    active[i] = False
                else:
                    survivors.append(i)
            index = len(costs)
            labels[other] = survivors + [index]
            costs.append(new_cost)
            parent.append((other, state, edge))
            active.append(True)
            heapq.heappush(queue, (new_cost, index))
    raise ValueError("No path fits the graph length budget")
