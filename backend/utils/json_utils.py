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