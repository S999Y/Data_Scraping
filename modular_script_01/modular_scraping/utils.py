"""
Utility functions for the scraper.
"""

import json
import os
import requests
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
import pandas as pd

def load_config_from_file(filepath: str) -> Dict:
    """
    Load configuration from a JSON file.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Configuration dictionary
    """
    with open(filepath, 'r') as f:
        return json.load(f)

def save_config_to_file(config: Dict, filepath: str):
    """
    Save configuration to a JSON file.
    
    Args:
        config: Configuration dictionary
        filepath: Path to save JSON file
    """
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)

def combine_datasets(file1: str, file2: str, output_file: str):
    """
    Combine two scraped datasets.
    
    Args:
        file1: First CSV file
        file2: Second CSV file
        output_file: Output file path
    """
    df1 = pd.read_csv(file1)
    df2 = pd.read_csv(file2)
    combined = pd.concat([df1, df2], ignore_index=True)
    combined.to_csv(output_file, index=False)
    print(f"Combined {len(df1)} + {len(df2)} = {len(combined)} records")

def validate_config(config: Dict) -> bool:
    """
    Validate a configuration dictionary.
    
    Args:
        config: Configuration to validate
        
    Returns:
        True if valid, False otherwise
    """
    required_keys = ['container', 'extractors']
    
    for key in required_keys:
        if key not in config:
            print(f"Missing required key: {key}")
            return False
    
    # Check container
    container = config['container']
    if 'tag' not in container and 'css' not in container:
        print("Container must have 'tag' or 'css'")
        return False
    
    # Check extractors
    for extractor in config['extractors']:
        if 'field' not in extractor:
            print("Extractor missing 'field'")
            return False
        if 'selector' not in extractor:
            print(f"Extractor '{extractor.get('field')}' missing 'selector'")
            return False
        if 'type' not in extractor:
            print(f"Extractor '{extractor.get('field')}' missing 'type'")
            return False
    
    return True

def print_statistics(stats: Dict):
    """
    Pretty print statistics.
    
    Args:
        stats: Statistics dictionary
    """
    print("\n" + "=" * 60)
    print("SCRAPING STATISTICS")
    print("=" * 60)
    
    print(f"\nTotal Items: {stats.get('total', 0)}")
    
    field_completeness = stats.get('field_completeness', {})
    if field_completeness:
        print("\nField Completeness:")
        for field, info in field_completeness.items():
            print(f"  {field}: {info['present']}/{stats['total']} ({info['percentage']:.1f}%)")
    
    print("=" * 60)

def export_to_excel(data: List[Dict], output_file: str):
    """
    Export scraped data to Excel file.
    
    Args:
        data: List of dictionaries
        output_file: Output file path
    """
    df = pd.DataFrame(data)
    
    # Handle list fields
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, list)).any():
            df[col] = df[col].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
    
    df.to_excel(output_file, index=False)
    print(f"Data exported to {output_file}")

def save_html(url: str, filename: Optional[str] = None, clean: bool = False, body_only: bool = False) -> Optional[str]:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_dir = os.path.join(root, 'html_pages')
    os.makedirs(html_dir, exist_ok=True)

    if not filename:
        parsed = urlparse(url)
        filename = parsed.netloc + parsed.path.rstrip('/').replace('/', '_')
        if not filename.endswith('.html'):
            filename += '.html'

    filepath = os.path.join(html_dir, filename)

    try:
        resp = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        resp.raise_for_status()

        html = resp.text
        if clean or body_only:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            if clean:
                for tag in soup.find_all(['script', 'style']):
                    tag.decompose()
                for tag in soup.find_all('link', rel='stylesheet'):
                    tag.decompose()
            if body_only:
                body = soup.find('body')
                html = str(body) if body else str(soup)
            else:
                html = str(soup)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"HTML saved to {filepath}")
        return filepath
    except Exception as e:
        print(f"Failed to save HTML from {url}: {e}")
        return None
