"""Generic config-driven faculty scraper.

Works for most university directory pages without bespoke code:

- Fetches the listing page (requests first, Playwright fallback for JS/blocked).
- Finds professor entries via config CSS selectors, or via heuristics when the
  config doesn't specify any (anchors whose text looks like a person name and
  whose href looks like a profile link).
- Optionally follows each profile page (config ``follow_profiles``) to enrich
  title / email / lab link / research text.

Config schema (per university, see data/school_config.json)::

    {
      "entries": "css for the per-professor container (optional)",
      "name": "css for name anchor within entry (optional)",
      "email": "css for mailto/email within entry (optional)",
      "profile_url": "css for profile link within entry (optional)",
      "research": "css for research-area tags within entry (optional)",
      "pagination": {"next": "css selector for 'next page' link", "max_pages": N} | null,
      "follow_profiles": true|false,
      "profile": {
          "title": "css (optional)",
          "email": "css (optional)",
          "lab": "css (optional)",
          "research_text": "css (optional)"
      }
    }
"""

import re
from urllib.parse import urljoin, urlparse

from .base import BaseScraper

NAME_RE = re.compile(
    r"^[A-Z][A-Za-z'.\-]*(?:\s+[A-Za-z][A-Za-z'.\-]*){1,5}$"
)
PROFILE_HINT = re.compile(
    r"(/people/|/faculty|/professor|profile|/person|/directory|/user/|~[a-z])",
    re.I,
)
LINK_TEXT_STOP = re.compile(
    r"(skip to|main content|view all|learn more|read more|load more|about|research|"
    r"contact|faculty|directory|staff|professor|assistant|department|college|"
    r"menu|home|news|events|programs|degrees|admissions|alumni|people|office|"
    r"leadership|advising|director|fellows|postdoctoral|emeriti|emeritus|"
    r"council|committee|facilities|administration|resources|information|team|"
    r"students|student|awards|donor|profiles|graduating|honors|fellowship|"
    r"careers|staff directory|search results|all faculty|faculty directory)",
    re.I,
)
LAB_TEXT_STOP = re.compile(
    r"(website|homepage|home page|personal page|lab page|webpage|personal website)",
    re.I,
)
HONORIFIC_RE = re.compile(
    r"^(Mr|Mrs|Ms|Dr|Prof|Professor|Assistant Professor|Associate Professor|"
    r"Distinguished Professor)\.?\s+",
    re.I,
)

def _name_like(text):
    if not text or len(text) > 80:
        return False
    if LINK_TEXT_STOP.search(text):
        return False
    if LAB_TEXT_STOP.search(text):
        return False
    words = text.split()
    if not (2 <= len(words) <= 6):
        return False
    if any(ch.isdigit() for ch in text):
        return False
    return bool(NAME_RE.match(text))


def _pick_with_text(scope, selector, fallback=None):
    """Select an element matching ``selector`` that has non-empty text, else fallback.

    Some sites render an empty image anchor immediately before the named link, so
    ``select_one`` picks the empty one; this prefers the link carrying the name.
    """
    for el in scope.select(selector):
        if el.get_text(" ", strip=True):
            return el
    return scope.select_one(selector) or fallback


def _text_holder(scope):
    """Return the entry container itself when it directly holds the name text."""
    if scope is None:
        return None
    return scope if scope.get_text(" ", strip=True) else None


def _href_like_profile(href):
    return PROFILE_HINT.search(href)


