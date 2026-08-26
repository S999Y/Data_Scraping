"""
Pipeline - ties the collectors together.

For every professor it runs the enabled sources, merges the results
(profile fields by source priority, publications de-duplicated by title /
DOI), infers research-area tags, looks up the university ranking, then
appends one row to professor_master.csv and one row per paper to
publications.csv.
"""

import logging
import os
import re

from ._paths import (FACULTY_DIR, PROFESSOR_MASTER_CSV, PUBLICATIONS_CSV,
                     SCHOLARS_DIR, ensure_dirs)
from .rankings import lookup_rank
from .sources import SOURCE_PRIORITY, SourceRegistry
from .storage import append_rows, dedupe_best, dedupe_csv
from .topics import combine_topics, infer_topics

logger = logging.getLogger(__name__)

MASTER_FIELDS = [
    # basic profile
    'name', 'university', 'department', 'country', 'position', 'email',
    'website', 'scholar_url', 'orcid', 'interests', 'bio',
    # research metrics
    'total_citations', 'h_index', 'i10_index', 'total_publications',
    'citations_per_year', 'avg_citations_per_paper', 'active_since',
    'career_span', 'citation_history',
    # topics + rank
    'research_topics', 'rank',
    # provenance
    'sources', 'scholar_user', 'openalex_id', 'semantic_id', 'dblp_pid',
    'profile_url', 'source_url', 'other_names',
]

PUBLICATION_FIELDS = [
    'professor', 'title', 'abstract', 'keywords', 'authors', 'venue',
    'year', 'citations', 'doi', 'url', 'source',
]

# collector kwargs needed per source (other than `name`).
# These must match the parameter names in collect_professor() so that
# scholar_url / faculty_url / faculty_config actually reach the collectors.
_SOURCE_KWARGS = {
    'scholar': ('scholar_url', 'html_path', 'user_id'),
    'faculty': ('faculty_url', 'faculty_config', 'faculty_rows'),
    'openalex': ('university_hint',),
}

# which normalized profile field each source's raw result contributes
_PROFILE_KEYS = {
    'name': ('name',),
    'university': ('university',),
    'department': ('department',),
    'country': ('country',),
    'position': ('position',),
    'email': ('verified_email', 'email'),
    'website': ('homepage_url', 'website'),
    'orcid': ('orcid',),
    'interests': ('interests',),
    'bio': ('bio',),
    'research_areas': ('research_areas',),
    'total_citations': ('total_citations',),
    'h_index': ('h_index',),
    'i10_index': ('i10_index',),
    'total_publications': ('total_publications',),
    'citation_history': ('citation_history',),
    'profile_url': ('profile_url',),
    'source_url': ('source_url',),
    'scholar_user': ('scholar_user',),
    'openalex_id': ('openalex_id',),
    'semantic_id': ('semantic_id',),
    'dblp_pid': ('dblp_pid',),
    'other_names': ('other_names',),
}

PRIORITY_KEYS = set(SOURCE_PRIORITY)


def collect_professor(name: str = '', sources=None, scholar_url: str = None,
                      html_path: str = None, user_id: str = None,
                      faculty_url: str = None, faculty_config: str = None,
                      faculty_rows: list = None, orcid: str = None,
                      university_hint: str = None,
                      use_cache: bool = True, delay: float = 0.3,
                      api_key: str = None) -> dict:
    """
    Collect data for a single professor across the enabled sources and
    return one merged, normalized dict.

    Args:
        name: professor name used for searches.
        sources: list of source names (defaults to all registered).
        scholar_url / html_path: for the scholar source (live or offline).
        user_id: Google Scholar profile id (used if scholar_url has none).
        faculty_url / faculty_config: faculty-list page + config key.
        faculty_rows: rows already read from a faculty CSV.
        orcid: optional ORCID id to help the orcid collector.
        university_hint: known affiliation used to disambiguate name matches
            (currently used by the openalex collector).
        use_cache / delay: passed through to the collectors.
        api_key: OpenAlex API key for authenticated requests.

    Returns:
        Merged normalized dict (see MASTER_FIELDS) including 'publications'.
    """
    ensure_dirs()
    registry = SourceRegistry(sources, use_cache=use_cache, delay=delay,
                              api_key=api_key)
    results = {}
    name = (name or '').strip()

    for source in registry.names:
        collector = registry.instance(source)
        kwargs = {}
        for key in _SOURCE_KWARGS.get(source, ()):
            kwargs[key] = locals().get(key)
        if source == 'orcid' and orcid:
            kwargs['orcid'] = orcid
        try:
            results[source] = collector.collect(name=name, **kwargs)
        except Exception as e:
            logger.warning('[pipeline] source %s failed for %s: %s', source, name, e)
            results[source] = collector.empty_result(name)

    merged = _merge_results(results, name)
    return merged


