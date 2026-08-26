"""
Faculty-page collector - wraps the existing modular_scraping.scrape_faculty_page
so a university faculty listing becomes a pipeline source.

In single-professor mode the collector extracts the listing rows and keeps the
row(s) matching the requested name.  In batch mode the pipeline can also hand
over rows already read from datasets/faculty/*.csv via `faculty_rows`.
"""

import logging

from .base import BaseCollector

logger = logging.getLogger(__name__)

try:
    from modular_scraping.configs import get_config
    from modular_scraping.faculty import scrape_faculty_page
except ImportError:
    get_config = None
    scrape_faculty_page = None


class FacultyCollector(BaseCollector):
    source = 'faculty'

    def collect(self, name: str = '', url: str = None, config_key: str = None,
                faculty_rows: list = None, faculty_url: str = None,
                faculty_config: str = None) -> dict:
        result = self.empty_result(name or url or '')
        url = url or faculty_url
        config_key = config_key or faculty_config

        if faculty_rows:
            matched = [r for r in faculty_rows
                       if _names_overlap(name, r.get('name') or '')]
            rows = matched if name else faculty_rows
            return self._from_rows(rows, name, result)

        if url and config_key and scrape_faculty_page is not None:
            config = get_config(config_key) if get_config else None
            if not config:
                logger.warning('[faculty] unknown config key: %s', config_key)
                return result
            try:
                rows = scrape_faculty_page(url, config, output=None)
            except Exception as e:
                logger.warning('[faculty] scrape failed: %s', e)
                return result
            return self._from_rows(rows, name, result)

        return result

    def _from_rows(self, rows: list, name: str, result: dict) -> dict:
        if not rows:
            return result
        row = rows[0]
        result['name'] = row.get('name') or name
        result['university'] = row.get('university_name') or ''
        result['position'] = row.get('designation') or row.get('title') or ''
        result['department'] = row.get('department') or ''
        result['bio'] = row.get('summary') or row.get('bio') or ''
        result['profile_url'] = row.get('profile_url') or row.get('url') or ''
        result['email'] = row.get('email') or ''
        result['research_areas'] = row.get('research_areas') or ''
        result['source_url'] = row.get('source_url') or ''
        result['matches'] = len(rows)
        return result


def _names_overlap(a: str, b: str) -> bool:
    a_tokens = {t.lower() for t in a.replace(',', ' ').split() if len(t) > 2}
    b_tokens = {t.lower() for t in b.replace(',', ' ').split() if len(t) > 2}
    return bool(a_tokens & b_tokens)