class GenericScraper(BaseScraper):
    """Parses any faculty listing using config selectors + heuristics."""

    def __init__(self, university, rank, faculty_url, config=None, **kwargs):
        super().__init__(university, rank, faculty_url, **kwargs)
        self.config = config or {}

    # ---- listing ----
    def scrape(self):
        profiles = {}
        urls = self.config.get("pages") or [self.faculty_url]
        for url in urls:
            soup = self._get_listing(url)
            entries = self._find_entries(soup)
            for entry in entries:
                prof = self._parse_entry(entry, used_js=False)
                if prof is None:
                    continue
                profiles.setdefault(prof["profile_url"] or prof["name"], prof)
        if self.config.get("follow_profiles", True):
            for prof in profiles.values():
                if prof["profile_url"]:
                    try:
                        self._enrich_profile(prof)
                    except Exception:  # noqa: BLE001
                        pass
        return list(profiles.values())

    def _get_listing(self, url):
        """Fetch a listing page; auto-fallback to JS render when empty/blocked."""
        wait_ms = self.config.get("js_wait_ms", 2500)
        force_js = self.config.get("force_js", False)
        if force_js:
            return self._get_listing_js(url, wait_ms)
        try:
            soup = self.get_soup(url)
        except Exception:  # noqa: BLE001
            try:
                return self._get_listing_js(url, wait_ms)
            except Exception:  # noqa: BLE001
                raise
        if not self.config.get("entries") and not self._heuristic_entries(soup):
            try:
                soup2 = self._get_listing_js(url, wait_ms)
                if self._heuristic_entries(soup2):
                    return soup2
            except Exception:  # noqa: BLE001
                pass
        return soup

    def _get_listing_js(self, url, wait_ms):
        """Render via Playwright, retrying because embedded content loads slowly/flaky."""
        entries_sel = self.config.get("entries")
        last = None
        for attempt in range(3):
            soup = self.get_soup_js(url, wait_ms)
            last = soup
            if entries_sel:
                if soup.select(entries_sel):
                    return soup
            elif self._heuristic_entries(soup):
                return soup
        return last

    def _find_entries(self, soup):
        entries_sel = self.config.get("entries")
        if entries_sel:
            return soup.select(entries_sel)
        return self._heuristic_entries(soup)

    def _heuristic_entries(self, soup):
        seen = set()
        out = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            href = a.get("href", "")
            if not _name_like(text):
                continue
            if not _href_like_profile(href):
                continue
            container = _nearest_container(a)
            cid = id(container)
            if cid in seen:
                continue
            seen.add(cid)
            out.append((container, a))
        return out

    def _parse_entry(self, entry, used_js=False):
        cfg = self.config
        if isinstance(entry, tuple):
            container, anchor = entry
        else:
            container, anchor = entry, None
        name_el = (
            _pick_with_text(container, cfg["name"], anchor)
            if cfg.get("name")
            else (anchor or container.find("a", href=True))
        )
        if name_el is None and isinstance(entry, tuple) is False and not cfg.get("name"):
            name_el = _text_holder(container)
        if name_el is None:
            return None
        name = name_el.get_text(" ", strip=True)
        name = re.sub(r"\s+", " ", name).strip()
        name = HONORIFIC_RE.sub("", name).strip()
        if not _name_like(name) and not cfg.get("name"):
            return None
        link_el = (
            _pick_with_text(container, cfg["profile_url"], anchor)
            if cfg.get("profile_url")
            else (anchor or name_el)
        )
        href = link_el.get("href", "") if link_el else ""
        if not href and name_el is not None:
            href = name_el.get("href", "") or ""
        if not href and entry is not None and not isinstance(entry, tuple):
            href = entry.get("href", "") or ""
        profile_url = urljoin(self.faculty_url, href) if href else ""

        email = ""
        if cfg.get("email"):
            e = container.select_one(cfg["email"])
            if e:
                email = _mailto(e)
        else:
            email = _find_email(container)

        research = []
        if cfg.get("research"):
            for tag in container.select(cfg["research"]):
                t = tag.get_text(" ", strip=True)
                if t:
                    research.append(t)
        else:
            research = _find_research(container, exclude=name)

        return {
            "name": name,
            "title": "",
            "email": email,
            "profile_url": profile_url,
            "lab_url": "",
            "research_areas": research,
            "research_text": " ".join(research),
        }

    # ---- profile enrichment ----
    def _enrich_profile(self, prof):
        pcfg = self.config.get("profile") or {}
        soup, _ = self.get_soup_fallback(prof["profile_url"])

        title = ""
        if pcfg.get("title"):
            t = soup.select_one(pcfg["title"])
            title = t.get_text(" ", strip=True) if t else ""
        else:
            title = _heuristic_title(soup)
        if title and title == prof["name"]:
            title = ""
        prof["title"] = title

        if not prof["email"]:
            if pcfg.get("email"):
                e = soup.select_one(pcfg["email"])
                if e:
                    prof["email"] = _mailto(e)
            else:
                prof["email"] = _find_email(soup)

        lab = ""
        if pcfg.get("lab"):
            l = soup.select_one(pcfg["lab"])
            if l:
                lab = urljoin(prof["profile_url"], l.get("href", ""))
        else:
            lab = _find_lab_link(soup, prof["profile_url"])
        prof["lab_url"] = lab

        text = ""
        if pcfg.get("research_text"):
            parts = [x.get_text(" ", strip=True) for x in soup.select(pcfg["research_text"])]
            text = " ".join(p for p in parts if p)
        else:
            text = _find_research_text(soup)
        if text:
            prof["research_text"] = " ".join(
                p for p in (prof["research_text"], text) if p
            )
            prof["research_areas"] = [prof["research_text"]]

    # ---- helpers ----
    def get_soup_fallback(self, url, wait_ms=2500):
        try:
            return self.get_soup(url), False
        except Exception:  # noqa: BLE001
            try:
                return self.get_soup_js(url, wait_ms), True
            except Exception:  # noqa: BLE001
                raise


