"""Scraper for Carnegie Mellon CSD faculty directory.

The listing is a paginated table; each profile page adds lab link, research
areas and research statement.
"""

from urllib.parse import urljoin

from .base import BaseScraper


def _format_name(raw):
    raw = raw.strip()
    if "," in raw:
        last, _, first = raw.partition(",")
        return f"{first.strip()} {last.strip()}".strip()
    return raw


class CMUScraper(BaseScraper):
    """Parses https://csd.cmu.edu/people/faculty (+ ?page=N and profile pages)."""

    def scrape(self):
        profiles = {}
        page = 0
        while True:
            url = self.faculty_url if page == 0 else f"{self.faculty_url}?page={page}"
            soup = self.get_soup(url)
            rows = soup.select("div.tablefield tbody tr")
            if not rows:
                break
            for row in rows:
                name_link = row.select_one('td.views-field-field-first-name a[href*="/people/faculty/"]')
                if name_link is None:
                    continue
                slug = name_link.get("href")
                name = _format_name(name_link.get_text(" ", strip=True))
                email_el = row.select_one('td.views-field-field-first-name a[href^="mailto:"]')
                email = email_el.get("href", "").replace("mailto:", "") if email_el else ""
                profiles.setdefault(
                    slug,
                    {
                        "name": name,
                        "title": "",
                        "email": email,
                        "profile_url": urljoin(self.faculty_url, slug),
                        "lab_url": "",
                        "research_areas": [],
                        "research_text": "",
                    },
                )
            last = soup.select_one('a[title="Last page"]')
            next_ = soup.select_one('a[rel="next"]')
            if last:
                last_page = int(last.get("href", "").split("page=")[-1])
            elif next_:
                last_page = page + 1
            else:
                break
            if page >= last_page:
                break
            page += 1

        for profile in profiles.values():
            self._enrich_profile(profile)
        return list(profiles.values())

    def _enrich_profile(self, profile):
        if not profile["profile_url"]:
            return
        soup = self.get_soup(profile["profile_url"])
        title_el = soup.select_one("article.person-full p strong")
        profile["title"] = title_el.get_text(" ", strip=True) if title_el else ""
        email_el = soup.select_one("article.person-full span.email")
        if email_el:
            profile["email"] = email_el.get_text(" ", strip=True)
        web_el = soup.select_one("article.person-full span.web a")
        if web_el:
            profile["lab_url"] = web_el.get("href", "")
        areas = [
            a.get_text(" ", strip=True)
            for a in soup.select('article.person-full a[href*="/research/research-areas/"]')
        ]
        profile["research_areas"] = areas
        statement = soup.select_one("article.person-full h2")
        text_parts = []
        if statement:
            node = statement.find_next_sibling()
            while node is not None and node.name != "h2":
                if node.name == "p":
                    text_parts.append(node.get_text(" ", strip=True))
                node = node.find_next_sibling()
        profile["research_text"] = " ".join(text_parts).strip()
