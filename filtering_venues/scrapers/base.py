"""Base scraping utilities shared by all university scrapers."""

import threading
import time

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_js_lock = threading.Lock()
_js_session = None


def _get_js_session():
    """Lazy singleton Playwright renderer (Chromium)."""
    global _js_session
    if _js_session is None:
        with _js_lock:
            if _js_session is None:
                from playwright.sync_api import sync_playwright

                pw = sync_playwright().start()
                browser = pw.chromium.launch(headless=True)
                _js_session = {"pw": pw, "browser": browser}
    return _js_session


class BaseScraper:
    """Common session handling for fetching and parsing university pages."""

    def __init__(self, university, rank, faculty_url, delay=0.5, timeout=30):
        self.university = university
        self.rank = rank
        self.faculty_url = faculty_url
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get_soup(self, url):
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        time.sleep(self.delay)
        return BeautifulSoup(resp.text, "lxml")

    def get_soup_js(self, url, wait_ms=2500):
        """Render a page with Playwright/Chromium (for JS/blocked pages)."""
        js = _get_js_session()
        browser = js["browser"]
        page = browser.new_page(user_agent=USER_AGENT)
        try:
            page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            html = page.content()
        finally:
            page.close()
        time.sleep(self.delay)
        return BeautifulSoup(html, "lxml")

    def get_soup_fallback(self, url, wait_ms=2500):
        """Try requests first, then Playwright; return (soup, used_js)."""
        try:
            return self.get_soup(url), False
        except Exception:
            return self.get_soup_js(url, wait_ms), True

    def scrape(self):
        """Return a list of faculty profiles.

        Each profile is a dict with keys:
            name, title, email, profile_url, lab_url, research_areas, research_text
        """
        raise NotImplementedError
