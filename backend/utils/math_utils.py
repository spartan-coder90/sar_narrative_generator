def safe_divide(numerator, denominator, default=0):
    """
    Safely divide two numbers, returning default if denominator is zero
    
    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Default value to return if denominator is zero
        
    Returns:
        float: Result of division or default value
    """
    return numerator / denominator if denominator != 0 else default