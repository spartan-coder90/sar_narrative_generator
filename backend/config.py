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

"""
Configuration file for SAR Narrative Generator templates
"""

# SAR Narrative template sections
SAR_TEMPLATES = {
    "INTRODUCTION": """U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report {activity_type} totaling {total_amount} {derived_from} by {subjects} in {account_type} account number {account_number}. The suspicious activity was conducted from {start_date} through {end_date}.""",
    
    "PRIOR_CASES": """Prior SAR (Case Number: {prior_case_number}) was filed on {prior_filing_date} reporting {prior_description}.""",
    
    "ACCOUNT_INFO": """Personal {account_type} account {account_number} was opened on {open_date} and {account_status} on {close_date}. The account was closed due to {closure_reason}. The account closure funds were moved to {funds_destination} on {transfer_date}.""",
    
    "ACCOUNT_INFO_OPEN": """Personal {account_type} account {account_number} was opened on {open_date} and remains open.""",
    
    "SUBJECT_INFO": """{name} is employed as a {occupation} at {employer}. {name} is listed as {relationship} on the account.""",
    
    "ACTIVITY_SUMMARY": """The account activity for {account_number} from {start_date} to {end_date} included total credits of {total_credits} and total debits of {total_debits}. {activity_description}The AML risks associated with these transactions are as follows: {aml_risks}.""",
    
    "TRANSACTION_SAMPLES": """A sample of the suspicious transactions includes: {transactions}""",
    
    "CONCLUSION": """In conclusion, USB is reporting {total_amount} in {activity_type} which gave the appearance of suspicious activity and were conducted by {subjects} in account number {account_number} from {start_date} through {end_date}. USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number {case_number}."""
}

# Activity type definitions with indicators and derived_from values
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
    },
    "WIRE_FRAUD": {
        "name": "wire fraud",
        "derived_from": "derived from debits",
        "indicators": ["unauthorized wire transfers", "unusual destinations", "social engineering"]
    },
    "IDENTITY_THEFT": {
        "name": "identity theft",
        "derived_from": "derived from credits and debits",
        "indicators": ["unauthorized account access", "new account openings", "changes to account information"]
    },
    "CHECK_FRAUD": {
        "name": "check fraud",
        "derived_from": "derived from credits",
        "indicators": ["counterfeit checks", "check kiting", "altered checks"]
    }
}

# LLM prompts for section generation
LLM_PROMPTS = {
    "introduction": """
    Write the first paragraph of a SAR narrative with this exact information:
    - Bank: U.S. Bank National Association (USB)
    - Activity type: {activity_type}
    - Total amount: {total_amount}
    - Derived from: {derived_from}
    - Subjects: {subjects}
    - Account type: {account_type}
    - Account number: {account_number}
    - Date range: {start_date} to {end_date}
    
    Start with: 'U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report...'
    
    Keep it to one paragraph and be very specific using only the facts provided.
    """,
    
    "account_info": """
    Write a brief paragraph about the account using only these facts:
    - Account type: {account_type}
    - Account number: {account_number}
    - Open date: {open_date}
    - Account status: {account_status}
    - Close date: {close_date}
    - Closure reason: {closure_reason}
    
    Just state the facts directly without speculation or additional details.
    """,
    
    "subject_info": """
    Write a brief description of the subject using only these facts:
    - Name: {name}
    - Occupation: {occupation}
    - Employer: {employer}
    - Relationship to account: {relationship}
    
    Just state the facts directly without speculation or additional details.
    """,
    
    "activity_summary": """
    Write a paragraph summarizing the suspicious account activity using only these facts:
    - Account number: {account_number}
    - Date range: {start_date} to {end_date}
    - Total credits: {total_credits}
    - Total debits: {total_debits}
    - Transaction patterns: {activity_description}
    - AML risks: {aml_risks}
    
    Focus only on the facts provided without speculation.
    """,
    
    "conclusion": """
    Write a conclusion paragraph for the SAR narrative using only these facts:
    - Total amount: {total_amount}
    - Activity type: {activity_type}
    - Subjects: {subjects}
    - Account number: {account_number}
    - Date range: {start_date} to {end_date}
    - Case number: {case_number}
    
    Start with: 'In conclusion, USB is reporting...' and end with '...USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number [CASE NUMBER].'
    """
}

# Keywords to identify suspicious activity indicators
SUSPICIOUS_INDICATORS = {
    "structuring": [
        "multiple deposits below $10,000",
        "structured deposits",
        "multiple branch deposits",
        "cash structuring",
        "avoiding CTR threshold",
        "deposits just under $10,000"
    ],
    "money_laundering": [
        "layering",
        "shell company",
        "funnel account",
        "third-party deposits",
        "rapid movement",
        "international transfers",
        "high-risk jurisdictions"
    ],
    "fraud": [
        "unauthorized access",
        "account takeover",
        "identity theft",
        "altered documents",
        "counterfeit checks",
        "fraudulent wire transfers",
        "synthetic identity"
    ],
    "unusual_activity": [
        "inconsistent with profile",
        "deviation from normal patterns",
        "unexplained transactions",
        "lack of business purpose",
        "high-velocity trading",
        "unusual cash activity"
    ]
}

# Section headers from the SAR template
SECTION_HEADERS = {
    "introduction": "Introduction",
    "prior_cases": "Prior Cases",
    "account_info": "Account Information",
    "subject_info": "Subject Information",
    "activity_summary": "Activity Summary",
    "transaction_samples": "Sample Transactions",
    "conclusion": "Conclusion"
}
