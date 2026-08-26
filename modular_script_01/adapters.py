"""
Per-site parsers for university CS faculty listing pages.

Every parser takes a BeautifulSoup object and a base URL, and returns a list
of dicts:

    {name, title, email, mail, lab_link, research}

    name      - professor's name (First Last)
    title     - position / appointment title
    email     - primary email address
    mail      - secondary email address (rare)
    lab_link  - personal / lab / profile website
    research  - research areas (comma separated)
"""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup


def _txt(el):
    if el is None:
        return ''
    return ' '.join(el.get_text(' ', strip=True).split())


def _first_last(name):
    """Turn 'Doe, John' into 'John Doe'."""
    if ',' in name:
        parts = [p.strip() for p in name.split(',')]
        if len(parts) == 2 and parts[1] and not re.search(r'\d', parts[0][:3]):
            return ' '.join(reversed(parts))
    return name


def _emails_from(node):
    """Return (primary, secondary) emails found under node."""
    out = []
    for a in node.find_all('a', href=lambda h: h and h.startswith('mailto:')):
        e = a.get('href', '')[7:].strip()
        if e and e.lower() not in [x.lower() for x in out]:
            out.append(e)
    for m in re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',
                        node.get_text(' ', strip=True)):
        if m.lower() not in [x.lower() for x in out]:
            out.append(m)
    return (out[0] if out else '', out[1] if len(out) > 1 else '')


def _cf_decode(hexstr):
    """Decode a Cloudflare email-protection token (data-cfemail)."""
    try:
        key = int(hexstr[:2], 16)
        return ''.join(chr(int(hexstr[i:i + 2], 16) ^ key)
                       for i in range(2, len(hexstr), 2))
    except Exception:
        return ''


def _cf_email(el):
    """Get email from an element that may contain a Cloudflare token."""
    cf = el.find('span', class_='__cf_email__')
    if cf and cf.get('data-cfemail'):
        return _cf_decode(cf['data-cfemail'])
    href = el.get('href', '')
    if href.startswith('mailto:'):
        return href[7:]
    for a in el.find_all('a', href=lambda h: h and h.startswith('mailto:')):
        return a['href'][7:]
    return ''


# ============================================================================
# MIT EECS
# ============================================================================
def parse_mit_eecs(soup, base):
    rows = []
    for p in soup.find_all('div', class_='people-entry'):
        nameel = p.find('h5')
        if nameel is None:
            continue
        a = nameel.find('a', href=True)
        name = _txt(a or nameel)
        title = ''
        para = nameel.find_next_sibling('p')
        if para:
            title = _txt(para)
        email, mail = _emails_from(p)
        research = ', '.join(dict.fromkeys(
            _txt(x) for x in p.select('div.people-research a')))
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': research})
    return rows


# ============================================================================
# CMU CSD  (table, surname-first names, ?page=N pagination)
# ============================================================================
def parse_cmu_csd(soup, base):
    rows = []
    for tr in soup.find_all('table')[0].find_all('tr') if soup.find('table') else []:
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        cell = tds[1]
        a = cell.find('a', href=True)
        name = _txt(a) if a else ''
        if not name:
            continue
        name = _first_last(name)
        text = _txt(cell)
        rest = text.replace(_first_last(_txt(a)), '', 1) if a else ''
        # first non-empty line after the name is the title
        lines = [ln.strip() for ln in cell.get_text('\n', strip=True).split('\n')]
        title = ''
        for ln in lines:
            if ln and ln != name and not ln.startswith(('(', '9', '8', '7')) \
               and not re.match(r'^[A-Za-z0-9._%+-]+@', ln):
                title = ln
                break
        email, mail = _emails_from(cell)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Berkeley EECS  (single static page, alphabetical)
# ============================================================================
def parse_berkeley(soup, base):
    rows = []
    for item in soup.find_all('div', class_='cc-image-list__item'):
        h3 = item.find('h3')
        a = h3.find('a', href=True) if h3 else None
        name = _txt(a or h3)
        if not name:
            continue
        p = item.find('p')
        strong = p.find('strong') if p else None
        title = _txt(strong) if strong else ''
        research = ', '.join(dict.fromkeys(
            _txt(x) for x in p.find_all('a', href=lambda h: h and '/Research/' in h)
        )) if p else ''
        email, mail = _emails_from(item)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': research})
    return rows


# ============================================================================
# Stanford  (photo + name cards, ?page=N pagination, no emails on listing)
# ============================================================================
def parse_stanford(soup, base):
    rows = []
    for div in soup.find_all('div', class_=re.compile(r'\bnode stanford-person')):
        h3 = div.find('h3')
        a = h3.find('a', href=True) if h3 else None
        if not a:
            continue
        name = _txt(a)
        rows.append({'name': name, 'title': '', 'email': '', 'mail': '',
                     'lab_link': urljoin(base, a['href']), 'research': ''})
    return rows