def _with_page(url, page):
    if "?" in url:
        return f"{url}&page={page}"
    return f"{url}?page={page}"


def _nearest_container(a, max_up=6):
    node = a
    for _ in range(max_up):
        node = node.parent
        if node is None:
            break
        if node.name in ("li", "tr", "article", "div", "section", "td"):
            if _is_entry_container(node):
                return node
    return a.parent


def _is_entry_container(node):
    cls = node.get("class") or []
    return any(k in " ".join(cls).lower() for k in ("profile", "people", "faculty", "person", "staff", "card", "row", "member", "entry"))


def _mailto(el):
    href = el.get("href", "") or ""
    if href.lower().startswith("mailto:"):
        return href[7:].strip().replace("%0A", "").replace("%0D", "").strip()
    text = el.get_text(" ", strip=True)
    if "@" in text:
        return text
    return ""


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _find_email(scope):
    for a in scope.find_all("a", href=True):
        href = a.get("href", "")
        if href.lower().startswith("mailto:"):
            return href[7:].strip()
    text = scope.get_text(" ", strip=True)
    m = EMAIL_RE.search(text)
    return m.group(0) if m else ""


def _find_research(scope, exclude=""):
    out = []
    for el in scope.find_all(["a", "span", "div", "p", "h3", "h4"]):
        cls = " ".join(el.get("class") or []).lower()
        if not any(k in cls for k in ("research", "area", "interest", "field", "tag")):
            continue
        t = el.get_text(" ", strip=True)
        if t and t != exclude and "@" not in t:
            out.append(t)
    return out[:12]


def _heuristic_title(soup):
    for sel in ("h1", ".node-title h1", "meta[property='og:title']"):
        if sel.startswith("meta"):
            m = soup.select_one(sel)
            if m:
                return m.get("content", "").strip()
        else:
            el = soup.select_one(sel)
            if el:
                t = el.get_text(" ", strip=True)
                if t:
                    return t
    return ""


def _find_lab_link(soup, base):
    domain = urlparse(base).netloc
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True)
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        if re.search(r"(lab|group|homepage|personal page|website)", text, re.I):
            return urljoin(base, href)
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href:
            continue
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        abs_url = urljoin(base, href)
        netloc = urlparse(abs_url).netloc
        if netloc and netloc != domain and "w3.org" not in netloc and "javascript" not in netloc.lower():
            return abs_url
    return ""


def _find_research_text(soup):
    parts = []
    for el in soup.select("h2, h3"):
        t = el.get_text(" ", strip=True)
        if re.search(r"(research|interest|area|about)", t, re.I):
            nxt = el.find_next_sibling()
            if nxt:
                parts.append(nxt.get_text(" ", strip=True))
    if not parts:
        main = soup.select_one("article, main, #main-content, .field-name-body, .node__content")
        if main:
            parts = [p.get_text(" ", strip=True) for p in main.find_all("p")[:8]]
    return " ".join(p for p in parts if p)[:1500]
