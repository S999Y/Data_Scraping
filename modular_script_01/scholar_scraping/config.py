"""
Google Scholar - single comprehensive configuration.

Extracts every data point available on a Google Scholar citations
profile page (view_op=list_works):
  * page metadata (title, meta description, user id, total articles)
  * profile header (name, affiliation, organization, email, homepage,
    interests, photo)
  * citation metrics (citations / h-index / i10-index x all + since)
  * citation histogram (per-year counts)
  * public access stats
  * the full publication list (title, url, authors, venue, year,
    citation count, citation url)
  * co-authors (name, url, affiliation, verified email)

Designed to be used ONLY with Google Scholar profiles via ScholarScraper.
"""

import re
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse


# ---------------------------------------------------------------------------
# Small helper functions used by the config's custom extractors
# ---------------------------------------------------------------------------

def _text(el) -> str:
    if el is None:
        return ''
    return re.sub(r'\s+', ' ', el.get_text(strip=True)).strip()


def _num(el, default=None):
    if el is None:
        return default
    m = re.search(r'\d[\d,]*', _text(el))
    if not m:
        return default
    return int(m.group().replace(',', ''))


def _user_id(href: str) -> str:
    qs = parse_qs(urlparse(href).query)
    return qs.get('user', [''])[0]


def _last_number(el):
    if el is None:
        return None
    nums = re.findall(r'\d+', _text(el))
    return int(nums[-1]) if nums else None


def _strip_year(el) -> str:
    if el is None:
        return ''
    return re.sub(r',\s*\d{4}\s*$', '', _text(el))


def _td_std(el, idx):
    if el is None:
        return None
    tds = el.find_all('td', class_='gsc_rsb_std')
    return tds[idx] if idx < len(tds) else None


def _make_std_field(name: str, idx: int) -> Dict:
    return {
        'field': name,
        'selector': {'find': lambda el, i=idx: _td_std(el, i)},
        'type': 'custom',
        'function': lambda el: _num(el),
    }


def _make_gray_field(name: str, idx: int, fn) -> Dict:
    return {
        'field': name,
        'selector': {'find': lambda el: el.find_all('div', class_='gs_gray')},
        'index': idx,
        'type': 'custom',
        'function': fn,
    }


# ---------------------------------------------------------------------------
# Single configuration - everything on the Scholar profile page
# ---------------------------------------------------------------------------

