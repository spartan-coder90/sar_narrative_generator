"""
Utility functions for data type conversions and comparisons.

This module provides helper functions to robustly convert string values to
numerical types (float, int) and to compare date strings in various formats.
These utilities are used across the application to handle data extracted from
different sources with varying formats.
"""
import re
from datetime import datetime
from typing import Any, Optional # Added for more precise type hinting

def to_float(value: Any) -> float:
    """
    Converts a value to a float, removing currency symbols and commas if it's a string.
    Returns 0.0 if conversion fails or the input value is None or an unhandled type.

    Args:
        value: The value to convert. Can be None, int, float, or str.

    Returns:
        The float representation of the value, or 0.0 on failure.
    Returns 0.0 if conversion fails or the input value is None or an unhandled type.
    """
    if value is None:
        return 0.0
    if isinstance(value, (float, int)): # If already a number, just convert to float
        return float(value)
    if not isinstance(value, str): # If not a string and not a number/None, return 0.0
        return 0.0

    # For strings: remove currency symbols, commas, and whitespace
    cleaned_value = re.sub(r'[$\s,]', '', value)
    if not cleaned_value: # If string becomes empty after cleaning
        return 0.0
    try:
        return float(cleaned_value)
    except ValueError: # If conversion to float fails
        return 0.0

def to_int(value: Any) -> int:
    """
    Converts a value to an integer. If the value is a string, it removes
    currency symbols and commas. If it's a float, it truncates to an integer.
    Returns 0 if conversion fails or the input value is None or an unhandled type.

    Args:
        value: The value to convert. Can be None, int, float, or str.

    Returns:
        The integer representation of the value, or 0 on failure.
    """
    if value is None:
        return 0
    if isinstance(value, int): # If already an int, return as is
        return value
    if isinstance(value, float): # If float, truncate to int
        return int(value)
    if not isinstance(value, str): # If not a string and not a number/None, return 0
        return 0

    # For strings: remove currency symbols, commas, and whitespace
    cleaned_value = re.sub(r'[$\s,]', '', value)
    if not cleaned_value:
        return 0
    try:
        # Handle potential float strings by first converting to float
        return int(float(cleaned_value))
    except ValueError:
        return 0

def compare_dates(date1_str: str, date2_str: str, mode: str = 'earliest') -> str | None:
    """
    Compares two date strings and returns the earliest or latest.
    Returns None if both dates are invalid or None. If one date is valid and the other
    is not, the valid date string is returned.
    Supported string formats for dates: YYYY-MM-DD, MM/DD/YYYY, YYYYMMDD.
    Date strings can also include time information (e.g., "YYYY-MM-DD HH:MM:SS"),
    which will be ignored for the comparison.

    Args:
        date1_str: The first date string.
        date2_str: The second date string.
        mode: Comparison mode, either 'earliest' or 'latest'. Defaults to 'earliest'.

    Returns:
        The date string that is determined to be the earliest or latest based on the mode,
        or None if a definitive comparison cannot be made or both inputs are invalid.
    """
    # Handle cases where one or both date strings are empty or None.
    if not date1_str and not date2_str:
        return None
    if not date1_str: # If only date1 is invalid, return date2
        return date2_str
    if not date2_str: # If only date2 is invalid, return date1
        return date1_str

    dt1: Optional[datetime] = None
    dt2: Optional[datetime] = None
    # Common date formats to attempt parsing.
    possible_formats = ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d', '%m-%d-%Y', '%d-%m-%Y', '%Y/%m/%d']

    # Attempt to parse the first date string.
    # str(date1_str).split(" ")[0] handles cases like "YYYY-MM-DD HH:MM:SS" by taking only the date part.
    for fmt in possible_formats:
        try:
            dt1 = datetime.strptime(str(date1_str).split(" ")[0], fmt)
            break # Successfully parsed, exit loop.
        except (ValueError, TypeError):
            continue # Try next format.

    # Attempt to parse the second date string.
    for fmt in possible_formats:
        try:
            dt2 = datetime.strptime(str(date2_str).split(" ")[0], fmt)
            break # Successfully parsed, exit loop.
        except (ValueError, TypeError):
            continue # Try next format.

    # Decision logic based on parsed dates:
    if not dt1 and not dt2: # Both dates are invalid after trying all formats.
        return None
    if not dt1: # Only date1 is invalid.
        return date2_str
    if not dt2: # Only date2 is invalid.
        return date1_str

    # Both dates are valid, perform comparison based on mode.
    if mode == 'earliest':
        return date1_str if dt1 < dt2 else date2_str
    elif mode == 'latest':
        return date1_str if dt1 > dt2 else date2_str

    # Should not be reached if mode is correctly 'earliest' or 'latest'.
    # Consider raising an error for invalid mode if strictness is desired.
    return None
