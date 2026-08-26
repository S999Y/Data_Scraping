"""
OpenAlex collector - search authors by name and pull profile metrics,
affiliation, topics and the top-cited publications.

Free API with usage-based pricing. An API key is required for production use
and provides 10x the daily budget (100,000 credits/day vs 10,000 without).
"""

import logging
import math
import re

from .base import BaseCollector

logger = logging.getLogger(__name__)

AUTHOR_SEARCH = 'https://api.openalex.org/authors'
AUTHOR_DETAIL = 'https://api.openalex.org/authors/{id}'
WORKS = 'https://api.openalex.org/works'


def _tokens(name: str) -> set:
    """Lowercase letter-tokens, dropping single-letter initials like 'E'."""
    return {t for t in re.split(r'[^a-z]+', name.lower()) if len(t) > 1}


_INST_GENERIC = {
    'university', 'college', 'institute', 'system', 'state', 'of', 'the',
    'and', 'school', 'univ', 'campus', 'at', 'technology', 'sciences',
    'engineering', 'research',
}


def _inst_tokens(name: str) -> set:
    """Distinctive institution tokens, ignoring generic words like 'university'."""
    return {t for t in re.split(r'[^a-z0-9]+', (name or '').lower())
            if len(t) > 3 and t not in _INST_GENERIC}


def _author_institution_tokens(author: dict) -> set:
    """Union of distinctive tokens across an author's known institutions."""
    tokens = set()
    for inst in (author.get('last_known_institutions') or []):
        tokens |= _inst_tokens(inst.get('display_name') or '')
    for aff in (author.get('affiliations') or []):
        tokens |= _inst_tokens((aff.get('institution') or {}).get('display_name') or '')
    return tokens


def _author_last_inst_tokens(author: dict) -> set:
    """Distinctive tokens of the author's *current* institutions only."""
    tokens = set()
    for inst in (author.get('last_known_institutions') or []):
        tokens |= _inst_tokens(inst.get('display_name') or '')
    return tokens


def reconstruct_abstract(inverted_index) -> str:
    """OpenAlex stores abstracts as word -> [positions]; rebuild the text."""
    if not inverted_index:
        return ''
    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))
    words.sort()
    return ' '.join(word for _, word in words)


class OpenAlexCollector(BaseCollector):
    source = 'openalex'

    def _search_authors(self, name: str, university_hint: str = None) -> list:
        params = {
            'filter': f'display_name.search:{name}', 'per-page': 25,
        }
        if self.api_key:
            params['api_key'] = self.api_key
        data = self.get_json(AUTHOR_SEARCH, params)
        results = data.get('results') or []
        if not results:
            params2 = {'search': name, 'per-page': 25}
            if self.api_key:
                params2['api_key'] = self.api_key
            data = self.get_json(AUTHOR_SEARCH, params2)
            results = data.get('results') or []
        if not results:
            return []
        wanted = _tokens(name)
        first = name.split()[0].lower()
        last = name.split()[-1].lower()
        hint = _inst_tokens(university_hint) if university_hint else set()
        scored = []
        for i, r in enumerate(results):
            display = _tokens(r.get('display_name') or '')
            score = 0.0
            if display and display == wanted:
                score += 100
            if last in display:
                score += 20
            if first in display:
                score += 10
            last_overlap = bool(hint) and bool(
                hint & _author_last_inst_tokens(r))
            aff_overlap = bool(hint) and bool(
                hint & _author_institution_tokens(r))
            if last_overlap:
                # hard preference: an author whose *current* institution is
                # the hinted university wins over a highly-cited same-name
                # author from another school
                score += 2000
            elif aff_overlap:
                score += 300
            # productivity tie-breaker: prefer the more established author
            score += math.log10((r.get('works_count') or 1) + 1) * 3
            # keep OpenAlex's relevance ordering as a tiny bonus
            score += (10 - i) / 10
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored]

    def _affiliation(self, author: dict) -> dict:
        insts = list(author.get('last_known_institutions') or [])
        insts.sort(key=lambda i: i.get('type') != 'education')
        for inst in insts:
            name = (inst.get('display_name') or '')
            country = (inst.get('country_code') or '')
            if name:
                return {'university': name, 'country': country}
        for inst in (author.get('affiliations') or []):
            name = ((inst.get('institution') or {}).get('display_name') or '')
            if name:
                return {'university': name,
                        'country': (inst.get('country_code') or '')}
        return {'university': '', 'country': ''}

    def _works(self, author_id: str) -> list:
        params = {
            'filter': f'author.id:{author_id}', 'per-page': 25,
            'sort': 'cited_by_count:desc',
        }
        if self.api_key:
            params['api_key'] = self.api_key
        data = self.get_json(WORKS, params)
        pubs = []
        for w in (data.get('results') or []):
            authors = []
            for a in (w.get('authorships') or []):
                auth = (a.get('author') or {}).get('display_name')
                if auth:
                    authors.append(auth)
            venue = ''
            loc = w.get('primary_location') or {}
            src = loc.get('source') or {}
            if isinstance(src, dict):
                venue = src.get('display_name') or ''
            topics = [t.get('display_name') for t in (w.get('topics') or [])
                      if isinstance(t, dict) and t.get('display_name')]
            pubs.append({
                'title': w.get('title') or '',
                'abstract': reconstruct_abstract(w.get('abstract_inverted_index')),
                'keywords': topics[:5],
                'authors': authors,
                'venue': venue,
                'year': w.get('publication_year'),
                'citations': w.get('cited_by_count'),
                'doi': w.get('doi') or '',
                'url': w.get('id') or '',
            })
        return pubs

    def collect(self, name: str, university_hint: str = None) -> dict:
        result = self.empty_result(name)
        candidates = self._search_authors(name, university_hint=university_hint)
        if not candidates:
            logger.info('[openalex] no author match for %s', name)
            return result

        author = candidates[0]
        author_id = author.get('id') or ''
        result['openalex_id'] = author_id
        result['name'] = author.get('display_name') or name
        result['orcid'] = author.get('orcid') or ''

        aff = self._affiliation(author)
        result['university'] = aff['university']
        result['country'] = aff['country']

        topics = [t.get('display_name') for t in (author.get('topics') or [])
                  if isinstance(t, dict) and t.get('display_name')]
        result['topics'] = topics[:8]

        stats = author.get('summary_stats') or {}
        result['total_citations'] = stats.get('cited_by_count')
        result['h_index'] = stats.get('h_index')
        result['i10_index'] = stats.get('i10_index')
        result['total_publications'] = author.get('works_count')

        if author_id:
            detail_params = {}
            if self.api_key:
                detail_params['api_key'] = self.api_key
            detail = self.get_json(AUTHOR_DETAIL.format(id=author_id),
                                   params=detail_params if detail_params else None)
            if detail.get('display_name'):
                topics = [t.get('display_name') for t in (detail.get('topics') or [])
                          if isinstance(t, dict) and t.get('display_name')]
                if topics:
                    result['topics'] = topics[:8]
                result['works_api_url'] = detail.get('works_api_url') or ''
                result['updated_date'] = detail.get('updated_date') or ''
                if result['total_citations'] is None:
                    result['total_citations'] = detail.get('cited_by_count')
                if not result['total_publications']:
                    result['total_publications'] = detail.get('works_count')

        result['publications'] = self._works(author_id) if author_id else []
        return result
