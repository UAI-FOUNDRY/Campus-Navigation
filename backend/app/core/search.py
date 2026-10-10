import difflib
import re

try:  # rapidfuzz is faster and smarter, but the search still works without it
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def _fuzzy(a, b):
    if fuzz is not None:
        return fuzz.WRatio(a, b)
    return 100 * difflib.SequenceMatcher(None, a, b).ratio()


class PlaceIndex:
    """Search over room names and aliases. O(R) per query, fine for a few hundred rooms."""

    def __init__(self, rooms):
        self.entries = []
        for r in rooms:
            terms = {norm(r["name"])} | {norm(a) for a in r.get("aliases", [])}
            terms.discard("")
            self.entries.append((r, sorted(terms)))

    def search(self, query, limit=8):
        q = norm(query)
        if not q:
            return sorted((r for r, _ in self.entries), key=lambda r: r["name"].lower())[:limit]
        qc = q.replace(" ", "")
        scored = []
        for room, terms in self.entries:
            best = 0
            for t in terms:
                tc = t.replace(" ", "")
                if q == t or qc == tc:
                    s = 100
                elif t.startswith(q) or tc.startswith(qc):
                    s = 92
                elif q in t or qc in tc:
                    s = 85
                else:
                    s = _fuzzy(q, t)
                best = max(best, s)
            if best >= 65:
                scored.append((best, room))
        scored.sort(key=lambda x: (-x[0], x[1]["name"].lower()))
        return [r for _, r in scored[:limit]]
