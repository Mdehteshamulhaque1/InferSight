"""Caching layer with graceful Redis fallback.

When Redis is unreachable (or disabled), a process-local TTL cache keeps the
application fully functional so a cache outage never takes down the API.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time

from app.core.config import get_settings

_DEFAULT_TTL = 60  # seconds


class LocalTTLCache:
    """Thread-safe in-memory cache with absolute TTL expiry."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_pattern(self, pattern: str) -> None:
        with self._lock:
            for key in list(self._store):
                if pattern in key:
                    self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class CacheService:
    """Unified cache facade over Redis or the local fallback."""

    def __init__(self) -> None:
        self._local = LocalTTLCache()
        self._redis = None
        self._enabled = False
        settings = get_settings()
        if settings.redis_enabled:
            try:
                import redis  # type: ignore

                client = redis.Redis.from_url(
                    settings.redis_url, socket_connect_timeout=0.5, decode_responses=True
                )
                client.ping()
                self._redis = client
                self._enabled = True
            except Exception:
                self._redis = None
                self._enabled = False

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "local"

    def get(self, key: str) -> str | None:
        if self._redis is not None:
            try:
                return self._redis.get(key)
            except Exception:
                pass
        return self._local.get(key)

    def set(self, key: str, value: str, ttl: int = _DEFAULT_TTL) -> None:
        if self._redis is not None:
            try:
                self._redis.set(key, value, ex=ttl)
            except Exception:
                pass
        self._local.set(key, value, ttl)

    def delete(self, key: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._local.delete(key)

    def delete_pattern(self, pattern: str) -> None:
        if self._redis is not None:
            try:
                for key in self._redis.scan_iter(match=f"*{pattern}*", count=500):
                    self._redis.delete(key)
            except Exception:
                pass
        self._local.delete_pattern(pattern)

    def cache_get_json(self, prefix: str, *parts: object) -> dict | list | None:
        key = self._build_key(prefix, *parts)
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def cache_set_json(
        self, value: object, prefix: str, *parts: object, ttl: int = _DEFAULT_TTL
    ) -> None:
        key = self._build_key(prefix, *parts)
        self.set(key, json.dumps(value, default=str), ttl)

    def invalidate_prefix(self, prefix: str) -> None:
        self.delete_pattern(prefix)

    @staticmethod
    def _build_key(prefix: str, *parts: object) -> str:
        joined = "|".join(str(p) for p in parts)
        digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}:{digest}"


cache_service = CacheService()
