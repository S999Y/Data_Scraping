"""
Configuration builder utilities for creating scraper configurations.
"""

from typing import Dict, List, Callable, Optional

class ConfigBuilder:
    """
    Helper class to build configurations dynamically.
    """
    
    @staticmethod
    def create_config(container_tag: str, container_class: str, fields: List[Dict]) -> Dict:
        """
        Create a configuration from simple parameters.
        
        Args:
            container_tag: HTML tag of the container (e.g., 'div')
            container_class: CSS class of the container
            fields: List of field configurations
            
        Returns:
            Complete configuration dictionary
        """
        return {
            'name': 'Custom Configuration',
            'container': {
                'tag': container_tag,
                'class': container_class
            },
            'extractors': fields,
            'delay': 1.5
        }
    
    @staticmethod
    def field(name: str, tag: str, class_name: str = None, 
              field_type: str = 'text', attribute: str = None, 
              required: bool = False) -> Dict:
        """
        Helper to create a field configuration.
        
        Args:
            name: Field name
            tag: HTML tag
            class_name: CSS class (optional)
            field_type: 'text', 'attribute', 'list', 'custom'
            attribute: For type='attribute', which attribute to extract
            required: Whether field is required
            
        Returns:
            Field configuration dictionary
        """
        selector = {'tag': tag}
        if class_name:
            selector['class'] = class_name
        if attribute:
            selector['attribute'] = attribute
            
        return {
            'field': name,
            'selector': selector,
            'type': field_type,
            'required': required
        }
    
    @staticmethod
    def list_field(name: str, container_tag: str, container_class: str, 
                   item_tag: str, item_class: str = None) -> Dict:
        """
        Helper to create a list field configuration.
        
        Args:
            name: Field name
            container_tag: HTML tag of the container
            container_class: CSS class of the container
            item_tag: HTML tag of items within container
            item_class: CSS class of items (optional)
            
        Returns:
            List field configuration
        """
        return {
            'field': name,
            'selector': {
                'container': {'tag': container_tag, 'class': container_class},
                'item': {'tag': item_tag, 'class': item_class} if item_class else {'tag': item_tag}
            },
            'type': 'list'
        }
    
    @staticmethod
    def custom_field(name: str, tag: str, class_name: str, 
                     function: Callable) -> Dict:
        """
        Helper to create a custom field with a transformation function.
        
        Args:
            name: Field name
            tag: HTML tag
            class_name: CSS class
            function: Function to transform the element
            
        Returns:
            Custom field configuration
        """
        return {
            'field': name,
            'selector': {
                'tag': tag,
                'class': class_name,
                'function': function
            },
            'type': 'custom'
        }
    
    @staticmethod
    def simple_config(container_tag: str, container_class: str, 
                     field_mappings: Dict[str, Dict]) -> Dict:
        """
        Create a configuration from a simple field mapping.
        
        Args:
            container_tag: HTML tag of the container
            container_class: CSS class of the container
            field_mappings: Dictionary mapping field names to extraction rules
                           Example: {'name': {'tag': 'h2', 'class': 'name'}}
            
        Returns:
            Complete configuration dictionary
        """
        extractors = []
        
        for field_name, mapping in field_mappings.items():
            extractor = {
                'field': field_name,
                'selector': {'tag': mapping['tag']},
                'type': mapping.get('type', 'text')
            }
            
            if 'class' in mapping:
                extractor['selector']['class'] = mapping['class']
            if 'attribute' in mapping:
                extractor['selector']['attribute'] = mapping['attribute']
            if 'required' in mapping:
                extractor['required'] = mapping['required']
                
            extractors.append(extractor)
        
        return {
            'name': 'Simple Configuration',
            'container': {
                'tag': container_tag,
                'class': container_class
            },
            'extractors': extractors,
            'delay': 1.5
        }
