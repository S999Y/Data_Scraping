"""Wright State University: faculty come from the people.wright.edu JSON API.

The Drupal page renders three ``wsu-embed-people`` blocks that each call
``https://people.wright.edu/people/json/list/<id>``. List 640 is the Computer
Science faculty directory (role Faculty/Emeritus, ou=Computer Science).
"""

import time

import requests

from .base import BaseScraper

CS_FACULTY_LIST = "640"


class WrightStateScraper(BaseScraper):
    def scrape(self):
        url = f"https://people.wright.edu/people/json/list/{CS_FACULTY_LIST}"
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        time.sleep(self.delay)
        payload = resp.json()
        items = payload.get("data", payload) if isinstance(payload, dict) else payload

        out = []
        for item in items:
            a = item.get("attributes", {})
            roles = [r.lower() for r in a.get("wsuRole", [])]
            if "faculty" not in roles and "emeritus" not in roles:
                continue
            name = a.get("cn", "").strip()
            if not name:
                continue
            links = item.get("links", {})
            profile = links.get("self") or links.get("libguide") or ""
            out.append(
                {
                    "name": name,
                    "title": a.get("title", "").strip(),
                    "email": (a.get("mail", "") or "").strip(),
                    "profile_url": profile,
                    "lab_url": links.get("url", "") or "",
                    "research_areas": [],
                    "research_text": "",
                }
            )
        return out
