"""
Faculty page scraper - CSE check and university-name enrichment.

Reuses the existing ConfigurableScraper (your config drives the actual
extraction). Before extracting it checks whether the page belongs to a
Computer Science / CSE department or field, and it always adds the
university name, a CSE flag and the source URL to every row.
"""

import os
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from .scraper import ConfigurableScraper


# ---------------------------------------------------------------------------
# CSE detection
# ---------------------------------------------------------------------------

# Words that mean "this is a Computer Science / CSE page".
# They are compared against the page text (lowercase).
CSE_KEYWORDS = [
    'computer science',
    'computer science and engineering',
    'computer engineering',
    'dept of computer',
    'department of computer',
    'school of computing',
    'computing and',
    'cse ',
    'cse-',
    'cs department',
    'software engineering',
    'information technology',
    'information systems',
    'artificial intelligence',
    'machine learning',
    'data science',
    'computational',
    'eecs',
    'computer sciences',
]


def is_cse_page(soup: BeautifulSoup) -> bool:
    """
    Check if a page is related to the CSE (Computer Science & Engineering)
    department or field.

    Args:
        soup: Parsed HTML of the page.

    Returns:
        True if the page looks like a CSE / CS page, otherwise False.
    """
    if soup is None:
        return False

    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True).lower() if title_tag else ''

    text = soup.get_text(' ', strip=True).lower()
    haystack = f'{title}\n{text}'

    for keyword in CSE_KEYWORDS:
        if keyword in haystack:
            return True
    return False


# ---------------------------------------------------------------------------
# University name detection
# ---------------------------------------------------------------------------

# Fallback map: website domain -> university full name.
# The page itself is checked first (meta tags, title, copyright line).
DOMAIN_TO_UNIVERSITY = {
    'mit.edu': 'Massachusetts Institute of Technology',
    'stanford.edu': 'Stanford University',
    'berkeley.edu': 'University of California, Berkeley',
    'harvard.edu': 'Harvard University',
    'jhu.edu': 'Johns Hopkins University',
    'cmu.edu': 'Carnegie Mellon University',
    'umd.edu': 'University of Maryland',
    'utexas.edu': 'University of Texas at Austin',
    'gatech.edu': 'Georgia Institute of Technology',
    'illinois.edu': 'University of Illinois Urbana-Champaign',
    'washington.edu': 'University of Washington',
    'cornell.edu': 'Cornell University',
    'princeton.edu': 'Princeton University',
    'caltech.edu': 'California Institute of Technology',
    'duke.edu': 'Duke University',
    'northwestern.edu': 'Northwestern University',
    'columbia.edu': 'Columbia University',
    'nyu.edu': 'New York University',
    'ucla.edu': 'University of California, Los Angeles',
    'bu.edu': 'Boston University',
}


def detect_university(url: str, soup: Optional[BeautifulSoup] = None) -> str:
    """
    Try to find the university name from the page metadata, then fall back
    to the website domain.

    Args:
        url: The faculty page URL.
        soup: Parsed HTML of the page (optional).

    Returns:
        University name, or '' if it could not be found.
    """
    meta_name = ''
    if soup is not None:
        # 1) <meta property="og:site_name"> / <meta name="site_name">
        meta = soup.find('meta', attrs={'property': 'og:site_name'})
        if not meta:
            meta = soup.find('meta', attrs={'name': 'site_name'})
        if meta and meta.get('content', '').strip():
            meta_name = meta['content'].strip()

    # If the meta tag really names the university, use it.
    university_marker = re.search(r'[Uu]niversity|[Cc]ollege|[Ii]nstitut|Univ\.', meta_name)
    if university_marker:
        return meta_name

    # 2) fall back to the domain map
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or '').lower()
    for domain, name in DOMAIN_TO_UNIVERSITY.items():
        if host == domain or host.endswith('.' + domain):
            return name

    # 3) copyright line, e.g. "© 2026 The Trustees of ... University"
    if soup is not None:
        text = soup.get_text(' ', strip=True)
        m = re.search(r'[©\u00a9]\s*((?:\w+\s+){1,6}[Uu]niversity)', text)
        if m:
            return re.sub(r'\s+', ' ', m.group(1)).strip()

    # 4) last resort: whatever the meta tag said
    return meta_name


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def scrape_faculty_page(url: str, config: Dict, output: Optional[str] = None,
                        append: bool = False) -> List[Dict]:
    """
    Fetch a university faculty page, check it is CSE-related, then extract
    every field described in `config` and save the result as a CSV.

    Args:
        url: The faculty page URL.
        config: A modular scraping config (container + extractors).
        output: Output CSV path (default: datasets/faculty/<domain>.csv).
        append: True to add rows to the existing file.

    Returns:
        List of extracted rows (empty if the page is not CSE-related).
    """
    scraper = ConfigurableScraper(config)
    soup = scraper.scrape_page(url)

    if soup is None:
        print('Could not open the page. Check the URL and internet connection.')
        return []

    if not is_cse_page(soup):
        print('This page does not look like a Computer Science / CSE page.')
        print('No data was extracted.')
        return []

    print('CSE page detected - extracting data...')

    # Extract every row using the caller's config.
    records = scraper.scrape_soup(soup, url)

    if not records:
        print('The config did not find anything on this page.')
        return []

    # Add useful extra columns for model training.
    university = detect_university(url, soup)
    for row in records:
        row['university_name'] = university
        row['is_cse'] = True
        row['source_url'] = url

    # Save.
    if output:
        path = output if output.endswith('.csv') else f'{output}.csv'
    else:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or 'faculty').replace('.', '_')
        out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'datasets', 'faculty')
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f'{host}.csv')

    import pandas as pd
    df = pd.DataFrame(records)
    for col in df.columns:
        df[col] = df[col].apply(lambda v: ', '.join(v) if isinstance(v, list) else v)

    exists = os.path.exists(path)
    df.to_csv(path, index=False, encoding='utf-8-sig',
              mode='a' if (append and exists) else 'w',
              header=not (append and exists))

    print(f'Extracted {len(records)} row(s) -> {path}')
    return records