# ============================================================================
# Harvard SEAS  (views-row, ?page=%2CN pagination)
# ============================================================================
def parse_harvard(soup, base):
    rows = []
    for row in soup.find_all('div', class_='views-row'):
        h2 = row.find('h2')
        a = h2.find('a', href=True) if h2 else None
        name = _txt(a or h2)
        if not name:
            continue
        title = ''
        pt = row.find('div', class_=re.compile('person-directory__titles|person__title'))
        if pt:
            t = _txt(pt)
            title = t.replace(name, '', 1).strip()
        email, mail = _emails_from(row)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Wisconsin  (faculty-member cards)
# ============================================================================
def parse_wisc(soup, base):
    rows = []
    for m in soup.find_all('div', class_='faculty-member'):
        h3 = m.find('h3', class_='faculty-name')
        a = h3.find('a', href=True) if h3 else None
        name = _txt(a or h3)
        if not name:
            continue
        title = ''
        pt = m.find('p', class_='position-title')
        if pt:
            title = _txt(pt).replace('Position title:', '').strip()
        email, mail = _emails_from(m)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Penn State  (results-individual-revised cards)
# ============================================================================
def parse_psu(soup, base):
    rows = []
    for card in soup.find_all('div', class_='results-individual-revised'):
        nameel = card.find('p', class_='name')
        a = nameel.find('a', href=True) if nameel else None
        name = _txt(a or nameel)
        if not name:
            continue
        title = _txt(card.find('p', class_='title'))
        email, mail = _emails_from(card)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Ohio State  (directory grid, surname-first, ?page=N)
# ============================================================================
def parse_osu(soup, base):
    rows = []
    for g in soup.find_all('div', class_='grid-item-link-wrapper'):
        h2 = g.find('h2', class_='directory-grid-name')
        name = _txt(h2) if h2 else ''
        if not name:
            continue
        name = _first_last(name)
        title = _txt(g.find('div', class_='appointment-name'))
        email_el = g.find('div', class_='directory-grid-email')
        email = _txt(email_el) if email_el else ''
        link = ''
        a = g.find('a', class_='grid-item-link', href=True)
        if a:
            link = urljoin(base, a['href'])
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': '', 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# UMD  (media blocks; no emails on listing)
# ============================================================================
def parse_umd(soup, base):
    rows = []
    for b in soup.find_all('div', class_='views-field views-field-nothing-1 media'):
        h4 = b.find('h4', class_='media-heading')
        a = h4.find('a', href=True) if h4 else None
        name = _txt(a or h4)
        if not name:
            continue
        body = b.find('div', class_='media-body')
        title = ''
        if body:
            full = _txt(body)
            t = full.replace(name, '', 1).strip()
            t = re.sub(r'^[,;:\s]+', '', t)
            title = re.split(r'\s{2,}|,?\s+(?=[A-Z][a-z]+ and |$)', t)[0][:120]
        research = ', '.join(dict.fromkeys(
            _txt(x) for x in body.find_all('a', href=lambda h: h and '/research-area/' in h)
        )) if body else ''
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                     'lab_link': link, 'research': research})
    return rows


# ============================================================================
# NC State  (person cards, Cloudflare emails, /people/page/N/ pagination)
# ============================================================================
def parse_ncsu(soup, base):
    rows = []
    for card in soup.find_all('div', class_='person-card'):
        a = card.find('a', class_='name', href=True)
        name = _txt(a) if a else ''
        if not name:
            continue
        title = _txt(card.find('p', class_='title'))
        email_el = card.find('a', class_='email')
        email = _cf_email(email_el) if email_el else ''
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': '', 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Duke  (member-card articles)
# ============================================================================
def parse_duke(soup, base):
    rows = []
    for art in soup.find_all('article'):
        mc = art.find('div', class_='member-card')
        if mc is None:
            continue
        nameel = mc.find('div', class_='h4')
        name = _txt(nameel)
        if not name:
            continue
        title = ''
        for h6 in art.find_all('div', class_='h6'):
            t = _txt(h6)
            if t:
                title = t
        email, mail = _emails_from(art)
        link = ''
        wa = art.find('div', class_='views-field-field-websites')
        if wa:
            w = wa.find('a', href=True)
            if w:
                link = urljoin(base, w['href'])
        if not link:
            img = art.find('a', href=True)
            if img:
                link = urljoin(base, img['href'])
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Arizona  (person article rows)
# ============================================================================
def parse_arizona(soup, base):
    rows = []
    for art in soup.find_all('article', class_='node--type-az-person'):
        h3 = art.find('h3')
        a = h3.find('a', href=True) if h3 else None
        name = _txt(a or h3)
        if not name:
            continue
        title = ''
        for item in art.find_all('div', class_='field__item'):
            t = _txt(item)
            if t and not t.lower().startswith('office') and not t.startswith('('):
                title = t
                break
        email, mail = _emails_from(art)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Georgia Tech  (profile cards; alpha pages /people/faculty/{letter})
