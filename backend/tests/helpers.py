import heapq


def dijkstra(graph, start, goal):
    """Plain Dijkstra (no heuristic), used to cross-check A*. Skips restricted edges like A* does."""
    dist, heap = {start: 0.0}, [(0.0, start)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w, eid in graph.adj[u]:
            if graph.edges[eid]["type"] == "restricted":
                continue
            if d + w < dist.get(v, float("inf")):
                dist[v] = d + w
                heapq.heappush(heap, (d + w, v))
    return dist.get(goal)
