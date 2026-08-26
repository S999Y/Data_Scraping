"""
University Faculty Scraper Package
A modular scraper for extracting professor data from university websites.
"""

from .scraper import ConfigurableScraper
from .config_builder import ConfigBuilder
from .configs import (
    JHU_CONFIG,
    CONFIG_REGISTRY,
    get_config,
    register_config
)
from .analyze_html import AnalyzeHTML
from .faculty import (
    is_cse_page,
    detect_university,
    scrape_faculty_page,
    CSE_KEYWORDS
)
from .utils import (
    validate_config,
    load_config_from_file,
    save_config_to_file,
    print_statistics,
    combine_datasets,
    export_to_excel,
    save_html
)

__version__ = "1.0.0"
__all__ = [
    'ConfigurableScraper',
    'ConfigBuilder',
    'AnalyzeHTML',
    'JHU_CONFIG',
    'CONFIG_REGISTRY',
    'get_config',
    'register_config',
    'is_cse_page',
    'detect_university',
    'scrape_faculty_page',
    'CSE_KEYWORDS',
    'validate_config',
    'load_config_from_file',
    'save_config_to_file',
    'print_statistics',
    'combine_datasets',
    'export_to_excel',
    'save_html'
]
