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
        # Attempt to get case_number from the new standardized structure
        case_info = self.case_data.get("caseInfo", {})
        case_number = case_info.get("caseNumber", "")

        if case_number:
            # For compatibility with fill_missing_data, ensure case_number is also at top level of self.case_data
            self.case_data["case_number"] = case_number
        else:
            # Log that case number is missing.
            self.missing_required.append("Case number is missing from caseInfo.caseNumber")
            # Relaxed validation: In a strict mode, this would be `return False`.
            # For dev purposes, we might still set a placeholder if other parts of the system expect it.
            # However, the current logic just logs and proceeds.
            # To maintain previous behavior of having *something* in self.case_data["case_number"] for fill_missing_data:
            self.case_data["case_number"] = "" # Ensure the key exists if downstream code expects it

        # Relaxed validation: Current logic allows any non-empty case number and doesn't enforce specific formats.
        # Always returns True for development.
        return True
    
    def validate_alert_info(self) -> bool:
        """
        Validate alert information from self.case_data.alerts.
        This method employs relaxed validation for development purposes.
        It ensures `alert_info` (which is what fill_missing_data expects) is populated
        by transforming data from self.case_data.get('alerts', []).
        If no alerts are found, a default placeholder alert is created.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        source_alerts = self.case_data.get("alerts", []) # From new structure
        processed_alert_info = [] # To be populated in the format expected by fill_missing_data

        if source_alerts and isinstance(source_alerts, list):
            for alert_item_new_struct in source_alerts:
                if not isinstance(alert_item_new_struct, dict):
                    self.warnings.append(f"Skipping non-dict item in source_alerts: {alert_item_new_struct}")
                    continue

                # Transform to the structure expected by fill_missing_data
                alert_obj_old_struct = {
                    "alert_id": alert_item_new_struct.get("alertId", ""),
                    "alert_month": alert_item_new_struct.get("alertMonth", ""), # Add if needed by templates
                    "description": alert_item_new_struct.get("description", ""),
                    "review_period": {
                        "start": alert_item_new_struct.get("reviewPeriod", {}).get("startDate", ""),
                        "end": alert_item_new_struct.get("reviewPeriod", {}).get("endDate", "")
                    }
                }
                processed_alert_info.append(alert_obj_old_struct)

        if not processed_alert_info:
            self.warnings.append("Alert information is missing from case_data.alerts. Adding default alert placeholder.")
            processed_alert_info.append({
                "alert_id": "DEFAULT001",
                "alert_month": "", # Default month
                "description": "Default alert - No specific alert information found.",
                "review_period": {"start": "", "end": ""}
            })

        # Store the transformed/defaulted list in self.case_data["alert_info"] for downstream compatibility
        self.case_data["alert_info"] = processed_alert_info
            
        # Relaxed validation: This method always returns True for development,
        # relying on logging warnings and using defaults for missing data.
        return True
    
    def validate_subjects(self) -> bool:
        """
        Validate subject information from self.case_data.subjects.
        This method employs relaxed validation. It transforms subjects from the new
        structure to the "old" structure expected by fill_missing_data.
        If no subjects are found, a default "UNKNOWN SUBJECT" is created.
        It also ensures at least one subject is marked as primary.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        source_subjects = self.case_data.get("subjects", []) # From new structure
        processed_subjects_old_struct = []

        if source_subjects and isinstance(source_subjects, list):
            for subj_new in source_subjects:
                if not isinstance(subj_new, dict):
                    self.warnings.append(f"Skipping non-dict item in source_subjects: {subj_new}")
                    continue

                # Format address from new structure (list of address objects) to a single string
                address_str = "N/A"
                addresses_list = subj_new.get("addresses", [])
                if addresses_list and isinstance(addresses_list, list) and addresses_list[0]:
                    first_addr = addresses_list[0]
                    if isinstance(first_addr, dict): # Expecting address object
                        # Concatenate parts of the address. Adjust as needed.
                        address_parts = [
                            first_addr.get("addressLine1", ""),
                            first_addr.get("addressLine2", ""),
                            first_addr.get("city", ""),
                            first_addr.get("stateOrProvince", ""),
                            first_addr.get("postalCode", ""),
                            first_addr.get("countryCode", "")
                        ]
                        address_str = ", ".join(filter(None, address_parts))
                    elif isinstance(first_addr, str): # Fallback if it's just a string
                        address_str = first_addr

                subject_old_struct = {
                    "name": subj_new.get("name", ""),
                    "is_primary": subj_new.get("isPrimary", False),
                    "party_key": subj_new.get("partyKey", ""),
                    "occupation": subj_new.get("occupation", ""),
                    "employer": subj_new.get("employerName", ""), # Mapping from employerName
                    "nationality": subj_new.get("countryOfNationality", ""), # Mapping
                    "address": address_str,
                    "account_relationship": subj_new.get("accountRelationship", "") # Default if not in new struct
                }
                processed_subjects_old_struct.append(subject_old_struct)

        if not processed_subjects_old_struct:
            self.warnings.append("Subject information is missing from case_data.subjects. Adding default 'UNKNOWN SUBJECT'.")
            processed_subjects_old_struct.append({
                "name": "UNKNOWN SUBJECT",
                "is_primary": True,
                "party_key": "",
                "occupation": "",
                "employer": "",
                "nationality": "",
                "address": "",
                "account_relationship": ""
            })
        
        # Ensure at least one subject is marked as primary.
        has_primary = any(s.get("is_primary", False) for s in processed_subjects_old_struct)
        if not has_primary and processed_subjects_old_struct:
            self.warnings.append("No primary subject identified. Setting first subject as primary.")
            processed_subjects_old_struct[0]["is_primary"] = True
        
        # Store the transformed/defaulted list in self.case_data["subjects"] for downstream compatibility
        self.case_data["subjects"] = processed_subjects_old_struct
        
        return True
    
    def validate_account_info(self) -> bool:
        """
        Validate account information, sourcing from self.case_data.accounts[0]
        and transforming to the "old" account_info structure for compatibility.
        This method employs relaxed validation. Defaults are provided for missing fields,
        and warnings are logged.
        
        Returns:
            bool: True (due to relaxed validation).
        """
        accounts_list_new_struct = self.case_data.get("accounts", [])
        primary_account_new_struct = {}
        processed_account_info_old_struct = {} # This will hold the transformed data

        if accounts_list_new_struct and isinstance(accounts_list_new_struct, list):
            primary_account_new_struct = accounts_list_new_struct[0] # Take the first account as primary
            if not isinstance(primary_account_new_struct, dict):
                self.warnings.append(f"First item in case_data.accounts is not a dictionary: {primary_account_new_struct}. Using empty default.")
                primary_account_new_struct = {}
        else:
            self.warnings.append("No accounts found in case_data.accounts. Using empty default for primary account.")

        # Transform data from primary_account_new_struct to processed_account_info_old_struct
        processed_account_info_old_struct = {
            "account_number": str(primary_account_new_struct.get("accountKey", "")),
            "account_type": ", ".join(primary_account_new_struct.get("accountTypes", [])),
            "account_title": primary_account_new_struct.get("accountTitle", ""),
            "open_date": primary_account_new_struct.get("openingDate", ""),
            "close_date": primary_account_new_struct.get("closingDate", ""), # Not in example, default to ""
            "status": primary_account_new_struct.get("statusDescription", ""),
            "related_parties": [], # Default, as new structure's relatedParties might differ or be absent
            "branch": primary_account_new_struct.get("branchName", "") # Assuming 'branchName', default to ""
        }
        
        # If relatedParties exists in new structure and needs specific transformation:
        # new_related_parties = primary_account_new_struct.get("relatedParties", [])
        # for party_new in new_related_parties:
        #    processed_account_info_old_struct["related_parties"].append({"name": party_new.get("name"), "role": party_new.get("role")})


        # Default for account_type if missing or empty after transformation
        if not processed_account_info_old_struct.get("account_type"):
            self.warnings.append("Account type is missing after transformation. Defaulting to 'checking/savings account'.")
            processed_account_info_old_struct["account_type"] = "checking/savings account"

        # Default for account_number if missing after transformation.
        # Attempts to derive from `excel_data.account_summaries` as a last resort.
        if not processed_account_info_old_struct.get("account_number"):
            self.warnings.append("Account number is missing after transformation. Attempting to derive from excel_data.")
            account_summaries = self.excel_data.get("account_summaries", {})
            if account_summaries and isinstance(account_summaries, dict) and len(account_summaries) > 0:
                derived_account_number = next(iter(account_summaries.keys()), "UNKNOWN_ACC_FROM_SUM")
                processed_account_info_old_struct["account_number"] = derived_account_number
                self.warnings.append(f"Derived account number '{derived_account_number}' from account_summaries.")
            else: # Final fallback if no derivation is possible.
                processed_account_info_old_struct["account_number"] = "ACC_NUM_MISSING"
                self.warnings.append("Could not derive account number, set to 'ACC_NUM_MISSING'.")
        
        # Store the transformed/defaulted account_info in self.case_data["account_info"] for downstream compatibility
        self.case_data["account_info"] = processed_account_info_old_struct

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
        def get_date_from_sources(date_key_internal: str, default_value: str) -> str:
            # date_key_internal is "start" or "end"
            # Map to new structure keys "startDate" or "endDate"
            date_key_new_struct = "startDate" if date_key_internal == "start" else "endDate"

            # Source 1: self.case_data.caseInfo.reviewPeriod (New Structure)
            case_info_data = self.case_data.get("caseInfo", {})
            review_period_new_struct = case_info_data.get("reviewPeriod", {})
            if review_period_new_struct.get(date_key_new_struct):
                return review_period_new_struct[date_key_new_struct]
            
            # Source 2: self.case_data.alert_info[0].review_period
            # This uses self.case_data["alert_info"] which validate_alert_info already transformed
            # to the "old" structure with "start"/"end" keys.
            alert_info_list = self.case_data.get("alert_info", []) # Already transformed by validate_alert_info
            first_alert = alert_info_list[0] if alert_info_list and isinstance(alert_info_list,list) else {}
            alert_review_period = first_alert.get("review_period", {}) if isinstance(first_alert, dict) else {}
            if alert_review_period.get(date_key_internal): # Uses "start" or "end"
                return alert_review_period[date_key_internal]
            
            # Sources 3 & 4 (full_data) are removed as full_data is deprecated.
            # If reviewPeriod was not in caseInfo, and not in the first alert,
            # it will fall through to default_value.
            # Add a log if no date is found from primary sources.
            logger.warning(f"Date for '{date_key_internal}' not found in caseInfo.reviewPeriod or first alert's review_period.")
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
            
            # Attempt 1: Extract from `self.case_data.transactions.unusualActivitySample` (New Structure)
            transactions_data_new_struct = self.case_data.get("transactions", {})
            unusual_activity_sample_new_struct = transactions_data_new_struct.get("unusualActivitySample", [])

            if unusual_activity_sample_new_struct:
                for sample_item_new in unusual_activity_sample_new_struct:
                    if not isinstance(sample_item_new, dict): continue
                    # Map new structure fields to the structure expected by `derived_samples`
                    derived_samples.append({
                        "date": sample_item_new.get("date", ""),
                        "amount": sample_item_new.get("amount", 0),
                        "type": sample_item_new.get("transactionType", sample_item_new.get("description","N/A")), # Or specific type field
                        "description": sample_item_new.get("description", ""),
                        "account": str(sample_item_new.get("accountKey", ""))
                    })
                if derived_samples:
                     self.warnings.append(f"Derived {len(derived_samples)} unusual activity samples from case_data.transactions.unusualActivitySample.")

            # Attempt 2: If no samples from new structure, try to derive from `excel_data.transaction_summary`.
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
        # Note: case_number, alert_info, subjects, account_info are already transformed/set up
        # by their respective validate_* methods to be in the format fill_missing_data expects.

        # Get review_period from the new structure and map it for combined_data
        case_info_data = self.case_data.get("caseInfo", {})
        review_period_new_struct = case_info_data.get("reviewPeriod", {})
        review_period_for_combined = {
            "start": review_period_new_struct.get("startDate", ""),
            "end": review_period_new_struct.get("endDate", "")
        }

        combined_data = {
            "case_number": self.case_data.get("case_number", ""), # Already set by validate_case_number
            "alert_info": self.case_data.get("alert_info", []),   # Already set/transformed by validate_alert_info
            "subjects": self.case_data.get("subjects", []),     # Already set/transformed by validate_subjects
            "account_info": self.case_data.get("account_info", {}), # Already set/transformed by validate_account_info
            "prior_cases": self.case_data.get('priorSars', []), # New path
            "database_searches": self.case_data.get('databaseSearches', {}), # New path
            "review_period": review_period_for_combined # Mapped from new structure
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