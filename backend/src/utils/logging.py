"""Logging utilities for the application."""
from typing import Dict, Any, Union

def truncate_data(data: Union[Dict, str, Any]) -> Union[Dict, str, Any]:
    """Truncate sensitive or large data for logging."""
    def _truncate_value(value: Any) -> Any:
        """Helper to truncate individual values."""
        if not isinstance(value, str):
            return value
            
        # Truncate base64 image data
        if 'base64,' in value:
            return '[BASE64_IMAGE]'
        # Truncate HTML
        if '<' in value and '>' in value:
            return '[HTML_CONTENT]'
        # Truncate JSON
        if '{"' in value or '[{' in value:
            return '[JSON_CONTENT]'
        # Truncate long strings
        if len(value) > 30:  # Even shorter truncation
            return f"{value[:30]}..."
        return value

    def _truncate_dict(d: Dict) -> Dict:
        """Recursively truncate dictionary values."""
        result = {}
        for k, v in d.items():
            # Always truncate certain fields
            if k in ['screenshot', 'html', 'content', 'response']:
                result[k] = '[TRUNCATED]'
                continue
                
            if isinstance(v, dict):
                result[k] = _truncate_dict(v)
            elif isinstance(v, list):
                result[k] = [_truncate_value(item) for item in v]
            else:
                result[k] = _truncate_value(v)
        return result

    if isinstance(data, dict):
        return _truncate_dict(data)
    return _truncate_value(data) 