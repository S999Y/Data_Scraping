"""Scraper for MIT EECS Computer Science faculty directory."""

from .base import BaseScraper


class MITScraper(BaseScraper):
    """Parses https://www.eecs.mit.edu/role/faculty-cs/ (static HTML)."""

    def scrape(self):
        soup = self.get_soup(self.faculty_url)
        profiles = []
        for entry in soup.select("div.people-entry"):
            name_el = entry.select_one("h5 a")
            if name_el is None:
                continue
            name = name_el.get_text(" ", strip=True)
            profile_url = name_el.get("href", "")
            title_el = entry.select_one("h5 + p")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            email_el = entry.select_one('a[href^="mailto:"]')
            email = email_el.get("href", "").replace("mailto:", "") if email_el else ""
            areas = [a.get_text(" ", strip=True) for a in entry.select("div.people-research a")]
            profiles.append(
                {
                    "name": name,
                    "title": title,
                    "email": email,
                    "profile_url": profile_url,
                    "lab_url": "",
                    "research_areas": areas,
                    "research_text": " ".join(areas),
                }
            )
        return profiles
