"""Plan <-> GPS and plan <-> picture conversions for the indoor maps.

Indoor positions are stored in PLAN METRES: x to the right, y down, measured on the architect's floor plans
(all floors share one frame, so a lift is at the same x,y on every floor). Two small fits turn them into:

  * latitude/longitude  (georef):  a similarity fit (scale, rotation, shift) from control points, i.e. places
    that are both on the plan and on the outdoor GeoJSON (doors on the facade). Used for the A* heuristic,
    for drawing indoor routes on the real map, and for snapping a phone's GPS fix.
  * picture pixels      (display): an affine fit from anchor points (plan metres -> pixels on the public
    signage picture, e.g. ground.png), plus a small correction so each anchor lands exactly. The signage
    picture is not to scale, so this only decides where the route line is DRAWN; distances never use it.

Pure Python (no numpy) so the backend and the tools can share it.
"""
import math

EARTH_R = 6371000.0


def _mean(pts):
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


class LocalMetres:
    """Flat east/north metres around a reference latitude/longitude."""

    def __init__(self, lat0, lng0):
        self.lat0, self.lng0 = lat0, lng0
        self.kx = math.radians(1) * EARTH_R * math.cos(math.radians(lat0))
        self.ky = math.radians(1) * EARTH_R

    def en(self, lat, lng):
        return ((lng - self.lng0) * self.kx, (lat - self.lat0) * self.ky)

    def latlng(self, e, n):
        return (self.lat0 + n / self.ky, self.lng0 + e / self.kx)


class Georef:
    """Similarity transform plan metres (x right, y down) -> latitude/longitude."""

    def __init__(self, pairs):
        """pairs: [((x_m, y_m), (lat, lng)), ...] with at least 2 well separated points."""
        if len(pairs) < 2:
            raise ValueError("georef needs at least 2 control points")
        lat0 = sum(q[0] for _, q in pairs) / len(pairs)
        lng0 = sum(q[1] for _, q in pairs) / len(pairs)
        self.loc = LocalMetres(lat0, lng0)
        P = [(x, -y) for (x, y), _ in pairs]          # plan y points down; make it a normal x,y frame
        Q = [self.loc.en(*q) for _, q in pairs]
        pc, qc = _mean(P), _mean(Q)
        sxx = sxy = syx = syy = 0.0
        var = 0.0
        for (px, py), (qx, qy) in zip(P, Q):
            ax, ay, bx, by = px - pc[0], py - pc[1], qx - qc[0], qy - qc[1]
            sxx += ax * bx; sxy += ax * by; syx += ay * bx; syy += ay * by
            var += ax * ax + ay * ay
        self.theta = math.atan2(sxy - syx, sxx + syy)   # rotation plan -> east/north
        c, s = math.cos(self.theta), math.sin(self.theta)
        self.scale = ((sxx + syy) * c + (sxy - syx) * s) / var
        self.pc, self.qc = pc, qc
        self.residuals = [math.dist(self._en(x, y), q) for ((x, y), _), q in zip(pairs, Q)]

    def _en(self, x, y):
        px, py = x - self.pc[0], -y - self.pc[1]
        c, s = math.cos(self.theta), math.sin(self.theta)
        return (self.qc[0] + self.scale * (c * px - s * py), self.qc[1] + self.scale * (s * px + c * py))

    def to_latlng(self, x, y):
        lat, lng = self.loc.latlng(*self._en(x, y))
        return (round(lat, 7), round(lng, 7))

    def to_plan(self, lat, lng):
        e, n = self.loc.en(lat, lng)
        dx, dy = (e - self.qc[0]) / self.scale, (n - self.qc[1]) / self.scale
        c, s = math.cos(self.theta), math.sin(self.theta)
        px, py = c * dx + s * dy, -s * dx + c * dy
        return (px + self.pc[0], -(py + self.pc[1]))

    @property
    def rms(self):
        return math.sqrt(sum(r * r for r in self.residuals) / len(self.residuals))


class Display:
    """Plan metres -> pixels on the signage picture: affine fit + inverse-distance correction of the residuals."""

    def __init__(self, anchors):
        """anchors: [((x_m, y_m), (px, py)), ...] at least 3, not all on one line."""
        if len(anchors) < 3:
            raise ValueError("display needs at least 3 anchors")
        self.anchors = anchors
        self.M = _affine([a for a, _ in anchors], [b for _, b in anchors])
        self.res = [(a, (b[0] - p[0], b[1] - p[1])) for (a, b), p in zip(anchors, (self._aff(*a) for a, _ in anchors))]

    def _aff(self, x, y):
        m = self.M
        return (m[0] * x + m[1] * y + m[2], m[3] * x + m[4] * y + m[5])

    def to_px(self, x, y):
        px, py = self._aff(x, y)
        wsum = dx = dy = 0.0
        for (ax, ay), (rx, ry) in self.res:
            d2 = (x - ax) ** 2 + (y - ay) ** 2
            if d2 < 1e-9:
                return (round(px + rx), round(py + ry))
            w = 1.0 / (d2 * d2)   # strong locality: corrections fade quickly away from an anchor
            wsum += w; dx += w * rx; dy += w * ry
        return (round(px + dx / wsum), round(py + dy / wsum))


def _affine(P, Q):
    """Least-squares affine (6 numbers) mapping P -> Q, solved with 3x3 normal equations."""
    A = [[0.0] * 3 for _ in range(3)]
    bx, by = [0.0] * 3, [0.0] * 3
    for (x, y), (u, v) in zip(P, Q):
        r = (x, y, 1.0)
        for i in range(3):
            for j in range(3):
                A[i][j] += r[i] * r[j]
            bx[i] += r[i] * u
            by[i] += r[i] * v
    return (*_solve3(A, bx), *_solve3(A, by))


def _solve3(A, b):
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(M[r][c]))
        if abs(M[p][c]) < 1e-12:
            raise ValueError("anchors are all on one line")
        M[c], M[p] = M[p], M[c]
        for r in range(3):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, 4):
                    M[r][k] -= f * M[c][k]
    return [M[i][3] / M[i][i] for i in range(3)]
