"""
Google Scholar collector - wraps the existing scholar_scraping.ScholarScraper
so the fully-paginated profile extraction is reused as one pipeline source.

Works live (a scholar URL) or offline (a saved HTML fixture).
"""

import logging
import os

from .base import BaseCollector

logger = logging.getLogger(__name__)

try:
    from scholar_scraping.scraper import ScholarScraper
except ImportError:
    ScholarScraper = None


class ScholarCollector(BaseCollector):
    source = 'scholar'

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('delay', 1.5)
        super().__init__(*args, **kwargs)
        self._scraper = None

    def _get_scraper(self):
        if ScholarScraper is None:
            raise RuntimeError('scholar_scraping package is not importable')
        if self._scraper is None:
            self._scraper = ScholarScraper()
        return self._scraper

    def collect(self, name: str = '', url: str = None,
                html_path: str = None, user_id: str = None,
                scholar_url: str = None) -> dict:
        result = self.empty_result(name or url or '')
        scraper = self._get_scraper()
        url = url or scholar_url

        if url and 'user=' not in url and user_id:
            url = f'{url}?user={user_id}'
        if not url and not html_path and user_id:
            url = ('https://scholar.google.com/citations?'
                   f'hl=en&user={user_id}&view_op=list_works')

        try:
            data = scraper.collect_data(url=url, html_path=html_path)
        except Exception as e:
            logger.warning('[scholar] collect failed: %s', e)
            return result

        profile = data.get('profile') or {}
        result['name'] = profile.get('name') or name
        result['affiliation'] = profile.get('affiliation') or ''
        result['organization'] = profile.get('organization') or ''
        result['verified_email'] = profile.get('verified_email') or ''
        result['homepage_url'] = profile.get('homepage_url') or ''
        result['interests'] = profile.get('interests') or []
        result['scholar_user'] = profile.get('user_id') or _user_id_from_pubs(
            data.get('publications') or [])
        result['photo_url'] = profile.get('photo_url') or ''
        result['total_citations'] = profile.get('citations_all')
        result['h_index'] = profile.get('h_index_all')
        result['i10_index'] = profile.get('i10_index_all')
        result['total_publications'] = profile.get('total_articles')
        result['citation_history'] = profile.get('citation_history') or ''
        result['articles_available'] = profile.get('articles_available')
        result['coauthors'] = profile.get('coauthor_names') or []

        pubs = []
        for p in (data.get('publications') or []):
            pubs.append({
                'title': p.get('paper_title') or '',
                'abstract': '',
                'keywords': [],
                'authors': _authors_list(p.get('authors')),
                'venue': p.get('venue') or p.get('venue_full') or '',
                'year': _int_or_none(p.get('year')),
                'citations': _int_or_none(p.get('citations')),
                'doi': '',
                'url': p.get('paper_url') or '',
            })
        result['publications'] = pubs
        return result


def _authors_list(value) -> list:
    if isinstance(value, str):
        return [a.strip() for a in value.split(';') if a.strip()]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _int_or_none(value):
    if value is None:
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _user_id_from_pubs(pubs: list) -> str:
    import re
    for p in pubs:
        url = p.get('url') or p.get('paper_url') or ''
        m = re.search(r'[?&]user=([A-Za-z0-9_-]+)', url)
        if m:
            return m.group(1)
    return ''