def _merge_results(results: dict, fallback_name: str) -> dict:
    merged = {'name': fallback_name, 'publications': []}
    by_source = {}

    for source in results:
        res = results[source] or {}
        by_source[source] = res
        if res.get('publications'):
            merged['publications'].extend(res['publications'])

    # profile fields, taken from the highest-priority source that has a value.
    # The requested `name` is authoritative: an API name-match (which may be a
    # different person) must never overwrite it.
    for field, keys in _PROFILE_KEYS.items():
        if field == 'name' and fallback_name.strip():
            continue
        for source in SOURCE_PRIORITY:
            if source not in by_source:
                continue
            for key in keys:
                value = by_source[source].get(key)
                if _has_value(value):
                    merged[field] = value
                    break
            if field in merged and _has_value(merged.get(field)):
                break

    if not _has_value(merged.get('name')):
        for source in SOURCE_PRIORITY:
            if by_source.get(source, {}).get('name'):
                merged['name'] = by_source[source]['name']
                break

    # research topics: direct tags + inferred from available text
    direct = []
    for source in by_source.values():
        direct.extend(source.get('topics') or [])
    text_sources = []
    for key in ('interests', 'research_areas', 'bio', 'affiliation'):
        if merged.get(key):
            text_sources.append(merged[key])
    text_sources.extend(p['title'] for p in merged['publications'][:200]
                        if p.get('title'))
    merged['research_topics'] = combine_topics(
        [direct, infer_topics(text_sources)])

    # publications: de-duplicate by normalized title / DOI
    merged['publications'] = _dedupe_publications(merged['publications'])

    merged['sources'] = [s for s in results if _source_contributed(by_source[s])]

    merged['scholar_url'] = _scholar_url(merged.get('scholar_user'))
    _derive_career_metrics(merged)
    # ensure university is a string before lookup
    uni_val = merged.get('university') or ''
    if isinstance(uni_val, (list, tuple)):
        uni_val = ' '.join(str(v) for v in uni_val)
    merged['rank'] = lookup_rank(uni_val)
    return merged


def _scholar_url(user_id) -> str:
    if not user_id:
        return ''
    return ('https://scholar.google.com/citations?'
            f'hl=en&user={user_id}&view_op=list_works')


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple)):
        return bool(value)
    return True


def _source_contributed(res: dict) -> bool:
    if res.get('publications'):
        return True
    for keys in _PROFILE_KEYS.values():
        for key in keys:
            if key != 'name' and _has_value(res.get(key)):
                return True
    return False


def _dedupe_publications(pubs: list) -> list:
    seen = set()
    out = []
    for p in pubs:
        title = _norm_title(p.get('title') or '')
        doi = (p.get('doi') or '').lower()
        key = doi if (doi and not title) else title
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _norm_title(title: str) -> str:
    return re.sub(r'[^a-z0-9]', '', title.lower())


def _derive_career_metrics(merged: dict) -> None:
    years = []
    for p in merged.get('publications') or []:
        y = p.get('year')
        if isinstance(y, (int, float)) and 1950 < y <= 2100:
            years.append(int(y))
    if years:
        merged['active_since'] = min(years)
        merged['career_span'] = max(years) - min(years) + 1
    total_cites = merged.get('total_citations')
    total_pubs = merged.get('total_publications')
    career_span = merged.get('career_span')
    if isinstance(total_cites, (int, float)):
        if isinstance(career_span, (int, float)) and career_span:
            merged['citations_per_year'] = round(total_cites / career_span, 1)
        if isinstance(total_pubs, (int, float)) and total_pubs:
            merged['avg_citations_per_paper'] = round(total_cites / total_pubs, 1)


