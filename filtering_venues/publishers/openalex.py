"""OpenAlex enrichment: author lookup, works, venues and topics."""

import json
import threading
import time

import requests


class OpenAlexClient:
    """Thin client over the OpenAlex API with polite rate limiting."""

    BASE = "https://api.openalex.org"

    def __init__(self, mailto=None, delay=0.15, per_page=200, max_works=500, rate_limit=8.0, api_key=None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": f"faculty-scraper mailto:{mailto or 'dev@example.com'}"})
        if isinstance(api_key, list):
            self._api_keys = [k for k in api_key if k]
        elif api_key:
            self._api_keys = [api_key]
        else:
            self._api_keys = []
        self._key_idx = 0
        self._key_lock = threading.Lock()
        self.delay = delay
        self.per_page = per_page
        self.max_works = max_works
        self.rate_limit = float(rate_limit)
        self._lock = threading.Lock()
        self._next_ok = 0.0

    def _next_api_key(self):
        if not self._api_keys:
            return None
        with self._key_lock:
            key = self._api_keys[self._key_idx % len(self._api_keys)]
            self._key_idx += 1
            return key

    def _throttle(self):
        """Globally space requests so all workers combined stay under the cap."""
        with self._lock:
            now = time.monotonic()
            wait = self._next_ok - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_ok = now + 1.0 / self.rate_limit

    def _get_json(self, endpoint, params):
        self._throttle()
        url = f"{self.BASE}/{endpoint}"
        headers = {}
        key = self._next_api_key()
        if key:
            headers["api_key"] = key
        resp = None
        for attempt in range(20):
            try:
                resp = self.session.get(url, params=params, headers=headers, timeout=60)
            except requests.exceptions.RequestException:
                time.sleep(min(2 ** attempt, 60) + 1)
                continue
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                try:
                    backoff = float(retry_after)
                except (TypeError, ValueError):
                    backoff = min(2 ** attempt, 60)
                time.sleep(max(backoff, 5) + 1)
                key = self._next_api_key()
                if key:
                    headers["api_key"] = key
                continue
            if resp.status_code < 500:
                break
            time.sleep(min(2 ** attempt, 30) + 1)
        resp.raise_for_status()
        time.sleep(self.delay)
        return resp.json()

    def find_author(self, name, ror=None):
        params = {"search": name, "per-page": 10}
        if ror:
            params["filter"] = f"last_known_institutions.id:{ror}"
        data = self._get_json("authors", params)
        results = data.get("results") or []
        if not results and ror:
            params.pop("filter", None)
            data = self._get_json("authors", params)
            results = data.get("results") or []
        if not results:
            return None
        return {
            "id": results[0]["id"],
            "display_name": results[0]["display_name"],
            "works_count": results[0].get("works_count"),
            "h_index": (results[0].get("summary_stats") or {}).get("h_index"),
        }

    def find_institution(self, name):
        """Return the ROR id of the best-matching institution, or None."""
        data = self._get_json("institutions", {"search": name, "per-page": 3})
        for res in data.get("results") or []:
            ror = res.get("ror")
            if ror:
                return ror
        return None

    def search_authors(self, name, per_page=50):
        """Return raw author results for a name search (no institution filter)."""
        data = self._get_json("authors", {"search": name, "per-page": per_page})
        return data.get("results") or []

    def get_works_filtered(self, author_id, year_from=None, year_to=None):
        """Fetch an author's works, optionally restricted to a publication year
        range, using ``authorships.author.id`` and ``publication_year`` filters."""
        works = []
        cursor = "*"
        while cursor and len(works) < self.max_works:
            filters = [f"authorships.author.id:{author_id}"]
            if year_from is not None and year_to is not None:
                filters.append(f"publication_year:{year_from}-{year_to}")
            params = {
                "filter": ",".join(filters),
                "per-page": min(self.per_page, 200),
                "cursor": cursor,
                "sort": "publication_date:desc",
            }
            data = self._get_json("works", params)
            results = data.get("results") or []
            works.extend(results)
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not results:
                break
        return works[: self.max_works]

    def get_works(self, author_id):
        works = []
        cursor = "*"
        while cursor and len(works) < self.max_works:
            params = {
                "filter": f"author.id:{author_id}",
                "per-page": min(self.per_page, 200),
                "cursor": cursor,
                "sort": "publication_date:desc",
            }
            data = self._get_json("works", params)
            results = data.get("results") or []
            works.extend(results)
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not results:
                break
        return works[: self.max_works]

    @staticmethod
    def extract_source(work):
        src = (work.get("primary_location") or {}).get("source") or {}
        return src.get("display_name")

    @staticmethod
    def extract_topics(work):
        topics = []
        primary = work.get("primary_topic") or {}
        if primary.get("display_name"):
            topics.append(primary["display_name"])
        for t in (work.get("topics") or [])[:3]:
            if t.get("display_name"):
                topics.append(t["display_name"])
        return topics

    def enrich(self, name, ror=None):
        """Return dict of publication-derived fields, or None if not found."""
        author = self.find_author(name, ror)
        if author is None:
            return None
        works = self.get_works(author["id"])
        sources = [s for s in (self.extract_source(w) for w in works) if s]
        topics = []
        for w in works:
            topics.extend(self.extract_topics(w))
        return {
            "author": author,
            "works_count": author["works_count"],
            "h_index": author["h_index"],
            "sources": sources,
            "topics": list(dict.fromkeys(topics))[:15],
            "n_works_fetched": len(works),
        }


def venue_matches(sources, target_venues):
    """Map OpenAlex source names to configured target venue short labels.

    Returns (matched_short_labels, matched_source_names).
    """
    matched_labels = []
    matched_sources = []
    for source in sources:
        if not source:
            continue
        low = source.lower()
        label = None
        for short, aliases in target_venues.items():
            if any(alias in low for alias in aliases):
                label = short
                break
        if label:
            matched_labels.append(label)
            matched_sources.append(source)
    return list(dict.fromkeys(matched_labels)), matched_sources


class WorksCache:
    """Disk cache for OpenAlex enrichment keyed by (school, profile slug)."""

    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path(self, school, slug):
        safe = "".join(c if c.isalnum() else "_" for c in slug)[:80]
        return self.cache_dir / f"{school}_{safe}.json"

    def load(self, school, slug):
        p = self.path(school, slug)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def save(self, school, slug, payload):
        self.path(school, slug).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
        )
