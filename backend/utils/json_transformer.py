"""
Helper functions for accessing specific data from the case JSON structure
"""
from typing import Dict, List, Any, Optional, Union

def find_section(case_data: List[Dict[str, Any]], section_name: str) -> Optional[Dict[str, Any]]:
    """
    Find a specific section in the case data
    
    Args:
        case_data: List of section objects from the case
        section_name: Name of the section to find
    
    Returns:
        Dict: Section data or None if not found
    """
    for section in case_data:
        if section.get("section") == section_name:
            return section
    
    return None

def get_case_number(case_data: List[Dict[str, Any]]) -> str:
    """
    Get the case number from case data
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        str: Case number or empty string if not found
    """
    section = find_section(case_data, "Case Information")
    return section.get("Case Number", "") if section else ""

def get_alert_info(case_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get alert information from case data
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        List[Dict]: Alert information for application use
    """
    section = find_section(case_data, "Alerting Details")
    if not section or "alerts" not in section:
        return []
    
    alerts = []
    for alert in section["alerts"]:
        alert_info = {
            "alert_id": alert.get("Alert ID", ""),
            "alert_month": alert.get("Alert Month", ""),
            "description": alert.get("Description", ""),
            "review_period": {"start": "", "end": ""}
        }
        
        # Extract review period dates if available
        review_period = alert.get("Review Period", "")
        if review_period:
            dates = review_period.split(" - ")
            if len(dates) == 2:
                alert_info["review_period"]["start"] = dates[0]
                alert_info["review_period"]["end"] = dates[1]
        
        alerts.append(alert_info)
    
    return alerts

def get_subjects(case_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get subject information from case data
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        List[Dict]: Subject information for application use
    """
    section = find_section(case_data, "Customer Information")
    if not section:
        return []
    
    subjects = []
    
    # Extract from US Bank Customer Information format
    if "US Bank Customer Information" in section:
        for customer in section["US Bank Customer Information"]:
            subject = {
                "name": customer.get("Primary Party", ""),
                "is_primary": "Primary Party" in customer or customer.get("Original Case Subject") == "Yes",
                "party_key": customer.get("Party Key", ""),
                "occupation": customer.get("Occupation Description", ""),
                "employer": customer.get("Employer", ""),
                "nationality": customer.get("Country of Nationality", ""),
                "address": "",
                "account_relationship": ""
            }
            
            # Extract addresses
            if "Addresses" in customer and customer["Addresses"]:
                if isinstance(customer["Addresses"], list) and len(customer["Addresses"]) > 0:
                    subject["address"] = customer["Addresses"][0]
            
            subjects.append(subject)
    
    # Extract from alternative structure if needed
    elif "customerInformation" in section and "US Bank Customers" in section["customerInformation"]:
        for customer in section["customerInformation"]["US Bank Customers"]:
            subject = {
                "name": customer.get("Name", ""),
                "is_primary": True if len(subjects) == 0 else False,  # First subject is primary
                "party_key": customer.get("Party Key", ""),
                "occupation": customer.get("Occupation Description", ""),
                "employer": customer.get("Employer", ""),
                "nationality": customer.get("Nationality", ""),
                "address": "",
                "account_relationship": ""
            }
            
            # Extract addresses
            if "Addresses" in customer and customer["Addresses"]:
                if isinstance(customer["Addresses"], list) and len(customer["Addresses"]) > 0:
                    subject["address"] = customer["Addresses"][0]
            
            subjects.append(subject)
    
    return subjects

def get_account_info(case_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get account information from case data
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        Dict: Account information for application use
    """
    section = find_section(case_data, "Account Information")
    if not section:
        return {}
    
    # Initialize account info
    account_info = {
        "account_number": "",
        "account_type": "",
        "account_title": "",
        "open_date": "",
        "close_date": "",
        "status": "",
        "related_parties": [],
        "branch": ""
    }
    
    # Extract from Accounts format
    if "Accounts" in section and section["Accounts"]:
        account = section["Accounts"][0]  # Use the first account
        
        account_info.update({
            "account_number": account.get("Account Key", ""),
            "account_type": ", ".join(account.get("Account Type", [])) if isinstance(account.get("Account Type"), list) else "",
            "account_title": account.get("Account Title", ""),
            "open_date": account.get("Account Opening Date & Branch", ""),
            "close_date": account.get("Account Closing Date", ""),
            "status": account.get("Status Description", ""),
            "branch": account.get("Account Holding Branch", "")
        })
        
        # Process related parties
        if "Related Parties" in account and isinstance(account["Related Parties"], list):
            for party in account["Related Parties"]:
                parts = party.split(" (")
                if len(parts) == 2:
                    name = parts[0].strip()
                    role = parts[1].strip().rstrip(")")
                    account_info["related_parties"].append({"name": name, "role": role})
                else:
                    account_info["related_parties"].append({"name": party, "role": ""})
    
    # Extract from alternative structure if needed
    elif "accountInformation" in section and "Account" in section["accountInformation"]:
        account = section["accountInformation"]["Account"]
        
        account_info.update({
            "account_number": account.get("Account Key", ""),
            "account_type": ", ".join(account.get("Types", [])) if isinstance(account.get("Types"), list) else "",
            "account_title": account.get("Title", ""),
            "status": account["Status"]["Description"] if "Status" in account and "Description" in account["Status"] else ""
        })
        
        # Handle opening date
        if "Opening" in account:
            account_info["open_date"] = account["Opening"].get("Date", "")
            account_info["branch"] = account["Opening"].get("Branch", "")
        
        # Handle closing date
        account_info["close_date"] = account.get("Closing Date", "")
        
        # Process related parties
        if "Related Parties" in account and isinstance(account["Related Parties"], list):
            for party in account["Related Parties"]:
                account_info["related_parties"].append({"name": party, "role": ""})
    
    return account_info

def get_accounts(case_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get all accounts from case data
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        List[Dict]: All accounts information for application use
    """
    section = find_section(case_data, "Account Information")
    if not section:
        return []
    
    accounts = []
    
    # Extract from Accounts format
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
            
            accounts.append(account_data)
    
    # Extract from alternative structure if needed
    elif "accountInformation" in section and "Account" in section["accountInformation"]:
        account = section["accountInformation"]["Account"]
        
        account_data = {
            "account_number": account.get("Account Key", ""),
            "account_type": ", ".join(account.get("Types", [])) if isinstance(account.get("Types"), list) else "",
            "account_title": account.get("Title", ""),
            "status": account["Status"]["Description"] if "Status" in account and "Description" in account["Status"] else "",
            "related_parties": [],
            "branch": ""
        }
        
        # Handle opening date
        if "Opening" in account:
            account_data["open_date"] = account["Opening"].get("Date", "")
            account_data["branch"] = account["Opening"].get("Branch", "")
        
        # Handle closing date
        account_data["close_date"] = account.get("Closing Date", "")
        
        # Process related parties
        if "Related Parties" in account and isinstance(account["Related Parties"], list):
            for party in account["Related Parties"]:
                account_data["related_parties"].append({"name": party, "role": ""})
        
        accounts.append(account_data)
    
    return accounts

def get_prior_cases(case_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get prior cases from case data
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        List[Dict]: Prior cases information for application use
    """
    section = find_section(case_data, "Prior Cases/SARs")
    if not section or "priorCases" not in section:
        return []
    
    prior_cases = []
    
    for prior_case in section["priorCases"]:
        case_data = {
            "case_number": prior_case.get("Case Number", ""),
            "alert_id": [],
            "alert_month": [],
            "review_period": {"start": "", "end": ""},
            "sar_form_number": "",
            "filing_date": "",
            "summary": ""
        }
        
        # Extract alert IDs and months
        if "Alerting Information" in prior_case:
            case_data["alert_id"] = prior_case["Alerting Information"].get("Alert IDs", [])
            case_data["alert_month"] = prior_case["Alerting Information"].get("Alert Months", [])
        
        # Extract review period
        if "Scope of Review" in prior_case:
            if isinstance(prior_case["Scope of Review"], dict):
                case_data["review_period"]["start"] = prior_case["Scope of Review"].get("start", "")
                case_data["review_period"]["end"] = prior_case["Scope of Review"].get("end", "")
        
        # Extract SAR details
        if "SAR Details" in prior_case:
            case_data["sar_form_number"] = prior_case["SAR Details"].get("Form Number", "")
            case_data["filing_date"] = prior_case["SAR Details"].get("Filing Date", "")
            case_data["summary"] = prior_case["SAR Details"].get("SAR Summary", "")
        
        # Extract summary from Investigation Summary if available
        if "summary" not in case_data or not case_data["summary"]:
            case_data["summary"] = prior_case.get("Investigation Summary", "")
        
        prior_cases.append(case_data)
    
    return prior_cases

def get_database_searches(case_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get database searches information from case data
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        Dict: Database searches information for application use
    """
    section = find_section(case_data, "Database Searches")
    if not section:
        return {"kyc": {"results": ""}, "adverse_media": {"results": ""}, "risk_ratings": []}
    
    db_searches = {
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
        
        db_searches["kyc"]["results"] = "\n".join(kyc_results) if kyc_results else "No WebKYC form links found"
    
    # Process adverse media
    if "Adverse Media Review" in section:
        db_searches["adverse_media"]["results"] = section["Adverse Media Review"]
    
    # Process risk ratings
    if "Risk Ratings" in section:
        for rating in section["Risk Ratings"]:
            db_searches["risk_ratings"].append({
                "name": rating.get("Subject Name", ""),
                "party_key": rating.get("Party Key", ""),
                "sor": rating.get("SOR", ""),
                "rating": rating.get("Party Risk Rating Code Description", "")
            })
    
    return db_searches

def get_review_period(case_data: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Get review period from case data
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        Dict: Review period with start and end dates
    """
    review_period = {"start": "", "end": ""}
    
    # Try to get from Account Information section
    account_section = find_section(case_data, "Account Information")
    if account_section:
        if "Case Review Period" in account_section:
            review_period_str = account_section.get("Case Review Period", "")
            dates = review_period_str.split(" - ")
            if len(dates) == 2:
                review_period["start"] = dates[0]
                review_period["end"] = dates[1]
                return review_period
        
        # Try alternative format
        if "accountInformation" in account_section and "Review Period" in account_section["accountInformation"]:
            review_period_str = account_section["accountInformation"].get("Review Period", "")
            dates = review_period_str.split(" – ")  # Note the different dash character
            if len(dates) == 2:
                review_period["start"] = dates[0]
                review_period["end"] = dates[1]
                return review_period
    
    # Try to get from alert info if available
    alerting_section = find_section(case_data, "Alerting Details")
    if alerting_section and "alerts" in alerting_section and alerting_section["alerts"]:
        alert = alerting_section["alerts"][0]  # Use first alert
        if "Review Period" in alert:
            review_period_str = alert.get("Review Period", "")
            dates = review_period_str.split(" - ")
            if len(dates) == 2:
                review_period["start"] = dates[0]
                review_period["end"] = dates[1]
    
    return review_period

def extract_flattened_case(case_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract data from case sections into the flattened format expected by the application
    
    Args:
        case_data: List of section objects from the case
    
    Returns:
        Dict: Case data in flattened format used by application
    """
    # Create the flattened structure with all original data preserved
    flattened_data = {
        "case_number": get_case_number(case_data),
        "alert_info": get_alert_info(case_data),
        "subjects": get_subjects(case_data),
        "account_info": get_account_info(case_data),
        "accounts": get_accounts(case_data),
        "prior_cases": get_prior_cases(case_data),
        "database_searches": get_database_searches(case_data),
        "review_period": get_review_period(case_data),
        # Store the full original data
        "original_data": case_data
    }
    
    return flattened_data