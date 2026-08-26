"""
University research classification (Carnegie R1 / R2 / R3).

The official list is scraped from Wikipedia
(`List_of_research_universities_in_the_United_States`) into
datasets/rankings/carnegie_rankings.csv via build_rankings_csv().

lookup_rank() then matches a university name against that CSV, with a small
built-in fallback map for the most common schools so offline lookups work
even before the CSV exists.
"""

import logging
import os
import re

import requests
from bs4 import BeautifulSoup

from ._paths import RANKINGS_CSV, RANKINGS_DIR

logger = logging.getLogger(__name__)

WIKI_URL = ('https://en.wikipedia.org/wiki/'
            'List_of_research_universities_in_the_United_States')
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36')

# Fallback for the most common schools (used until the CSV is built).
FALLBACK_RANK = {
    'Massachusetts Institute of Technology': 'R1',
    'Stanford University': 'R1',
    'University of California, Berkeley': 'R1',
    'Harvard University': 'R1',
    'Carnegie Mellon University': 'R1',
    'Johns Hopkins University': 'R1',
    'Cornell University': 'R1',
    'Princeton University': 'R1',
    'Columbia University': 'R1',
    'California Institute of Technology': 'R1',
    'University of Washington': 'R1',
    'Texas A&M University': 'R1',
    'University of Texas at Austin': 'R1',
    'Georgia Institute of Technology': 'R1',
    'University of Illinois Urbana-Champaign': 'R1',
    'University of Maryland': 'R1',
    'Boston University': 'R1',
    'Duke University': 'R1',
    'Northwestern University': 'R1',
    'New York University': 'R1',
    'University of California, Los Angeles': 'R1',
}


def fetch_rankings() -> list:
    """Scrape the Wikipedia list and return [(university, rank), ...]."""
    resp = requests.get(WIKI_URL, headers={'User-Agent': USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    rows = []
    rank_by_table = {0: 'R1', 1: 'R2', 2: 'R3'}
    tables = soup.find_all('table', class_='wikitable')

    for table_index, table in enumerate(tables[:3]):
        rank = rank_by_table.get(table_index, 'R?')
        for tr in table.find_all('tr')[1:]:
            name = _first_cell(tr)
            if name:
                rows.append((name, rank))
    return rows


def _first_cell(tr) -> str:
    th = tr.find('th')
    if th:
        return re.sub(r'\s+', ' ', th.get_text(' ', strip=True)).strip()
    for cell in tr.find_all('td'):
        text = re.sub(r'\s+', ' ', cell.get_text(' ', strip=True)).strip()
        if text and text not in ('Institution', 'Location'):
            return text
    return ''


def build_rankings_csv(url: str = WIKI_URL) -> str:
    """Fetch the current list and write datasets/rankings/carnegie_rankings.csv."""
    import pandas as pd

    rows = fetch_rankings() if url == WIKI_URL else _fetch_rankings_from(url)
    df = pd.DataFrame(rows, columns=['university', 'rank'])
    os.makedirs(RANKINGS_DIR, exist_ok=True)
    df.to_csv(RANKINGS_CSV, index=False, encoding='utf-8-sig')
    logger.info('Wrote %d university rankings -> %s', len(df), RANKINGS_CSV)
    return RANKINGS_CSV


def _fetch_rankings_from(url: str) -> list:
    resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')
    rows = []
    rank_by_table = {0: 'R1', 1: 'R2', 2: 'R3'}
    for table_index, table in enumerate(soup.find_all('table', class_='wikitable')[:3]):
        rank = rank_by_table.get(table_index, 'R?')
        for tr in table.find_all('tr')[1:]:
            name = _first_cell(tr)
            if name:
                rows.append((name, rank))
    return rows


def _norm(name: str) -> str:
    return re.sub(r'[^a-z0-9 ]', '', name.lower())


def lookup_rank(university: str) -> str:
    """
    Return the Carnegie classification ('R1'/'R2'/'R3') for a university
    name, or '' if it could not be matched.
    """
    if not university:
        return ''

    target = _norm(university)

    # 1) built-in fallback
    for name, rank in FALLBACK_RANK.items():
        if target == _norm(name) or target in _norm(name):
            return rank

    # 2) rankings CSV (if built)
    if not os.path.exists(RANKINGS_CSV):
        return ''

    import pandas as pd
    try:
        df = pd.read_csv(RANKINGS_CSV, dtype=str)
    except (ValueError, OSError):
        return ''

    if df.empty:
        return ''

    for _, row in df.iterrows():
        name = _norm(row['university'])
        if target == name or target in name or name in target:
            return row['rank']

    # 3) token-overlap match (e.g. "MIT" vs "Massachusetts Institute of Technology")
    target_tokens = {t for t in target.split() if len(t) > 2}
    for _, row in df.iterrows():
        name_tokens = {t for t in _norm(row['university']).split() if len(t) > 2}
        overlap = target_tokens & name_tokens
        if len(overlap) >= max(1, len(target_tokens) // 2):
            return row['rank']

    return ''
