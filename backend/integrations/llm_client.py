"""
LLM Client for interaction with language models
"""
import requests
import json
import logging
from typing import Dict, Any, Optional

import backend.config as config

logger = logging.getLogger(__name__)

class LLMClient:
    """Client for interacting with language models to enhance narrative generation"""
    
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the LLM client
        
        Args:
            api_url: API URL for LLM service
            api_key: API key for authentication
            model: Model identifier
        """
        self.api_url = api_url or config.LLM_API_URL
        self.api_key = api_key or config.LLM_API_KEY
        self.model = model or config.LLM_MODEL
        
        if not self.api_url:
            logger.warning("LLM API URL not configured. LLM features will be disabled.")
        
        if not self.api_key:
            logger.warning("LLM API key not configured. LLM features will be disabled.")
    
    def generate_narrative(self, prompt_template: str, data: Dict[str, Any]) -> str:
        """
        Generate narrative using LLM
        
        Args:
            prompt_template: The prompt template with placeholders
            data: Data to fill the template
            
        Returns:
            str: Generated text
        """
        if not self.api_url or not self.api_key:
            logger.warning("LLM not configured, using fallback generation")
            return self._fallback_generation(data)
            
        # Format prompt with data
        try:
            prompt = prompt_template.format(**data)
        except KeyError as e:
            logger.error(f"Error formatting prompt: {e}")
            prompt = prompt_template
            
        # Prepare request payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": 1000,
            "temperature": 0.3,
            "top_p": 0.95
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Make API request
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result.get("choices", [{}])[0].get("text", "").strip()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling LLM API: {e}")
            return self._fallback_generation(data)
    
    def determine_activity_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine type of suspicious activity from data
        
        Args:
            data: Case and transaction data
            
        Returns:
            Dict: Activity type information
        """
        # Simple determination based on keywords in available data
        activity_indicators = {
            "STRUCTURING": ["structure", "ctr", "cash deposit", "multiple deposit"],
            "UNUSUAL_ACH": ["ach", "wire", "transfer", "electronic"],
            "UNUSUAL_CASH": ["cash", "atm", "withdraw", "deposit"],
            "MONEY_LAUNDERING": ["launder", "shell", "funnel", "layering"]
        }
        
        # Extract relevant information for detection
        alert_info = data.get("alert_info", {})
        alert_desc = alert_info.get("description", "").lower()
        activity_desc = data.get("activity_summary", {}).get("description", "").lower()
        
        # Count matches for each activity type
        scores = {activity: 0 for activity in activity_indicators}
        
        for activity, keywords in activity_indicators.items():
            for keyword in keywords:
                if keyword in alert_desc:
                    scores[activity] += 2
                if keyword in activity_desc:
                    scores[activity] += 1
        
        # Get activity type with highest score, default to UNUSUAL_ACH
        best_match = max(scores.items(), key=lambda x: x[1])[0] if any(scores.values()) else "UNUSUAL_ACH"
        
        # Return the activity type information from config
        return config.ACTIVITY_TYPES.get(best_match, config.ACTIVITY_TYPES["UNUSUAL_ACH"])
    
    def _fallback_generation(self, data: Dict[str, Any]) -> str:
        """
        Fallback generation when LLM is not available
        
        Args:
            data: Case and transaction data
            
        Returns:
            str: Simple generated text
        """
        # Extract basic information for a simple narrative
        account_info = data.get("account_info", {})
        activity_summary = data.get("activity_summary", {})
        case_number = data.get("case_number", "Unknown")
        
        # Create a basic narrative
        fallback_text = (
            f"USB is filing this SAR to report suspicious activity in account {account_info.get('account_number', '')}. "
            f"The total suspicious amount is approximately ${activity_summary.get('total_amount', 0):,.2f}. "
            f"The activity occurred from {activity_summary.get('start_date', '')} to {activity_summary.get('end_date', '')}. "
            f"For additional information, please reference case number {case_number}."
        )
        
        return fallback_text