SCHOLAR_CONFIG: Dict[str, Any] = {
    'name': 'Google Scholar - Complete Profile',
    'batch_size': 100,
    'delay': 1.5,
    'sections': {

        # ---- page metadata -------------------------------------------------
        'page': {
            'extractors': [
                {
                    'field': 'page_title',
                    'selector': {'tag': 'title'},
                    'type': 'text',
                    'default': '',
                },
                {
                    'field': 'meta_description',
                    'selector': {
                        'find': lambda s: s.find('meta', attrs={'name': 'description'}),
                        'attribute': 'content',
                    },
                    'type': 'attribute',
                    'default': '',
                },
                {
                    'field': 'user_id',
                    'selector': {'find': lambda s: s.find('link', rel='canonical')},
                    'type': 'custom',
                    'function': lambda el: _user_id(el.get('href', '') if el else ''),
                    'default': '',
                },
                {
                    'field': 'total_articles',
                    'selector': {'find': lambda s: s.find('span', id='gsc_a_nn')},
                    'type': 'custom',
                    'function': lambda el: _last_number(el),
                },
            ],
        },

        # ---- profile header -------------------------------------------------
        'profile': {
            'container': {'tag': 'div', 'id': 'gsc_prf'},
            'extractors': [
                {
                    'field': 'name',
                    'selector': {'tag': 'div', 'id': 'gsc_prf_in'},
                    'type': 'text',
                    'default': '',
                },
                {
                    'field': 'affiliation',
                    'selector': {'find': lambda el: el.find('div', class_='gsc_prf_il')},
                    'type': 'custom',
                    'function': lambda el: _text(el),
                },
                {
                    'field': 'organization',
                    'selector': {'find': lambda el: el.find_all('a', class_='gsc_prf_ila')},
                    'index': 0,
                    'type': 'custom',
                    'function': lambda el: _text(el),
                },
                {
                    'field': 'org_url',
                    'selector': {'find': lambda el: el.find_all('a', class_='gsc_prf_ila')},
                    'index': 0,
                    'type': 'attribute',
                    'attribute': 'href',
                    'default': '',
                },
                {
                    'field': 'verified_email',
                    'selector': {'find': lambda el: el.find('div', id='gsc_prf_ivh')},
                    'type': 'custom',
                    'function': lambda el: (_text(el).split('-')[0].strip() if el else ''),
                },
                {
                    'field': 'homepage_url',
                    'selector': {
                        'find': lambda el: (el.find('div', id='gsc_prf_ivh') or el).find('a')
                    },
                    'type': 'attribute',
                    'attribute': 'href',
                    'default': '',
                },
                {
                    'field': 'interests',
                    'selector': {'find': lambda el: el.find('div', id='gsc_prf_int')},
                    'type': 'custom',
                    'function': lambda el: [a.get_text(strip=True) for a in el.find_all('a')] if el else [],
                },
                {
                    'field': 'photo_url',
                    'selector': {'tag': 'img', 'id': 'gsc_prf_pup-img', 'attribute': 'src'},
                    'type': 'attribute',
                    'default': '',
                },
            ],
        },

        # ---- citation metrics -------------------------------------------------
        'metrics': {
            'container': {'tag': 'table', 'id': 'gsc_rsb_st'},
            'extractors': [
                _make_std_field('citations_all', 0),
                _make_std_field('citations_since', 1),
                _make_std_field('h_index_all', 2),
                _make_std_field('h_index_since', 3),
                _make_std_field('i10_index_all', 4),
                _make_std_field('i10_index_since', 5),
            ],
        },

        # ---- citation histogram -------------------------------------------------
        'histogram': {
            'extractors': [
                {
                    'field': 'histogram_years',
                    'selector': {'find_all': lambda s: s.find_all('span', class_='gsc_g_t')},
                    'multiple': True,
                    'type': 'text',
                },
                {
                    'field': 'histogram_counts',
                    'selector': {'find_all': lambda s: s.find_all('span', class_='gsc_g_al')},
                    'multiple': True,
                    'type': 'custom',
                    'function': lambda el: _num(el),
                },
                {
                    'field': 'citation_history',
                    'type': 'derived',
                    'function': lambda row: '; '.join(
                        f'{y}:{c}'
                        for y, c in zip(row.get('histogram_years') or [],
                                        row.get('histogram_counts') or [])
                    ),
                },
            ],
        },

        # ---- public access -------------------------------------------------
        'public_access': {
            'container': {'tag': 'div', 'id': 'gsc_rsb_mnd'},
            'extractors': [
                {
                    'field': 'articles_available',
                    'selector': {'find': lambda el: el.find_all('div', class_='gsc_rsb_m_a')},
                    'index': 0,
                    'type': 'custom',
                    'function': lambda el: _num(el),
                },
                {
                    'field': 'articles_not_available',
                    'selector': {'find': lambda el: el.find_all('div', class_='gsc_rsb_m_na')},
                    'index': 0,
                    'type': 'custom',
                    'function': lambda el: _num(el),
                },
            ],
        },

        # ---- publications (repeated per paper) ---------------------------------
        'publications': {
            'container': {'tag': 'tr', 'class': 'gsc_a_tr'},
            'extractors': [
                {
                    'field': 'paper_title',
                    'selector': {'tag': 'a', 'class': 'gsc_a_at'},
                    'type': 'text',
                    'required': True,
                    'default': '',
                },
                {
                    'field': 'paper_url',
                    'selector': {'tag': 'a', 'class': 'gsc_a_at', 'attribute': 'href'},
                    'type': 'attribute',
                    'default': '',
                },
                {
                    'field': 'authors',
                    'selector': {'find': lambda el: el.find('div', class_='gs_gray')},
                    'type': 'custom',
                    'function': lambda el: _text(el),
                },
                _make_gray_field('venue_full', 1, lambda el: _text(el)),
                _make_gray_field('venue', 1, lambda el: _strip_year(el)),
                {
                    'field': 'year',
                    'selector': {'tag': 'span', 'class': 'gsc_a_h'},
                    'type': 'text',
                    'default': '',
                },
                {
                    'field': 'year',
                    'type': 'derived',
                    'function': lambda row: (row.get('year') or
                        re.search(r'\b(19|20)\d{2}\b', row.get('venue_full') or '').group(0)
                        if not (row.get('year') or '') and re.search(r'\b(19|20)\d{2}\b', row.get('venue_full') or '')
                        else row.get('year') or ''),
                },
                {
                    'field': 'citations',
                    'selector': {'tag': 'a', 'class': 'gsc_a_ac'},
                    'type': 'custom',
                    'function': lambda el: _num(el),
                },
                {
                    'field': 'citations_url',
                    'selector': {'tag': 'a', 'class': 'gsc_a_ac', 'attribute': 'href'},
                    'type': 'attribute',
                    'default': '',
                },
            ],
        },

        # ---- co-authors (not present in some saved pages) ------------------------
        'coauthors': {
            'container': {'tag': 'ul', 'class': 'gsc_rsb_a'},
            'extractors': [
                {
                    'field': 'coauthor_names',
                    'selector': {'find_all': lambda el: el.find_all('li')},
                    'multiple': True,
                    'type': 'custom',
                    'function': lambda li: _text(li.find('a')),
                },
                {
                    'field': 'coauthor_urls',
                    'selector': {'find_all': lambda el: el.find_all('li')},
                    'multiple': True,
                    'type': 'custom',
                    'function': lambda li: li.find('a').get('href', '') if li.find('a') else '',
                },
                {
                    'field': 'coauthor_affiliations',
                    'selector': {'find_all': lambda el: el.find_all('li')},
                    'multiple': True,
                    'type': 'custom',
                    'function': lambda li: _text(li.find('span', class_='gsc_rsb_a_ext')),
                },
                {
                    'field': 'coauthor_emails',
                    'selector': {'find_all': lambda el: el.find_all('li')},
                    'multiple': True,
                    'type': 'custom',
                    'function': lambda li: _text(li.find('span', class_='gsc_rsb_a_ext2')),
                },
            ],
        },
    },
}
