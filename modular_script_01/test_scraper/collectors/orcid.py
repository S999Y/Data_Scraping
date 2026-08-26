"""
ORCID collector - find a person via the public expanded-search API, then
fetch their public record (bio, website, identifiers, works summary).

Free API, no key required.  Accept header must be application/json.
"""

import logging
import re

from .base import BaseCollector

logger = logging.getLogger(__name__)

EXPANDED_SEARCH = 'https://pub.orcid.org/v3.0/expanded-search/'
RECORD_URL = 'https://pub.orcid.org/v3.0/{orcid}/record'

JSON_HEADERS = {'Accept': 'application/json'}


def _split_name(name: str):
    parts = re.split(r'\s+', name.strip())
    if not parts:
        return '', ''
    return parts[0], parts[-1]


class OrcidCollector(BaseCollector):
    source = 'orcid'

    def _search(self, name: str) -> list:
        given, family = _split_name(name)
        query = f'family-name:{family} AND given-names:{given}'
        data = self.get_json(EXPANDED_SEARCH, {'q': query}, headers=JSON_HEADERS)
        results = data.get('expanded-result') or []
        return results

    def _record(self, orcid: str) -> dict:
        return self.get_json(RECORD_URL.format(orcid=orcid), headers=JSON_HEADERS)

    def collect(self, name: str) -> dict:
        result = self.empty_result(name)
        results = self._search(name)
        if not results:
            logger.info('[orcid] no record found for %s', name)
            return result

        best = results[0]
        orcid = best.get('orcid-id') or ''
        result['orcid'] = orcid
        result['name'] = (best.get('given-names') or name)
        institution = best.get('institution-name') or best.get('institution')
        if institution:
            result['university'] = institution
        result['other_names'] = [n for n in (best.get('other-names') or [])
                                 if n and n != name]

        if not orcid:
            return result

        rec = self._record(orcid)
        person = rec.get('person') or {}
        name_data = person.get('name') or {}
        given = (name_data.get('given-names') or {}).get('value') or ''
        family = (name_data.get('family-name') or {}).get('value') or ''
        if given or family:
            result['name'] = f'{given} {family}'.strip()
        if (name_data.get('credit-name') or {}).get('value'):
            result['name'] = name_data['credit-name']['value']

        bio = person.get('biography') or {}
        result['bio'] = bio.get('content') or ''

        urls = []
        for entry in ((person.get('researcher-urls') or {}).get('researcher-url') or []):
            url = (entry.get('url') or {}).get('value') or ''
            if url:
                urls.append(url)
        result['website'] = urls[0] if urls else ''

        external_ids = []
        for entry in ((person.get('external-identifiers') or {}).get('external-identifier') or []):
            ext_type = entry.get('external-id-type') or ''
            ext_value = entry.get('external-id-value') or ''
            if ext_type and ext_value:
                external_ids.append(f'{ext_type}:{ext_value}')
        result['external_ids'] = external_ids

        activities = rec.get('activities-summary') or {}
        works = activities.get('works') or {}
        result['total_publications'] = works.get('group') and len(works['group']) or None

        return result