# ============================================================================
def parse_gt(soup, base):
    rows = []
    for card in soup.find_all('div', class_='profile-card__content'):
        h4 = card.find('h4', class_='card-block__title')
        a = h4.find('a', href=True) if h4 else None
        name = _txt(a or h4)
        if not name:
            continue
        title = _txt(card.find('h6', class_='card-block__subtitle'))
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                     'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Purdue  (people-item cards)
# ============================================================================
def parse_purdue(soup, base):
    rows = []
    for item in soup.find_all('div', class_='people-item'):
        nameel = item.find('p', class_='people-name')
        a = nameel.find('a', href=True) if nameel else None
        name = _txt(a or nameel)
        if not name:
            continue
        title = _txt(item.find('p', class_='people-title'))
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                     'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# UT Austin  (views-rows with research groups)
# ============================================================================
def parse_utexas(soup, base):
    rows = []
    for row in soup.select('div.view-content.row div.views-row'):
        title_el = row.find('div', class_='views-field-title')
        a = title_el.find('a', href=True) if title_el else None
        name = _txt(a or title_el)
        if not name:
            continue
        title = _txt(row.find('div', class_='views-field-field-contact-faculty-title'))
        research = ', '.join(dict.fromkeys(
            _txt(x) for x in row.find_all('a', href=lambda h: h and '/research/' in h)))
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                     'lab_link': link, 'research': research})
    return rows


# ============================================================================
# Clark Atlanta  (person-list-item; ?page=N)
# ============================================================================
def parse_cau(soup, base):
    rows = []
    for item in soup.find_all('div', class_='person-list-item'):
        h2 = item.find('h2', class_='person-list-item__name')
        a = h2.find('a', href=True) if h2 else None
        name = _txt(a or h2)
        if not name:
            continue
        title = _txt(item.find('p', class_='person-list-item__title'))
        dept = _txt(item.find('div', class_='person-list-item__categories'))
        if not re.search(r'computer|cyber|physics', dept.lower(), re.I):
            continue
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                     'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# FAMU  (accordion paragraphs with mailto)
# ============================================================================
def parse_famu(soup, base):
    rows = []
    for p in soup.find_all('p'):
        m = p.find('a', href=lambda h: h and h.startswith('mailto:'))
        if not m:
            continue
        strong = p.find('strong')
        name = _txt(strong) if strong else ''
        if not name:
            continue
        ems = p.find_all('em')
        title = _txt(ems[0]) if ems else ''
        email, mail = _emails_from(p)
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': '', 'research': ''})
    return rows


# ============================================================================
# Hampton  (elementor person blocks)
# ============================================================================
def parse_hampton(soup, base):
    rows = []
    for h3 in soup.find_all('h3', class_='elementor-heading-title'):
        name = _txt(h3)
        if not name:
            continue
        title = ''
        research = ''
        node = h3
        while node:
            sib = node.find_next_sibling()
            if sib is None:
                break
            t = _txt(sib)
            if t:
                if not title and len(t) < 200 and 'Expertise' not in t and 'Dr.' not in t:
                    title = t
                elif 'Expertise' in t:
                    research = t.replace('Areas of Expertise:', '').strip()
                elif 'Expertise' in t:
                    research = t.replace('Areas of Expertise:', '').strip()
            if len(t) > 250 or 'Expertise' in t:
                break
            node = sib
        rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                     'lab_link': '', 'research': research})
    return rows


# ============================================================================
# Morgan State  (profile-box; emails contain spaces)
# ============================================================================
def parse_morgan(soup, base):
    rows = []
    for pb in soup.find_all('div', class_='profile-box'):
        h4 = pb.find('h4')
        name = _txt(h4) if h4 else ''
        if not name:
            continue
        title = _txt(pb.find('p', class_='title'))
        email, mail = _emails_from(pb)
        email = email.replace(' ', '')
        mail = mail.replace(' ', '')
        link = ''
        la = pb.find('div', class_='link')
        if la:
            a = la.find('a', href=True)
            if a:
                link = urljoin(base, a['href'])
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# UALR  (wp-block-list items: name - title)
# ============================================================================
def parse_ualr(soup, base):
    rows = []
    for ul in soup.select('div.main-content ul.wp-block-list'):
        for li in ul.find_all('li', recursive=False):
            a = li.find('a', href=True)
            if a:
                name = _txt(a)
            else:
                name = _txt(li)
            if not name:
                continue
            txt = _txt(li)
            title = ''
            m = re.search(r'\s*[–-]\s*(.+)$', txt)
            if m:
                title = m.group(1).strip()
            link = urljoin(base, a['href']) if a else ''
            rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                         'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Prairie View A&M  (fusion per-person columns)
# ============================================================================
_TITLE_RE = re.compile(
    r'(Professor|Lecturer|Instructor|Coordinator|Head|Chair|Dean)')


