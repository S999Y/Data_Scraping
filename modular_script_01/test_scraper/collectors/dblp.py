"""
DBLP collector - find the author's DBLP page, then list their publications
(title, venue, year, DOI, authors) from the official person XML feed.

Free API, no key required.
"""

import logging
import re
import xml.etree.ElementTree as ET

from .base import BaseCollector

logger = logging.getLogger(__name__)

AUTHOR_SEARCH = 'https://dblp.org/search/author/api'
PUBL_SEARCH = 'https://dblp.org/search/publ/api'
PID_XML = 'https://dblp.org/pid/{pid}.xml'


def _pid_from_url(url: str) -> str:
    m = re.search(r'/pid/([\w/]+?)(?:\.html)?$', url)
    if not m:
        return ''
    return m.group(1)


class DblpCollector(BaseCollector):
    source = 'dblp'

    def _find_pid(self, name: str) -> str:
        data = self.get_json(AUTHOR_SEARCH, {'q': name, 'format': 'json', 'h': 20})
        hits = (((data.get('result') or {}).get('hits') or {}).get('hit') or [])
        wanted = re.sub(r'\s+', ' ', name.strip().lower())
        for hit in hits:
            info = (hit.get('info') or {})
            author = (info.get('author') or '').strip()
            if re.sub(r'\s+', ' ', author.lower()) == wanted:
                return _pid_from_url(info.get('url') or '')
        for hit in hits:
            info = (hit.get('info') or {})
            author = (info.get('author') or '').strip()
            if (wanted.split(' ')[-1] in author.lower()
                    and wanted.split(' ')[0] in author.lower()):
                return _pid_from_url(info.get('url') or '')
        return ''

    def _pubs_by_pid(self, pid: str) -> list:
        xml_text = self.get_text(PID_XML.format(pid=pid), use_cache=False)
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning('[dblp] could not parse XML for %s: %s', pid, e)
            return []

        pubs = []
        for rec in root.iter('r'):
            authors = [a.text for a in rec.findall('author') if a.text]
            title = (rec.findtext('title') or '').strip()
            if not title:
                continue
            venue = (rec.findtext('venue')
                     or rec.findtext('journal')
                     or rec.findtext('booktitle') or '').strip()
            doi = (rec.findtext('doi') or '').strip()
            ee = (rec.findtext('ee') or '').strip()
            pubs.append({
                'title': title,
                'abstract': '',
                'keywords': [],
                'authors': authors,
                'venue': venue,
                'year': _int_or_none(rec.findtext('year')),
                'citations': None,
                'doi': doi,
                'url': ee,
            })
        return pubs

    def _pubs_by_name(self, name: str) -> list:
        data = self.get_json(PUBL_SEARCH, {'q': f'author:{name}:', 'format': 'json', 'h': 100})
        hits = (((data.get('result') or {}).get('hits') or {}).get('hit') or [])
        pubs = []
        for hit in hits:
            info = (hit.get('info') or {})
            authors = []
            raw_auth = info.get('authors') or {}
            for a in (raw_auth.get('author') or []):
                if isinstance(a, str):
                    authors.append(a)
                elif isinstance(a, dict):
                    authors.append(a.get('text') or a.get('_') or '')
            if not authors and isinstance(raw_auth.get('author'), str):
                authors = [raw_auth['author']]
            pubs.append({
                'title': info.get('title') or '',
                'abstract': '',
                'keywords': [],
                'authors': authors,
                'venue': info.get('venue') or info.get('journal') or '',
                'year': _int_or_none(info.get('year')),
                'citations': None,
                'doi': info.get('doi') or '',
                'url': info.get('url') or '',
            })
        return pubs

    def collect(self, name: str) -> dict:
        result = self.empty_result(name)
        pid = self._find_pid(name)
        if pid:
            result['dblp_pid'] = pid
            pubs = self._pubs_by_pid(pid)
            if pubs:
                result['publications'] = pubs
                result['total_publications'] = len(pubs)
                return result
        pubs = self._pubs_by_name(name)
        if pubs:
            result['publications'] = pubs
            result['total_publications'] = len(pubs)
        return result


def _int_or_none(value):
    if value is None:
        return None
    m = re.search(r'\d{4}', str(value))
    return int(m.group()) if m else None
