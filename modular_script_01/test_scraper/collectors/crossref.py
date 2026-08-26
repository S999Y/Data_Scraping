"""
Crossref collector - find recent works where the person appears as an
author.  Useful for publication-level detail (title, DOI, venue, year,
abstract) rather than profile metrics.
"""

import logging
import re

from .base import BaseCollector

logger = logging.getLogger(__name__)

WORKS_URL = 'https://api.crossref.org/works'


def _author_tokens(name: str) -> list:
    return [t for t in re.split(r'[\s.,-]+', name.lower()) if len(t) > 1]


class CrossrefCollector(BaseCollector):
    source = 'crossref'

    def _works(self, name: str) -> list:
        data = self.get_json(WORKS_URL, {
            'query.author': name,
            'rows': 30,
            'select': 'DOI,title,author,container-title,issued,abstract,subject,URL',
        })
        message = data.get('message') or {}
        wanted = set(_author_tokens(name))
        pubs = []
        for item in (message.get('items') or []):
            authors = []
            matches = False
            for a in (item.get('author') or []):
                fam = (a.get('family') or '').lower()
                given = (a.get('given') or '').lower()
                full = f'{given} {fam}'.strip()
                authors.append(' '.join(full.split()))
                if fam and fam in wanted or given and given in wanted:
                    matches = True
            if not matches:
                continue
            title = ''
            if item.get('title'):
                title = item['title'][0]
            if not title:
                continue
            year = None
            issued = item.get('issued') or {}
            if issued.get('date-parts'):
                parts = issued['date-parts'][0]
                if parts:
                    year = parts[0]
            venue = ''
            if item.get('container-title'):
                venue = item['container-title'][0]
            pubs.append({
                'title': title,
                'abstract': item.get('abstract') or '',
                'keywords': [s for s in (item.get('subject') or [])][:5],
                'authors': authors,
                'venue': venue,
                'year': year,
                'citations': item.get('is-referenced-by-count'),
                'doi': item.get('DOI') or '',
                'url': item.get('URL') or '',
            })
        return pubs

    def collect(self, name: str) -> dict:
        result = self.empty_result(name)
        result['publications'] = self._works(name)
        result['total_publications'] = len(result['publications'])
        return result
