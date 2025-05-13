"""
Repository for case data loaded from JSON files at runtime.
Integrates transaction data for use in the SAR narrative generation.
"""
import json
import os
from typing import Dict, List, Any, Optional
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Global cases dictionary - will be populated on first access
# This will store the full, original JSON structure
CASES_FULL = {}

# Default data path - check common locations
DEFAULT_DATA_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases.json'),  # In the same directory
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'cases.json'),  # In parent's data directory
]

def _initialize_cases():
    """
    Initialize the cases dictionary by loading from JSON file
    """
    global CASES_FULL
    
    # Check if cases are already loaded
    if CASES_FULL:
        return
    
    # Try to find the JSON file in default locations
    json_path = None
    for path in DEFAULT_DATA_PATHS:
        if os.path.exists(path):
            json_path = path
            break
    
    # If not found in default locations, look for an environment variable
    if not json_path:
        env_path = os.environ.get('CASE_DATA_PATH')
        if env_path and os.path.exists(env_path):
            json_path = env_path
    
    # If still not found, use fallback data
    if not json_path:
        logger.warning("Case data JSON file not found. Using fallback data.")
        CASES_FULL = _get_fallback_cases()
        return
    
    # Load from JSON file
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        # Check if data is in expected format (list of case section arrays)
        if not isinstance(raw_data, list):
            logger.warning(f"Unexpected data format in {json_path}. Expected list of cases.")
            CASES_FULL = _get_fallback_cases()
            return
            
        # Organize by case number
        for case_array in raw_data:
            if not isinstance(case_array, list):
                continue
                
            # Find the case information section to get the case number
            case_number = None
            for section in case_array:
                if isinstance(section, dict) and section.get("section") == "Case Information":
                    case_number = section.get("Case Number")
                    break
            
            if case_number:
                CASES_FULL[case_number] = case_array
                
        logger.info(f"Successfully loaded {len(CASES_FULL)} cases from {json_path}")
    except Exception as e:
        logger.error(f"Error loading cases from JSON: {str(e)}")
        CASES_FULL = _get_fallback_cases()

