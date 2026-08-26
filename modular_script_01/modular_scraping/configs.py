"""
Predefined configurations for various universities.
"""

from urllib.parse import urljoin
from typing import Dict, Any


# ============================================================================
# Configuration Registry
# ============================================================================

CONFIG_REGISTRY: Dict[str, Any] = {}

def get_config(university: str) -> Dict[str, Any]:
    """
    Get configuration for a specific university.
    
    Args:
        university: University name key
        
    Returns:
        Configuration dictionary
    """
    return CONFIG_REGISTRY.get(university.lower())

def register_config(name: str, config: Dict[str, Any]):
    """
    Register a new configuration.
    
    Args:
        name: Configuration name
        config: Configuration dictionary
    """
    CONFIG_REGISTRY[name.lower()] = config


'''
============================================================================
 JHU Configuration
============================================================================
'''
# example config
JHU_CONFIG = {
    'name': 'Johns Hopkins University - CS',
    'container': {
        'tag': 'div',
        'class': 'entity'
    },
    'extractors': [
        {
            'field': 'name',
            'selector': {'tag': 'a', 'class': 'entity_name_link'},
            'type': 'text',
            'required': True
        },
        {
            'field': 'profile_url',
            'selector': {'tag': 'a', 'class': 'entity_name_link', 'attribute': 'href'},
            'type': 'attribute',
            'required': False
        },
        {
            'field': 'title',
            'selector': {'tag': 'div', 'class': 'entity_title'},
            'type': 'text'
        },
        {
            'field': 'department',
            'selector': {
                'tag': 'a', 
                'class': 'entity_detail_link',
                'function': lambda el: el.find('span', class_='entity_detail_info_label').get_text(strip=True) if el and el.find('span', class_='entity_detail_info_label') else ''
            },
            'type': 'custom'
        },
        {
            'field': 'email',
            'selector': {
                'find': lambda el: el.find_all('a', href=lambda x: x and x.startswith('mailto:')),
                'function': lambda el: el.get('href', '').replace('mailto:', '') if el else ''
            },
            'type': 'custom'
        },
        {
            'field': 'research_areas',
            'selector': {
                'container': {'tag': 'div', 'class': 'entity_meta_detail_research_areas'},
                'item': {'tag': 'span'}
            },
            'type': 'list'
        },
        {
            'field': 'image_url',
            'selector': {
                'tag': 'img',
                'attribute': 'src',
                'function': lambda el: urljoin('https://www.cs.jhu.edu', el.get('src', '')) if el else ''
            },
            'type': 'custom'
        }
    ],
    'delay': 1.5
}


john_hopkins_config = {
    'name': 'Johns Hopkins University - CS Faculty',
    'container': {
        'tag': 'div',
        'class': 'entity'
    },
    'extractors': [
        {
            'field': 'name',
            'selector': {
                'tag': 'a',
                'class': 'entity_name_link'
            },
            'type': 'text',
            'required': True
        },
        {
            'field': 'designation',
            'selector': {
                'tag': 'div',
                'class': 'entity_title'
            },
            'type': 'text'
        },
        {
            'field': 'profile_url',
            'selector': {'tag': 'a', 'class': 'entity_name_link', 'attribute': 'href'},
            'type': 'attribute',
            'required': True
        },
        {
            'field': 'department',
            'selector': {
                'tag': 'a',
                'class': 'entity_detail_link',
                'function': lambda el: (
                    el.find('span', class_='entity_detail_info_label').get_text(strip=True)
                    if el and el.find('span', class_='entity_detail_info_label')
                    else ''
                )
            },
            'type': 'custom'
        },
        {
            'field': 'email',
            'selector': {
                'find': lambda container: container.find_all(
                    'a',
                    href=lambda href: href and href.startswith('mailto:')
                ),
                'function': lambda el: (
                    el.get('href', '').replace('mailto:', '')
                    if el else ''
                )
            },
            'type': 'custom'
        },
        {
            'field': 'research_areas',
            'selector': {
                'container': {
                    'tag': 'div',
                    'class': 'entity_meta_detail_research_areas'
                },
                'item': {
                    'tag': 'span'
                }
            },
            'type': 'list'
        }
    ],
    'delay': 1.5
}

