"""
Core scraper module for extracting professor data from university websites.
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigurableScraper:
    """
    A modular scraper that uses configuration dictionaries to extract data
    from any website structure.
    """
    
    def __init__(self, config: Dict[str, Any], output_file: str = "scraped_data.csv"):
        """
        Initialize the scraper with a configuration.
        
        Args:
            config: Configuration dictionary with extraction rules
            output_file: Output file path
        """
        self.config = config
        self.output_file = output_file
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.data = []
        
    def extract_from_element(self, element: BeautifulSoup, extractors: List[Dict]) -> Dict:
        """
        Extract data from a single element using the provided extractors.
        
        Args:
            element: BeautifulSoup element to extract from
            extractors: List of extraction rules
            
        Returns:
            Dictionary of extracted data
        """
        result = {}
        
        for rule in extractors:
            field_name = rule.get('field', 'unknown')
            selector = rule.get('selector', {})
            extraction_type = rule.get('type', 'text')
            multiple = rule.get('multiple', False)
            required = rule.get('required', False)
            
            try:
                if extraction_type == 'list':
                    # List type uses container/item selectors, not tag/css
                    container_rule = selector.get('container', {})
                    item_rule = selector.get('item', {})
                    
                    if container_rule and item_rule:
                        if 'class' in container_rule:
                            container = element.find(container_rule['tag'], 
                                                     class_=container_rule['class'])
                        else:
                            container = element.find(container_rule['tag'])
                            
                        if container:
                            if 'class' in item_rule:
                                items = container.find_all(item_rule['tag'], 
                                                          class_=item_rule['class'])
                            else:
                                items = container.find_all(item_rule['tag'])
                            result[field_name] = [item.get_text(strip=True) for item in items]
                        else:
                            result[field_name] = None
                    else:
                        result[field_name] = None
                    continue
                
                # Find the element(s) for non-list types
                if 'css' in selector:
                    elements = element.select(selector['css'])
                elif 'find' in selector:
                    raw = selector['find'](element)
                    elements = raw if isinstance(raw, list) else [raw]
                elif 'tag' in selector and ('class' in selector or 'id' in selector):
                    kwargs = {}
                    if 'class' in selector:
                        kwargs['class_'] = selector['class']
                    if 'id' in selector:
                        kwargs['id'] = selector['id']
                    elements = element.find_all(selector['tag'], **kwargs)
                elif 'tag' in selector:
                    elements = element.find_all(selector['tag'])
                else:
                    elements = []
                    
                if not elements:
                    if required:
                        logger.warning(f"Required field '{field_name}' not found")
                    result[field_name] = None
                    continue
                
                # Extract based on type
                if extraction_type == 'text':
                    if multiple:
                        result[field_name] = [el.get_text(strip=True) for el in elements]
                    else:
                        result[field_name] = elements[0].get_text(strip=True)
                        
                elif extraction_type == 'attribute':
                    attr = selector.get('attribute', 'href')
                    if multiple:
                        result[field_name] = [el.get(attr, '') for el in elements]
                    else:
                        result[field_name] = elements[0].get(attr, '')
                        
                elif extraction_type == 'html':
                    if multiple:
                        result[field_name] = [str(el) for el in elements]
                    else:
                        result[field_name] = str(elements[0])
                        
                elif extraction_type == 'custom':
                    custom_func = selector.get('function')
                    if custom_func:
                        if multiple:
                            result[field_name] = [custom_func(el) for el in elements]
                        else:
                            result[field_name] = custom_func(elements[0])
                    else:
                        logger.warning(f"No custom function provided for {field_name}")
                        result[field_name] = None
                        
                else:
                    result[field_name] = None
                    
            except Exception as e:
                logger.error(f"Error extracting {field_name}: {e}")
                result[field_name] = None
                    
        return result
    
    def scrape_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a webpage.
        
        Args:
            url: URL to scrape
            
        Returns:
            BeautifulSoup object or None
        """
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def scrape(self, url: str) -> List[Dict]:
        """
        Main scraping method using the configuration.
        
        Args:
            url: URL to scrape
            
        Returns:
            List of extracted data dictionaries
        """
        soup = self.scrape_page(url)
        if not soup:
            return []
        return self.scrape_soup(soup, url)

    def scrape_soup(self, soup: BeautifulSoup, url: str = '') -> List[Dict]:
        """
        Extract data from an already-fetched page using the configuration.
        Used by wrappers that need to inspect the page first (e.g. CSE check).
        
        Args:
            soup: Already parsed page
            url: Original URL (stored in each row for reference)
            
        Returns:
            List of extracted data dictionaries
        """
        # Get container configuration
        container_config = self.config.get('container', {})
        extractors = self.config.get('extractors', [])
        
        # Find all items to extract
        if 'tag' in container_config and ('class' in container_config or 'id' in container_config):
            kwargs = {}
            if 'class' in container_config:
                kwargs['class_'] = container_config['class']
            if 'id' in container_config:
                kwargs['id'] = container_config['id']
            items = soup.find_all(container_config['tag'], **kwargs)
        elif 'tag' in container_config:
            items = soup.find_all(container_config['tag'])
        elif 'css' in container_config:
            items = soup.select(container_config['css'])
        else:
            logger.error("No container configuration found")
            return []
        
        # Extract data from each item
        results = []
        for idx, item in enumerate(items):
            extracted = self.extract_from_element(item, extractors)
            
            # Add URL for reference
            extracted['url'] = url
            extracted['index'] = idx
            
            results.append(extracted)
            name = extracted.get('name', 'Unknown')
            logger.info(f"Extracted item {idx+1}: {name[:50]}")
            
        self.data.extend(results)
        return results
    
    def scrape_multiple(self, urls: List[str]) -> List[Dict]:
        """
        Scrape multiple URLs.
        
        Args:
            urls: List of URLs to scrape
            
        Returns:
            Combined results
        """
        all_results = []
        for url in urls:
            results = self.scrape(url)
            all_results.extend(results)
            time.sleep(self.config.get('delay', 2))
        return all_results
    
    def scrape_paginated(self, base_url: str, start_page: int = 1, end_page: Optional[int] = None) -> List[Dict]:
        """
        Scrape paginated results.
        
        Args:
            base_url: URL pattern with {page} placeholder
            start_page: Starting page number
            end_page: Ending page number (None for unlimited)
            
        Returns:
            Combined results
        """
        page = start_page
        all_results = []
        
        while True:
            if end_page and page > end_page:
                break
                
            url = base_url.format(page=page)
            results = self.scrape(url)
            
            if not results:
                break
                
            all_results.extend(results)
            logger.info(f"Page {page}: Found {len(results)} items")
            
            if end_page and page >= end_page:
                break
                
            page += 1
            time.sleep(self.config.get('delay', 2))
            
        return all_results
    
    def save(self, fmt: str = 'csv'):
        """
        Save scraped data to file.
        
        Args:
            fmt: 'csv' or 'json'
        """
        if not self.data:
            logger.warning("No data to save")
            return
            
        df = pd.DataFrame(self.data)
        
        # Handle list fields
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, list)).any():
                df[col] = df[col].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
        
        if fmt == 'csv':
            output = self.output_file if self.output_file.endswith('.csv') else f"{self.output_file}.csv"
            df.to_csv(output, index=False, encoding='utf-8')
            logger.info(f"Data saved to {output}")
        elif fmt == 'json':
            output = self.output_file if self.output_file.endswith('.json') else f"{self.output_file}.json"
            df.to_json(output, orient='records', indent=2)
            logger.info(f"Data saved to {output}")
        else:
            logger.error(f"Unsupported format: {fmt}")
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the scraped data.
        
        Returns:
            Dictionary with statistics
        """
        if not self.data:
            return {'total': 0}
        
        stats = {
            'total': len(self.data),
            'fields': list(self.data[0].keys()),
            'field_completeness': {}
        }
        
        for field in stats['fields']:
            if field in ['url', 'index']:
                continue
            present = sum(1 for item in self.data if item.get(field) is not None and item.get(field) != '')
            stats['field_completeness'][field] = {
                'present': present,
                'percentage': (present / len(self.data)) * 100
            }
        
        return stats
    
    def clear_data(self):
        """Clear all collected data."""
        self.data = []
