"""
ScholarScraper - loads a Google Scholar profile page and extracts every
available data point using the single SCHOLAR_CONFIG.

Before extracting publications it first FULLY LOADS the paper list by
replicating the browser's "Show more" POST requests (cstart/pagesize +
xsrf), so the entire list is captured, not just the first page.
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .config import SCHOLAR_CONFIG

logger = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
SCHOLAR_BASE = 'https://scholar.google.com/citations'


class ScholarScraper:
    """Extract everything from a Google Scholar citations profile page."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or SCHOLAR_CONFIG
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    # ------------------------------------------------------------------
    # Low-level extraction engine (single config format)
    # ------------------------------------------------------------------

    def _resolve_elements(self, scope, selector):
        if 'css' in selector:
            return scope.select(selector['css'])
        if 'find' in selector:
            res = selector['find'](scope)
            if res is None:
                return []
            return res if isinstance(res, list) else [res]
        if 'find_all' in selector:
            return list(selector['find_all'](scope))
        if 'tag' in selector:
            kwargs = {}
            if 'class' in selector:
                kwargs['class_'] = selector['class']
            if 'id' in selector:
                kwargs['id'] = selector['id']
            return scope.find_all(selector['tag'], **kwargs)
        return []

    def _extract_value(self, el, selector, etype, rule=None):
        rule = rule or {}
        if etype == 'text':
            import re as _re
            return _re.sub(r'\s+', ' ', el.get_text(strip=True)).strip()
        if etype == 'attribute':
            return el.get(selector.get('attribute') or rule.get('attribute') or 'href', '')
        if etype == 'html':
            return str(el)
        if etype == 'custom':
            fn = rule.get('function') or selector.get('function')
            return fn(el) if fn else None
        return None

    def extract_field(self, scope, rule):
        selector = rule.get('selector', {})
        etype = rule.get('type', 'text')
        multiple = rule.get('multiple', False)
        index = rule.get('index')
        default = rule.get('default')
        try:
            elements = self._resolve_elements(scope, selector)
            if index is not None and elements:
                elements = [elements[index]]
            if not elements:
                return [] if multiple else default
            if multiple:
                return [self._extract_value(el, selector, etype, rule) for el in elements]
            return self._extract_value(elements[0], selector, etype, rule)
        except Exception as e:
            logger.error(f"Error extracting '{rule.get('field')}': {e}")
            return [] if multiple else default

    def extract_section(self, scope, section, use_container: bool = True) -> List[Dict]:
        extractors = section.get('extractors', [])
        if use_container and section.get('container'):
            containers = self._resolve_elements(scope, section['container'])
        else:
            containers = [scope]

        rows = []
        for container in containers:
            row = {}
            for rule in extractors:
                if rule.get('type') == 'derived':
                    continue
                row[rule['field']] = self.extract_field(container, rule)
            for rule in extractors:
                if rule.get('type') == 'derived':
                    row[rule['field']] = rule['function'](row)
            rows.append(row)
        return rows

    def _section_defaults(self, section) -> Dict:
        defaults = {}
        for rule in section.get('extractors', []):
            defaults[rule['field']] = [] if rule.get('multiple') else None
        return defaults

    # ------------------------------------------------------------------
    # Google Scholar helpers
    # ------------------------------------------------------------------

    def _params(self, url: str):
        qs = parse_qs(urlparse(url).query)
        user = qs.get('user', [''])[0]
        hl = qs.get('hl', ['en'])[0]
        sortby = qs.get('sortby', ['pubdate'])[0]
        return user, hl, sortby

    def _list_url(self, url: str) -> str:
        user, hl, sortby = self._params(url)
        return f'{SCHOLAR_BASE}?hl={hl}&user={user}&view_op=list_works&sortby={sortby}'

    def _get_soup(self, url: str) -> BeautifulSoup:
        logger.info(f'Fetching: {url}')
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.content, 'html.parser')

    def _pub_rows(self, soup) -> List:
        tbody = soup.find('tbody', id='gsc_a_b')
        if not tbody:
            return []
        return tbody.find_all('tr', class_='gsc_a_tr')

    def _show_more_enabled(self, soup) -> bool:
        btn = soup.find('button', id='gsc_bpf_more')
        if btn is None:
            return False
        return not btn.has_attr('disabled')

    def _row_key(self, tr) -> str:
        a = tr.find('a', class_='gsc_a_at')
        return a.get('href', '') if a else tr.get_text(strip=True)

    # ------------------------------------------------------------------
    # Full loading of the paper list (page-by-page pagination)
    # ------------------------------------------------------------------

    def load_all_publications(self, url: str, batch_size: Optional[int] = None,
                              first_soup: Optional[BeautifulSoup] = None) -> List:
        """Fully load every publication on the profile page before extracting.

        Google Scholar now serves the paper list in pages of `batch_size`
        (100) via GET with `pagesize` + `cstart`; the loop keeps requesting
        the next page until the "Show more" button disappears or no new
        rows come back.
        """
        batch_size = batch_size or self.config.get('batch_size', 100)
        user, hl, sortby = self._params(url)
        if not user:
            raise ValueError('Scholar URL must include user=<profile-id>')

        soup = first_soup or self._get_soup(self._list_url(url))
        rows = self._pub_rows(soup)
        logger.info(f'First page loaded: {len(rows)} publications')

        if not rows or not self._show_more_enabled(soup):
            logger.info('All publications already loaded on the first page.')
            return rows

        delay = self.config.get('delay', 1.5)
        seen = {self._row_key(tr) for tr in rows}

        while self._show_more_enabled(soup):
            cstart = len(rows)
            next_url = (self._list_url(url)
                        + f'&pagesize={batch_size}&cstart={cstart}')
            logger.info(f'Loading more publications (cstart={cstart}, pagesize={batch_size})')
            soup = self._get_soup(next_url)

            new_rows = [tr for tr in self._pub_rows(soup) if self._row_key(tr) not in seen]
            if not new_rows:
                logger.warning('Show more returned no new rows; stopping.')
                break
            for tr in new_rows:
                seen.add(self._row_key(tr))
            rows.extend(new_rows)
            logger.info(f'Loaded {len(rows)} publications total')
            time.sleep(delay)

        return rows

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    def scrape_scholar(self, url: str, output: Optional[str] = None,
                       append: bool = False) -> List[Dict]:
        """Fully load the profile page (live) and extract everything."""
        soup = self._get_soup(self._list_url(url))
        pub_rows = self.load_all_publications(url, first_soup=soup)
        return self._extract_and_save(soup, pub_rows, output=output, append=append, source=url)

    def scrape_from_file(self, html_path: str, output: Optional[str] = None,
                         append: bool = False) -> List[Dict]:
        """Extract everything from a saved HTML file (offline)."""
        with open(html_path, encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        pub_rows = self._pub_rows(soup)
        logger.info(f'Found {len(pub_rows)} publications in {html_path}')
        return self._extract_and_save(soup, pub_rows, output=output, append=append, source=html_path)

    def collect_data(self, url: Optional[str] = None,
                     html_path: Optional[str] = None) -> Dict[str, Any]:
        """Collect profile + publications as a dict without saving anything.

        Returns {'profile': {...}, 'publications': [...]}.  Provide exactly
        one of `url` (live load, fully paginated) or `html_path` (offline).
        """
        if html_path:
            with open(html_path, encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            pub_rows = self._pub_rows(soup)
        elif url:
            soup = self._get_soup(self._list_url(url))
            pub_rows = self.load_all_publications(url, first_soup=soup)
        else:
            raise ValueError('Provide either url or html_path')

        base, records = self._collect(soup, pub_rows)
        return {'profile': base, 'publications': records}

    def _collect(self, soup, pub_rows) -> Tuple[Dict, List[Dict]]:
        sections = self.config['sections']

        base = {}
        for key, section in sections.items():
            if key == 'publications':
                continue
            results = self.extract_section(soup, section)
            merged = results[0] if results else self._section_defaults(section)
            base.update(merged)

        if not (base.get('total_articles') or 0) or base['total_articles'] < len(pub_rows):
            base['total_articles'] = len(pub_rows)

        records = []
        for idx, tr in enumerate(pub_rows):
            record = dict(base)
            pub = self.extract_section(tr, sections['publications'], use_container=False)
            if pub:
                record.update(pub[0])
            record['paper_index'] = idx
            records.append(record)

        if not records:
            records = [dict(base)]
            logger.warning('No publications found; returning a single profile-only row.')

        return base, records

    def _extract_and_save(self, soup, pub_rows, output=None, append=False, source='') -> List[Dict]:
        base, records = self._collect(soup, pub_rows)

        professor = base.get('name') or base.get('user_id') or 'unknown'
        path = self._write(records, professor, append=append, output=output)
        logger.info(f'Extracted {len(records)} rows from {source} -> {path}')
        return records

    # ------------------------------------------------------------------
    # Output / saving
    # ------------------------------------------------------------------

    def _to_frame(self, records: List[Dict]) -> pd.DataFrame:
        df = pd.DataFrame(records)
        for col in df.columns:
            df[col] = df[col].apply(lambda v: '; '.join(str(x) for x in v) if isinstance(v, list) else v)
        return df

    def _write(self, records: List[Dict], professor_name: str,
               append: bool = False, output: Optional[str] = None) -> str:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(root, 'datasets', 'scholars')
        os.makedirs(out_dir, exist_ok=True)

        if output:
            path = output if output.endswith('.csv') else f'{output}.csv'
        elif append:
            path = os.path.join(out_dir, 'professor_details.csv')
        else:
            slug = re.sub(r'[^\w]+', '_', professor_name or 'unknown').strip('_') or 'unknown'
            path = os.path.join(out_dir, f'{slug}.csv')

        df = self._to_frame(records)
        exists = os.path.exists(path)
        df.to_csv(path, index=False, encoding='utf-8-sig',
                  mode='a' if (append and exists) else 'w',
                  header=not (append and exists))
        logger.info(f'Saved {len(df)} rows to {path}')
        return path
