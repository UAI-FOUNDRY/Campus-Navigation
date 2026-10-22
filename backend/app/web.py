"""HTTP hardening and speed: security headers, request limits, rate limiting, ETag/304, gzip.

Everything here is plain Flask/stdlib (no extra packages, free hosting friendly). The graph never changes while the
server runs, so every GET answer is fully decided by (graph version, URL): that is what the ETag is made of, and a
repeat request is answered with 304 before any routing work is done.
"""
import gzip
import hashlib
import threading
import time
from collections import OrderedDict

from flask import jsonify, make_response, request

from . import config

# GET endpoints whose answer depends only on the graph version and the URL (safe to cache in browsers/CDNs)
CACHEABLE = {"api.floors": 3600, "api.search_rooms": 300, "api.get_room": 300, "api.route": 300,
             "api.app_search": 300, "api.graph_full": 0, "api.graph_version": 0}
MAX_ARG_LEN = 120          # longest query value we accept (place ids are < 64 chars, search text < 100)
GZIP_MIN_BYTES = 1400      # smaller answers fit in one packet anyway


class RateLimiter:
    """Token bucket per (client, bucket name), in memory. Each gunicorn worker keeps its own buckets: good enough
    to stop a script hammering the free server; not meant as an exact quota."""

    def __init__(self, max_clients=20000):
        self.lock = threading.Lock()
        self.buckets = OrderedDict()
        self.max_clients = max_clients

    def allow(self, key, rate_per_min, burst):
        now = time.monotonic()
        with self.lock:
            tokens, last = self.buckets.pop(key, (float(burst), now))
            tokens = min(float(burst), tokens + (now - last) * rate_per_min / 60.0)
            ok = tokens >= 1.0
            self.buckets[key] = (tokens - 1.0 if ok else tokens, now)
            while len(self.buckets) > self.max_clients:      # forget the clients seen longest ago
                self.buckets.popitem(last=False)
            return ok, 0 if ok else int((1.0 - tokens) * 60.0 / rate_per_min) + 1


def _limits(endpoint, method):
    """(bucket, requests per minute, burst) for this request."""
    if endpoint in ("api.report_problem",):
        return "report", config.RATE_REPORT_PER_MIN, 3
    if endpoint in ("api.wifi_add",):
        return "wifi", config.RATE_WIFI_PER_MIN, 10
    if endpoint in ("api.estimates", "api.app_route"):
        return "heavy", config.RATE_HEAVY_PER_MIN, 20
    return "read", config.RATE_READ_PER_MIN, 60


def _err(code, message, status, **headers):
    resp = jsonify(error={"code": code, "message": message})
    resp.status_code = status
    resp.headers.update(headers)
    return resp


def _etag(version):
    if request.endpoint == "api.graph_full":
        return f'"{version}"'           # same value as GET /api/graph/version, so a client can compare directly
    return '"' + hashlib.sha1(f"{version}|{request.full_path}".encode()).hexdigest()[:20] + '"'


def install(app, graph):
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_BODY_BYTES
    if config.TRUSTED_PROXIES:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=config.TRUSTED_PROXIES, x_proto=config.TRUSTED_PROXIES)
    limiter = RateLimiter()
    app.extensions["rate_limiter"] = limiter
    gz_cache = OrderedDict()     # etag -> gzipped body (graph, floors, full place list: computed once)
    gz_lock = threading.Lock()

    @app.before_request
    def guard():
        if request.method == "OPTIONS":
            return None
        for v in request.args.values():
            if len(v) > MAX_ARG_LEN:
                return _err("bad_request", "query value too long", 400)
        if config.RATE_LIMITS_ON:
            bucket, rate, burst = _limits(request.endpoint, request.method)
            ok, wait = limiter.allow((request.remote_addr or "?", bucket), rate, burst)
            if not ok:
                return _err("rate_limited", "too many requests, try again in a moment", 429, **{"Retry-After": str(wait)})
        if request.method == "GET" and request.endpoint in CACHEABLE:
            tag = _etag(graph.version)
            inm = request.headers.get("If-None-Match", "")
            if tag in [t.strip().removeprefix("W/") for t in inm.split(",")] or inm.strip() == graph.version:
                resp = make_response("", 304)
                resp.headers["ETag"] = tag
                return resp
        return None

    @app.after_request
    def finish(resp):
        h = resp.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["Referrer-Policy"] = "no-referrer"
        h["X-Frame-Options"] = "DENY"
        h["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        h["Cross-Origin-Resource-Policy"] = "cross-origin"
        h.pop("Server", None)
        if request.method == "GET" and request.endpoint in CACHEABLE and resp.status_code == 200:
            h["ETag"] = _etag(graph.version)
            age = CACHEABLE[request.endpoint]
            h["Cache-Control"] = f"public, max-age={age}" if age else "no-cache"
        _maybe_gzip(resp)
        return resp

    def _maybe_gzip(resp):
        if (resp.status_code != 200 or resp.direct_passthrough or "Content-Encoding" in resp.headers
                or "gzip" not in request.headers.get("Accept-Encoding", "").lower()
                or not (resp.mimetype or "").endswith("json")):
            return
        resp.vary.add("Accept-Encoding")
        tag = resp.headers.get("ETag")
        with gz_lock:
            body = gz_cache.get(tag) if tag else None
        if body is None:
            raw = resp.get_data()
            if len(raw) < GZIP_MIN_BYTES:
                return
            body = gzip.compress(raw, compresslevel=6, mtime=0)
            if tag and len(raw) > 20000:          # keep the few big, often-asked answers
                with gz_lock:
                    gz_cache[tag] = body
                    while len(gz_cache) > 32:
                        gz_cache.popitem(last=False)
        resp.set_data(body)
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Content-Length"] = str(len(body))

    @app.errorhandler(413)
    def too_big(_):
        return _err("too_large", f"request body is larger than {config.MAX_BODY_BYTES // 1024} KB", 413)

    @app.errorhandler(405)
    def bad_method(_):
        return _err("method_not_allowed", "this endpoint does not accept that method", 405)
