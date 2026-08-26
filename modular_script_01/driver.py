"""
Driver: ties universities.py metadata to the per-site parsers in adapters.py
and produces the final combined CSV.

    University,R,Ranking,Professor name,Email,Mail,Lab link,Research area

Usage:
    python driver.py --offline     # parse saved HTML copies (single page each)
    python driver.py               # live scrape (requests; Playwright for JS sites)
    python driver.py mit berkeley  # live scrape only those sites
    python driver.py --reuse-only  # just copy the reuse CSVs into the combined file
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from adapters import (parse_arizona, parse_berkeley, parse_brown, parse_cau,
                      parse_cmu_csd, parse_cornell, parse_csula, parse_duke,
                      parse_famu, parse_fsu, parse_gt, parse_hampton,
                      parse_harvard, parse_idaho, parse_lamar, parse_marshall,
                      parse_mit_eecs, parse_morgan, parse_montana, parse_ncsu,
                      parse_nyu, parse_osu, parse_pepperdine, parse_pitt,
                      parse_psu, parse_purdue, parse_pvamu, parse_rice,
                      parse_stanford, parse_subr, parse_tnstate, parse_uah,
                      parse_ualr, parse_ucsb, parse_ucsd, parse_uci, parse_ucla,
                      parse_umd, parse_umich, parse_umkc, parse_unlv,
                      parse_utexas, parse_vsu, parse_wisc, parse_wright,
                      parse_yale, parse_und,
                      parse_generic, _emails_from, _cf_decode)

try:
    import universities
except ImportError:
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import universities

try:
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except ImportError:
    HAVE_PLAYWRIGHT = False

ROOT = Path(__file__).resolve().parent
HTML_DIR = ROOT / 'html_pages'
OUT_DIR = ROOT / 'datasets' / 'faculty'

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/124.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9',
}

# ---------------------------------------------------------------------------
# Site specs: slug -> (parser, pagination)
#   pagination: None        single page
#               'query'     append ?page=N
#               'harvard'   append ?page=%2CN
#               'ncsu'      append /page/N/   (N >= 2)
#               'alpha'     /people/faculty/{letter}
#               'js'        requires Playwright rendering
# ---------------------------------------------------------------------------
STATIC_PARSERS = {
    'mit_eecs': (parse_mit_eecs, None),
    'berkeley': (parse_berkeley, None),
    'ucsd': (parse_ucsd, None),
    'purdue': (parse_purdue, None),
    'cs_brown_edu': (parse_brown, None),
    'marshall_edu': (parse_marshall, None),
    'cs_nyu_edu': (parse_nyu, None),
    'cs_ucsb_edu': (parse_ucsb, None),
    'cs_pitt_edu': (parse_pitt, None),
    'cs_fsu_edu': (parse_fsu, None),
    'cs_cornell_edu': (parse_cornell, None),
    'unlv_edu': (parse_unlv, None),
    'directory_uidaho_edu': (parse_idaho, None),
    'engineering_und_edu': (parse_und, None),
    'sse_umkc_edu': (parse_umkc, None),
    'cs_montana_edu': (parse_montana, None),
    'engineering_yale_edu': (parse_yale, 'js'),
    'utexas': (parse_utexas, None),
    'wisc': (parse_wisc, None),
    'psu': (parse_psu, None),
    'umd': (parse_umd, None),
    'duke': (parse_duke, None),
    'arizona': (parse_arizona, None),
    'famu': (parse_famu, None),
    'hampton': (parse_hampton, None),
    'morgan': (parse_morgan, None),
    'ualr': (parse_ualr, None),
    'pvamu': (parse_pvamu, None),
    'subr': (parse_subr, None),
    'tnstate': (parse_tnstate, None),
    'pepperdine': (parse_pepperdine, None),
    'lamar': (parse_lamar, None),
    'csula': (parse_csula, None),
    'uah': (parse_uah, None),
    'ucla': (parse_ucla, 'js'),
    'uci': (parse_uci, None),
    'rice': (parse_rice, 'js'),
    'vsu': (parse_vsu, 'js'),
    'wright': (parse_wright, 'js'),
    'umich': (parse_umich, 'wayback'),
}

PAGINATED_PARSERS = {
    'cmu_csd': (parse_cmu_csd, 'query'),
    'osu': (parse_osu, 'query'),
    'cau': (parse_cau, 'query'),
    'stanford': (parse_stanford, 'query'),
    'gt': (parse_gt, 'query'),
    'harvard': (parse_harvard, 'harvard'),
    'ncsu': (parse_ncsu, 'ncsu'),
}

JS_SITES = {
    'tsu': None,
}

# Slug -> university name (key in universities.py)
SLUG_TO_UNIV = {
    'mit_eecs': 'Massachusetts Institute of Technology',
    'cmu_csd': 'Carnegie Mellon University',
    'stanford': 'Stanford University',
    'harvard': 'Harvard University',
    'berkeley': 'University of California, Berkeley',
    'ucsd': 'University of California, San Diego',
    'gt': 'Georgia Institute of Technology',
    'purdue': 'Purdue University',
    'utexas': 'University of Texas at Austin',
    'wisc': 'University of Wisconsin–Madison',
    'psu': 'Pennsylvania State University',
    'osu': 'Ohio State University',
    'umd': 'University of Maryland',
    'ncsu': 'North Carolina State University',
    'duke': 'Duke University',
    'arizona': 'University of Arizona',
    'cau': 'Clark Atlanta University',
    'famu': 'Florida Agricultural and Mechanical University',
    'hampton': 'Hampton University',
    'morgan': 'Morgan State University',
    'ualr': 'University of Arkansas at Little Rock',
    'pvamu': 'Prairie View A&M University',
    'subr': 'Southern University and A&M College',
    'tnstate': 'Tennessee State University',
    'pepperdine': 'Pepperdine University',
    'lamar': 'Lamar University',
    'csula': 'California State University, Los Angeles',
    'uah': 'University of Alabama in Huntsville',
    'ucla': 'University of California, Los Angeles',
    'uci': 'University of California, Irvine',
    'umich': 'University of Michigan',
    'rice': 'Rice University',
    'vsu': 'Virginia State University',
    'wright': 'Wright State University',
    'tsu': 'Texas Southern University',
}

FINAL_COLUMNS = ['University', 'R', 'Ranking', 'Professor name',
                 'Email', 'Mail', 'Lab link', 'Research area']

# Universities skipped because their sites are unreachable from this network or
# are fully JS-only with no accessible data source (verified repeatedly):
#   Northwestern / U. Chicago      connect-timeout from this network
#   Texas Southern                 Cloudflare-gated
#   CSU Fullerton                  faculty list is an empty AJAX endpoint
#   UMKC                           JS-only directory, endpoint now 404
SKIP_UNIVERSITIES = ('Northwestern', 'University of Chicago',
                     'Texas Southern', 'Fullerton', 'Kansas City')


def univ_by_name(name):
    for u in universities.UNIVERSITIES:
        if u['name'] == name:
            return u
    return None


def build_slugs(args):
    """Return the list of slugs to process."""
    if args.reuse_only:
        return []
    slugs = sorted(SLUG_TO_UNIV)
    if args.offline:
        return [s for s in slugs if (HTML_DIR / f'{s}.html').exists()]
    if args.sites:
        want = set(args.sites)
        return [s for s in slugs if s in want]
    return slugs


# ---------------------------------------------------------------------------
# Fetch layer
# ---------------------------------------------------------------------------
def fetch(url, use_playwright=False, offline=None):
    """Return the response text for a URL (or the saved offline HTML)."""
    if offline is not None:
        return offline
    if url.startswith('https://web.archive.org/web/'):
        return fetch_wayback(url)
    if use_playwright and HAVE_PLAYWRIGHT:
        return fetch_playwright(url)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f'    [fetch error {e}] {url}')
        if HAVE_PLAYWRIGHT:
            return fetch_playwright(url)
        return None


def fetch_wayback(url):
    """Fetch a page from the Wayback Machine using the CDX API to resolve
    a concrete snapshot (avoids flaky redirect/rate-limit responses)."""
    base = url.split('web/2023/')[-1]
    cdx = ('https://web.archive.org/cdx/search/cdx?'
           f'url={base}&output=json&limit=3&filter=statuscode:200&from=2022')
    for attempt in range(3):
        try:
            r = requests.get(cdx, headers={'User-Agent': 'research-script/1.0'},
                             timeout=40)
            if r.status_code == 429:
                time.sleep(10)
                continue
            data = r.json()
            if len(data) < 2:
                print(f'    [wayback no snapshot] {base}')
                return None
            for row in reversed(data[1:]):
                ts = row[1]
                for variant in (f'https://web.archive.org/web/{ts}id_/{base}',
                                f'https://web.archive.org/web/{ts}/{base}'):
                    try:
                        rr = requests.get(variant,
                                          headers={'User-Agent': HEADERS['User-Agent']},
                                          timeout=60)
                        if rr.status_code == 200:
                            return rr.text
                    except Exception:
                        continue
            print(f'    [wayback all snapshots failed] {base}')
            return None
        except Exception as e:
            print(f'    [wayback error {e}]')
            time.sleep(10)
    return None


def fetch_playwright(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS['User-Agent'])
            page.goto(url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(12000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f'    [playwright error] {e}')
        return None


def page_urls(base, pagination):
    """Yield (url, page_index) for each page of a site, based on pagination."""
    if pagination is None or pagination == 'js':
        yield base, 0
        return
    if pagination == 'wayback':
        yield f'https://web.archive.org/web/2023/{base}', 0
        return
    if pagination == 'query':
        for i in range(0, 60):
            yield f'{base}?page={i}', i
    elif pagination == 'harvard':
        for i in range(0, 60):
            yield f'{base}?page=%2C{i}', i
    elif pagination == 'ncsu':
        yield base, 1
        for i in range(2, 40):
            yield f'{base.rstrip("/")}/page/{i}/', i
    elif pagination == 'alpha':
        import string
        yield base, 0
        for letter in string.ascii_lowercase:
            yield f'{base.rstrip("/")}/{letter}', letter


def slug_from_url(url):
    """Hostname-based slug (brown.cs -> cs_brown_edu), for sites without a
    hand-tuned adapter."""
    host = urlparse(url).netloc.lower()
    host = host.replace('www.', '').split(':')[0]
    return re.sub(r'[^a-z0-9]+', '_', host).strip('_')


_NAME_BLOCKWORDS = (
    'faculty', 'staff', 'people', 'home', 'contact', 'directory', 'about',
    'menu', 'search', 'profile', 'member', 'welcome', 'overview', 'leadership',
    'administration', 'department', 'program', 'student', 'research',
    'university', 'college', 'alumni', 'news', 'events', 'admissions',
    'academics', 'resources', 'careers', 'graduate', 'undergraduate')


def _name_like(text):
    if not text:
        return False
    parts = text.split()
    if not 2 <= len(parts) <= 4:
        return False
    if any(part[0].islower() for part in parts if part):
        return False
    if text.lower() in _NAME_BLOCKWORDS:
        return False
    if any(w in text.lower() for w in ('apply', 'now', 'sheet', 'bookstore',
                                       'calendar', 'alert', 'emergency',
                                       'tuition', 'dining', 'residency',
                                       'mission', 'calculator', 'extension',
                                       'services', 'affairs')):
        return False
    return True


_NAV_LAST_SEG = frozenset((
    'about', 'news', 'contact', 'faculty', 'staff', 'research', 'people',
    'directory', 'events', 'alumni', 'admissions', 'academics', 'programs',
    'courses', 'search', 'impact', 'stories', 'history', 'community', 'blog',
    'careers', 'join', 'visit', 'apply', 'home', 'index', 'overview',
    'resources', 'newsletter', 'awards', 'opportunities', 'outreach',
    'partnerships', 'calendar', 'welcome', 'meet', 'our', 'why', 'campus',
    'support', 'giving', 'donate', 'library', 'students', 'graduate',
    'undergraduate', 'current', 'prospective', 'about-us', 'counseling'))

_SECTION_TEXT = frozenset((
    'faculty emeritus', 'faculty emeriti', 'faculty/staff', 'faculty & staff',
    'faculty and staff', 'full-time faculty', 'research areas', 'recent news',
    'exploring the impact', 'computer science', 'tenure / tenure track',
    'teaching faculty', 'research faculty', 'adjunct faculty',
    'biomedical computation collaborative', 'primary faculty', 'secondary faculty',
    'main campus', 'panama city campus', 'department faculty', 'staff directory'))


def _profile_href(href):
    """A fallback name-link should look like a profile/directory URL, not a
    top-level nav page (/about, /blog, /news...)."""
    from urllib.parse import unquote
    path = unquote(urlparse(href).path or '').lower()
    segs = [s for s in path.split('/') if s and s not in ('index',)]
    segs = [re.sub(r'\.(html?|php|aspx?)$', '', s) for s in segs]
    if not segs:
        return False
    if segs[-1] in _NAV_LAST_SEG:
        return False
    if any(t in path for t in ('/people/', '/faculty/', '/profile/', '/staff/',
                               '/member/', '/person/', '/directory/', '/~',
                               '/researcher/', '/lab/', '/scholar/',
                               '?user=', '/id=', '/user/', '/cid=')):
        return True
    return len(segs) >= 2


def extract_name_links(soup, base):
    """Fallback: pull name-like links (with any nearby card email) from pages
    whose layout is just a list of profile links."""
    rows, seen = [], set()
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
            continue
        if not _profile_href(href):
            continue
        t = ' '.join(a.get_text(' ', strip=True).split())
        if not _name_like(t):
            continue
        if t.lower() in _SECTION_TEXT:
            continue
        if '/' in t:
            continue
        if a.find_parent(['nav', 'header', 'footer']) is not None:
            continue
        if any('menu' in (c or '').lower() or 'nav' in (c or '').lower()
               or 'header' in (c or '').lower() or 'footer' in (c or '').lower()
               for el in a.parents if el.name not in ('body', 'html')
               for c in (el.get('class') or [])):
            continue
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        card = a.find_parent(['div', 'li', 'article'])
        email = mail = ''
        if card is not None:
            email, mail = _emails_from(card)
        rows.append({'name': t, 'title': '', 'email': email, 'mail': mail,
                     'lab_link': urljoin(base, href), 'research': ''})
    return rows


def _cf_email_from_soup(soup):
    el = soup.find('span', class_='__cf_email__')
    if el and el.get('data-cfemail'):
        return _cf_decode(el['data-cfemail'])
    return ''


def scrape_site(slug, url, offline_text=None):
    parser = None
    pagination = None
    for name, (p, pag) in list(STATIC_PARSERS.items()) + list(PAGINATED_PARSERS.items()):
        if name == slug:
            parser, pagination = p, pag
            break

    is_generic = parser is None
    if parser is None:
        # no hand-tuned adapter: fall back to the generic card parser
        parser = parse_generic
        pagination = None

    rows = []
    seen_names = set()
    first_offline_done = False
    used_js = False
    for page_url, idx in page_urls(url, pagination):
        if offline_text is not None:
            if first_offline_done:
                break
            text = offline_text
            first_offline_done = True
        else:
            time.sleep(0.8)
            use_js = (pagination == 'js')
            if use_js and HAVE_PLAYWRIGHT:
                text = fetch(page_url, use_playwright=True)
                used_js = True
            else:
                text = fetch(page_url)
            if text is None:
                continue
        soup = BeautifulSoup(text, 'html.parser')
        page_rows = parser(soup, page_url)
        if not page_rows and parser is parse_generic:
            # card parser found nothing: try the name-links fallback
            page_rows = extract_name_links(soup, page_url)
        new = 0
        for r in page_rows:
            key = r['name'].lower().strip()
            if key and key not in seen_names:
                seen_names.add(key)
                rows.append(r)
                new += 1
        if pagination is None:
            break
        if new == 0:
            break

    # JS-rendered page (content only appears after scripts run)?  Re-render
    # the base URL with a headless browser and try once more.
    if len(rows) < 3 and is_generic and HAVE_PLAYWRIGHT and not used_js:
        js_html = fetch(url, use_playwright=True)
        if js_html:
            js_soup = BeautifulSoup(js_html, 'html.parser')
            js_rows = parser(js_soup, url) or extract_name_links(js_soup, url)
            js_new = 0
            for r in js_rows:
                key = r['name'].lower().strip()
                if key and key not in seen_names:
                    seen_names.add(key)
                    rows.append(r)
                    js_new += 1
            if js_new:
                print(f'    [{slug}] Playwright render added {js_new} rows')
    return rows, 'ok'


def fetch_profile_page(url, retries=4):
    """Fetch an ICS `?people=` profile page, retrying when the site soft-blocks
    (it serves a generic ~40KB page without the person's `h1.subheader__title`
    after ~7 rapid requests; the block clears after a short quiet period)."""
    for attempt in range(retries):
        text = fetch(url)
        if text:
            soup = BeautifulSoup(text, 'html.parser')
            h1 = soup.find('h1', class_='subheader__title')
            if h1 is not None and 'Whoops!' not in h1.get_text(' ', strip=True):
                return soup
            if attempt < retries - 1:
                print(f'    [uci profile] rate-limited, waiting 60s '
                      f'(attempt {attempt + 1}/{retries})', flush=True)
                time.sleep(60)
        else:
            if attempt < retries - 1:
                time.sleep(30)
    return None


def enrich_uci_profiles(rows):
    """Fetch each UCI professor's ICS profile page and fill in research areas
    and a personal-website lab link (the listing page has neither).

    Profile URLs come from `lab_link` (https://ics.uci.edu/?people=<slug>).
    Research areas live in `article.item--research h3.item__title span`; the
    personal website is the link whose text is exactly 'website'.  Profiles
    that 404 ('Whoops!') or lack a section are kept as-is.
    """
    for i, r in enumerate(rows, 1):
        url = r.get('lab_link') or ''
        if not url.startswith('http'):
            continue
        soup = fetch_profile_page(url)
        if soup is None:
            print(f'    [uci profile {i}/{len(rows)}] skipped: {r["name"]}')
            continue
        areas = [a.get_text(' ', strip=True)
                 for a in soup.select('article.item--research h3.item__title span')]
        if areas:
            r['research'] = ', '.join(dict.fromkeys(a for a in areas if a))
        website = ''
        for a in soup.find_all('a', href=True):
            if a.get_text(' ', strip=True).lower() == 'website':
                website = a['href']
                break
        if website:
            r['lab_link'] = website
        print(f'    [uci profile {i}/{len(rows)}] {r["name"]}: '
              f'{len(areas)} area(s)'
              f'{", website" if website else ""}', flush=True)
        time.sleep(4.0)
    return rows


# ---------------------------------------------------------------------------
# Reuse CSVs
# ---------------------------------------------------------------------------
REUSE_COLUMNS = {
    'name': 'Professor name',
    'email': 'Email',
    'research_areas': 'Research area',
    'research_area': 'Research area',
    'profile_url': 'Lab link',
    'titles': 'Research area',
}


def _write_uni_csv(univ_name, r, ranking, slug, rows):
    """Write datasets/faculty/<slug>_faculty.csv (feeds the pickable step)."""
    path = ROOT / 'datasets' / 'faculty' / f'{slug}_faculty.csv'
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def load_reuse(u, final_rows):
    """Map an existing datasets/faculty CSV into the final schema."""
    path = ROOT / 'datasets' / 'faculty' / u['reuse']
    if not path.exists():
        print(f'  [reuse MISSING] {path}')
        return
    with open(path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get('name') or '').strip()
            if not name:
                continue
            email = (row.get('email') or '').strip()
            mail = (row.get('mail') or row.get('email2') or '').strip()
            if email and mail and email == mail:
                mail = ''
            research = (row.get('research_areas') or row.get('research_area')
                        or row.get('titles') or '').strip()
            lab = (row.get('profile_url') or row.get('url') or '').strip()
            if lab.startswith('/'):
                lab = urljoin(u['faculty_url'], lab)
            final_rows.append({
                'University': u['name'],
                'R': u['r'],
                'Ranking': u['ranking'],
                'Professor name': name,
                'Email': email,
                'Mail': mail,
                'Lab link': lab,
                'Research area': research,
            })
    print(f'  [reuse] {u["name"]}: {len(final_rows)} rows so far')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sites', nargs='*', help='slugs to scrape')
    ap.add_argument('--offline', action='store_true',
                    help='parse saved HTML in html_pages/faculty')
    ap.add_argument('--reuse-only', action='store_true')
    ap.add_argument('--out', default=str(OUT_DIR / 'combined_faculty.csv'))
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slugs = build_slugs(args)

    final_rows = []
    skipped_js = []
    total_live = 0

    for u in universities.UNIVERSITIES:
        name = u['name']
        if any(s in name for s in SKIP_UNIVERSITIES):
            print(f'  [skip] {name}')
            continue
        if u.get('reuse'):
            if not args.sites:
                load_reuse(u, final_rows)
            continue

        slug = next((s for s, n in SLUG_TO_UNIV.items() if n == name), None)
        slug = slug or slug_from_url(u['faculty_url'])
        if args.sites and slug not in args.sites:
            continue

        if args.offline:
            html_file = HTML_DIR / f'{slug}.rendered.html'
            if not html_file.exists():
                html_file = HTML_DIR / f'{slug}.html'
            text = html_file.read_text(encoding='utf-8', errors='ignore') \
                if html_file.exists() else None
        else:
            text = None

        rows, status = scrape_site(slug, u['faculty_url'], offline_text=text)
        if status == 'js':
            skipped_js.append(name)
            continue

        if slug == 'uci' and rows:
            print(f'  [uci] enriching {len(rows)} profiles (research + website)')
            rows = enrich_uci_profiles(rows)

        uni_rows = []
        for r in rows:
            uni_rows.append({
                'University': name,
                'R': u['r'],
                'Ranking': u['ranking'],
                'Professor name': r['name'],
                'Email': r['email'],
                'Mail': r['mail'],
                'Lab link': r['lab_link'],
                'Research area': r['research'],
            })
        final_rows.extend(uni_rows)

        # per-university faculty CSV (feeds the pickable API step later)
        if uni_rows and not args.offline:
            _write_uni_csv(u['name'], u['r'], u['ranking'], slug, uni_rows)

        n_email = sum(1 for r in rows if r['email'])
        total_live += len(rows)
        print(f'  [{slug}] {len(rows)} rows ({n_email} with email)  {name}')

    # Write combined CSV
    with open(args.out, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
        writer.writeheader()
        writer.writerows(final_rows)

    print(f'\nWrote {len(final_rows)} rows -> {args.out}')
    print(f'Live-total (new scrapes): {total_live}')
    if skipped_js:
        print(f'JS sites skipped (need Playwright): {", ".join(skipped_js)}')


if __name__ == '__main__':
    main()
