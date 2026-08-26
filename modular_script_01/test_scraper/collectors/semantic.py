"""
Semantic Scholar collector - search for the author, then fetch the full
author record with affiliations, metrics and papers.

Free API, no key required (unauthenticated rate limit applies).
"""

import logging

from .base import BaseCollector

logger = logging.getLogger(__name__)

AUTHOR_SEARCH = 'https://api.semanticscholar.org/graph/v1/author/search'
AUTHOR_DETAIL = 'https://api.semanticscholar.org/graph/v1/author/{id}'

PAPER_FIELDS = ','.join(f'papers.{f}' for f in
                        'title,year,venue,citationCount,abstract,externalIds'.split(','))
AUTHOR_FIELDS = ('name,affiliations,paperCount,citationCount,hIndex,url,' + PAPER_FIELDS)


class SemanticScholarCollector(BaseCollector):
    source = 'semantic'

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('delay', 1.0)
        super().__init__(*args, **kwargs)

    def _search(self, name: str) -> list:
        data = self.get_json(AUTHOR_SEARCH, {'query': name, 'limit': 10})
        return data.get('data') or []

    def _detail(self, author_id: str) -> dict:
        return self.get_json(
            AUTHOR_DETAIL.format(id=author_id), {'fields': AUTHOR_FIELDS})

    def collect(self, name: str) -> dict:
        result = self.empty_result(name)
        candidates = self._search(name)
        if not candidates:
            logger.info('[semantic] no author match for %s', name)
            return result

        best = candidates[0]
        author_id = best.get('authorId')
        result['semantic_id'] = author_id
        result['name'] = best.get('name') or name
        result['university'] = best.get('affiliation') or ''
        result['total_publications'] = best.get('paperCount')
        result['total_citations'] = best.get('citationCount')
        result['h_index'] = best.get('hIndex')
        result['url'] = best.get('url') or ''

        if not author_id:
            return result

        detail = self._detail(author_id)
        result['name'] = detail.get('name') or result['name']
        if detail.get('affiliations'):
            result['university'] = '; '.join(detail['affiliations'])
        result['total_publications'] = detail.get('paperCount') or result['total_publications']
        result['total_citations'] = detail.get('citationCount') or result['total_citations']
        result['h_index'] = detail.get('hIndex') or result['h_index']
        result['url'] = detail.get('url') or result['url']
        interests = [i for i in (detail.get('interests') or []) if i]
        result['interests'] = interests

        pubs = []
        for p in (detail.get('papers') or []):
            ids = p.get('externalIds') or {}
            doi = ids.get('DOI') or ''
            url = ids.get('ArXiv') or ids.get('CorpusId') or ''
            pubs.append({
                'title': p.get('title') or '',
                'abstract': p.get('abstract') or '',
                'keywords': [],
                'authors': [],
                'venue': p.get('venue') or '',
                'year': p.get('year'),
                'citations': p.get('citationCount'),
                'doi': doi,
                'url': str(url),
            })
        result['publications'] = pubs
        return result
