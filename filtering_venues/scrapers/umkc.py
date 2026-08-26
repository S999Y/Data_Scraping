"""University of Missouri-Kansas City: directory data served from a .json endpoint (blocks non-browser UAs)."""

import requests

from .base import BaseScraper

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class UMKcScraper(BaseScraper):
    def scrape(self):
        headers = {
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        json_url = self.faculty_url.replace(".html", ".json")
        r = self.session.get(json_url, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        out = []
        for item in data:
            title = item.get("title")
            if isinstance(title, list):
                title = "; ".join(title)
            out.append(
                {
                    "name": item.get("name", "").strip(),
                    "title": title or "",
                    "email": (item.get("email") or "").strip(),
                    "profile_url": item.get("link") or "",
                    "lab_url": "",
                    "research_areas": [],
                    "research_text": "",
                }
            )
        return out
