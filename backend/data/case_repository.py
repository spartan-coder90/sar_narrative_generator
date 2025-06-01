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

# Global dictionary to store the full, new standardized case data.
# Populated by _initialize_cases() on first access.
CASES_FULL: Dict[str, Dict[str, Any]] = {}

# Default search paths for the 'cases.json' file.
DEFAULT_DATA_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cases.json'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', 'cases.json'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cases.json'),
]

def _initialize_cases():
    """
    Initializes the global `CASES_FULL` dictionary by loading structured case data
    from 'cases.json'. The file is expected to contain a dictionary of case objects,
    keyed by case number.
    """
    global CASES_FULL
    if CASES_FULL: # Prevent re-initialization
        return

    json_path = None
    for path_option in DEFAULT_DATA_PATHS:
        if os.path.exists(path_option):
            json_path = path_option
            logger.info(f"Found 'cases.json' at: {json_path}")
            break
    
    if not json_path:
        env_path = os.environ.get('CASE_DATA_PATH')
        if env_path and os.path.exists(env_path):
            json_path = env_path
            logger.info(f"Found 'cases.json' via CASE_DATA_PATH: {json_path}")
        else:
            logger.warning(f"CASE_DATA_PATH ('{env_path}') not valid or file not found.")

    if not json_path:
        logger.warning("Case data JSON file ('cases.json') not found. Using fallback data.")
        CASES_FULL = _get_fallback_cases()
        return

    try:
        logger.info(f"Loading case data from: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            # Expecting a dictionary of case objects keyed by case number
            loaded_data = json.load(f)
        
        if not isinstance(loaded_data, dict):
            logger.warning(f"Unexpected data format in '{json_path}'. Expected a JSON dictionary of cases. Using fallback data.")
            CASES_FULL = _get_fallback_cases()
            return

        CASES_FULL = loaded_data
        logger.info(f"Successfully loaded {len(CASES_FULL)} cases from '{json_path}'.")
    except Exception as e:
        logger.error(f"Error loading cases from JSON file '{json_path}': {str(e)}. Using fallback data.")
        CASES_FULL = _get_fallback_cases()

def _get_fallback_cases() -> Dict[str, Dict[str, Any]]:
    """
    Provides a predefined, minimal fallback case in the new standardized JSON structure.
    This is used if 'cases.json' is missing or invalid.
    
    Returns:
        Dict: A dictionary containing a single fallback case keyed by its case number.
    """
    logger.info("Using fallback case data for CC0015823420.")
    # This is a simplified version of the transformed case CC0015823420
    return {
        "CC0015823420": {
            "caseInfo": {
                "caseNumber": "CC0015823420",
                "rbiTier": "Blue",
                "relevantAccountNumbers": ["204784659052"],
                "reviewPeriod": {"startDate": "2023-01-01", "endDate": "2024-03-18"}
            },
            "alerts": [{
                "alertId": "FALLBACK_ALERT", "alertMonth": "202301", "alertingAccount": "9999988",
                "description": "Fallback alert data.",
                "reviewPeriod": {"startDate": "2020-02-01", "endDate": "2024-01-31"}
            }],
            "subjects": [{
                "name": "GLENN A BROWDER", "isPrimary": True, "partyKey": "001996028488849833",
                "dateOfBirth": "1970-11-12", "occupation": "Doctor/Dentist"
            }],
            "accounts": [{
                "accountKey": "ICS9999988",
                "accountTypes": ["ICSNPSLV", "NPSL Visa"],
                "accountTitle": "BROWDER, GLENN ANDREW",
                "openingDate": "2018-09-04",
                "statusDescription": "i50 (GOOD ACCOUNT)",
                "activitySummary": {
                    "creditsByType": [{
                        "type": "Cash Deposit", "percentOfTotal": 55.2, "totalAmount": 27600.00,
                        "transactionCount": 3, "minTransactionAmount": 8900.00, "maxTransactionAmount": 9500.00,
                        "minTransactionDate": "2023-02-15", "maxTransactionDate": "2023-02-17"
                    }],
                    "debitsByType": [{
                        "type": "Wire Transfer", "percentOfTotal": 52.08, "totalAmount": 25000.00,
                        "transactionCount": 1, "minTransactionAmount": 25000.00, "maxTransactionAmount": 25000.00,
                        "minTransactionDate": "2023-02-18", "maxTransactionDate": "2023-02-18"
                    }]
                }
            }],
            "transactions": {"all": [], "unusualActivitySample": [], "ctaSample": [], "bipSample": []},
            "priorSars": [],
            "databaseSearches": {
                 "kycDatabase": [{"subjectName": "GLENN A BROWDER", "webKycFormLink": "N/A"}],
                 "riskRatings": [{"subjectName": "GLENN A BROWDER", "partyRiskRating": "1 Standard"}],
                 "adverseMediaReview": "No adverse media found in fallback.",
            },
            "recommendationsPlaceholder": {"generalNote":"Fallback recommendations."}
        }
    }

def get_case(case_number: str) -> Optional[Dict[str, Any]]:
    """
    Get case data by case number.
    With the new standardized JSON structure, this directly returns the case object.
    
    Args:
        case_number: Case number to retrieve.
        
    Returns:
        Dict: Case data in the new standardized format or None if not found.
    """
    # Initialize cases if not already loaded
    if not CASES_FULL:
        _initialize_cases()
    
    # CASES_FULL is a dict of dicts; .get() returns None if case_number is not found.
    return CASES_FULL.get(case_number)

def get_full_case(case_number: str) -> Optional[Dict[str, Any]]:
    """
    Get the full, standardized case data.
    This is an alias for get_case as the new structure doesn't distinguish
    between a "summary" and "full" version at this level.
    
    Args:
        case_number: Case number to retrieve.
        
    Returns:
        Dict: Case data in the new standardized format or None if not found.
    """
    # Initialize cases if not already loaded
    if not CASES_FULL:
        _initialize_cases()
    
    # Returns the entire case object for the given case_number
    return CASES_FULL.get(case_number)

def get_available_cases() -> List[Dict[str, Any]]:
    """
    Get list of available cases for UI dropdown, adapted for the new standardized JSON structure.
    
    Returns:
        List[Dict]: List of case summary objects.
    """
    # Initialize cases if not already loaded
    if not CASES_FULL:
        _initialize_cases()
    
    case_summaries = []
    
    for case_number, case_data in CASES_FULL.items():
        summary = {
            "case_number": case_number,
            "subjects": [],
            "account_number": "",
            "alert_count": 0
        }

        # Extract primary subject name
        if case_data.get("subjects"):
            primary_subject = next((s["name"] for s in case_data["subjects"] if s.get("isPrimary")), None)
            if primary_subject:
                summary["subjects"] = [primary_subject]
            elif case_data["subjects"]: # Fallback to first subject if no primary is marked
                summary["subjects"] = [case_data["subjects"][0].get("name", "N/A")]
        
        # Extract first relevant account number
        if case_data.get("caseInfo") and case_data["caseInfo"].get("relevantAccountNumbers"):
            summary["account_number"] = case_data["caseInfo"]["relevantAccountNumbers"][0]
            logger.debug(f"Found account number {summary['account_number']} from caseInfo for case {case_number}")
        else:
            # Fallback: check accounts section if caseInfo doesn't have it (should be rare with new structure)
            if case_data.get("accounts") and case_data["accounts"]:
                summary["account_number"] = case_data["accounts"][0].get("accountKey", "")
                logger.debug(f"Found account number {summary['account_number']} from accounts section for case {case_number}")

        # Count alerts
        if case_data.get("alerts"):
            summary["alert_count"] = len(case_data["alerts"])

        if not summary["account_number"]:
            logger.warning(f"No account number found for case {case_number} in get_available_cases.")

        case_summaries.append(summary)
    
    return case_summaries


def get_case_account_numbers(case_number: str) -> List[str]:
    """
    Get all account numbers associated with a case from the new standardized structure.
    It primarily uses 'caseInfo.relevantAccountNumbers' and 'accounts.accountKey'.
    
    Args:
        case_number: Case number to retrieve.
        
    Returns:
        List[str]: List of unique account numbers found in the case.
    """
    account_numbers = []
    case_data = get_case(case_number) # Uses the refactored get_case

    if not case_data:
        return []

    # Extract from caseInfo.relevantAccountNumbers
    case_info = case_data.get("caseInfo", {})
    if case_info.get("relevantAccountNumbers"):
        account_numbers.extend(
            [str(acct) for acct in case_info["relevantAccountNumbers"]]
        )

    # Extract from accounts section (accountKey for each account)
    accounts_data = case_data.get("accounts", [])
    for account in accounts_data:
        if account.get("accountKey"):
            account_numbers.append(str(account["accountKey"]))
    
    # Remove duplicates and empty strings, then ensure all are strings
    unique_account_numbers = list(set(filter(None, account_numbers)))
    return [str(num) for num in unique_account_numbers]

def load_cases_from_file(file_path: str) -> bool:
    """
    Load cases from a specific JSON file path.
    The JSON file is expected to be a dictionary where keys are case numbers
    and values are the standardized case data objects.
    
    Args:
        file_path: Path to the JSON file.
    
    Returns:
        bool: True if loaded successfully, False otherwise.
    """
    global CASES_FULL
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        if not isinstance(loaded_data, dict):
            logger.warning(
                f"Unexpected data format in {file_path}. Expected a JSON dictionary "
                f"where keys are case numbers and values are case objects. "
                f"Actual type: {type(loaded_data)}"
            )
            return False
        
        # Directly assign the loaded dictionary to CASES_FULL
        # This assumes the keys in the JSON are case numbers and values are the case objects
        CASES_FULL = loaded_data
        
        logger.info(f"Successfully loaded {len(CASES_FULL)} cases from '{file_path}'.")
        return True
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from file {file_path}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error loading cases from {file_path}: {str(e)}")
        return False