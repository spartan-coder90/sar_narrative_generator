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
API_PORT = int(os.getenv("API_PORT", "8081"))
API_DEBUG = os.getenv("API_DEBUG", "False").lower() == "true"

# LLM settings
LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:3000/api/chat")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "lama3:8b")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))  # Low temperature for more predictable outputs

# LLM model configuration
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llama3-8b")

# Llama 3 configuration
LLAMA_API_ENDPOINT = os.getenv("LLAMA_API_ENDPOINT", "http://localhost:11434/api/chat")
LLAMA_API_KEY = os.getenv("LLAMA_API_KEY", "")

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")



# SAR Narrative template sections
TEMPLATES = {
    "INTRODUCTION": """U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report {activity_type} totaling {total_amount} {derived_from} by {subjects} in {account_type} account number {account_number}. The suspicious activity was conducted from {start_date} through {end_date}.""",
    
    "PRIOR_CASES": """Prior SAR (Case Number: {prior_case_number}) was filed on {prior_filing_date} reporting {prior_description}.""",
    
    "ACCOUNT_INFO": """Personal {account_type} account {account_number} was opened on {open_date} and {account_status} on {close_date}. The account was closed due to {closure_reason}. The account closure funds were moved to {funds_destination} on {transfer_date}.""",
    
    "ACCOUNT_INFO_OPEN": """Personal {account_type} account {account_number} was opened on {open_date} and remains open.""",
    
    "SUBJECT_INFO": """{name} is employed as a {occupation} at {employer}. {name} is listed as {relationship} on the account.""",
    
    "ACTIVITY_SUMMARY": """The account activity for {account_number} from {start_date} to {end_date} included total credits of {total_credits} and total debits of {total_debits}. {activity_description}The AML risks associated with these transactions are as follows: {aml_risks}.""",
    
    "TRANSACTION_SAMPLES": """A sample of the suspicious transactions includes: {transactions}""",
    
    "CONCLUSION": """In conclusion, USB is reporting {total_amount} in {activity_type} which gave the appearance of suspicious activity and were conducted by {subjects} in account number {account_number} from {start_date} through {end_date}. USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number {case_number}."""
}

# SAR Template with all required sections and formats
SAR_TEMPLATE = {
    "RECOMMENDATION": {
        "ALERTING_ACTIVITY": """**Alerting Activity / Reason for Review** {case_number}: {alerting_account_types} and {alerting_account_numbers} alerted in {alerting_months} for {alerting_description}.""",
        
        "PRIOR_SARS": """**Prior SARs** {prior_sar_content}""",
        
        "SCOPE_OF_REVIEW": """**Scope of Review** {review_start_date} - {review_end_date}""",
        
        "SUMMARY_OF_INVESTIGATION": """**Summary of the Investigation (Red Flags, Supporting Evidence, etc.)** {investigation_summary}""",
        
        "CONCLUSION": """**Conclusion** In conclusion a SAR is recommended to report unusual {unusual_activity_types} activity involving USB accounts {unusual_activity_usb_accounts} and subjects {sar_subjects}. The unusual activity totaled {unusual_activity_total} {derived_from} between {unusual_activity_start_date} and {unusual_activity_end_date}."""
    },
    
    "ESCALATIONS_REFERRALS": {
        "CTA": """**CTA** CTA Request Type: {cta_request_type}
        
What is our customer's current or most recent occupation(s) and employer?
{employment_question}

If the customer is a student, what is their field of study and what school is being attended?
{student_question}

What is the nature of the customer's business?
{business_nature_question}

If available, please provide the customer's website as well as any physical addresses for their business locations.
{business_website_question}

What is the source of the customer's account credit activity (cash, wires, other transactions) as described in the summary?
{credits_source_question}

What is the purpose of the customer's account debit activity as described in the summary?
{debits_purpose_question}

Does the customer expect to have similar transactions (cash, wires or other activity described in the summary) in the future? If yes, what is the anticipated frequency, amount(s) and purpose of the activity?
{future_activity_question}

What is the purpose of the wire transactions occurring in the customer's accounts?
{wire_purpose_question}

What is our customer's relationship to the wire originators and/or wire beneficiaries referenced in the summary?
{wire_relationships_question}
        """,
        
        "RETAIN_OR_CLOSE": """**Retain or Close Customer Relationship(s)**
**Retain**: No further action is necessary at this time. The customer relationship(s) can remain open.

**Closure**: Requesting closure for USB customer(s) {f_coded_customers}, due to {high_risk_typology}.
USB customer(s) {non_f_coded_customers} should NOT be F-coded.

The risk factors are as follows:
{risk_factors}

Closure Summary:
{closure_summary}
        """
    },
    
    "SAR_NARRATIVE": {
        "INTRODUCTION": """U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report {activity_type} totaling ${total_amount} by {subject_name} in {account_type} account number {account_number}. The suspicious {activity_type} were conducted from {start_date} through {end_date}.""",
        
        "SUBJECT_ACCOUNT_INFO": """**Add details around Subject/Account Information:**
{subject_account_details}""",
        
        "SUSPICIOUS_ACTIVITY": """**Add details around Suspicious Activity:**
{suspicious_activity_details}""",
        
        "TRANSACTION_SAMPLES": """**A sample of the suspicious transactions:**
{transaction_samples}""",
        
        "CONCLUSION": """In conclusion, USB is reporting ${total_amount} in {activity_type} which gave the appearance of {activity_appearance} and were conducted by {subject_name} in {account_type} account number {account_number} from {start_date} through {end_date}. USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequestsml@usbank.com referencing AML case number {case_number}."""
    }
}

