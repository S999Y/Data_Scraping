"""
HTML analysis tool - inspects HTML structure to help build configs.
"""

import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

TEXT_MAX = 120
ATTR_KEYWORDS = {'href', 'src', 'alt', 'title', 'data-href', 'data-src'}


def _safe(s: Any, maxlen: int = 0) -> str:
    s = str(s)
    if maxlen and len(s) > maxlen:
        s = s[:maxlen] + '...'
    return s.encode('utf-8', errors='replace').decode('utf-8', errors='replace')


class AnalyzeHTML:
    def __init__(self, source: str, source_type: str = 'auto'):
        self.source = source
        self.soup: Optional[BeautifulSoup] = None
        self._analysis: Optional[Dict] = None

        if source_type == 'auto':
            if source.startswith(('http://', 'https://')):
                source_type = 'url'
            elif os.path.isfile(source):
                source_type = 'file'
            else:
                source_type = 'string'

        if source_type == 'url':
            resp = requests.get(source, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            resp.raise_for_status()
            self.soup = BeautifulSoup(resp.content, 'html.parser')
        elif source_type == 'file':
            with open(source, encoding='utf-8') as f:
                self.soup = BeautifulSoup(f.read(), 'html.parser')
        else:
            self.soup = BeautifulSoup(source, 'html.parser')

    def analyze(self) -> Dict:
        if self._analysis:
            return self._analysis

        soup = self.soup
        if not soup:
            return {}

        body = soup.find('body') or soup

        elements: List[Dict] = []
        seen: Set[str] = set()
        tag_groups: Dict[str, List[Tag]] = defaultdict(list)

        for el in body.find_all(True):
            if isinstance(el, Tag) and el.name not in ('script', 'style'):
                self._collect_element(el, elements, seen, tag_groups)

        repeated = [
            {'selector': sel, 'tag': tag, 'count': len(group)}
            for (tag, sel), group in sorted(tag_groups.items(), key=lambda x: -len(x[1]))
            if len(group) > 1
        ]

        containers = self._find_containers(body)
        links_data = self._collect_links(body)
        images_data = self._collect_images(body)

        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ''

        self._analysis = {
            'title': title,
            'elements': elements,
            'repeated_patterns': repeated[:30],
            'container_candidates': containers[:15],
            'links': links_data,
            'images': images_data,
            'element_count': len(elements),
        }
        return self._analysis

    def _css_path(self, el: Tag) -> str:
        parts = []
        for parent in el.parents:
            if parent.name == '[document]':
                break
            tag = parent.name
            cls = parent.get('class', [])
            if cls and isinstance(cls, list):
                tag += '.' + '.'.join(cls)
            parts.append(tag)
        parts.reverse()
        tag = el.name
        cls = el.get('class', [])
        if cls and isinstance(cls, list):
            tag += '.' + '.'.join(cls)
        parts.append(tag)
        return ' > '.join(parts)

    def _collect_element(self, el: Tag, elements: List[Dict], seen: Set[str], tag_groups: Dict[str, List[Tag]]):
        classes = el.get('class', [])
        if isinstance(classes, str):
            classes = [classes]
        classes = [c for c in classes if c]
        el_id = el.get('id', '')

        key = f'{el.name}.' + '.'.join(sorted(classes)) + (f'#{el_id}' if el_id else '')
        if key in seen:
            sel = el.name
            if classes:
                sel += '.' + '.'.join(classes)
            tag_groups[(el.name, sel)].append(el)
            return

        seen.add(key)

        text = _safe(el.get_text(strip=True)[:TEXT_MAX])
        attrs = {}
        for k, v in el.attrs.items():
            if k in ATTR_KEYWORDS or k.startswith('data-') or k == 'style':
                val = str(v) if not isinstance(v, list) else ' '.join(v)
                if len(val) > 120:
                    val = val[:120] + '...'
                attrs[k] = _safe(val)

        sel = el.name
        if classes:
            sel += '.' + '.'.join(classes)

        children_count = sum(1 for c in el.children if isinstance(c, Tag) and c.name not in ('script', 'style'))

        elements.append({
            'tag': el.name,
            'classes': classes,
            'id': el_id or None,
            'selector': sel,
            'css_path': self._css_path(el),
            'text': text or None,
            'attrs': attrs or None,
            'children': children_count,
            'count': 1,
        })
        tag_groups[(el.name, sel)].append(el)

    def _find_containers(self, body: Tag) -> List[Dict]:
        candidates = []
        seen_patterns: Dict[str, int] = defaultdict(int)
        pattern_samples: Dict[str, Tag] = {}

        for el in body.find_all(True):
            if el.name in ('script', 'style', 'noscript'):
                continue
            classes = el.get('class', [])
            if isinstance(classes, str):
                classes = [classes]
            classes = [c for c in classes if c]

            if not classes and not el.get('id'):
                continue

            direct_children = [
                c for c in el.children
                if isinstance(c, Tag) and c.name not in ('script', 'style')
            ]
            if len(direct_children) < 1:
                continue

            child_sigs = []
            for c in direct_children:
                cc = c.get('class', [])
                if isinstance(cc, str):
                    cc = [cc]
                cc = [x for x in cc if x]
                cid = c.get('id', '')
                child_sigs.append(f'{c.name}.' + '.'.join(sorted(cc)) + (f'#{cid}' if cid else ''))

            pattern = '|'.join(child_sigs)
            seen_patterns[pattern] += 1
            if pattern not in pattern_samples:
                pattern_samples[pattern] = el

        for pattern, count in sorted(seen_patterns.items(), key=lambda x: -x[1]):
            if count < 2:
                continue
            sample = pattern_samples[pattern]
            classes = sample.get('class', [])
            if isinstance(classes, str):
                classes = [classes]
            classes = [c for c in classes if c]

            sel = sample.name
            if classes:
                sel += '.' + '.'.join(classes)
            if sample.get('id'):
                sel += '#' + sample['id']

            child_summary = []
            for c in sample.children:
                if isinstance(c, Tag) and c.name not in ('script', 'style'):
                    cc = c.get('class', [])
                    if isinstance(cc, str):
                        cc = [cc]
                    cc = [x for x in cc if x]
                    child_sel = c.name
                    if cc:
                        child_sel += '.' + '.'.join(cc)
                    if c.get('id'):
                        child_sel += '#' + c['id']
                    child_summary.append(child_sel)

            candidates.append({
                'selector': sel,
                'count': count,
                'children': child_summary,
            })

        return candidates

    def _collect_links(self, body: Tag) -> List[Dict]:
        links = []
        seen_urls: Set[str] = set()
        for a in body.find_all('a', href=True):
            href = _safe(a['href'])
            if href.startswith('javascript:') or href == '#':
                continue
            key = href[:80]
            if key in seen_urls:
                continue
            seen_urls.add(key)
            text = _safe(a.get_text(strip=True)[:80]) or None
            cls = ' '.join(a.get('class', [])) if a.get('class') else None
            links.append({
                'href': href[:120],
                'text': text,
                'classes': cls,
            })
            if len(links) >= 20:
                break
        return links

    def _collect_images(self, body: Tag) -> List[Dict]:
        images = []
        seen_src: Set[str] = set()
        for img in body.find_all('img', src=True):
            src = _safe(img['src'])
            key = src[:80]
            if key in seen_src:
                continue
            seen_src.add(key)
            alt = _safe(img.get('alt', '')[:80]) or None
            cls = ' '.join(img.get('class', [])) if img.get('class') else None
            images.append({
                'src': src[:120],
                'alt': alt,
                'classes': cls,
            })
            if len(images) >= 10:
                break
        return images

    def to_dict(self) -> Dict:
        return self.analyze()

    def save_markdown(self, filename: str = 'analysis.md') -> str:
        md = self.to_markdown()
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out_dir = os.path.join(root, 'analyze')
        os.makedirs(out_dir, exist_ok=True)
        filepath = os.path.join(out_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md)
        print(f'Analysis saved to {filepath}')
        return filepath

    def to_markdown(self) -> str:
        data = self.analyze()
        lines = []
        lines.append(f'# HTML Analysis: {data["title"]}')
        lines.append(f'**Unique elements:** {data["element_count"]}')
        lines.append('')

        if data['repeated_patterns']:
            lines.append('## Repeated Patterns (potential containers)')
            lines.append('| Selector | Tag | Count |')
            lines.append('|----------|------|-------|')
            for p in data['repeated_patterns'][:20]:
                lines.append(f'| `{p["selector"]}` | `{p["tag"]}` | {p["count"]} |')
            lines.append('')

        if data['container_candidates']:
            lines.append('## Container Candidates')
            lines.append('Elements whose children follow the same pattern:')
            lines.append('')
            for c in data['container_candidates'][:10]:
                lines.append(f'### `{c["selector"]}` (\u00d7{c["count"]})')
                lines.append('Children:')
                for child in c['children']:
                    lines.append(f'  - `{child}`')
                lines.append('')

        if data['elements']:
            lines.append('## All Unique Elements')
            lines.append('| Tag | Classes | ID | Selector | Text | Attributes |')
            lines.append('|-----|---------|----|----------|------|------------|')
            for el in data['elements'][:50]:
                cls = ' '.join(el['classes']) if el['classes'] else ''
                txt = (el['text'][:60] + '...') if el['text'] and len(el['text']) > 60 else (el['text'] or '')
                attrs = ', '.join(f'{k}="{v}"' for k, v in (el['attrs'] or {}).items()) if el['attrs'] else ''
                lines.append(f'| `{el["tag"]}` | {cls} | {el["id"] or ""} | `{el["selector"]}` | {txt} | {attrs} |')
            lines.append('')

        if data['links']:
            lines.append('## Sample Links')
            lines.append('| URL | Text | Classes |')
            lines.append('|-----|------|---------|')
            for ln in data['links'][:15]:
                txt = ln['text'] or ''
                cls = ln['classes'] or ''
                lines.append(f'| `{ln["href"]}` | {txt} | {cls} |')
            lines.append('')

        if data['images']:
            lines.append('## Sample Images')
            lines.append('| Src | Alt | Classes |')
            lines.append('|-----|-----|---------|')
            for im in data['images'][:8]:
                alt = im['alt'] or ''
                cls = im['classes'] or ''
                lines.append(f'| `{im["src"]}` | {alt} | {cls} |')
            lines.append('')

        return '\n'.join(lines)

    def summarize(self):
        data = self.analyze()
        print(f'Title: {_safe(data["title"])}')
        print(f'Unique elements: {data["element_count"]}')
        print()

        if data['repeated_patterns']:
            print(f'Repeated patterns ({len(data["repeated_patterns"])}):')
            for p in data['repeated_patterns'][:10]:
                print(f'  {_safe(p["selector"]):40s} \u00d7{p["count"]}')

        if data['container_candidates']:
            print(f'\nContainer candidates ({len(data["container_candidates"])}):')
            for c in data['container_candidates'][:8]:
                children = ', '.join(c['children'][:4])
                print(f'  {_safe(c["selector"]):40s} \u00d7{c["count"]:3d}  [{_safe(children)}]')
                if len(c['children']) > 4:
                    print(f'  {"":40s}   ... and {len(c["children"]) - 4} more')

        print(f'\nElements ({len(data["elements"])}):')
        for el in data['elements'][:20]:
            cls = ' '.join(el['classes']) if el['classes'] else ''
            txt = _safe(el['text'][:60]) if el['text'] else ''
            print(f'  <{el["tag"]}>{("." + cls) if cls else ""}{("#" + el["id"]) if el["id"] else ""}  {txt}')

        if data['links']:
            print(f'\nLinks ({len(data["links"])} shown):')
            for ln in data['links'][:8]:
                txt = _safe(ln['text'][:40]) if ln['text'] else ''
                print(f'  {_safe(ln["href"][:60]):60s}  {txt}')

        if data['images']:
            print(f'\nImages ({len(data["images"])} shown):')
            for im in data['images'][:5]:
                print(f'  {_safe(im["src"][:60]):60s}  {_safe(im.get("alt",""))}')
