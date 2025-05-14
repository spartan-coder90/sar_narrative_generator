"""
JSON utilities for serialization and deserialization
"""
import json
import decimal
from datetime import date, datetime
import numpy as np
import pandas as pd
from typing import Any

class EnhancedJSONEncoder(json.JSONEncoder):
    """
    Enhanced JSON encoder that handles additional types:
    - datetime, date: converts to ISO format
    - Decimal: converts to float
    - Numpy types: converts to Python standard types
    - Pandas DataFrame: converts to dictionary
    - Sets: converts to list
    """
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)

def serialize_to_json(obj: Any) -> str:
    """
    Serialize an object to JSON string
    
    Args:
        obj: Object to serialize
        
    Returns:
        str: JSON string
    """
    return json.dumps(obj, cls=EnhancedJSONEncoder)

def save_to_json_file(obj: Any, filepath: str) -> None:
    """
    Save an object to a JSON file
    
    Args:
        obj: Object to save
        filepath: Path to JSON file
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(obj, f, cls=EnhancedJSONEncoder)

def load_from_json_file(filepath: str) -> Any:
    """
    Load an object from a JSON file
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Any: Loaded object
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def sanitize_for_json(data):
    """
    Sanitize data to prevent JSON serialization issues
    
    Args:
        data: Data to sanitize
        
    Returns:
        Any: Sanitized data
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, (int, float, bool)) or data is None:
        return data
    else:
        # Convert everything else to string
        try:
            return str(data)
        except:
            return "Error converting to string"