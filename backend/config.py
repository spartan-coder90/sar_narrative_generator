"""
Configuration file for the SAR Narrative Generator
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
UPLOAD_DIR = BASE_DIR / "uploads"
LOG_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
for directory in [TEMPLATE_DIR, UPLOAD_DIR, LOG_DIR]:
    os.makedirs(directory, exist_ok=True)

# API settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
API_DEBUG = os.getenv("API_DEBUG", "False").lower() == "true"

# LLM settings
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:3000/api/chat")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3-8b")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))  # Low temperature for more predictable outputs

# SAR Narrative templates (placeholders to be filled in)
TEMPLATES = {
    "INTRODUCTION": """Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report {activity_type} totaling ${total_amount} {derived_from} by {subjects} in {account_type} account number {account_number}. The suspicious activity was conducted from {start_date} through {end_date}. This SAR contains an attached Comma Separated Value (CSV) file that provides additional details of the suspicious transactions being reported in this SAR.""",
    
    "PRIOR_CASES": """Prior SAR (Case Number: {prior_case_number}) was filed on {prior_filing_date} reporting similar activity.""",
    
    "ACCOUNT_INFO": """Personal {account_type} account {account_number} was opened on {open_date} and {account_status} on {close_date}. The account was closed due to {closure_reason}. The account closure funds were moved to {funds_destination} on {transfer_date}.""",
    
    "ACTIVITY_SUMMARY": """The suspicious activity identified in account {account_number} was conducted from {start_date} to {end_date} and consisted of {activity_description}. The AML risks associated with these transactions are as follows: {aml_risks}.""",
    
    "CONCLUSION": """In conclusion, USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number {case_number}."""
}

# Activity type definitions
ACTIVITY_TYPES = {
    "STRUCTURING": {
        "name": "structuring",
        "derived_from": "derived from credits and debits",
        "indicators": ["structured deposits below CTR threshold", "layering", "multi-location activity", "rapid movement of funds"]
    },
    "UNUSUAL_ACH": {
        "name": "Automated Clearing House (ACH) activity",
        "derived_from": "derived from credits",
        "indicators": ["unknown sources/beneficiaries", "high-frequency transactions", "inconsistent with customer profile"]
    },
    "UNUSUAL_CASH": {
        "name": "cash activity",
        "derived_from": "derived from credits and debits",
        "indicators": ["large cash deposits", "large cash withdrawals", "structured cash transactions"]
    },
    "MONEY_LAUNDERING": {
        "name": "money laundering",
        "derived_from": "derived from credits and debits",
        "indicators": ["layering", "structuring", "shell company involvement", "rapid movement of funds"]
    }
}