def _get_fallback_cases() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get fallback case data when JSON file is not available
    
    Returns:
        Dict: Dictionary of fallback cases in original structure
    """
    # Define a minimal fallback case in the original structure
    return {
        "CC0015823420": [
            {
                "section": "Case Information",
                "Case Number": "CC0015823420",
                "Relevant Accounts": ["204784659052"],
                "RBI Tier": "Blue"
            },
            {
                "section": "Alerting Details",
                "alerts": [
                    {
                        "Alert ID": "AMLR5881633",
                        "Alert Month": "201902",
                        "Description": "Number of Transactions: 2; High Risk Country; Accounts Involved: 4037670331863968; High-Risk Flag:0; Score=2",
                        "Review Period": "02/01/2023 - 01/31/2024"
                    }
                ]
            },
            {
                "section": "Customer Information",
                "US Bank Customer Information": [
                    {
                        "Primary Party": "GLENN A BROWDER",
                        "Party Key": "001996028488849833",
                        "Occupation Description": "Doctor/Dentist",
                        "Employer": "SUMMIT ORTHOPEDICS",
                        "Country of Nationality": "US",
                        "Addresses": [
                            "857 FAIRMOUNT AVE SAINT PAUL MN SAINT PAUL, MINNESOTA, 55105-3341 UNITED STATES OF AMERICA"
                        ]
                    }
                ]
            },
            {
                "section": "Account Information",
                "Case Review Period": "01/01/2023 - 03/18/2024",
                "Accounts": [
                    {
                        "Account Key": "ICS9999988",
                        "Account Type": ["ICSNPSLV", "NPSL Visa"],
                        "Account Title": "BROWDER, GLENN ANDREW",
                        "Account Opening Date & Branch": "09/04/2018",
                        "Status Description": "I50 (GOOD ACCOUNT)",
                        "Related Parties": [
                            "GLENN A BROWDER (First Co-Owner)"
                        ]
                    }
                ]
            },
            {
                "section": "Scope of Review",
                "Start Date": "01/01/2023",
                "End Date": "03/18/2024"
            },
            {
                "section": "Activity Summary",
                "Activity Summary": [
                    {
                        "Account": "204784659052",
                        "Credits": [
                            {
                                "Custom Language": "Cash Deposit",
                                "% of Credits": 55.2,
                                "Total ": 27600.00,
                                "# Transactions ": 3,
                                "Min Credit Amt.": 8900.00,
                                "Max Credit Amt.": 9500.00,
                                "Min Txn Date ": "02/15/2023",
                                "Max Txn Date ": "02/17/2023"
                            }
                        ],
                        "Debits": [
                            {
                                "Custom Language": "Wire Transfer",
                                "% of Debits": 52.08,
                                "Total ": 25000.00,
                                "# Transactions ": 1,
                                "Min Debit Amt.": 25000.00,
                                "Max Debit Amt.": 25000.00,
                                "Min Txn Date ": "02/18/2023",
                                "Max Txn Date ": "02/18/2023"
                            }
                        ]
                    }
                ]
            }
        ]
    }

def get_case(case_number: str) -> Optional[Dict[str, Any]]:
    """
    Get case data by case number, converting to the flattened format expected by the application
    
    Args:
        case_number: Case number to retrieve
        
    Returns:
        Dict: Case data in flattened format or None if not found
    """
    # Initialize cases if not already loaded
    if not CASES_FULL:
        _initialize_cases()
    
    # Check if case exists
    if case_number not in CASES_FULL:
        return None
    
    # Get the full case data
    case_sections = CASES_FULL[case_number]
    
    # Convert to the flattened format expected by the application
    flattened_data = {
        "case_number": case_number,
        "alert_info": [],
        "subjects": [],
        "account_info": {},
        "accounts": [],
        "prior_cases": [],
        "database_searches": {},
        "review_period": {},
        # Store the full data for access if needed
        "full_data": case_sections
    }
    
    # Extract key information needed by the application
    for section in case_sections:
        section_type = section.get("section", "")
        
        if section_type == "Alerting Details":
            # Process alerts
            alerts = section.get("alerts", [])
            for alert in alerts:
                alert_info = {
                    "alert_id": alert.get("Alert ID", ""),
                    "alert_month": alert.get("Alert Month", ""),
                    "description": alert.get("Description", ""),
                    "review_period": {"start": "", "end": ""}
                }
                
                # Extract review period dates if available
                review_period = alert.get("Review Period", "")
                if review_period and " - " in review_period:
                    dates = review_period.split(" - ")
                    if len(dates) == 2:
                        alert_info["review_period"]["start"] = dates[0]
                        alert_info["review_period"]["end"] = dates[1]
                
                flattened_data["alert_info"].append(alert_info)
        
        elif section_type == "Customer Information":
            # Extract subjects from US Bank Customer Information
            if "US Bank Customer Information" in section:
                for customer in section["US Bank Customer Information"]:
                    subject = {
                        "name": customer.get("Primary Party", ""),
                        "is_primary": "Primary Party" in customer,
                        "party_key": customer.get("Party Key", ""),
                        "occupation": customer.get("Occupation Description", ""),
                        "employer": customer.get("Employer", ""),
                        "nationality": customer.get("Country of Nationality", ""),
                        "address": "",
                        "account_relationship": ""
                    }
                    
                    # Extract addresses
                    if "Addresses" in customer and isinstance(customer["Addresses"], list) and customer["Addresses"]:
                        subject["address"] = customer["Addresses"][0]
                    
                    flattened_data["subjects"].append(subject)
            
            # Handle alternative structure if needed
            elif "customerInformation" in section and "US Bank Customers" in section["customerInformation"]:
                for customer in section["customerInformation"]["US Bank Customers"]:
                    subject = {
                        "name": customer.get("Name", ""),
                        "is_primary": True if len(flattened_data["subjects"]) == 0 else False,
                        "party_key": customer.get("Party Key", ""),
                        "occupation": customer.get("Occupation Description", ""),
                        "employer": customer.get("Employer", ""),
                        "nationality": customer.get("Nationality", ""),
                        "address": "",
                        "account_relationship": ""
                    }
                    
                    # Extract addresses
                    if "Addresses" in customer and isinstance(customer["Addresses"], list) and customer["Addresses"]:
                        subject["address"] = customer["Addresses"][0]
                    
                    flattened_data["subjects"].append(subject)
        
        elif section_type == "Account Information":
            # Extract review period
            if "Case Review Period" in section:
                review_period = section.get("Case Review Period", "")
                dates = review_period.split(" - ")
                if len(dates) == 2:
                    flattened_data["review_period"]["start"] = dates[0]
                    flattened_data["review_period"]["end"] = dates[1]
            
            # Extract account information
            if "Accounts" in section and section["Accounts"]:
                for account in section["Accounts"]:
                    account_data = {
                        "account_number": account.get("Account Key", ""),
                        "account_type": ", ".join(account.get("Account Type", [])) if isinstance(account.get("Account Type"), list) else "",
                        "account_title": account.get("Account Title", ""),
                        "open_date": account.get("Account Opening Date & Branch", ""),
                        "close_date": account.get("Account Closing Date", ""),
                        "status": account.get("Status Description", ""),
                        "related_parties": [],
                        "branch": account.get("Account Holding Branch", "")
                    }
                    
                    # Process related parties
                    if "Related Parties" in account and isinstance(account["Related Parties"], list):
                        for party in account["Related Parties"]:
                            parts = party.split(" (")
                            if len(parts) == 2:
                                name = parts[0].strip()
                                role = parts[1].strip().rstrip(")")
                                account_data["related_parties"].append({"name": name, "role": role})
                            else:
                                account_data["related_parties"].append({"name": party, "role": ""})
                    
                    # Extract credits and debits information if available
                    if "Credits" in account:
                        account_data["credits"] = {}
                    
                    if "Debits" in account:
                        account_data["debits"] = {}
                    
                    flattened_data["accounts"].append(account_data)
                
                # Set first account as primary account_info
                if flattened_data["accounts"]:
                    flattened_data["account_info"] = flattened_data["accounts"][0]
        
        elif section_type == "Prior Cases/SARs":
            # Extract prior cases information
            prior_cases = section.get("priorCases", [])
            for prior_case in prior_cases:
                case_data = {
                    "case_number": prior_case.get("Case Number", ""),
                    "alert_id": [],
                    "alert_month": [],
                    "review_period": {"start": "", "end": ""},
                    "sar_form_number": "",
                    "filing_date": "",
                    "summary": ""
                }
                
                # Extract alert information
                if "Alerting Information" in prior_case:
                    alert_info = prior_case["Alerting Information"]
                    case_data["alert_id"] = alert_info.get("Alert IDs", [])
                    case_data["alert_month"] = alert_info.get("Alert Months", [])
                
                # Extract review period
                if "Scope of Review" in prior_case:
                    review_period = prior_case["Scope of Review"]
                    case_data["review_period"]["start"] = review_period.get("start", "")
                    case_data["review_period"]["end"] = review_period.get("end", "")
                
                # Extract SAR details
                if "SAR Details" in prior_case:
                    sar_details = prior_case["SAR Details"]
                    case_data["sar_form_number"] = sar_details.get("Form Number", "")
                    case_data["filing_date"] = sar_details.get("Filing Date", "")
                    case_data["summary"] = sar_details.get("SAR Summary", "")
                
                flattened_data["prior_cases"].append(case_data)
        
        elif section_type == "Database Searches":
            # Extract database searches
            database_searches = {
                "kyc": {"results": ""},
                "adverse_media": {"results": ""},
                "risk_ratings": []
            }
            
            # Process KYC database results
            if "KYC Database" in section:
                kyc_results = []
                for entry in section["KYC Database"]:
                    subject_name = entry.get("Subject Name", "")
                    if "WebKYC Form Link" in entry:
                        kyc_results.append(f"{subject_name}: {entry.get('WebKYC Form Link', '')}")
                    else:
                        kyc_results.append(f"{subject_name}: No WebKYC form links found")
                
                database_searches["kyc"]["results"] = "\n".join(kyc_results) if kyc_results else "No WebKYC form links found"
            
            # Process risk ratings
            if "Risk Ratings" in section:
                for rating in section["Risk Ratings"]:
                    database_searches["risk_ratings"].append({
                        "name": rating.get("Subject Name", ""),
                        "party_key": rating.get("Party Key", ""),
                        "sor": rating.get("SOR", ""),
                        "rating": rating.get("Party Risk Rating Code Description", "")
                    })
            
            # Process adverse media
            if "Adverse Media Review" in section:
                database_searches["adverse_media"]["results"] = section["Adverse Media Review"]
            
            flattened_data["database_searches"] = database_searches
        
        elif section_type == "Scope of Review":
            # Extract start and end dates
            flattened_data["review_period"]["start"] = section.get("Start Date", "")
            flattened_data["review_period"]["end"] = section.get("End Date", "")
    
    return flattened_data

def get_full_case(case_number: str) -> Optional[List[Dict[str, Any]]]:
    """
    Get the full, original case data without any transformation
    
    Args:
        case_number: Case number to retrieve
        
    Returns:
        List[Dict]: Original case data as a list of section objects, or None if not found
    """
    # Initialize cases if not already loaded
    if not CASES_FULL:
        _initialize_cases()
    
    return CASES_FULL.get(case_number)

def get_available_cases() -> List[Dict[str, Any]]:
    """
    Get list of available cases for UI dropdown
    
    Returns:
        List[Dict]: List of case summary objects
    """
    # Initialize cases if not already loaded
    if not CASES_FULL:
        _initialize_cases()
    
    case_summaries = []
    
    for case_number, case_sections in CASES_FULL.items():
        # Prepare summary info
        summary = {
            "case_number": case_number,
            "subjects": [],
            "account_number": "",  # Will be populated correctly
            "alert_count": 0
        }
        
        # Extract subject names and relevant information from case sections
        for section in case_sections:
            # Process Case Information section FIRST to get Relevant Accounts
            if section.get("section") == "Case Information":
                # Use Relevant Accounts array from Case Information section
                if "Relevant Accounts" in section and section["Relevant Accounts"]:
                    # Take the first relevant account as the main account number
                    summary["account_number"] = section["Relevant Accounts"][0]
                    logger.debug(f"Found account number {summary['account_number']} from Relevant Accounts for case {case_number}")
            
            # Get subject information
            elif section.get("section") == "Customer Information":
                if "US Bank Customer Information" in section:
                    summary["subjects"] = [customer.get("Primary Party", "") 
                                         for customer in section["US Bank Customer Information"]
                                         if "Primary Party" in customer]
                elif "customerInformation" in section and "US Bank Customers" in section["customerInformation"]:
                    summary["subjects"] = [customer.get("Name", "")
                                         for customer in section["customerInformation"]["US Bank Customers"]
                                         if "Name" in customer]
            
            # Count alerts
            elif section.get("section") == "Alerting Details":
                if "alerts" in section:
                    summary["alert_count"] = len(section["alerts"])
        
        # If account_number is still empty, look in Account Information section as fallback
        if not summary["account_number"]:
            for section in case_sections:
                if section.get("section") == "Account Information":
                    if "Accounts" in section and section["Accounts"]:
                        summary["account_number"] = section["Accounts"][0].get("Account Key", "")
                        logger.debug(f"Found account number {summary['account_number']} from Account Key for case {case_number}")
                    elif "accountInformation" in section and "Account" in section["accountInformation"]:
                        summary["account_number"] = section["accountInformation"]["Account"].get("Account Key", "")
                        logger.debug(f"Found account number {summary['account_number']} from accountInformation for case {case_number}")
        
        # If still no account number found, try Activity Summary as a last resort
        if not summary["account_number"]:
            for section in case_sections:
                if section.get("section") == "Activity Summary" and "Activity Summary" in section:
                    activity_summary = section["Activity Summary"]
                    if activity_summary and isinstance(activity_summary, list) and activity_summary[0].get("Account"):
                        summary["account_number"] = str(activity_summary[0]["Account"])
                        logger.debug(f"Found account number {summary['account_number']} from Activity Summary for case {case_number}")
        
        # If still no account number, log a warning
        if not summary["account_number"]:
            logger.warning(f"No account number found for case {case_number}")
        
        case_summaries.append(summary)
    
    return case_summaries


def get_section(case_number: str, section_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific section from a case
    
    Args:
        case_number: Case number
        section_name: Section name (e.g., "Case Information", "Alerting Details")
        
    Returns:
        Dict: Section data or None if not found
    """
    case_data = get_full_case(case_number)
    if not case_data:
        return None
    
    for section in case_data:
        if section.get("section") == section_name:
            return section
    
    return None


