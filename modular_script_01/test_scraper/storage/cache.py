"""
Small JSON cache.

Each remote source gets its own cache file under datasets/cache/.  The cache
key is the natural identity of the thing being looked up (a scholar user id,
an OpenAlex author id, a DOI, ...).  This keeps re-runs fast and polite to
the free APIs without persisting anything heavy.
"""

import json
import os
import time

from .._paths import CACHE_DIR, ensure_dirs


class JsonCache:
    """JSON file cache keyed by (source, key)."""

    def __init__(self, source: str, ttl: int = 60 * 60 * 24 * 7):
        ensure_dirs()
        self.source = source
        self.ttl = ttl
        self.path = os.path.join(CACHE_DIR, f'{source}.json')
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding='utf-8') as f:
                return json.load(f)
        except (ValueError, OSError):
            return {}

    def _save(self) -> None:
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False)

    def get(self, key: str, default=None):
        entry = self._data.get(key)
        if not entry:
            return default
        if entry.get('_ts', 0) + self.ttl < time.time():
            return default
        return entry.get('value', default)

    def set(self, key: str, value) -> None:
        self._data[key] = {'_ts': time.time(), 'value': value}
        self._save()

    def clear(self) -> None:
        self._data = {}
        if os.path.exists(self.path):
            os.remove(self.path)
