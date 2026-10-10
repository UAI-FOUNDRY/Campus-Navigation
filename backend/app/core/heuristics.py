from .geo import haversine


def make_heuristic(graph, goal_ids):
    """Heuristic for A*: scaled straight-line metres to the NEAREST goal.

    Safe (never overestimates) because graph.scale is computed from the real graph. Indoor nodes have no
    GPS position, so they, and any search that has an indoor goal, use 0 (which is still safe).
    """
    goals = [graph.nodes[g] for g in goal_ids]
    if graph.scale <= 0 or any(g["lat"] is None for g in goals):
        return lambda node_id: 0.0
    points = [(g["lat"], g["lng"]) for g in goals]
    scale, cache = graph.scale, {}

    def h(node_id):
        v = cache.get(node_id)
        if v is None:
            n = graph.nodes[node_id]
            if n["lat"] is None:
                v = 0.0
            else:
                v = scale * min(haversine(n["lat"], n["lng"], la, lo) for la, lo in points)
            cache[node_id] = v
        return v

    return h
