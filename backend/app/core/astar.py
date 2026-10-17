import heapq
import itertools
from collections import namedtuple

from .heuristics import make_heuristic

Result = namedtuple("Result", "nodes edges distance start goal")


def _as_list(x):
    return [x] if isinstance(x, str) else list(x)


def astar(graph, starts, goals, accessible_only=False):
    """Shortest walking route from any of `starts` to any of `goals` (node ids; a single id also works).

    A place with several entrances (the mess) is simply several start/goal nodes: the nearest one wins.
    Returns Result(nodes, edges, distance_m, start_used, goal_used), or None when there is no route.
    Restricted edges are never used; with accessible_only=True, stairs are skipped too.
    Worst case O(E log V); the heuristic usually prunes most of the graph. Nodes are re-opened when a
    cheaper path is found, so the answer is optimal for any safe heuristic.
    """
    starts, goals = _as_list(starts), _as_list(goals)
    for n in starts + goals:
        if n not in graph.nodes:
            raise KeyError(n)
    goalset = set(goals)
    for s in starts:
        if s in goalset:
            return Result([s], [], 0.0, s, s)

    h = make_heuristic(graph, goals)
    tie = itertools.count()  # breaks ties so the heap never compares ids
    heap = [(h(s), next(tie), s) for s in starts]
    heapq.heapify(heap)
    g = {s: 0.0 for s in starts}
    came_from = {}  # node -> (previous node, edge id)

    while heap:
        f, _, cur = heapq.heappop(heap)
        if f > g[cur] + h(cur) + 1e-9:
            continue  # an outdated heap entry
        if cur in goalset:
            nodes, edges, node = [cur], [], cur
            while node in came_from:
                node, eid = came_from[node]
                nodes.append(node)
                edges.append(eid)
            nodes.reverse()
            edges.reverse()
            return Result(nodes, edges, g[cur], nodes[0], cur)
        for nbr, weight, eid in graph.adj[cur]:
            edge = graph.edges[eid]
            if edge["type"] == "restricted" or (accessible_only and not edge["accessible"]):
                continue
            new_g = g[cur] + weight
            if new_g < g.get(nbr, float("inf")) - 1e-12:
                g[nbr] = new_g
                came_from[nbr] = (cur, eid)
                heapq.heappush(heap, (new_g + h(nbr), next(tie), nbr))
    return None


def walk_times(graph, starts, walk_speed, accessible_only=False):
    """One Dijkstra from `starts` to every node: {node id: (route cost, walking seconds)}. Used for the "2 min walk"
    labels, so asking for 130 places costs one search instead of 130 (and does not fill the route cache)."""
    starts = _as_list(starts)
    tie = itertools.count()
    best = {s: 0.0 for s in starts}
    secs = {s: 0.0 for s in starts}
    heap = [(0.0, next(tie), s) for s in starts]
    while heap:
        d, _, cur = heapq.heappop(heap)
        if d > best[cur] + 1e-9:
            continue
        for nbr, weight, eid in graph.adj[cur]:
            edge = graph.edges[eid]
            if edge["type"] == "restricted" or (accessible_only and not edge["accessible"]):
                continue
            nd = d + weight
            if nd < best.get(nbr, float("inf")) - 1e-12:
                best[nbr] = nd
                secs[nbr] = secs[cur] + edge["length"] / walk_speed + edge.get("extra_s", 0.0)
                heapq.heappush(heap, (nd, next(tie), nbr))
    return {n: (best[n], secs[n]) for n in best}
