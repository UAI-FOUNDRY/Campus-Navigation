"""Tests fire hundreds of requests from one client: switch the per-client rate limit off (test_web.py turns it on)."""
from app import config

config.RATE_LIMITS_ON = False