def get_case_account_numbers(case_number: str) -> List[str]:
    """
    Get all account numbers associated with a case from all possible sources
    
    Args:
        case_number: Case number to retrieve
        
    Returns:
        List[str]: List of account numbers found in the case
    """
    account_numbers = []
    
    # Get Case Information section for Relevant Accounts
    case_info_section = get_section(case_number, "Case Information")
    if case_info_section and "Relevant Accounts" in case_info_section:
        account_numbers.extend([
            str(acct) for acct in case_info_section["Relevant Accounts"]
        ])
    
    # Get Account Information section for Account Keys
    account_info_section = get_section(case_number, "Account Information")
    if account_info_section:
        if "Accounts" in account_info_section and account_info_section["Accounts"]:
            account_numbers.extend([
                account.get("Account Key", "")
                for account in account_info_section["Accounts"]
                if "Account Key" in account
            ])
    
    # Get Activity Summary section for Account numbers
    activity_section = get_section(case_number, "Activity Summary")
    if activity_section and "Activity Summary" in activity_section:
        for activity in activity_section["Activity Summary"]:
            if "Account" in activity:
                account_numbers.append(str(activity["Account"]))
    
    # Remove duplicates and empty strings
    return list(set(filter(None, account_numbers)))

def load_cases_from_file(file_path: str) -> bool:
    """
    Load cases from a specific JSON file path
    
    Args:
        file_path: Path to the JSON file
    
    Returns:
        bool: True if loaded successfully, False otherwise
    """
    global CASES_FULL
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        # Clear existing data
        CASES_FULL = {}
        
        # Check if data is in expected format (list of case section arrays)
        if not isinstance(raw_data, list):
            logger.warning(f"Unexpected data format in {file_path}. Expected list of cases.")
            return False
        
        # Organize by case number
        for case_array in raw_data:
            if not isinstance(case_array, list):
                continue
                
            # Find the case information section to get the case number
            case_number = None
            for section in case_array:
                if isinstance(section, dict) and section.get("section") == "Case Information":
                    case_number = section.get("Case Number")
                    break
            
            if case_number:
                CASES_FULL[case_number] = case_array
        
        return len(CASES_FULL) > 0
    except Exception as e:
        logger.error(f"Error loading cases from {file_path}: {str(e)}")
        return False