# Make sure ACTIVITY_TYPES is also defined
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

# AML Risk Indicators
AML_RISK_INDICATORS = {
    "STRUCTURING": [
        "multiple deposits below $10,000",
        "structured deposits",
        "multiple branch deposits",
        "cash structuring",
        "avoiding CTR threshold",
        "deposits just under $10,000"
    ],
    "MONEY_LAUNDERING": [
        "layering",
        "shell company",
        "funnel account",
        "third-party deposits",
        "rapid movement",
        "international transfers",
        "high-risk jurisdictions"
    ],
    "FRAUD": [
        "unauthorized access",
        "account takeover",
        "identity theft",
        "altered documents",
        "counterfeit checks",
        "fraudulent wire transfers",
        "synthetic identity"
    ],
    "UNUSUAL_ACTIVITY": [
        "inconsistent with profile",
        "deviation from normal patterns",
        "unexplained transactions",
        "lack of business purpose",
        "high-velocity trading",
        "unusual cash activity"
    ]
}

# Referral types
REFERRAL_TYPES = {
    "EDD": {
        "name": "EDD Referral",
        "description": "Referral to Enhanced Due Diligence",
        "template": "An EDD referral will be recommended. The customer demonstrates high-risk activity that requires enhanced due diligence monitoring."
    },
    "CDDO": {
        "name": "CDDO Referral",
        "description": "Referral to AML Case Disposition Designated Officer",
        "template": "A CDDO referral will be recommended. The customer demonstrates complex high-risk activity that requires additional review."
    },
    "AAD_FTS": {
        "name": "AAD First Time Structuring",
        "description": "Account Activity Discussion for First Time Structuring",
        "template": "Account #{account_number}, held by {signers}, was reviewed from {start_date} to {end_date} and identified potentially structured cash deposits/withdrawals conducted from {activity_start_date} to {activity_end_date} which totaled ${total_amount}. A first time structuring letter will be sent to the customer."
    },
    "AAD_NONFTS": {
        "name": "AAD Non-FTS",
        "description": "Account Activity Discussion for Non-First Time Structuring",
        "template": "Account #{account_number}, held by {signers}, was reviewed from {start_date} to {end_date} and identified potentially structured cash deposits/withdrawals conducted from {activity_start_date} to {activity_end_date} which totaled ${total_amount}. Please conduct an AAD with the customer(s) and inform them that continued structuring activity, intentional or unintentional, will result in permanent account closure and termination of their customer relationship."
    },
    "CTA": {
        "name": "CTA Referral",
        "description": "Customer Transaction Assessment",
        "template": "Account #{account_number}, held by {signers}, was reviewed from {start_date} to {end_date} and identified potentially unusual activity conducted from {activity_start_date} to {activity_end_date} which totaled ${total_amount}. The activity consisted of {transaction_types}. {analysis_description}"
    },
    "BIP": {
        "name": "BIP Referral",
        "description": "Business in Personal Referral",
        "template": "Account #{account_number}, held by {signer}, was reviewed from {start_date} to {end_date} and identified potentially business in personal activity conducted from {activity_start_date} to {activity_end_date} which totaled ${total_amount}. The business in personal activity consisted of {transaction_types}. {analysis_description}. Please inform customer to cease all business in personal activity and open a business account."
    },
    "LEET": {
        "name": "LEET Referral",
        "description": "Law Enforcement Engagement Team Referral",
        "template": "A LEET referral is recommended for Account #{account_number}, held by {signers}. {subpoena_info}. {referral_purpose}"
    },
    "FRAUD_IRF": {
        "name": "Fraud IRF",
        "description": "Fraud Investigation Referral Form",
        "template": "IRF #{irf_number}: Account #{account_number}, held by {signer}, was reviewed from {start_date} to {end_date} and identified potential fraud activity conducted from {activity_start_date} to {activity_end_date} which totaled ${total_amount}. The potential fraud activity consisted of {transaction_types}. {analysis_description}"
    }
}

