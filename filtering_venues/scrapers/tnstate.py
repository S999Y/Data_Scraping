"""Tennessee State University: faculty listed as <p> blocks with plain-text emails."""

import re
import time

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


class TennesseeStateScraper(BaseScraper):
    def scrape(self):
        resp = self.session.get(self.faculty_url, timeout=self.timeout)
        resp.raise_for_status()
        time.sleep(self.delay)
        soup = BeautifulSoup(resp.text, "lxml")
        main = soup.select_one(".template-content") or soup.select_one("#content") or soup

        out = []
        seen = set()
        for p in main.find_all("p"):
            text = p.get_text(" ", strip=True)
            m = EMAIL_RE.search(text)
            if not m:
                continue
            email = m.group(0)
            if email in seen:
                continue
            name_el = p.find("a")
            name = name_el.get_text(" ", strip=True).strip() if name_el else ""
            if not name:
                m2 = re.search(r"^\s*((?:Dr\.|Mr\.|Mrs\.|Ms\.)\s+[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+)*)", text)
                if m2:
                    name = m2.group(1)
            if not name:
                continue
            title = ""
            tm = re.search(r"\n\s*(.+?)\s*\n\s*Office:", text)
            if name_el:
                tm = re.search(r"(?:Chair|Professor|Instructor|Lecturer|Director|Coordinator|Dean)", text)
                if tm:
                    title = tm.group(0)
            profile = ""
            if name_el:
                profile = requests.compat.urljoin(self.faculty_url, name_el.get("href", ""))
            seen.add(email)
            out.append(
                {
                    "name": name,
                    "title": title,
                    "email": email,
                    "profile_url": profile,
                    "lab_url": "",
                    "research_areas": [],
                    "research_text": "",
                }
            )
        return out
