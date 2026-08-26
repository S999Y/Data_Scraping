"""UCLA Samueli: faculty search page renders results via a JS click -> AJAX admin-ajax.php.

We load the search-faculty page, select the Computer Science department, click
Search, wait for results, and parse article.card blocks.
"""

import time

from bs4 import BeautifulSoup

from .base import USER_AGENT, BaseScraper, _get_js_session


class UCLAScraper(BaseScraper):
    def scrape(self):
        browser = _get_js_session()["browser"]
        page = browser.new_page(user_agent=USER_AGENT)
        try:
            target = self.faculty_url.rstrip("/")
            if not target.endswith("/faculty"):
                target = "https://www.cs.ucla.edu/faculty/"
            page.goto(target, timeout=90000, wait_until="domcontentloaded")
            page.wait_for_selector("#sp_search_button", state="attached", timeout=60000)
            page.wait_for_timeout(3000)
            try:
                page.evaluate(
                    """() => {
                        const lis = document.querySelectorAll('.search_dropdown ul li');
                        for (const li of lis) {
                            if (li.getAttribute('dept') === 'cs') { li.click(); }
                        }
                    }"""
                )
                page.wait_for_timeout(800)
                page.click("#sp_search_button")
            except Exception:
                page.evaluate(
                    """() => {
                        document.querySelector('#sp_search_button').click();
                    }"""
                )
                page.wait_for_timeout(800)
            page.wait_for_selector("#sp-resulthere article.card", timeout=60000)
            page.wait_for_timeout(4000)
            html = page.content()
        finally:
            page.close()

        soup = BeautifulSoup(html, "lxml")
        out = []
        seen = set()
        for card in soup.select("#sp-resulthere article.card"):
            name_el = card.select_one("h4.people-title a")
            if not name_el:
                continue
            name = name_el.get_text(" ", strip=True)
            if not name or name in seen:
                continue
            title_el = card.select_one("p i")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            email_el = card.select_one("a.mailto-link")
            email = email_el.get("href", "").replace("mailto:", "") if email_el else ""
            profile = name_el.get("href", "")
            seen.add(name)
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
        time.sleep(self.delay)
        return out