register_config('john_hopkins_config',john_hopkins_config)


# ============================================================================
# MIT Professional Education - Instructor Profiles
# URL: https://professional.mit.edu/programs/instructor-profiles
# ============================================================================
from urllib.parse import urljoin

MIT_PROFED_BASE = 'https://professional.mit.edu'

MIT_PROFED_CONFIG = {
    'name': 'MIT Professional Education - Instructor Profiles',
    'container': {
        'tag': 'article',
        'class': 'node--type-faculty'
    },
    'extractors': [
        {
            'field': 'name',
            'selector': {'tag': 'div', 'class': 'faux-full-title'},
            'type': 'text',
            'required': True
        },
        {
            'field': 'designation',
            'selector': {
                'tag': 'div',
                'class': 'field--name-field-professional-titles',
                'function': lambda el: ' | '.join(
                    item.get_text(strip=True)
                    for item in (el.find_all('div', class_='field__item') if el else [])
                ) if el and el.find_all('div', class_='field__item') else (el.get_text(strip=True) if el else '')
            },
            'type': 'custom'
        },
        {
            'field': 'summary',
            'selector': {'tag': 'div', 'class': 'field--name-field-person-summary'},
            'type': 'text'
        },
        {
            'field': 'profile_url',
            'selector': {
                'tag': 'a',
                'class': 'people-card-wrap',
                'function': lambda el: urljoin(MIT_PROFED_BASE, el.get('href', '')) if el else ''
            },
            'type': 'custom'
        },
        {
            'field': 'photo_url',
            'selector': {
                'tag': 'img',
                'class': 'image-style-person-photo',
                'function': lambda el: urljoin(MIT_PROFED_BASE, el.get('src', '')) if el else ''
            },
            'type': 'custom'
        }
    ],
    'delay': 1.5
}
register_config('mit_profed_config', MIT_PROFED_CONFIG)


# ============================================================================
# Carnegie Mellon University - University Professors
# URL: https://www.cmu.edu/leadership/the-provost/university-professors
# ============================================================================
CMU_UNIVERSITY_PROFESSORS_CONFIG = {
    'name': 'CMU University Professors',
    'container': {
        'tag': 'div',
        'class': 'paragraph--type--up-panel-card'
    },
    'extractors': [
        {
            'field': 'name',
            'selector': {'tag': 'strong'},
            'type': 'text',
            'required': True
        },
        {
            'field': 'designation',
            'selector': {
                'tag': 'p',
                'function': lambda el: (
                    el.get_text(' ', strip=True)
                    .replace(el.find('strong').get_text(strip=True), '', 1)
                    .strip(' :;-,')
                    if el and el.find('strong') else (el.get_text(' ', strip=True) if el else '')
                )
            },
            'type': 'custom'
        }
    ],
    'delay': 1.5
}
register_config('cmu_university_professors_config', CMU_UNIVERSITY_PROFESSORS_CONFIG)

SCHOLAR_CONFIG = {
    'name': 'Google Scholar Profile',
    'container': {
        'tag': 'tr',
        'class': 'gsc_a_tr'
    },
    'extractors': [
        {
            'field': 'paper_title',
            'selector': {'tag': 'a', 'class': 'gsc_a_at'},
            'type': 'text',
            'required': True
        },
        {
            'field': 'paper_url',
            'selector': {'tag': 'a', 'class': 'gsc_a_at', 'attribute': 'href'},
            'type': 'attribute',
            'required': False
        },
        {
            'field': 'authors',
            'selector': {'tag': 'div', 'class': 'gs_gray'},
            'type': 'text',
            'required': False
        },
        {
            'field': 'conference',
            'selector': {
                'find': lambda el: el.find_all('div', class_='gs_gray')[1:2],
                'function': lambda el: el.get_text(strip=True).split(',')[0] if el else ''
            },
            'type': 'custom'
        },
        {
            'field': 'year',
            'selector': {
                'tag': 'span',
                'class': 'gs_oph',
                'function': lambda el: el.get_text(strip=True).lstrip(', ') if el else ''
            },
            'type': 'custom'
        }
    ],
    'delay': 1.5
}
register_config('SCHOLAR_CONFIG',SCHOLAR_CONFIG)
