"""
Module for validating and sanitizing case and transaction data.

This module defines the `DataValidator` class, which is responsible for
validating data extracted from case documents and transaction files (simulated as `excel_data`).
It employs a "relaxed validation" strategy, meaning it attempts to fill in missing
information with defaults or derive it from other available data points rather than
strictly failing. This approach is suitable for development and ensuring the application
can proceed even with incomplete datasets. Warnings are logged for missing or defaulted data.
The validator checks various components like case number, alert information, subject details,
account information, and transaction summaries.
"""
from typing import Dict, List, Any, Optional, Tuple
# import re # Removed as 're' is no longer used in this file
from datetime import datetime

from backend.utils.logger import get_logger

logger = get_logger(__name__)

class DataValidator:
    """Validates extracted data and handles missing information with relaxed requirements"""
    
    def __init__(self, case_data: Dict[str, Any], excel_data: Dict[str, Any]):
        """
        Initialize with extracted data
        
        Args:
            case_data: Extracted case document data
            excel_data: Extracted transaction data (in excel-compatible format)
        """
        self.case_data = case_data
        self.excel_data = excel_data
        self.validation_errors = []
        self.missing_required = []
        self.warnings = []
    
    def validate_case_number(self) -> bool:
        """
        Validate case number.
        This method employs relaxed validation for development purposes.
        It attempts to extract the case number from `case_data` or `full_data`.
        If missing, it logs it as a required field but still returns True.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        case_number = self.case_data.get("case_number", "")
        
        if not case_number:
            # Attempt to extract case number from the "full_data" structure if not directly available.
            full_data = self.case_data.get("full_data", [])
            if full_data:
                for section in full_data:
                    if section.get("section") == "Case Information":
                        case_number = section.get("Case Number", "")
                        if case_number:
                            self.case_data["case_number"] = case_number
                            break
            
            if not case_number:
                # Log that case number is missing, critical for production but allowed in dev.
                self.missing_required.append("Case number is missing")
                # Relaxed validation: In a strict mode, this would be `return False`.
        
        # Relaxed validation: Current logic allows any non-empty case number and doesn't enforce specific formats.
        # Always returns True for development.
        return True
    
    def validate_alert_info(self) -> bool:
        """
        Validate alert information.
        This method employs relaxed validation for development purposes.
        It ensures `alert_info` is a list and attempts to extract it from `full_data` if initially empty.
        If no alerts are found, a default placeholder alert is created and a warning is logged.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        alert_info = self.case_data.get("alert_info", [])
        
        # Ensure alert_info is a list, even if initially empty or a single dict.
        if not alert_info:
            alert_info = []
            self.case_data["alert_info"] = alert_info
        if isinstance(alert_info, dict):
            alert_info = [alert_info]
            self.case_data["alert_info"] = alert_info
        
        # Attempt to extract alert information from "full_data" if `alert_info` is empty.
        if not alert_info and self.case_data.get("full_data", []):
            for section in self.case_data["full_data"]:
                if section.get("section") == "Alerting Details": # Look for "Alerting Details" section
                    alerts_raw = section.get("alerts", [])
                    if alerts_raw:
                        processed_alerts = []
                        for alert_item in alerts_raw:
                            alert_obj = {
                                "alert_id": alert_item.get("Alert ID", ""),
                                "alert_month": alert_item.get("Alert Month", ""),
                                "description": alert_item.get("Description", ""),
                                "review_period": {"start": "", "end": ""}
                            }
                            # Parse review period if available in "Start - End" format.
                            review_period_str = alert_item.get("Review Period", "")
                            if review_period_str and " - " in review_period_str:
                                dates = review_period_str.split(" - ")
                                if len(dates) == 2:
                                    alert_obj["review_period"]["start"] = dates[0]
                                    alert_obj["review_period"]["end"] = dates[1]
                            processed_alerts.append(alert_obj)
                        self.case_data["alert_info"] = processed_alerts
                        alert_info = processed_alerts # Update local variable
                        break
        
        # If no alert information is found after attempts, create a default placeholder.
        if not alert_info:
            self.warnings.append("Alert information is missing. Adding default alert placeholder.")
            # Default alert information if none is found in case_data or full_data.
            self.case_data["alert_info"] = [{
                "alert_id": "DEFAULT001",
                "description": "Default alert - No specific alert information found.",
                "review_period": { # Default review period for the placeholder alert.
                    "start": "",
                    "end": ""
                }
            }]
            
        # Relaxed validation: This method always returns True for development,
        # relying on logging warnings and using defaults for missing data.
        return True
    
    def validate_subjects(self) -> bool:
        """
        Validate subject information.
        This method employs relaxed validation for development purposes.
        It attempts to extract subject details from `full_data` (checking "Hogan Search"
        then "Customer Information" sections) if `subjects` is initially empty.
        If no subjects are found, a default "UNKNOWN SUBJECT" is created.
        It also ensures at least one subject is marked as primary.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        subjects = self.case_data.get("subjects", [])
        
        # Attempt to extract subject information from "full_data" if `subjects` list is empty.
        if not subjects and self.case_data.get("full_data", []):
            # Prioritize "Hogan Search" section for subject data as it's a newer format.
            for section in self.case_data["full_data"]:
                if "Hogan Search" in section:
                    hogan_subjects_raw = section.get("Hogan Search", [])
                    if hogan_subjects_raw:
                        processed_subjects = []
                        for idx, hogan_subject in enumerate(hogan_subjects_raw):
                            subject = {
                                "name": hogan_subject.get("Case Subject", ""),
                                "is_primary": idx == 0,  # Assume first subject from Hogan Search is primary.
                                "party_key": str(hogan_subject.get("Primary Party Key", "")),
                                "occupation": "", # Default empty occupation
                                "employer": "",   # Default empty employer
                                "nationality": "",# Default empty nationality
                                "address": "",    # Default empty address
                                "account_relationship": "" # Default empty relationship
                            }
                            processed_subjects.append(subject)
                        self.case_data["subjects"] = processed_subjects
                        subjects = processed_subjects # Update local variable
                        break
            
            # If not found in "Hogan Search", try the older "Customer Information" section.
            if not subjects: # Check if subjects list is still empty
                for section in self.case_data["full_data"]:
                    if section.get("section") == "Customer Information":
                        if "US Bank Customer Information" in section: # Specific sub-key for customer data
                            customers_raw = section["US Bank Customer Information"]
                            processed_subjects = []
                            for idx, customer in enumerate(customers_raw):
                                subject = {
                                    "name": customer.get("Primary Party", ""),
                                    "is_primary": idx == 0,  # Assume first customer is primary.
                                    "party_key": customer.get("Party Key", ""),
                                    "occupation": customer.get("Occupation Description", ""),
                                    "employer": customer.get("Employer", ""),
                                    "nationality": customer.get("Country of Nationality", ""),
                                    "address": "", # Default address, to be filled if available
                                    "account_relationship": "" # Default relationship
                                }
                                # Extract first address if available within the customer's address list.
                                addresses_raw = customer.get("Addresses", [])
                                if isinstance(addresses_raw, list) and addresses_raw:
                                    subject["address"] = addresses_raw[0] # Take the first address string
                                processed_subjects.append(subject)
                            self.case_data["subjects"] = processed_subjects
                            subjects = processed_subjects # Update local variable
                            break

        # If no subject information is found after all attempts, create a default placeholder subject.
        if not subjects:
            self.warnings.append("Subject information is missing. Adding default 'UNKNOWN SUBJECT'.")
            # Default subject placeholder if no subjects are found.
            self.case_data["subjects"] = [{
                "name": "UNKNOWN SUBJECT",
                "is_primary": True, # Mark the default subject as primary.
                "occupation": "",
                "employer": "",
                "address": ""
            }]
            subjects = self.case_data["subjects"] # Update local variable
        
        # Ensure at least one subject is marked as primary.
        has_primary = any(subject.get("is_primary", False) for subject in subjects)
        if not has_primary and subjects: # If no primary subject and list is not empty
            self.warnings.append("No primary subject identified. Setting first subject as primary.")
            subjects[0]["is_primary"] = True # Designate the first subject as primary.
        
        # Update the main case_data with potentially modified subjects list.
        self.case_data["subjects"] = subjects
        
        # Relaxed validation: This method always returns True for development.
        return True
    
    def validate_account_info(self) -> bool:
        """
        Validate account information.
        This method employs relaxed validation for development purposes.
        It attempts to extract account details from `full_data` if `account_info`
        is initially empty or lacks an account number.
        Defaults are provided for missing fields like account_type and account_number,
        with warnings logged.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        account_info = self.case_data.get("account_info", {})
        
        # Attempt to extract account information from "full_data" if current `account_info` is minimal or empty.
        # This targets scenarios where account_number might be missing.
        if (not account_info or not account_info.get("account_number")) and self.case_data.get("full_data", []):
            for section in self.case_data["full_data"]:
                if section.get("section") == "Account Information": # Look for "Account Information" section
                    # Check for "Accounts" sub-section (newer format)
                    if "Accounts" in section and section["Accounts"]:
                        account_raw = section["Accounts"][0]  # Take the first account found.
                        account_info = {
                            "account_number": account_raw.get("Account Key", ""),
                            "account_type": ", ".join(account_raw.get("Account Type", [])) if isinstance(account_raw.get("Account Type"), list) else account_raw.get("Account Type", ""),
                            "account_title": account_raw.get("Account Title", ""),
                            "open_date": account_raw.get("Account Opening Date & Branch", ""), # This might contain branch info too.
                            "close_date": account_raw.get("Account Closing Date", ""),
                            "status": account_raw.get("Status Description", ""),
                            "related_parties": [],
                            "branch": account_raw.get("Account Holding Branch", "")
                        }
                        # Process related parties from the raw data.
                        parties_raw = account_raw.get("Related Parties", [])
                        if isinstance(parties_raw, list):
                            for party_str in parties_raw:
                                parts = party_str.split(" (") # Expects "Name (Role)" format.
                                if len(parts) == 2:
                                    name = parts[0].strip()
                                    role = parts[1].strip().rstrip(")")
                                    account_info["related_parties"].append({"name": name, "role": role})
                                else: # Fallback if format is unexpected.
                                    account_info["related_parties"].append({"name": party_str, "role": ""})
                        self.case_data["account_info"] = account_info
                        break # Found in "Accounts", exit loop.
                    # Check for "accountInformation" sub-section (older format)
                    elif "accountInformation" in section and "Account" in section["accountInformation"]:
                        account_raw = section["accountInformation"]["Account"]
                        account_info = {
                            "account_number": account_raw.get("Account Key", ""),
                            "account_type": ", ".join(account_raw.get("Types", [])) if isinstance(account_raw.get("Types"), list) else account_raw.get("Types", ""),
                            "account_title": account_raw.get("Title", ""),
                            "status": account_raw.get("Status", {}).get("Description", "") if "Status" in account_raw else "",
                            "related_parties": [],
                            "branch": "" # Branch info might be in "Opening" for this format.
                        }
                        # Extract opening date and branch if available.
                        if "Opening" in account_raw:
                            account_info["open_date"] = account_raw["Opening"].get("Date", "")
                            account_info["branch"] = account_raw["Opening"].get("Branch", "")
                        account_info["close_date"] = account_raw.get("Closing Date", "") # Closing date.
                        # Process related parties.
                        parties_raw = account_raw.get("Related Parties", [])
                        if isinstance(parties_raw, list):
                            for party_str in parties_raw: # Simpler party format here.
                                account_info["related_parties"].append({"name": party_str, "role": ""})
                        self.case_data["account_info"] = account_info
                        break # Found in "accountInformation", exit loop.
        
        # If account_info is still essentially empty after extraction attempts, create a default structure.
        if not account_info or not account_info.get("account_number"): # Check again as extraction might have failed
            self.warnings.append("Account information (especially account number) is missing. Using default structure.")
            # Default account_info structure if no data is found.
            account_info = {
                "account_number": "", # To be filled by later logic if possible
                "account_type": "Unknown Account",
                "status": "Unknown Status",
                "open_date": "", "close_date": "", "account_title": "", "related_parties": [], "branch": ""
            }
            self.case_data["account_info"] = account_info # Assign default to case_data
        
        # Default for account_type if missing.
        if not account_info.get("account_type"):
            self.warnings.append("Account type is missing, defaulting to 'checking/savings account'.")
            account_info["account_type"] = "checking/savings account"
        
        # Default for account_number if missing.
        # Attempts to derive from `excel_data.account_summaries` as a last resort.
        if not account_info.get("account_number"):
            self.warnings.append("Account number is missing.")
            account_summaries = self.excel_data.get("account_summaries", {})
            if account_summaries and isinstance(account_summaries, dict) and len(account_summaries) > 0:
                # Take the first account number found in account_summaries keys.
                derived_account_number = next(iter(account_summaries.keys()), "UNKNOWN_ACC_FROM_SUM")
                account_info["account_number"] = derived_account_number
                self.warnings.append(f"Derived account number '{derived_account_number}' from account_summaries.")
            else: # Final fallback if no derivation is possible.
                account_info["account_number"] = "ACC_NUM_MISSING"
                self.warnings.append("Could not derive account number, set to 'ACC_NUM_MISSING'.")

        # Ensure the potentially modified account_info is stored back.
        self.case_data["account_info"] = account_info
        
        # Relaxed validation: Always returns True for development.
        return True
    
    def validate_transaction_data(self) -> bool:
        """
        Validate transaction data from `excel_data`.
        This method employs relaxed validation for development purposes.
        It checks for the presence of `transaction_summary`, `activity_summary`,
        and `unusual_activity` in `excel_data`. If any are missing,
        default empty structures are created and warnings are logged.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        # Check for transaction_summary; provide default if missing.
        # This summary usually contains total credits/debits and breakdowns.
        transaction_summary = self.excel_data.get("transaction_summary", {})
        if not transaction_summary:
            self.warnings.append("Transaction summary from excel_data is missing. Using default empty structure.")
            # Default structure for transaction_summary.
            self.excel_data["transaction_summary"] = {
                "total_credits": 0, "total_debits": 0,
                "credit_breakdown": [], "debit_breakdown": []
            }
        
        # Check for activity_summary; provide default if missing.
        # This summary usually contains overall activity dates and total amount.
        activity_summary = self.excel_data.get("activity_summary", {})
        if not activity_summary:
            self.warnings.append("Activity summary from excel_data is missing. Using default empty structure.")
            # Default structure for activity_summary.
            self.excel_data["activity_summary"] = {
                "start_date": "", "end_date": "", "total_amount": 0
            }
        
        # Check for unusual_activity; provide default if missing.
        # This usually contains a list of transactions flagged as unusual.
        unusual_activity = self.excel_data.get("unusual_activity", {})
        if not unusual_activity:
            self.warnings.append("Unusual activity data from excel_data is missing. Using default empty structure.")
            # Default structure for unusual_activity.
            self.excel_data["unusual_activity"] = {"transactions": []}
        
        # Relaxed validation: Always returns True for development,
        # ensuring these keys exist in excel_data with default structures if needed.
        return True
    
    def validate_activity_summary(self) -> bool:
        """
        Validate activity summary details within `excel_data`.
        This method employs relaxed validation for development purposes.
        It ensures `activity_summary` exists, and populates `total_amount`,
        `start_date`, `end_date`, and `transaction_types` with defaults or
        derived values if they are missing, logging warnings accordingly.
        Data is sourced from `transaction_summary`, `case_data.review_period`,
        `case_data.alert_info`, or `case_data.full_data` before falling back to hardcoded defaults.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        activity_summary = self.excel_data.get("activity_summary", {})
        
        # If activity_summary itself is missing from excel_data, create a default structure.
        if not activity_summary: # This check might be redundant if validate_transaction_data ran first.
            self.warnings.append("Activity summary dict is missing in excel_data. Creating default structure.")
            # Default structure for activity_summary.
            activity_summary = {
                "total_amount": 0.0, "start_date": "", "end_date": "", "transaction_types": []
            }
            self.excel_data["activity_summary"] = activity_summary # Assign back to excel_data.
        
        # Validate and default 'total_amount'.
        # Attempts to derive from `excel_data.transaction_summary` if not present or zero.
        if activity_summary.get("total_amount", 0) <= 0: # Check if not present, None, or <= 0
            self.warnings.append(f"Activity total amount is missing or non-positive ('{activity_summary.get('total_amount')}'). Attempting to derive.")
            transaction_summary = self.excel_data.get("transaction_summary", {})
            if transaction_summary: # Check if transaction_summary exists and is not empty
                total_credits = transaction_summary.get("total_credits", 0)
                total_debits = transaction_summary.get("total_debits", 0)
                # Use the sum of total credits and debits as the derived total amount.
                derived_total = total_credits + total_debits # Or max(total_credits, total_debits) depending on definition
                if derived_total > 0:
                    activity_summary["total_amount"] = derived_total
                    self.warnings.append(f"Derived activity total amount: {derived_total}.")
                else: # If derived total is also zero.
                    activity_summary["total_amount"] = 0.0 # Keep it as 0.0 if no positive derivation.
                    self.warnings.append("Derived activity total amount is also zero.")
            else: # If no transaction_summary to derive from.
                activity_summary["total_amount"] = 0.0 # Fallback to 0.0.
                self.warnings.append("No transaction_summary to derive total_amount. Set to 0.0.")

        # Validate and default 'start_date' and 'end_date'.
        # Attempts to derive from `case_data` (review_period, alert_info, full_data sections)
        # before using hardcoded defaults.
        # Data sources for dates, in order of preference:
        # 1. case_data.review_period
        # 2. case_data.alert_info[0].review_period
        # 3. case_data.full_data ("Scope of Review" section)
        # 4. case_data.full_data ("Account Information" section's "Case Review Period")
        # 5. Hardcoded default ("01/01/2023" for start, current date for end)

        # Helper to get dates from various sources
        def get_date_from_sources(date_key: str, default_value: str) -> str:
            # Source 1: case_data.review_period
            review_period_data = self.case_data.get("review_period", {})
            if review_period_data.get(date_key): return review_period_data[date_key]
            
            # Source 2: case_data.alert_info[0].review_period
            alert_info_list = self.case_data.get("alert_info", [])
            first_alert = alert_info_list[0] if alert_info_list and isinstance(alert_info_list,list) else {}
            alert_review_period = first_alert.get("review_period", {}) if isinstance(first_alert, dict) else {}
            if alert_review_period.get(date_key): return alert_review_period[date_key]
            
            # Source 3 & 4: case_data.full_data
            full_data_list = self.case_data.get("full_data", [])
            for section in full_data_list:
                if section.get("section") == "Scope of Review": # Source 3
                    if section.get("Start Date" if date_key == "start" else "End Date"):
                        return section["Start Date" if date_key == "start" else "End Date"]
                if section.get("section") == "Account Information": # Source 4
                    review_period_str = section.get("Case Review Period", "")
                    if review_period_str and " - " in review_period_str:
                        dates = review_period_str.split(" - ")
                        if len(dates) == 2: return dates[0] if date_key == "start" else dates[1]
            return default_value # Source 5: Hardcoded default

        if not activity_summary.get("start_date"):
            activity_summary["start_date"] = get_date_from_sources("start", "01/01/2023")
            self.warnings.append(f"Activity start date is missing. Using derived/default: {activity_summary['start_date']}.")
            
        if not activity_summary.get("end_date"):
            activity_summary["end_date"] = get_date_from_sources("end", datetime.now().strftime("%m/%d/%Y"))
            self.warnings.append(f"Activity end date is missing. Using derived/default: {activity_summary['end_date']}.")

        # Validate and default 'transaction_types'.
        # Attempts to derive from `excel_data.transaction_summary.credit_breakdown`.
        if not activity_summary.get("transaction_types"):
            self.warnings.append("Activity transaction types are missing. Attempting to derive.")
            derived_types = []
            transaction_summary = self.excel_data.get("transaction_summary", {})
            if transaction_summary and transaction_summary.get("credit_breakdown"):
                # Take top 3 types from credit_breakdown.
                derived_types = [item.get("type", "Unknown") for item in transaction_summary.get("credit_breakdown", [])[:3]]
            
            if derived_types:
                activity_summary["transaction_types"] = derived_types
                self.warnings.append(f"Derived transaction types: {derived_types}.")
            else: # Fallback if no derivation possible.
                activity_summary["transaction_types"] = ["Unknown Transaction Type"]
                self.warnings.append("Could not derive transaction types. Using default.")
        
        # Ensure the potentially modified activity_summary is stored back.
        self.excel_data["activity_summary"] = activity_summary
        
        # Relaxed validation: Always returns True for development.
        return True
    
    def validate_unusual_activity(self) -> bool:
        """
        Validate unusual activity data within `excel_data`.
        This method employs relaxed validation for development purposes.
        It ensures `unusual_activity` and its `transactions` list exist.
        If `transactions` are missing, it attempts to derive them from `full_data`
        or `transaction_summary`. A summary for unusual activity is also
        created/defaulted based on `activity_summary`.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        unusual_activity = self.excel_data.get("unusual_activity", {})
        
        # Ensure basic structure of unusual_activity.
        if not unusual_activity: # If unusual_activity dict itself is missing.
            self.warnings.append("Unusual activity dict is missing in excel_data. Creating default structure.")
            unusual_activity = {"transactions": [], "summary": {}}
            self.excel_data["unusual_activity"] = unusual_activity # Assign back to excel_data.
        
        # Check for unusual activity transaction samples.
        samples = unusual_activity.get("transactions", [])
        if not samples: # If the 'transactions' list is missing or empty.
            self.warnings.append("No unusual activity samples found. Attempting to derive.")
            derived_samples = []
            # Attempt 1: Extract from `case_data.full_data` "Unusual Activity" section.
            full_data_list = self.case_data.get("full_data", [])
            for section in full_data_list:
                if "Unusual Activity" in section: # Section key
                    unusual_activity_raw_samples = section.get("Unusual Activity", []) # List of samples
                    if unusual_activity_raw_samples:
                        for sample_item in unusual_activity_raw_samples:
                            derived_samples.append({
                                "date": sample_item.get("Transaction Date", ""),
                                "amount": sample_item.get("Transaction Amount", 0), # Assuming this needs to_float if string
                                "type": sample_item.get("Custom Language", ""),
                                "description": sample_item.get("Memo", ""),
                                "account": str(sample_item.get("Account", ""))
                            })
                        break # Found samples in full_data
            
            # Attempt 2: If no samples from full_data, try to derive from `excel_data.transaction_summary`.
            if not derived_samples:
                transaction_summary = self.excel_data.get("transaction_summary", {})
                if transaction_summary:
                    # Create sample transactions from credit/debit breakdowns (e.g., 2 from each).
                    for breakdown_key in ["credit_breakdown", "debit_breakdown"]:
                        breakdown_items = transaction_summary.get(breakdown_key, [])
                        for item in breakdown_items[:2]: # Take top 2 items
                            txn_type = item.get("type", "Unknown")
                            avg_amount = item.get("amount", 0) / item.get("count", 1) if item.get("count", 0) > 0 else item.get("amount", 0)
                            derived_samples.append({
                                "date": self.excel_data.get("activity_summary", {}).get("start_date", "01/01/2023"), # Use activity start date
                                "amount": avg_amount,
                                "type": txn_type,
                                "description": f"Derived sample: {txn_type}"
                            })
            
            if derived_samples:
                unusual_activity["transactions"] = derived_samples
                self.warnings.append(f"Derived {len(derived_samples)} unusual activity samples.")
            else: # If still no samples.
                self.warnings.append("Could not derive any unusual activity samples.")
                unusual_activity["transactions"] = [] # Ensure it's an empty list.

            # Default or derive summary for unusual activity based on the main activity_summary.
            # This assumes unusual activity might span the same period/amount if not specified.
            activity_summary_ref = self.excel_data.get("activity_summary", {})
            unusual_activity["summary"] = {
                "total_amount": activity_summary_ref.get("total_amount", 0), # Default to overall activity amount
                "date_range": {
                    "start": activity_summary_ref.get("start_date", ""), # Default to overall activity start date
                    "end": activity_summary_ref.get("end_date", "")      # Default to overall activity end date
                }
            }
            if not unusual_activity.get("summary",{}).get("total_amount"): # If total amount is still 0
                 self.warnings.append("Unusual activity summary total_amount is zero, might indicate missing detailed data.")

        # Ensure the potentially modified unusual_activity is stored back.
        self.excel_data["unusual_activity"] = unusual_activity
        
        # Relaxed validation: Always returns True for development.
        return True
    
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all extracted data.
        This method employs relaxed validation for development purposes.
        It calls individual `validate_*` methods which may use default values
        for missing data and log warnings. This main validate method currently
        always returns `True` to allow processing even with incomplete data during development.
        
        Returns:
            Tuple: (is_valid, errors, warnings)
                   - `is_valid` is always True in relaxed mode.
                   - `errors` contains a list of missing required fields.
                   - `warnings` contains a list of non-critical issues or applied defaults.
        """
        # Reset validation lists for the current validation run.
        self.validation_errors = [] # Intended for hard errors, less used in relaxed mode.
        self.missing_required = []# For fields deemed essential even in relaxed mode (e.g. case_number).
        self.warnings = []         # For applied defaults or non-critical missing data.

        # Call individual validation methods. These methods will populate
        # `self.missing_required` and `self.warnings` and may modify
        # `self.case_data` and `self.excel_data` by filling in defaults.
        self.validate_case_number()
        self.validate_alert_info()
        self.validate_subjects()
        self.validate_account_info()
        self.validate_transaction_data() # Validates structure of transaction related dicts in excel_data
        self.validate_activity_summary() # Validates content of activity_summary in excel_data
        self.validate_unusual_activity() # Validates content of unusual_activity in excel_data
        
        # Combine errors and missing_required fields.
        # In strict validation, `self.validation_errors` would be checked.
        errors = self.validation_errors + self.missing_required
        
        # Relaxed validation for development: Always return True.
        # In a production/strict mode, this would be `len(errors) == 0`.
        logger.info(f"Data validation complete. Errors: {len(errors)}, Warnings: {len(self.warnings)}")
        if errors:
            logger.error(f"Validation - Missing required fields: {self.missing_required}")
        if self.warnings:
            logger.warning(f"Validation - Warnings: {self.warnings}")

        return True, errors, self.warnings
    
    def fill_missing_data(self) -> Dict[str, Any]:
        """
        Fills in missing data by first running the validation process (which applies
        defaults and logs warnings due to its relaxed nature) and then combines
        `case_data` and `excel_data`.

        This method further ensures critical fields in the `combined_data` dictionary,
        such as dates and total amounts for `activity_summary`, `review_period`,
        and the first alert's `review_period`, are populated with defaults if they
        are still missing after the initial validation and defaulting pass.

        The process is as follows:
        1. Calls `self.validate()`: This step performs the "relaxed validation" where
           individual `validate_*` methods attempt to extract data from various sources
           (e.g., `full_data`, other parts of `case_data` or `excel_data`) and apply
           default values if data is missing, logging warnings.
        2. Combines `case_data` and `excel_data`: Merges the (potentially modified by validation)
           `case_data` and `excel_data` into a single `combined_data` dictionary.
        3. Final Defaulting Pass: Explicitly checks and provides defaults for:
           - `activity_summary.total_amount` (derived from `transaction_summary` or hardcoded).
           - `activity_summary.start_date` and `activity_summary.end_date` (hardcoded defaults).
           - `review_period.start` and `review_period.end` (aligned with `activity_summary` dates).
           - `alert_info[0].review_period.start` and `alert_info[0].review_period.end`
             (aligned with `activity_summary` dates if the first alert exists).
        
        Returns:
            Dict: The combined data dictionary with missing fields populated by defaults.
        """
        # Step 1: Run the validation process.
        # This also handles initial data extraction attempts and defaulting for many fields
        # as defined in the individual validate_* methods, logging warnings.
        self.validate()
        
        # Step 2: Combine data from case_data and excel_data.
        # Start with fields primarily from case_data.
        combined_data = {
            "case_number": self.case_data.get("case_number", ""),
            "alert_info": self.case_data.get("alert_info", []),
            "subjects": self.case_data.get("subjects", []),
            "account_info": self.case_data.get("account_info", {}),
            "prior_cases": self.case_data.get("prior_cases", []),
            "database_searches": self.case_data.get("database_searches", {}),
            "review_period": self.case_data.get("review_period", {}) # review_period from case_data
        }

        # Add fields primarily from excel_data.
        combined_data.update({
            "activity_summary": self.excel_data.get("activity_summary", {}),
            "unusual_activity": self.excel_data.get("unusual_activity", {}),
            "cta_sample": self.excel_data.get("cta_sample", {}),
            "bip_sample": self.excel_data.get("bip_sample", {}),
            "transaction_summary": self.excel_data.get("transaction_summary", {}),
            "account_summaries": self.excel_data.get("account_summaries", {}),
            "inter_account_transfers": self.excel_data.get("inter_account_transfers", [])
        })

        # Step 3: Final Defaulting Pass for critical combined_data fields.

        # Ensure 'activity_summary' exists and is a dictionary.
        if not isinstance(combined_data.get("activity_summary"), dict):
            self.warnings.append("Combined_data 'activity_summary' was not a dict. Initializing.")
            combined_data["activity_summary"] = {}
        activity_summary = combined_data["activity_summary"] # Get a reference

        # Default for 'activity_summary.total_amount' if missing or non-positive.
        # Attempts to derive from 'transaction_summary' before using a hardcoded fallback.
        if activity_summary.get("total_amount", 0) <= 0:
            self.warnings.append("Activity summary total_amount is missing or non-positive in combined_data. Applying defaults.")
            transaction_summary = combined_data.get("transaction_summary", {})
            if transaction_summary: # Check if transaction_summary is available
                total_credits = transaction_summary.get("total_credits", 0)
                total_debits = transaction_summary.get("total_debits", 0)
                derived_total = max(total_credits, total_debits) # Or sum, depending on desired logic
                if derived_total > 0:
                    activity_summary["total_amount"] = derived_total
                else: # If derived is also zero
                    activity_summary["total_amount"] = 1000.0  # Hardcoded fallback if derivation yields zero.
            else: # If no transaction_summary to derive from.
                activity_summary["total_amount"] = 1000.0  # Hardcoded fallback.

        # Default for 'activity_summary.start_date' if missing.
        if not activity_summary.get("start_date"):
            self.warnings.append("Activity summary start_date missing in combined_data. Applying default '01/01/2023'.")
            activity_summary["start_date"] = "01/01/2023"  # Default fallback.

        # Default for 'activity_summary.end_date' if missing.
        if not activity_summary.get("end_date"):
            default_end_date = datetime.now().strftime("%m/%d/%Y")
            self.warnings.append(f"Activity summary end_date missing in combined_data. Applying default (today): {default_end_date}.")
            activity_summary["end_date"] = default_end_date # Default to current date.

        # Ensure 'review_period' exists and align its dates with 'activity_summary' if missing.
        review_period = combined_data.get("review_period", {})
        if not isinstance(review_period, dict): # Ensure review_period is a dict
            review_period = {}
            combined_data["review_period"] = review_period
            self.warnings.append("Combined_data 'review_period' was not a dict. Initializing.")

        if not review_period.get("start"):
            review_period["start"] = activity_summary["start_date"] # Align with activity_summary
            self.warnings.append("Review period start date missing. Aligned with activity_summary start_date.")
        if not review_period.get("end"):
            review_period["end"] = activity_summary["end_date"] # Align with activity_summary
            self.warnings.append("Review period end date missing. Aligned with activity_summary end_date.")

        # Ensure the first alert in 'alert_info' (if any) has its 'review_period' dates aligned.
        alert_info_list = combined_data.get("alert_info", [])
        if alert_info_list and isinstance(alert_info_list, list) and alert_info_list[0]: # Check if list and has first element
            first_alert = alert_info_list[0]
            if not isinstance(first_alert.get("review_period"), dict): # Ensure review_period in alert is a dict
                first_alert["review_period"] = {}
                self.warnings.append("First alert's review_period was not a dict. Initializing.")

            if not first_alert["review_period"].get("start"):
                first_alert["review_period"]["start"] = activity_summary["start_date"] # Align
                self.warnings.append("First alert's review_period start date missing. Aligned with activity_summary.")
            if not first_alert["review_period"].get("end"):
                first_alert["review_period"]["end"] = activity_summary["end_date"] # Align
                self.warnings.append("First alert's review_period end date missing. Aligned with activity_summary.")

        return combined_data

        # Start with case data
        combined_data = {
            "case_number": self.case_data.get("case_number", ""),
            "alert_info": self.case_data.get("alert_info", []),
            "subjects": self.case_data.get("subjects", []),
            "account_info": self.case_data.get("account_info", {}),
            "prior_cases": self.case_data.get("prior_cases", []),
            "database_searches": self.case_data.get("database_searches", {}),
            "review_period": self.case_data.get("review_period", {})
        }
        
        # Add Excel data
        combined_data.update({
            "activity_summary": self.excel_data.get("activity_summary", {}),
            "unusual_activity": self.excel_data.get("unusual_activity", {}),
            "cta_sample": self.excel_data.get("cta_sample", {}),
            "bip_sample": self.excel_data.get("bip_sample", {}),
            "transaction_summary": self.excel_data.get("transaction_summary", {}),
            "account_summaries": self.excel_data.get("account_summaries", {}),
            "inter_account_transfers": self.excel_data.get("inter_account_transfers", [])
        })
        
        # Ensure activity summary values are set
        if "activity_summary" not in combined_data or not combined_data["activity_summary"]:
            combined_data["activity_summary"] = {}
            
        activity_summary = combined_data["activity_summary"]
        
        # Ensure total_amount is set
        if "total_amount" not in activity_summary or activity_summary["total_amount"] <= 0:
            # Try to get from transaction_summary
            transaction_summary = combined_data.get("transaction_summary", {})
            if transaction_summary:
                total_credits = transaction_summary.get("total_credits", 0)
                total_debits = transaction_summary.get("total_debits", 0)
                activity_summary["total_amount"] = max(total_credits, total_debits)
            else:
                activity_summary["total_amount"] = 1000.0  # Fallback default
        
        # Ensure date range is set
        if "start_date" not in activity_summary or not activity_summary["start_date"]:
            activity_summary["start_date"] = "01/01/2023"  # Default fallback
            
        if "end_date" not in activity_summary or not activity_summary["end_date"]:
            activity_summary["end_date"] = datetime.now().strftime("%m/%d/%Y")  # Default to today
            
        # Ensure review period matches activity summary dates
        review_period = combined_data.get("review_period", {})
        if not review_period:
            review_period = {}
            combined_data["review_period"] = review_period
        
        if "start" not in review_period or not review_period["start"]:
            review_period["start"] = activity_summary["start_date"]
        
        if "end" not in review_period or not review_period["end"]:
            review_period["end"] = activity_summary["end_date"]
            
        # Ensure alert info has review period
        alert_info = combined_data.get("alert_info", [])
        if alert_info and isinstance(alert_info, list) and alert_info[0]:
            first_alert = alert_info[0]
            if "review_period" not in first_alert:
                first_alert["review_period"] = {}
                
            if "start" not in first_alert["review_period"] or not first_alert["review_period"]["start"]:
                first_alert["review_period"]["start"] = activity_summary["start_date"]
                
            if "end" not in first_alert["review_period"] or not first_alert["review_period"]["end"]:
                first_alert["review_period"]["end"] = activity_summary["end_date"]
        
        return combined_data