def master_row(merged: dict) -> dict:
    row = {}
    for field in MASTER_FIELDS:
        value = merged.get(field)
        if field == 'interests' and not value:
            value = merged.get('research_areas') or ''
        if isinstance(value, list):
            value = '; '.join(str(v) for v in value)
        row[field] = '' if value is None else value
    return row


def publication_rows(merged: dict) -> list:
    professor = merged.get('name') or ''
    rows = []
    for p in merged.get('publications') or []:
        row = {'professor': professor}
        for field in PUBLICATION_FIELDS:
            if field == 'professor':
                continue
            value = p.get(field)
            if isinstance(value, list):
                value = '; '.join(str(v) for v in value)
            row[field] = '' if value is None else value
        rows.append(row)
    return rows


def save_professor(merged: dict, master_path: str = PROFESSOR_MASTER_CSV,
                   pubs_path: str = PUBLICATIONS_CSV) -> None:
    ensure_dirs()
    append_rows([master_row(merged)], master_path)
    pub_rows = publication_rows(merged)
    if pub_rows:
        append_rows(pub_rows, pubs_path)
    # keep the most complete row per professor / per paper title
    dedupe_best(master_path, 'name')
    dedupe_csv(pubs_path, 'title', keep='last')


def run_pipeline(inputs, sources=None, use_cache=True, delay=0.3,
                 api_key=None, verbose=True):
    """
    Run collection for a list of professor inputs.

    Args:
        inputs: list of dicts with kwargs for collect_professor
                (e.g. {'name': ..., 'user_id': ..., 'faculty_rows': [...]}).
        sources: optional source list (overrides each input's 'sources').
        use_cache / delay: passed to collect_professor.
        api_key: OpenAlex API key for authenticated requests.

    Returns:
        List of merged result dicts.
    """
    collected = []
    for i, inp in enumerate(inputs, 1):
        if verbose:
            print(f'[{i}/{len(inputs)}] collecting: {inp.get("name", "")}')
        kwargs = dict(inp)
        kwargs.pop('name', None)
        if sources is not None:
            kwargs['sources'] = sources
        merged = collect_professor(
            name=inp.get('name', ''), use_cache=use_cache, delay=delay,
            api_key=api_key, **kwargs)
        save_professor(merged)
        collected.append(merged)
        if verbose:
            topics = '; '.join(merged.get('research_topics') or []) or 'none'
            pubs = len(merged.get('publications') or [])
            rank = merged.get('rank') or 'n/a'
            print(f'   -> {merged.get("name") or "?"} | rank={rank} | '
                  f'topics={topics} | publications={pubs}')
    return collected


def batch_from_datasets(scholars_dir: str = SCHOLARS_DIR,
                        faculty_dir: str = FACULTY_DIR,
                        scholar_limit: int = None,
                        faculty_limit: int = None) -> list:
    """
    Build a list of professor inputs from the existing datasets.

    Each file in datasets/scholars/*.csv holds one professor (one row per
    paper), so one input is created per file using the first row's name and
    user_id.  Each row in datasets/faculty/*.csv is one professor.
    """
    from .storage import load_csv_rows

    inputs = []

    if os.path.isdir(scholars_dir):
        for fname in sorted(os.listdir(scholars_dir)):
            if not fname.endswith('.csv'):
                continue
            rows = load_csv_rows(os.path.join(scholars_dir, fname))
            if not rows:
                continue
            first = rows[0]
            name = (first.get('name') or '').strip()
            if not name:
                name = (fname[:-4].replace('_', ' ')).strip()
            inputs.append({
                'name': name,
                'user_id': first.get('user_id') or '',
                'sources': ['scholar', 'openalex', 'semantic'],
            })
            if scholar_limit and len(inputs) >= scholar_limit:
                break

    if os.path.isdir(faculty_dir):
        scholar_count = len(inputs)
        faculty_seen = 0
        for fname in sorted(os.listdir(faculty_dir)):
            if not fname.endswith('.csv'):
                continue
            for row in load_csv_rows(os.path.join(faculty_dir, fname)):
                name = (row.get('name') or row.get('Professor name') or '').strip()
                if not name:
                    continue
                inputs.append({
                    'name': name,
                    'faculty_rows': [row],
                    'sources': ['faculty', 'openalex', 'semantic'],
                })
                faculty_seen += 1
                if faculty_limit and faculty_seen >= faculty_limit:
                    return inputs

    return inputs
