"""Scraper for Stanford CS faculty directory (Drupal).

The listing is paginated via "Load More" links (?page=N). Emails are not
public on the CS site; research area is derived later from publications.
"""

from urllib.parse import urljoin

from .base import BaseScraper


class StanfordScraper(BaseScraper):
    """Parses https://www.cs.stanford.edu/people/faculty."""

    def scrape(self):
        profiles = {}
        page = 0
        while True:
            url = self.faculty_url if page == 0 else f"{self.faculty_url}?page={page}"
            soup = self.get_soup(url)
            cards = soup.select("article.su-card--minimal")
            if not cards:
                break
            for card in cards:
                link = card.select_one(".node-title h3 a, div.node-title h3 a")
                if link is None:
                    continue
                slug = link.get("href", "")
                name = link.get_text(" ", strip=True)
                title_el = card.select_one(".su-person-short-title")
                title = title_el.get_text(" ", strip=True) if title_el else ""
                if "emeritus" in title.lower():
                    continue
                profiles.setdefault(
                    slug,
                    {
                        "name": name,
                        "title": title,
                        "email": "",
                        "profile_url": urljoin(self.faculty_url, slug),
                        "lab_url": "",
                        "research_areas": [],
                        "research_text": "",
                    },
                )
            load_more = soup.find("a", string=lambda t: t and "Load More" in t)
            if load_more is None:
                break
            page = int(load_more.get("href", "").split("page=")[-1])

        for profile in profiles.values():
            self._enrich_profile(profile)
        return list(profiles.values())

    def _enrich_profile(self, profile):
        if not profile["profile_url"]:
            return
        soup = self.get_soup(profile["profile_url"])
        title_el = soup.select_one(".su-person-full-title")
        if title_el:
            profile["title"] = title_el.get_text(" ", strip=True)
        link_el = soup.select_one(".su-person-links a")
        if link_el:
            profile["lab_url"] = link_el.get("href", "")
        # Emails are not published on the CS site; keep blank for manual fill.
        profile["email"] = ""
