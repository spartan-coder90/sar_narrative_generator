"""
Optimized LLM Client for interaction with Llama 3:8B
"""
import requests
import json
import logging
from typing import Dict, Any, Optional, List

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
    
    def _call_api(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """
        Call LLM API with error handling
        
        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in the response
            temperature: Temperature setting (lower is more deterministic)
            
        Returns:
            str: Generated text or empty string if API call fails
        """
        if not self.api_url or not self.api_key:
            logger.warning("LLM API not configured, returning empty result")
            return ""
            
        # Prepare request payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
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
            logger.error(f"Error calling LLM API: {str(e)}")
            return ""
    
    def generate_section(self, section_type: str, data: Dict[str, Any]) -> str:
        """
        Generate a specific section of the SAR narrative
        
        Args:
            section_type: Type of section to generate (introduction, subject_info, etc.)
            data: Preprocessed data for the section
            
        Returns:
            str: Generated section text
        """
        # Define focused, simple prompts for each section type
        prompts = {
            "introduction": (
                "Write the first paragraph of a SAR narrative with this exact information:\n"
                f"Bank: U.S. Bank National Association (USB)\n"
                f"Activity type: {data.get('activity_type', 'suspicious activity')}\n"
                f"Total amount: {data.get('total_amount', '$0.00')}\n"
                f"Derived from: {data.get('derived_from', '')}\n"
                f"Subjects: {data.get('subjects', 'unknown subjects')}\n"
                f"Account type: {data.get('account_type', 'checking/savings')}\n"
                f"Account number: {data.get('account_number', '')}\n"
                f"Date range: {data.get('start_date', '')} to {data.get('end_date', '')}\n\n"
                "Start with: 'U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report...'"
            ),
            "prior_cases": (
                "Write a short paragraph about prior SARs using this information:\n"
                f"Prior SARs: {data.get('prior_cases_text', 'No prior SARs were identified.')}\n\n"
                "If no prior SARs, simply write: 'No prior SARs were identified for the subjects or account.'"
            ),
            "account_info": (
                "Write a paragraph about the account using this information:\n"
                f"Account type: {data.get('account_type', 'checking/savings')}\n"
                f"Account number: {data.get('account_number', '')}\n"
                f"Open date: {data.get('open_date', '')}\n"
                f"Account status: {data.get('account_status', 'remains open')}\n"
                f"Close date: {data.get('close_date', '')}\n"
                f"Closure reason: {data.get('closure_reason', '')}\n\n"
                "Describe the account information in a single paragraph."
            ),
            "activity_summary": (
                "Write a paragraph summarizing account activity using this information:\n"
                f"Account number: {data.get('account_number', '')}\n"
                f"Date range: {data.get('start_date', '')} to {data.get('end_date', '')}\n"
                f"Total credits: {data.get('total_credits', '$0.00')}\n"
                f"Total debits: {data.get('total_debits', '$0.00')}\n"
                f"Activity description: {data.get('activity_description', '')}\n"
                f"AML risks: {data.get('aml_risks', '')}\n\n"
                "Summarize the activity factually without speculation."
            ),
            "conclusion": (
                "Write a conclusion paragraph for a SAR narrative with this information:\n"
                f"Case number: {data.get('case_number', '')}\n"
                f"Activity type: {data.get('activity_type', 'suspicious activity')}\n"
                f"Total amount: {data.get('total_amount', '$0.00')}\n"
                f"Subjects: {data.get('subjects', '')}\n"
                f"Account number: {data.get('account_number', '')}\n"
                f"Date range: {data.get('start_date', '')} to {data.get('end_date', '')}\n\n"
                "Start with 'In conclusion, USB is reporting...' and end with "
                "'USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting "
                "documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number [CASE NUMBER].'"
            )
        }
        
        # Get prompt for the requested section
        prompt = prompts.get(section_type, "")
        if not prompt:
            logger.warning(f"No prompt template defined for section type: {section_type}")
            return ""
        
        # Call LLM with simplified prompt
        return self._call_api(prompt, max_tokens=500, temperature=0.2)
    
    def determine_activity_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine type of suspicious activity from data
        
        Args:
            data: Case and transaction data
            
        Returns:
            Dict: Activity type information
        """
        # This function now does the determination entirely in Python
        # without relying on the LLM
        
        # Simple determination based on keywords in available data
        activity_indicators = {
            "STRUCTURING": ["structure", "ctr", "cash deposit", "multiple deposit", "9000", "below 10000"],
            "UNUSUAL_ACH": ["ach", "wire", "transfer", "electronic", "payment", "zelle", "venmo"],
            "UNUSUAL_CASH": ["cash", "atm", "withdraw", "deposit", "currency", "dollar bill"],
            "MONEY_LAUNDERING": ["launder", "shell", "funnel", "layering", "money laundering", "suspicious"]
        }
        
        # Extract relevant information for detection
        alert_info = data.get("alert_info", {})
        alert_desc = ""
        
        # Handle alert info in different formats
        if isinstance(alert_info, list) and alert_info:
            for alert in alert_info:
                if isinstance(alert, dict):
                    alert_desc += alert.get("description", "").lower() + " "
        elif isinstance(alert_info, dict):
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
        
        # Look for transaction patterns
        transaction_summary = data.get("transaction_summary", {})
        
        # Check if there are cash transactions
        credit_breakdown = transaction_summary.get("credit_breakdown", [])
        debit_breakdown = transaction_summary.get("debit_breakdown", [])
        
        for breakdown in credit_breakdown + debit_breakdown:
            txn_type = breakdown.get("type", "").lower()
            
            # Check for cash-related keywords
            if any(cash_word in txn_type for cash_word in ["cash", "atm", "currency"]):
                scores["UNUSUAL_CASH"] += 2
            
            # Check for ACH/wire-related keywords
            if any(ach_word in txn_type for ach_word in ["ach", "wire", "transfer"]):
                scores["UNUSUAL_ACH"] += 2
        
        # Check for structuring patterns
        unusual_activity = data.get("unusual_activity", {})
        transactions = unusual_activity.get("transactions", [])
        
        # Look for multiple transactions below CTR threshold ($10,000)
        below_threshold_count = sum(1 for txn in transactions 
                                  if isinstance(txn.get("amount"), (int, float)) and 
                                  txn.get("amount") > 8000 and txn.get("amount") < 10000)
        
        if below_threshold_count >= 2:
            scores["STRUCTURING"] += 3
        
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
        
        # Format total amount
        total_amount = activity_summary.get("total_amount", 0)
        if isinstance(total_amount, str):
            total_amount = total_amount.replace('$', '').replace(',', '')
            try:
                total_amount = float(total_amount)
            except ValueError:
                total_amount = 0
        
        # Format dates
        start_date = activity_summary.get("start_date", "")
        end_date = activity_summary.get("end_date", "")
        
        # Create a basic narrative
        fallback_text = (
            f"U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report suspicious activity in account {account_info.get('account_number', '')}. "
            f"The total suspicious amount is approximately ${total_amount:,.2f}. "
            f"The activity occurred from {start_date} to {end_date}. "
            f"USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number {case_number}."
        )
        
        return fallback_text