def parse_pvamu(soup, base):
    rows = []
    seen = set()
    for m in soup.find_all('a', href=lambda h: h and h.startswith('mailto:')):
        node = m
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            cls = ' '.join(node.get('class') or [])
            if 'fusion-column-wrapper' in cls:
                break
        h4 = node.find('h4') if node else None
        h4t = _txt(h4) if h4 else ''
        m2 = re.match(r'^(.*?),', h4t)
        if m2:
            name = m2.group(1).strip()
            title = h4t.replace(m2.group(0), '', 1).strip()
        else:
            mm = _TITLE_RE.search(h4t)
            if mm:
                name = h4t[:mm.start()].strip()
                title = h4t[mm.start():].strip()
            else:
                name = h4t
                title = ''
        if not name or name in seen:
            continue
        seen.add(name)
        email, mail = _emails_from(node)
        research = ''
        for p in node.find_all('p'):
            if 'Research Areas' in _txt(p):
                research = _txt(p).replace('Research Areas', '').strip()
                break
        link = ''
        for a in node.find_all('a', href=True):
            t = _txt(a)
            if t and 'professional website' in t.lower():
                link = urljoin(base, a['href'])
                break
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': research})
    return rows


# ============================================================================
# Southern University (SUBR)  (nav faculty links)
# ============================================================================
def parse_subr(soup, base):
    rows = []
    seen = set()
    for ul in soup.find_all('ul', class_='dropdown-menu'):
        if not any('/page/dr-' in a.get('href', '')
                   for a in ul.find_all('a', href=True)):
            continue
        for a in ul.find_all('a', href=True):
            h = a['href']
            if '/page/' not in h:
                continue
            name = _txt(a)
            if (not name or name in seen or len(name) > 50
                    or 'Retired' in name or 'Left' in name):
                continue
            seen.add(name)
            rows.append({'name': name, 'title': '', 'email': '', 'mail': '',
                         'lab_link': urljoin(base, h), 'research': ''})
    return rows


# ============================================================================
# Tennessee State  (faculty table rows)
# ============================================================================
def parse_tnstate(soup, base):
    rows = []
    for tr in soup.find_all('tr'):
        t = _txt(tr)
        if 'Email' not in t or not re.search(r'Professor|Instructor|Chair', t):
            continue
        a = tr.find('a', href=True)
        name = _txt(a) if a else ''
        if not name:
            m = re.match(r'^(Dr\.?\s*|Mr\.?\s*|Ms\.?\s*)?([A-Z][\w.\-]+(?:\s+[A-Z][\w.\-]+)+)', t)
            name = m.group(0) if m else ''
        email_m = re.search(r'Email:\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', t)
        email = email_m.group(1) if email_m else ''
        title = ''
        if a:
            rest = t.split(name, 1)[-1]
            title = re.split(r'\s*Office:', rest)[0].strip()[:120]
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': '', 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Pepperdine  (table rows)
# ============================================================================
def parse_pepperdine(soup, base):
    rows = []
    for tr in soup.find_all('table'):
        pass
    for tr in soup.select('table tbody tr'):
        ps = tr.find_all('p')
        if not ps:
            continue
        name = _txt(ps[0])
        if not name:
            continue
        email, mail = _emails_from(tr)
        title = _txt(ps[2]) if len(ps) > 2 else ''
        a = ps[0].find('a', href=True)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Lamar  (per-person columns)
# ============================================================================
def parse_lamar(soup, base):
    rows = []
    for h3 in soup.find_all('h3'):
        name = _txt(h3)
        if not name or not re.search(r'[A-Za-z]', name):
            continue
        col = h3.parent
        for _ in range(2):
            if col is None:
                break
            if 'columns' in ' '.join(col.get('class') or []):
                break
            col = col.parent
        txt = _txt(col)
        title = ''
        m = re.search(r'Position:\s*([^\n]+)', txt)
        if m:
            title = m.group(1).strip()
        research = ''
        m = re.search(r'Research\s*Interests\s*:\s*(.+?)\s*Email', txt)
        if m:
            research = m.group(1).strip()
        email, mail = _emails_from(col)
        link = ''
        for a in (col.find_all('a', href=True) if col else []):
            t = _txt(a)
            if t and 'email' not in t.lower() and a.get('href', '').startswith('http') \
               and 'lamar.edu' not in a['href']:
                link = urljoin(base, a['href'])
                break
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': research})
    return rows


# ============================================================================
# CSULA  (table rows with Cloudflare emails)
# ============================================================================
def parse_csula(soup, base):
    rows = []
    for tr in soup.select('tbody tr'):
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue
        strong = tds[1].find('strong')
        name = _txt(strong) if strong else ''
        if not name:
            continue
        title = _txt(tds[1].find('em'))
        email = _cf_email(tds[1])
        research = ''
        m = re.search(r'Specialization:\s*([^\n]+)', _txt(tds[1]))
        if m:
            research = m.group(1).strip()
        link = ''
        img = tds[0].find('a', href=True) if tds[0] else None
        if img:
            link = urljoin(base, img['href'])
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': '', 'lab_link': link, 'research': research})
    return rows


# ============================================================================
# UAH  (faculty cards, filter staff)
# ============================================================================
_FACULTY_TITLE_RE = re.compile(
    r'Professor|Lecturer|Chair|Instructor|University', re.I)


