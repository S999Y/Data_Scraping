"""
BaseCollector - shared plumbing for every data source.

Provides an HTTP session with a polite User-Agent, a JSON cache, retries on
transient network errors, and a configurable delay between requests so the
free APIs are not hammered.

Every collector subclass:
  * sets `source` (the source name used for caching + reporting)
  * implements `collect(self, ...)` returning a normalized dict with
    profile fields plus an optional `'publications'` list.
"""

import logging
import time

import requests

from ..storage import JsonCache

logger = logging.getLogger(__name__)

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/120.0 Safari/537.36')

TIMEOUT = 30
RETRIES = 3
RETRY_BACKOFF = 1.5


class BaseCollector:
    """Shared HTTP + cache behaviour for a single data source."""

    source = 'base'

    def __init__(self, use_cache: bool = True, delay: float = 0.3,
                 timeout: int = TIMEOUT, api_key: str = None):
        self.use_cache = use_cache
        self.delay = delay
        self.timeout = timeout
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.cache = JsonCache(self.source)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _cache_key(self, url: str, params) -> str:
        if params:
            for k, v in sorted(params.items()):
                url = f'{url}|{k}={v}'
        return url

    def get_json(self, url: str, params: dict = None, use_cache: bool = True,
                 headers: dict = None) -> dict:
        """
        GET a URL expecting JSON, honouring the cache and retrying on
        transient errors.  Returns {} on a hard failure.
        """
        key = self._cache_key(url, params or {})
        if use_cache and self.use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                return cached

        last_err = None
        for attempt in range(RETRIES):
            try:
                resp = self.session.get(
                    url, params=params, timeout=self.timeout, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if use_cache and self.use_cache:
                        self.cache.set(key, data)
                    if attempt:
                        time.sleep(self.delay)
                    return data
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_err = RuntimeError(f'HTTP {resp.status_code}')
                    time.sleep(RETRY_BACKOFF * (attempt + 1))
                    continue
                last_err = RuntimeError(f'HTTP {resp.status_code}')
                break
            except requests.RequestException as e:
                last_err = e
                time.sleep(RETRY_BACKOFF * (attempt + 1))

        logger.warning('[%s] failed to fetch %s: %s', self.source, url, last_err)
        return {}

    def get_text(self, url: str, params: dict = None, use_cache: bool = True,
                 headers: dict = None) -> str:
        key = self._cache_key(url, params or {})
        if use_cache and self.use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout,
                                    headers=headers)
            if resp.status_code == 200:
                text = resp.text
                if use_cache and self.use_cache:
                    self.cache.set(key, text)
                return text
        except requests.RequestException as e:
            logger.warning('[%s] failed to fetch %s: %s', self.source, url, e)
        return ''

    # ------------------------------------------------------------------
    # Normalized output
    # ------------------------------------------------------------------

    def empty_result(self, name: str) -> dict:
        return {'name': name, 'source': self.source, 'publications': []}

    def collect(self, *args, **kwargs) -> dict:
        """Subclasses implement this.  Returns a normalized result dict."""
        raise NotImplementedError
