"""
Repository for case data, primarily loaded from a 'cases.json' file at runtime.
This module manages access to case data, providing it in both its original
multi-section format and a "flattened" single-dictionary format suitable for
application use. It includes a fallback mechanism if 'cases.json' is not found.
"""
import json
import os
from typing import Dict, List, Any, Optional
import logging

# Set up logging for this module
logger = logging.getLogger(__name__)

# Global dictionary to store the full, original case data (list of sections per case).
# Populated by _initialize_cases() on first access to any case data.
CASES_FULL: Dict[str, List[Dict[str, Any]]] = {}

# Default search paths for the 'cases.json' file.
DEFAULT_DATA_PATHS = [
    # Path 1: In the same directory as this repository.py file.
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases.json'),
    # Path 2: In a 'data' subdirectory of the parent directory (e.g., if this is in backend/data, look in backend/data/data).
    # Corrected: Look in a 'data' subdirectory at the same level as the 'data' directory containing this file,
    # assuming this file is in something like 'backend/data_access'.
    # For a structure like /app/backend/data/case_repository.py and /app/data/cases.json:
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'cases.json'), # More common project structure
    # Path 3: Simpler relative path if this module is in /app/backend/data/
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cases.json'),
]

def _initialize_cases():
    """
    Initializes the global `CASES_FULL` dictionary by loading raw case data from 'cases.json'.

    The method searches for 'cases.json' in predefined paths:
    1. The same directory as this script (`backend/data/`).
    2. A `data` directory at the project root level (sibling to `backend`).
    3. A path specified by the `CASE_DATA_PATH` environment variable.

    If the JSON file is not found in any of these locations or if an error occurs during
    loading (e.g., file corruption, incorrect format), the system falls back to using
    `_get_fallback_cases()` to populate `CASES_FULL` with predefined sample data.

    The loaded data, which is expected to be a list of cases (where each case is a list
    of section dictionaries), is then organized into the `CASES_FULL` dictionary, keyed
    by `case_number`. The case number is extracted from the "Case Information" section
    of each case.
    """
    global CASES_FULL
    
    # Prevent re-initialization if cases are already loaded.
    if CASES_FULL:
        return
    
    json_path = None
    # Search for 'cases.json' in the predefined default locations.
    for path_option in DEFAULT_DATA_PATHS:
        if os.path.exists(path_option):
            json_path = path_option
            logger.info(f"Found 'cases.json' at: {json_path}")
            break
    
    # If not found in default paths, check the 'CASE_DATA_PATH' environment variable.
    if not json_path:
        env_path = os.environ.get('CASE_DATA_PATH')
        if env_path and os.path.exists(env_path):
            json_path = env_path
            logger.info(f"Found 'cases.json' via CASE_DATA_PATH environment variable: {json_path}")
        else:
            logger.warning(f"CASE_DATA_PATH environment variable set to '{env_path}', but file not found.")
    
    # If 'cases.json' is still not found after all checks, use fallback data.
    if not json_path:
        logger.warning("Case data JSON file ('cases.json') not found in any specified location. Using fallback data.")
        CASES_FULL = _get_fallback_cases()
        return
    
    # Attempt to load and process the JSON file.
    try:
        logger.info(f"Loading case data from: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            # Load the raw JSON data (expected to be a list of cases).
            raw_data = json.load(f)
        
        # Validate the top-level structure of the loaded data.
        if not isinstance(raw_data, list):
            logger.warning(f"Unexpected data format in '{json_path}'. Expected a JSON list of cases. Using fallback data.")
            CASES_FULL = _get_fallback_cases()
            return
            
        # Process each case in the loaded list.
        # Each 'case_array' is expected to be a list of section dictionaries.
        for case_array in raw_data:
            if not isinstance(case_array, list):
                logger.warning(f"Skipping invalid case entry (not a list) in '{json_path}'.")
                continue # Skip malformed case entries.
                
            # Extract the case number from the "Case Information" section.
            case_number = None
            for section in case_array:
                if isinstance(section, dict) and section.get("section") == "Case Information":
                    case_number = section.get("Case Number")
                    break # Found case number, no need to check other sections for it.
            
            # If a case number is found, add the case (list of sections) to CASES_FULL.
            if case_number:
                if case_number in CASES_FULL:
                    logger.warning(f"Duplicate case number '{case_number}' found in '{json_path}'. Overwriting.")
                CASES_FULL[case_number] = case_array
            else:
                logger.warning(f"Could not determine case number for a case entry in '{json_path}'. Skipping this case.")
                
        logger.info(f"Successfully loaded {len(CASES_FULL)} cases from '{json_path}'.")
    except Exception as e:
        # Catch any other errors during file reading or JSON parsing.
        logger.error(f"Error loading cases from JSON file '{json_path}': {str(e)}. Using fallback data.")
        CASES_FULL = _get_fallback_cases()

def _get_fallback_cases() -> Dict[str, List[Dict[str, Any]]]:
    """
    Provides a predefined, minimal set of fallback case data.
    This is used when the primary 'cases.json' file cannot be found or loaded,
    ensuring the application can still run with some sample data.
    
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
    Get case data by case_number, transforming it into a "flattened" dictionary structure.

    This method retrieves the raw case data for the given `case_number` from `CASES_FULL`.
    The raw data, which is a list of section objects (each a dictionary), is then
    processed or "flattened" into a single dictionary (`flattened_data`). This
    flattened structure is more convenient for application use, consolidating key
    information from various sections.

    The `flattened_data` dictionary includes the following key fields:
    - `case_number`: The case number.
    - `alert_info`: A list of alert details extracted from "Alerting Details" sections.
    - `subjects`: A list of subject (customer) information from "Customer Information" sections.
    - `account_info`: Information about the primary account, usually the first account found
                      in the "Account Information" section.
    - `accounts`: A list of all accounts detailed in "Account Information" sections.
    - `prior_cases`: A list of prior case/SAR details from "Prior Cases/SARs" sections.
    - `database_searches`: Consolidated results from "Database Searches" sections (KYC, Adverse Media, Risk Ratings).
    - `review_period`: Start and end dates for the case review, typically from "Scope of Review"
                       or "Account Information" sections.
    - `full_data`: A copy of the original, raw list of section objects for this case,
                   allowing access to any data not explicitly flattened.

    If the case number is not found, `None` is returned.
    
    Args:
        case_number: The case number to retrieve and process.
        
    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the flattened case data,
                                  or `None` if the case_number is not found.
    """
    # Ensure cases are loaded into CASES_FULL before proceeding.
    if not CASES_FULL:
        _initialize_cases()
    
    # Retrieve the raw case data (list of sections) for the given case number.
    if case_number not in CASES_FULL:
        logger.warning(f"Case number '{case_number}' not found in CASES_FULL.")
        return None
    
    case_sections = CASES_FULL[case_number] # This is a list of section dictionaries.
    
    # Initialize the dictionary that will hold the flattened case data.
    flattened_data = {
        "case_number": case_number,
        "alert_info": [],
        "subjects": [],
        "account_info": {}, # To be populated with the primary account's details.
        "accounts": [],     # To list all accounts associated with the case.
        "prior_cases": [],
        "database_searches": {},
        "review_period": {},
        "full_data": case_sections # Store the original multi-section data for reference.
    }
    
    # Iterate through each section in the raw case data to populate `flattened_data`.
    # This process "flattens" the list of sections into a single structured dictionary.
    for section in case_sections:
        section_type = section.get("section", "") # Get the name/type of the current section.
        
        # Populate 'alert_info' from "Alerting Details" sections.
        if section_type == "Alerting Details":
            alerts_raw = section.get("alerts", [])
            for alert_item in alerts_raw:
                alert_data = {
                    "alert_id": alert_item.get("Alert ID", ""),
                    "alert_month": alert_item.get("Alert Month", ""),
                    "description": alert_item.get("Description", ""),
                    "review_period": {"start": "", "end": ""} # Initialize review period for the alert.
                }
                # Extract review period dates if available for this specific alert.
                review_period_str = alert_item.get("Review Period", "")
                if review_period_str and " - " in review_period_str:
                    dates = review_period_str.split(" - ")
                    if len(dates) == 2:
                        alert_data["review_period"]["start"] = dates[0]
                        alert_data["review_period"]["end"] = dates[1]
                flattened_data["alert_info"].append(alert_data)
        
        # Populate 'subjects' from "Customer Information" sections.
        elif section_type == "Customer Information":
            # Handle primary structure: "US Bank Customer Information" list
            if "US Bank Customer Information" in section:
                for customer_item in section["US Bank Customer Information"]:
                    subject_data = {
                        "name": customer_item.get("Primary Party", ""),
                        "is_primary": "Primary Party" in customer_item, # True if "Primary Party" key exists.
                        "party_key": customer_item.get("Party Key", ""),
                        "occupation": customer_item.get("Occupation Description", ""),
                        "employer": customer_item.get("Employer", ""),
                        "nationality": customer_item.get("Country of Nationality", ""),
                        "address": "", # Default empty address.
                        "account_relationship": "" # Default empty relationship.
                    }
                    # Extract the first address if available.
                    addresses_list = customer_item.get("Addresses", [])
                    if isinstance(addresses_list, list) and addresses_list:
                        subject_data["address"] = addresses_list[0]
                    flattened_data["subjects"].append(subject_data)
            
            # Handle alternative structure: "customerInformation.US Bank Customers" list
            elif "customerInformation" in section and "US Bank Customers" in section["customerInformation"]:
                for customer_item in section["customerInformation"]["US Bank Customers"]:
                    subject_data = {
                        "name": customer_item.get("Name", ""),
                        "is_primary": len(flattened_data["subjects"]) == 0, # Assume first is primary if list is empty.
                        "party_key": customer_item.get("Party Key", ""),
                        "occupation": customer_item.get("Occupation Description", ""),
                        "employer": customer_item.get("Employer", ""),
                        "nationality": customer_item.get("Nationality", ""),
                        "address": "",
                        "account_relationship": ""
                    }
                    addresses_list = customer_item.get("Addresses", [])
                    if isinstance(addresses_list, list) and addresses_list:
                        subject_data["address"] = addresses_list[0]
                    flattened_data["subjects"].append(subject_data)
        
        # Populate 'review_period', 'accounts', and 'account_info' from "Account Information" sections.
        elif section_type == "Account Information":
            # Extract overall case review period if specified here.
            if "Case Review Period" in section:
                review_period_str = section.get("Case Review Period", "")
                dates = review_period_str.split(" - ")
                if len(dates) == 2:
                    flattened_data["review_period"]["start"] = dates[0]
                    flattened_data["review_period"]["end"] = dates[1]
            
            # Process list of accounts.
            if "Accounts" in section and section["Accounts"]:
                for account_item in section["Accounts"]:
                    account_data = {
                        "account_number": account_item.get("Account Key", ""),
                        "account_type": ", ".join(account_item.get("Account Type", [])) if isinstance(account_item.get("Account Type"), list) else "",
                        "account_title": account_item.get("Account Title", ""),
                        "open_date": account_item.get("Account Opening Date & Branch", ""), # May include branch.
                        "close_date": account_item.get("Account Closing Date", ""),
                        "status": account_item.get("Status Description", ""),
                        "related_parties": [],
                        "branch": account_item.get("Account Holding Branch", "")
                    }
                    # Process related parties for this account.
                    parties_list = account_item.get("Related Parties", [])
                    if isinstance(parties_list, list):
                        for party_str in parties_list:
                            parts = party_str.split(" (") # Expects "Name (Role)" format.
                            if len(parts) == 2:
                                name = parts[0].strip()
                                role = parts[1].strip().rstrip(")")
                                account_data["related_parties"].append({"name": name, "role": role})
                            else:
                                account_data["related_parties"].append({"name": party_str, "role": ""}) # Fallback.
                    # Placeholder for potential credit/debit summary within account item (if format changes).
                    if "Credits" in account_item: account_data["credits"] = {}
                    if "Debits" in account_item: account_data["debits"] = {}
                    flattened_data["accounts"].append(account_data)
                
                # Set the first account processed as the primary 'account_info'.
                if flattened_data["accounts"] and not flattened_data["account_info"]: # Check if account_info not already set
                    flattened_data["account_info"] = flattened_data["accounts"][0]
        
        # Populate 'prior_cases' from "Prior Cases/SARs" sections.
        elif section_type == "Prior Cases/SARs":
            prior_cases_raw = section.get("priorCases", []) # Assuming key is "priorCases"
            for prior_case_item in prior_cases_raw:
                prior_case_data = {
                    "case_number": prior_case_item.get("Case Number", ""),
                    "alert_id": [], "alert_month": [], # Initialize as lists.
                    "review_period": {"start": "", "end": ""},
                    "sar_form_number": "", "filing_date": "", "summary": ""
                }
                # Extract alert details for the prior case.
                alert_info_raw = prior_case_item.get("Alerting Information", {})
                prior_case_data["alert_id"] = alert_info_raw.get("Alert IDs", [])
                prior_case_data["alert_month"] = alert_info_raw.get("Alert Months", [])
                # Extract review period for the prior case.
                review_period_raw = prior_case_item.get("Scope of Review", {})
                prior_case_data["review_period"]["start"] = review_period_raw.get("start", "")
                prior_case_data["review_period"]["end"] = review_period_raw.get("end", "")
                # Extract SAR details for the prior case.
                sar_details_raw = prior_case_item.get("SAR Details", {})
                prior_case_data["sar_form_number"] = sar_details_raw.get("Form Number", "")
                prior_case_data["filing_date"] = sar_details_raw.get("Filing Date", "")
                prior_case_data["summary"] = sar_details_raw.get("SAR Summary", "")
                flattened_data["prior_cases"].append(prior_case_data)
        
        # Populate 'database_searches' from "Database Searches" sections.
        elif section_type == "Database Searches":
            db_searches_data = {
                "kyc": {"results": ""}, "adverse_media": {"results": ""}, "risk_ratings": []
            }
            # Process KYC database results.
            if "KYC Database" in section:
                kyc_results_list = []
                for entry in section["KYC Database"]:
                    subject_name = entry.get("Subject Name", "Unknown Subject")
                    link = entry.get("WebKYC Form Link", "No link found")
                    kyc_results_list.append(f"{subject_name}: {link}")
                db_searches_data["kyc"]["results"] = "\n".join(kyc_results_list) if kyc_results_list else "No KYC results."
            # Process risk ratings.
            if "Risk Ratings" in section:
                for rating_item in section["Risk Ratings"]:
                    db_searches_data["risk_ratings"].append({
                        "name": rating_item.get("Subject Name", ""),
                        "party_key": rating_item.get("Party Key", ""),
                        "sor": rating_item.get("SOR", ""), # System of Record
                        "rating": rating_item.get("Party Risk Rating Code Description", "")
                    })
            # Process adverse media review results.
            if "Adverse Media Review" in section:
                db_searches_data["adverse_media"]["results"] = section["Adverse Media Review"]
            flattened_data["database_searches"] = db_searches_data
        
        # Populate 'review_period' start and end dates from "Scope of Review" section.
        # This might override dates from "Account Information" if "Scope of Review" is processed later
        # and also contains these fields. The last one processed will take precedence for these specific keys.
        elif section_type == "Scope of Review":
            if section.get("Start Date"): # Ensure key exists before assigning
                flattened_data["review_period"]["start"] = section.get("Start Date", "")
            if section.get("End Date"): # Ensure key exists
                flattened_data["review_period"]["end"] = section.get("End Date", "")
    
    return flattened_data

def get_full_case(case_number: str) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieves the full, original case data for a given case number without any transformation.
    The data is returned as a list of section objects, exactly as loaded from the JSON file.
    
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
    Generates a list of case summaries, suitable for populating a UI dropdown or overview.

    Each summary object in the returned list provides key identifying information for a case,
    including:
    - `case_number`: The unique identifier for the case.
    - `subjects`: A list of primary subject names associated with the case, extracted
                  from the "Customer Information" section.
    - `account_number`: The primary account number associated with the case. This is
                        determined using a fallback logic:
                        1. First "Relevant Account" from the "Case Information" section.
                        2. If not found, the "Account Key" of the first account in the
                           "Account Information" section.
                        3. If still not found, the "Account" from the first entry in the
                           "Activity Summary" section.
                        A warning is logged if no account number can be determined.
    - `alert_count`: The number of alerts listed in the "Alerting Details" section.

    This method ensures that `_initialize_cases()` is called if `CASES_FULL` is not
    already populated.
    
    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary is a
                              summary of a case.
    """
    # Ensure cases are loaded before generating summaries.
    if not CASES_FULL:
        _initialize_cases()
    
    case_summaries = []
    
    # Iterate through all loaded cases in CASES_FULL.
    for case_number, case_sections in CASES_FULL.items():
        # Initialize a dictionary to hold the summary for the current case.
        summary = {
            "case_number": case_number,
            "subjects": [],
            "account_number": "", # To be populated by the logic below.
            "alert_count": 0
        }
        
        # --- Extract information from different sections of the case ---

        # First pass: Extract 'Relevant Accounts' from "Case Information" as primary source for account_number.
        # Also extract subject names from "Customer Information" and alert count from "Alerting Details".
        for section in case_sections:
            section_name = section.get("section", "")

            if section_name == "Case Information":
                relevant_accounts = section.get("Relevant Accounts", [])
                if relevant_accounts and isinstance(relevant_accounts, list):
                    summary["account_number"] = str(relevant_accounts[0]) # Take the first relevant account.
                    logger.debug(f"Extracted account_number '{summary['account_number']}' from 'Relevant Accounts' for case {case_number}.")
            
            elif section_name == "Customer Information":
                # Attempt to get subjects from "US Bank Customer Information" list.
                if "US Bank Customer Information" in section:
                    summary["subjects"] = [
                        customer.get("Primary Party", "")
                        for customer in section["US Bank Customer Information"]
                        if "Primary Party" in customer and customer.get("Primary Party")
                    ]
                # Fallback to "customerInformation.US Bank Customers" if the primary structure isn't found.
                elif "customerInformation" in section and "US Bank Customers" in section["customerInformation"]:
                    summary["subjects"] = [
                        customer.get("Name", "")
                        for customer in section["customerInformation"]["US Bank Customers"]
                        if "Name" in customer and customer.get("Name")
                    ]
            
            elif section_name == "Alerting Details":
                if "alerts" in section and isinstance(section["alerts"], list):
                    summary["alert_count"] = len(section["alerts"])
        
        # Fallback logic for 'account_number' if not found in "Case Information".
        if not summary["account_number"]:
            for section in case_sections:
                section_name = section.get("section", "")
                if section_name == "Account Information":
                    # Try "Accounts" list first.
                    accounts_list = section.get("Accounts", [])
                    if accounts_list and isinstance(accounts_list, list) and accounts_list[0].get("Account Key"):
                        summary["account_number"] = str(accounts_list[0]["Account Key"])
                        logger.debug(f"Extracted account_number '{summary['account_number']}' from 'Account Key' (Accounts list) for case {case_number}.")
                        break
                    # Try "accountInformation.Account" structure.
                    elif "accountInformation" in section and section["accountInformation"].get("Account", {}).get("Account Key"):
                        summary["account_number"] = str(section["accountInformation"]["Account"]["Account Key"])
                        logger.debug(f"Extracted account_number '{summary['account_number']}' from 'Account Key' (accountInformation) for case {case_number}.")
                        break
        
        # Second fallback for 'account_number': Try "Activity Summary" section.
        if not summary["account_number"]:
            for section in case_sections:
                section_name = section.get("section", "")
                if section_name == "Activity Summary" and "Activity Summary" in section:
                    activity_summary_list = section["Activity Summary"]
                    # Check if it's a list and has at least one entry with an "Account".
                    if activity_summary_list and isinstance(activity_summary_list, list) and activity_summary_list[0].get("Account"):
                        summary["account_number"] = str(activity_summary_list[0]["Account"])
                        logger.debug(f"Extracted account_number '{summary['account_number']}' from 'Activity Summary' for case {case_number}.")
                        break
        
        # Log a warning if no account number could be determined after all fallbacks.
        if not summary["account_number"]:
            logger.warning(f"Could not determine an account number for case summary: {case_number}")
        
        case_summaries.append(summary)
    
    return case_summaries


def get_section(case_number: str, section_name: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a specific section from a case by its name.
    
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