# Closure reasons
CLOSURE_REASONS = {
    "STRUCTURING": {
        "name": "Structuring Activity",
        "description": "The customer engaged in pattern of apparent structuring",
        "is_fraud": False
    },
    "MONEY_LAUNDERING": {
        "name": "Money Laundering",
        "description": "The customer engaged in patterns consistent with money laundering",
        "is_fraud": False
    },
    "FRAUD": {
        "name": "Fraudulent Activity",
        "description": "The customer engaged in fraudulent activity",
        "is_fraud": True
    },
    "UNKNOWN_SOURCE_OF_FUNDS": {
        "name": "Unknown Source of Funds",
        "description": "Unable to verify the legitimate source of funds",
        "is_fraud": False
    },
    "HIGH_RISK_BUSINESS": {
        "name": "High Risk Business",
        "description": "Customer operates in a high-risk industry outside bank's risk appetite",
        "is_fraud": False
    },
    "NEGATIVE_NEWS": {
        "name": "Negative News",
        "description": "Customer associated with negative news or adverse media",
        "is_fraud": False
    },
    "NON_COOPERATIVE": {
        "name": "Non-Cooperative",
        "description": "Customer unwilling to provide requested documentation",
        "is_fraud": False
    }
}

# Section headers for the SAR narrative
SECTION_HEADERS = {
    "introduction": "Introduction",
    "prior_cases": "Prior Cases",
    "account_info": "Account Information",
    "subject_info": "Subject Information",
    "activity_summary": "Activity Summary",
    "transaction_samples": "Sample Transactions",
    "conclusion": "Conclusion"
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
    
    "prior_cases": """
    Write a brief paragraph about prior SARs or cases related to this subject or account using only these facts:
    - Case numbers: {case_numbers}
    - SAR filing dates: {filing_dates}
    - SAR types: {sar_types}
    - Total amounts: {total_amounts}
    - Date ranges: {date_ranges}
    
    If no prior SARs exist, simply state: 'No prior SARs were identified for the subjects or account.'
    Just state the facts directly without speculation or additional details.
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
    
    "transaction_samples": """
    Create a sample list of suspicious transactions using the following information:
    - Transaction dates: {dates}
    - Transaction amounts: {amounts}
    - Transaction types: {types}
    - Transaction descriptions: {descriptions}
    
    Format each transaction as: "[Date]: $[Amount] ([Type]) - [Description]"
    List each transaction separated by semicolons, with a period after the final transaction.
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