def parse_uah(soup, base):
    rows = []
    for card in soup.find_all('div', class_='card'):
        superheads = [_txt(s) for s in card.find_all('span', class_='superhead')]
        titles = [s for s in superheads if _FACULTY_TITLE_RE.search(s)]
        if not titles:
            continue
        nameel = card.find('p', class_='raquo')
        name = _txt(nameel)
        if not name:
            continue
        name = re.sub(r',?\s*(Ph\.?D\.?|M\.?S\.?|B\.?S\.?)$', '', name).strip()
        title = ', '.join(titles)
        email, mail = _emails_from(card)
        link = ''
        a = card.find('a', href=True)
        if a:
            link = urljoin(base, a['href'])
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# UCSD  (faculty profile grid)
# ============================================================================
def parse_ucsd(soup, base):
    rows = []
    for v in soup.find_all('div', class_='views-field views-field-nothing'):
        a = v.find('a', href=True)
        if not a:
            continue
        strong = a.find('strong')
        if strong is None:
            for cand in v.find_all('a', href=True):
                strong = cand.find('strong')
                if strong is not None:
                    a = cand
                    break
        name = _txt(strong or a)
        if not name or 'Profile' in name:
            continue
        link = urljoin(base, a['href'])
        rows.append({'name': name, 'title': '', 'email': '', 'mail': '',
                     'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# UCLA Samueli  (article.card + people-title, rendered)
# ============================================================================
def parse_ucla(soup, base):
    rows = []
    for art in soup.find_all('article', class_='card'):
        t = art.find(class_='people-title')
        a = t.find('a', href=True) if t else None
        name = _txt(a or t)
        if not name or len(name) > 60:
            continue
        email, mail = _emails_from(art)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': '', 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Rice CS  (div.card.card--bio in js-profiles, rendered)
# ============================================================================
def parse_rice(soup, base):
    rows = []
    for prof in soup.find_all('div', class_='js-profiles'):
        for card in prof.find_all('div', class_=re.compile(r'\bcard card--bio')):
            a = card.find('a', class_='h6', href=True)
            if not a:
                a = card.find('a', href=True)
            name = _txt(a) if a else ''
            if not name:
                continue
            title = _txt(card.find('p', class_='body'))
            link = urljoin(base, a['href']) if a else ''
            rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                         'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Virginia State  (ng-repeat directory-item, rendered)
# ============================================================================
def parse_vsu(soup, base):
    rows = []
    for item in soup.find_all(attrs={'ng-repeat': True}):
        nameel = item.find(class_='name')
        a = nameel.find('a', href=True) if nameel else None
        name = _txt(a or nameel)
        if not name:
            continue
        name = _first_last(name)
        title = _txt(item.find(class_='department'))
        email, mail = _emails_from(item)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Wright State  (wsu-embed-people lists; include faculty 640 + joint 1991)
# ============================================================================
def parse_wright(soup, base):
    rows = []
    for block in soup.find_all('div', class_='wsu-embed-people'):
        list_id = block.get('data-list-id', '')
        if list_id and list_id not in ('640', '1991'):
            continue
        for li in block.find_all('li', class_='wsuperson'):
            h2 = li.find('h2', class_='wsuperson__title')
            a = h2.find('a', href=True) if h2 else None
            name = _txt(a or h2)
            if not name:
                continue
            title = ''
            tf = li.find(class_='wsuperson__field--title')
            if tf:
                fc = tf.find(class_='field__content')
                title = _txt(fc or tf)
            email, mail = _emails_from(li)
            link = urljoin(base, a['href']) if a else ''
            rows.append({'name': name, 'title': title, 'email': email,
                         'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# UMich  (eecs_person_wrapper; email hidden in inline JS var one/two)
# ============================================================================
def parse_umich(soup, base):
    rows = []
    for w in soup.find_all('div', class_='eecs_person_wrapper'):
        h4 = w.find('h4')
        name = _txt(h4) if h4 else ''
        if not name:
            continue
        name = _first_last(name)
        title = ', '.join(dict.fromkeys(
            _txt(s) for s in w.find_all('span', class_='person_title_section')))
        email = ''
        for script in w.find_all('script'):
            js = script.get_text()
            m1 = re.search(r"var one = '([^']+)'", js)
            m2 = re.search(r"var two = '([^']+)'", js)
            if m1 and m2:
                email = f"{m1.group(1)}@{m2.group(1)}"
                break
        if not email:
            email, _ = _emails_from(w)
        research = ''
        for s in w.find_all('span', class_='person_copy_section'):
            t = _txt(s)
            if t.lower().startswith('research interests'):
                research = t.replace('Research Interests:', '').strip()
                break
        link = ''
        web = w.find('a', class_='person_web', href=True)
        if web:
            link = urljoin(base, web['href'])
            link = re.sub(r'https://web\.archive\.org/web/[0-9]+(?:im_)?/', '', link)
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': '', 'lab_link': link, 'research': research})
    return rows


# ============================================================================
# UC Irvine  (article.item--person cards; research + website on profile pages)
# ============================================================================
def parse_uci(soup, base):
    rows = []
    for art in soup.find_all('article', class_='item--person'):
        content = art.find('div', class_='person__content')
        nameel = content.find('h3', class_='person__person-title') if content else None
        name = _txt(nameel)
        if not name:
            continue
        link = ''
        la = art.find('a', class_='item__link', href=True)
        if la:
            link = urljoin(base, la['href'])
        email, mail = _emails_from(art)
        title = ''
        if content:
            jt = content.find('span', class_='person__job-title')
            title = _txt(jt)
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# NYU (cs.nyu.edu people-listing: .name cards, 'at nyu.edu' emails)
# ============================================================================
_RANKS = ('Assistant Professor', 'Associate Professor', 'Professor of',
          'Assistant Professor of', 'Associate Professor of', 'Senior Lecturer',
          'Lecturer', 'Professor', 'Instructor', 'Chair', 'Dean', 'Research')


def _split_name_title(text):
    """Split 'James Aspnes Harold W. Cheel Professor' -> name, title."""
    low = text.lower()
    idxs = [low.find(r.lower()) for r in _RANKS if low.find(r.lower()) >= 0]
    if idxs:
        i = min(idxs)
        return text[:i].strip(), text[i:].strip()
    parts = text.split()
    if len(parts) > 2:
        return ' '.join(parts[:2]), ' '.join(parts[2:])
    return text, ''


def parse_yale(soup, base):
    rows, seen = [], set()
    for a in soup.find_all('a', class_='faculty-department-item', href=True):
        text = _txt(a)
        if not text or text in seen or len(text) > 80:
            continue
        seen.add(text)
        name, title = _split_name_title(text)
        link = urljoin(base, a['href'])
        rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                     'lab_link': link, 'research': ''})
    return rows


def parse_nyu(soup, base):
    rows, seen = [], set()
    for n in soup.find_all(['h2', 'h3', 'h4', 'div', 'span', 'p'],
                           class_=re.compile(r'\bname\b')):
        a = n.find('a', href=True)
        name = _txt(a or n)
        if not name or name in seen or len(name) > 70:
            continue
        seen.add(name)
        card = n.parent
        if card is None:
            card = n
        t = card.get_text(' ', strip=True)
        email = mail = ''
        m = re.search(r'([\w.\-+]+)\s+at\s+([\w\-.]+\.[a-z]{2,})\b', t, re.I)
        if m:
            email = f"{m.group(1)}@{m.group(2)}"
        title = ''
        mt = re.search(r'(?:Assistant|Associate|Full|Adjunct|Clinical|Research|'
                       r'Teaching|Distinguished|Global|Visiting|Professor)\s+'
                       r'Professor(?:[^,]*?)(?: of [^,]*)?', t, re.I)
        if mt:
            title = mt.group(0)
        research = ''
        mr = re.search(r'(?:email:|\bemail\b).*?\.(?:edu|org|com|net)\s*(.*?)(?:office:|ext:|\bemail:|$)', t, re.I)
        if mr and mr.group(1).strip():
            research = '; '.join(x.strip() for x in mr.group(1).split(',')
                                 if x.strip())[:150]
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': research})
    return rows


# ============================================================================
# Montana State (cs.montana.edu office-hours table: Person | Office | Hours)
# ============================================================================
def parse_montana(soup, base):
    rows, seen = [], set()
    for tr in soup.find_all('tr'):
        tds = tr.find_all(['td', 'th'])
        if len(tds) < 2:
            continue
        name = _first_last(_txt(tds[0]))
        if not name or name in seen or len(name) > 70:
            continue
        if any(w in name.lower() for w in ('advisor', 'manager', 'coordinator',
                                           'staff', 'faculty', 'director',
                                           'person')):
            continue
        seen.add(name)
        rows.append({'name': name, 'title': '', 'email': '', 'mail': '',
                     'lab_link': '', 'research': ''})
    return rows


# ============================================================================
# UMKC (sse.umkc.edu directories: HTML shell points at a data-src JSON file)
# ============================================================================
def parse_umkc(soup, base):
    import requests
    rows, seen = [], set()
    div = soup.find('div', class_='paginationDirectory')
    if div is None or not div.get('data-src'):
        return rows
    url = urljoin(base, div['data-src'])
    try:
        data = requests.get(url, timeout=30).json()
    except Exception:
        return rows
    for e in data:
        name = ' '.join((e.get('name') or '').strip().split())
        if not name or name.lower() in seen or len(name) > 70:
            continue
        seen.add(name.lower())
        email = (e.get('email') or '').strip()
        title = '; '.join(e.get('title') or []) if isinstance(e.get('title'), list) else (e.get('title') or '')
        link = (e.get('link') or '').strip()
        if link.startswith('/'):
            link = urljoin('https://sse.umkc.edu/', link)
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': email, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# North Dakota (engineering.und.edu people-listing items)
# ============================================================================
def parse_und(soup, base):
    rows, seen = [], set()
    for item in soup.find_all('div', class_='people-listing__item'):
        name = _txt(item.find(class_='people-listing__name'))
        if not name or name in seen or len(name) > 70:
            continue
        seen.add(name)
        email, mail = _emails_from(item)
        title = _txt(item.find(class_='people-listing__dept'))
        link = ''
        a = item.find('a', href=True)
        if a is not None:
            link = urljoin(base, a['href'])
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Idaho (directory.uidaho.edu table: Name | Phone | Title)
# ============================================================================
def parse_idaho(soup, base):
    rows, seen = [], set()
    for tr in soup.find_all('tr'):
        tds = tr.find_all(['td', 'th'])
        if len(tds) < 2:
            continue
        name = _first_last(_txt(tds[0]))
        if not name or name in seen or len(name) > 70:
            continue
        if name.lower() in ('name', 'department', 'person'):
            continue
        seen.add(name)
        title = _txt(tds[2]) if len(tds) > 2 else ''
        rows.append({'name': name, 'title': title, 'email': '', 'mail': '',
                     'lab_link': '', 'research': ''})
    return rows


# ============================================================================
# UNLV (unlv.edu/cs/directory views-row cards)
# ============================================================================
def parse_unlv(soup, base):
    rows, seen = [], set()
    for row in soup.find_all('div', class_='views-row'):
        h4 = row.find('h4')
        name = _txt(h4)
        if not name or name in seen or len(name) > 70:
            continue
        seen.add(name)
        email, mail = _emails_from(row)
        title = _txt(row.find('em'))
        link = ''
        for a in row.find_all('a', href=True):
            href = (a['href'] or '').strip()
            if href.startswith(('mailto:', 'tel:', '#')):
                continue
            link = urljoin(base, href)
            break
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Cornell (cs.cornell.edu directory-card markup)
# ============================================================================
def parse_cornell(soup, base):
    rows, seen = [], set()
    for card in soup.find_all('div', class_='directory-card'):
        name = _txt(card.find('div', class_='name'))
        if not name or name in seen or len(name) > 70:
            continue
        seen.add(name)
        email, mail = _emails_from(card)
        link = ''
        a = card.find('a', href=True)
        if a is not None:
            link = urljoin(base, a['href'])
        title = _txt(card.find('div', class_='position-titles'))
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Florida State (cs.fsu.edu faculty-card markup)
# ============================================================================
def parse_fsu(soup, base):
    rows, seen = [], set()
    for card in soup.find_all('article', class_='faculty-card'):
        a = card.find('a', class_='faculty-name')
        name = _txt(a)
        if not name or name in seen or len(name) > 70:
            continue
        seen.add(name)
        title = _txt(card.find('div', class_='faculty-title'))
        email, mail = _emails_from(card)
        link = urljoin(base, a['href']) if a else ''
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# UC Santa Barbara (cs.ucsb.edu person-teaser views-rows)
# ============================================================================
_SECTION_NAMES = {'faculty', 'faculty emeriti', 'affiliated faculty', 'faculty emerita',
                  'emeriti', 'emerita', 'main campus', 'panama city campus',
                  'adjunct faculty', 'teaching faculty', 'research faculty',
                  'lecturers', 'teaching professors'}


def parse_ucsb(soup, base):
    rows, seen = [], set()
    for row in soup.select('.view-faculty .views-row, .person-teaser .views-row'):
        h2 = row.find('h2')
        name = _txt(h2)
        if not name or name in seen or len(name) > 70:
            continue
        if name.lower().strip() in _SECTION_NAMES:
            continue
        seen.add(name)
        email, mail = _emails_from(row)
        link = ''
        for a in row.find_all('a', href=True):
            href = (a['href'] or '').strip()
            if href.startswith(('mailto:', 'tel:', '#')):
                continue
            link = urljoin(base, href)
            break
        rows.append({'name': name, 'title': '', 'email': email, 'mail': mail,
                     'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Pittsburgh (cs.pitt.edu view-people rows)
# ============================================================================
def parse_pitt(soup, base):
    rows, seen = [], set()
    for row in soup.select('.view-people .views-row'):
        name = _txt(row.select_one('.view-people__title'))
        if not name or name in seen or len(name) > 70:
            continue
        seen.add(name)
        email, mail = _emails_from(row)
        link = ''
        a = row.find('a', href=lambda h: h and '/people/' in h)
        if a is not None:
            link = urljoin(base, a['href'])
        rows.append({'name': name, 'title': '', 'email': email, 'mail': mail,
                     'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Marshall University (marshall.edu CECS profile-list markup)
# ============================================================================
def parse_marshall(soup, base):
    rows, seen = [], set()
    for a in soup.find_all('a', href=lambda h: h and '/profile/' in h):
        name = _txt(a)
        if not name or name in seen or len(name) > 70:
            continue
        seen.add(name)
        card = a.find_parent('div', class_=re.compile('entry-content'))
        if card is None:
            card = a.parent
        email, mail = _emails_from(card)
        link = ''
        for x in card.find_all('a', href=True):
            h = (x['href'] or '').strip()
            if h == a['href'] or h.startswith(('mailto:', 'tel:', '#')):
                continue
            if 'visit website' in x.get_text(' ', strip=True).lower():
                link = urljoin(base, h)
                break
        rows.append({'name': name, 'title': '', 'email': email, 'mail': mail,
                     'lab_link': link, 'research': ''})
    return rows


# ============================================================================
# Brown University (cs.brown.edu profile-list markup)
# ============================================================================
def parse_brown(soup, base):
    rows = []
    seen = set()
    for ul in soup.find_all('ul', class_='profile-list'):
        for li in ul.find_all('li', recursive=False):
            name = _txt(li.find('li', class_='profile-name')) or _txt(li.find('h3'))
            if not name or name in seen or len(name) > 70:
                continue
            seen.add(name)
            email, mail = _emails_from(li)
            areas = '; '.join(
                a for s in li.find_all('span', class_=('primary_areas',
                                                       'secondary_areas'))
                for a in [s.get_text(' ', strip=True)] if a)
            link = ''
            for a in li.find_all('a', href=True):
                href = (a['href'] or '').strip()
                label = a.get_text(' ', strip=True).lower()
                if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                    continue
                if 'profile' in label or 'home' in label:
                    link = urljoin(base, href)
                    break
            rows.append({'name': name, 'title': _txt(li.find('li', class_='profile-title')),
                         'email': email, 'mail': mail, 'lab_link': link,
                         'research': areas})
    return rows


# ============================================================================
# Generic fallback: any card-ish element with a name + link/email
# ============================================================================
def parse_generic(soup, base):
    rows = _generic_card_pass(soup, base)
    if not rows:
        rows = _generic_heading_pass(soup, base)
    return rows


def _generic_card_pass(soup, base):
    rows = []
    seen = set()
    _SKIP = ('block', 'view-', 'region', 'menu', 'nav', 'header', 'footer',
             'layout', 'pager', 'sidebar', 'tabs', 'tab-', 'widget')
    for node in soup.find_all(['div', 'li', 'article', 'section']):
        cls = ' '.join(node.get('class') or [])
        if not any(k in cls.lower() for k in
                   ['faculty', 'person', 'profile', 'people', 'staff', 'card',
                    'member', 'entity', 'listing', 'personnel', 't-']):
            continue
        # skip structural / framework wrappers (Drupal blocks & views, nav...)
        tokens = cls.lower().split()
        if any(any(t.startswith(s) for s in _SKIP) for t in tokens):
            continue
        nameel = node.find(['h2', 'h3', 'h4', 'h5'])
        name = _txt(nameel) if nameel else ''
        if not name or len(name) > 70 or name in seen:
            continue
        # a block/sidebar title heading ('Menu', 'Block title'...) is UI, not a
        # person name
        if nameel is not None:
            ncls = ' '.join(nameel.get('class') or []).lower()
            if 'block-title' in ncls or any(
                    t.startswith(s) for t in ncls.split()
                    for s in ('block', 'menu', 'sidebar', 'tabs')):
                continue
            pcls = ' '.join((nameel.parent.get('class') or [])).lower() \
                if nameel.parent is not None else ''
            if any(t.startswith(s) for t in pcls.split()
                   for s in ('block', 'menu', 'sidebar', 'region', 'tabs')):
                continue
        email, mail = _emails_from(node)
        link = ''
        for a in node.find_all('a', href=True):
            href = (a['href'] or '').strip()
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            if a.find_parent(['nav', 'header', 'footer']) is not None:
                continue
            link = urljoin(base, href)
            break
        if not email and not link:
            continue
        seen.add(name)
        title = _txt(node).replace(name, '', 1).strip()[:150]
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows


def _generic_heading_pass(soup, base):
    """Card-ish containers that carry a name heading + a link/email but use
    generic class names (t-entry, listing__row, entity_detail...)."""
    rows = []
    seen = set()
    for h in soup.find_all(['h2', 'h3', 'h4', 'h5']):
        name = _txt(h)
        if not name or len(name) > 70 or name in seen:
            continue
        parts = name.split()
        if not 2 <= len(parts) <= 5:
            continue
        if any(p and p[0].islower() for p in parts):
            continue
        if '/' in name or any('/' in p for p in parts):
            continue
        if name.lower() in _SECTION_NAMES:
            continue
        card = h.parent
        if card is None or card.find_parent(['nav', 'header', 'footer']) is not None:
            continue
        cls = ' '.join(card.get('class') or [])
        if any(t.startswith(s) for t in cls.lower().split()
               for s in ('block', 'view-', 'region', 'menu', 'nav', 'header',
                         'footer', 'layout', 'pager', 'sidebar', 'widget')):
            continue
        if len(card.get_text(' ', strip=True)) > 2000:
            continue
        email, mail = _emails_from(card)
        link = ''
        for a in card.find_all('a', href=True):
            href = (a['href'] or '').strip()
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue
            link = urljoin(base, href)
            break
        if not email and not link:
            continue
        seen.add(name)
        title = _txt(card).replace(name, '', 1).strip()[:150]
        rows.append({'name': name, 'title': title, 'email': email,
                     'mail': mail, 'lab_link': link, 'research': ''})
    return rows