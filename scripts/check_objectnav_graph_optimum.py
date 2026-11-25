"""Independent check using one scalar shortest-path problem per objective."""


def independent_cost(nodes, endpoints, edge_costs, start, goal):
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra

    pairs = np.asarray(endpoints, dtype=int)
    origins = np.concatenate([pairs[:, 0], pairs[:, 1]])
    destinations = np.concatenate([pairs[:, 1], pairs[:, 0]])
    costs = np.tile(np.asarray(edge_costs, dtype=np.int64), (2, 1))
    optima = []
    for column in range(costs.shape[1]):
        weights = costs[:, column]
        # Keep parallel edges eligible for the later objectives. Use only their
        # minimum current cost when assembling SciPy's scalar graph.
        order = np.lexsort((weights, destinations, origins))
        sorted_origins, sorted_destinations = origins[order], destinations[order]
        first = np.r_[True, (sorted_origins[1:] != sorted_origins[:-1]) | (sorted_destinations[1:] != sorted_destinations[:-1])]
        keep = order[first]
        graph = csr_matrix((weights[keep], (origins[keep], destinations[keep])), shape=(nodes, nodes))
        from_start = dijkstra(graph, indices=start, directed=True)
        optimum = from_start[goal]
        if not np.isfinite(optimum):
            raise ValueError("Independent solver cannot reach the frozen goal")
        optima.append(int(optimum))
        if column + 1 < costs.shape[1]:
            to_goal = dijkstra(graph.transpose().tocsr(), indices=goal, directed=True)
            tight = from_start[origins] + weights + to_goal[destinations] == optimum
            origins, destinations, costs = origins[tight], destinations[tight], costs[tight]
    return tuple(optima)
