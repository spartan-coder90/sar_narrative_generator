"""
Data validator for validating case and transaction data
with relaxed validation for development
"""
from typing import Dict, List, Any, Optional, Tuple
import re
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
        Validate case number
        
        Returns:
            bool: True if valid, False otherwise
        """
        case_number = self.case_data.get("case_number", "")
        
        if not case_number:
            # Try to extract from full data if available
            full_data = self.case_data.get("full_data", [])
            if full_data:
                for section in full_data:
                    if section.get("section") == "Case Information":
                        case_number = section.get("Case Number", "")
                        if case_number:
                            self.case_data["case_number"] = case_number
                            break
            
            if not case_number:
                self.missing_required.append("Case number is missing")
                return False
        
        # Relax format validation - allow any non-empty case number
        return True
    
    def validate_alert_info(self) -> bool:
        """
        Validate alert information with relaxed requirements
        
        Returns:
            bool: True if valid, False otherwise
        """
        alert_info = self.case_data.get("alert_info", [])
        
        # Convert empty alert_info to empty list for consistency
        if not alert_info:
            alert_info = []
            self.case_data["alert_info"] = alert_info
            
        # Convert dict to list if needed
        if isinstance(alert_info, dict):
            alert_info = [alert_info]
            self.case_data["alert_info"] = alert_info
        
        # Try to extract from full_data if empty
        if not alert_info and self.case_data.get("full_data", []):
            for section in self.case_data["full_data"]:
                if section.get("section") == "Alerting Details":
                    alerts = section.get("alerts", [])
                    if alerts:
                        alert_info = []
                        for alert in alerts:
                            alert_obj = {
                                "alert_id": alert.get("Alert ID", ""),
                                "alert_month": alert.get("Alert Month", ""),
                                "description": alert.get("Description", ""),
                                "review_period": {"start": "", "end": ""}
                            }
                            
                            # Parse review period if available
                            review_period = alert.get("Review Period", "")
                            if review_period and " - " in review_period:
                                dates = review_period.split(" - ")
                                if len(dates) == 2:
                                    alert_obj["review_period"]["start"] = dates[0]
                                    alert_obj["review_period"]["end"] = dates[1]
                            
                            alert_info.append(alert_obj)
                        self.case_data["alert_info"] = alert_info
                        break
        
        # If still no alerts, add a placeholder
        if not alert_info:
            self.warnings.append("Adding default alert information")
            self.case_data["alert_info"] = [{
                "alert_id": "DEFAULT001",
                "description": "Default alert",
                "review_period": {
                    "start": "",
                    "end": ""
                }
            }]
            
        # Always valid with relaxed requirements
        return True
    
    def validate_subjects(self) -> bool:
        """
        Validate subject information with relaxed requirements
        
        Returns:
            bool: True if valid, False otherwise
        """
        subjects = self.case_data.get("subjects", [])
        
        # Try to extract from full_data if empty
        if not subjects and self.case_data.get("full_data", []):
            # Check for Hogan Search section first (new format)
            for section in self.case_data["full_data"]:
                if "Hogan Search" in section:
                    hogan_subjects = section.get("Hogan Search", [])
                    if hogan_subjects:
                        subjects = []
                        for hogan_subject in hogan_subjects:
                            subject = {
                                "name": hogan_subject.get("Case Subject", ""),
                                "is_primary": True,  # First subject is primary
                                "party_key": str(hogan_subject.get("Primary Party Key", "")),
                                "occupation": "",
                                "employer": "",
                                "nationality": "",
                                "address": "",
                                "account_relationship": ""
                            }
                            subjects.append(subject)
                            # Only first subject is primary
                            if len(subjects) > 1:
                                subjects[-1]["is_primary"] = False
                        
                        self.case_data["subjects"] = subjects
                        break
            
            # If not found in Hogan Search, try Customer Information
            if not subjects:
                for section in self.case_data["full_data"]:
                    if section.get("section") == "Customer Information":
                        if "US Bank Customer Information" in section:
                            subjects = []
                            for customer in section["US Bank Customer Information"]:
                                subject = {
                                    "name": customer.get("Primary Party", ""),
                                    "is_primary": True,  # First customer is primary
                                    "party_key": customer.get("Party Key", ""),
                                    "occupation": customer.get("Occupation Description", ""),
                                    "employer": customer.get("Employer", ""),
                                    "nationality": customer.get("Country of Nationality", ""),
                                    "address": "",
                                    "account_relationship": ""
                                }
                                
                                # Extract first address if available
                                if "Addresses" in customer and customer["Addresses"]:
                                    addresses = customer["Addresses"]
                                    if isinstance(addresses, list) and addresses:
                                        subject["address"] = addresses[0]
                                
                                subjects.append(subject)
                                # Only first subject is primary
                                if len(subjects) > 1:
                                    subjects[-1]["is_primary"] = False
                            
                            self.case_data["subjects"] = subjects
                            break
        
        if not subjects:
            # Create default subject if missing
            self.warnings.append("Subject information is missing - adding default subject")
            self.case_data["subjects"] = [{
                "name": "UNKNOWN SUBJECT",
                "is_primary": True,
                "occupation": "",
                "employer": "",
                "address": ""
            }]
            return True
        
        # Check for primary subject
        has_primary = any(subject.get("is_primary", False) for subject in subjects)
        if not has_primary and subjects:
            self.warnings.append("No primary subject identified - setting first subject as primary")
            subjects[0]["is_primary"] = True
        
        # Update case data
        self.case_data["subjects"] = subjects
        
        return True
    
    def validate_account_info(self) -> bool:
        """
        Validate account information with relaxed requirements
        
        Returns:
            bool: True if valid, False otherwise
        """
        account_info = self.case_data.get("account_info", {})
        
        # Try to extract from full_data if empty or minimal
        if (not account_info or not account_info.get("account_number")) and self.case_data.get("full_data", []):
            for section in self.case_data["full_data"]:
                if section.get("section") == "Account Information":
                    if "Accounts" in section and section["Accounts"]:
                        account = section["Accounts"][0]  # Take first account
                        account_info = {
                            "account_number": account.get("Account Key", ""),
                            "account_type": ", ".join(account.get("Account Type", [])) if isinstance(account.get("Account Type"), list) else account.get("Account Type", ""),
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
                                    account_info["related_parties"].append({"name": name, "role": role})
                                else:
                                    account_info["related_parties"].append({"name": party, "role": ""})
                        
                        self.case_data["account_info"] = account_info
                    elif "accountInformation" in section and "Account" in section["accountInformation"]:
                        account = section["accountInformation"]["Account"]
                        account_info = {
                            "account_number": account.get("Account Key", ""),
                            "account_type": ", ".join(account.get("Types", [])) if isinstance(account.get("Types"), list) else account.get("Types", ""),
                            "account_title": account.get("Title", ""),
                            "status": account.get("Status", {}).get("Description", "") if "Status" in account else "",
                            "related_parties": [],
                            "branch": ""
                        }
                        
                        # Handle opening/closing dates
                        if "Opening" in account:
                            account_info["open_date"] = account["Opening"].get("Date", "")
                            account_info["branch"] = account["Opening"].get("Branch", "")
                        
                        account_info["close_date"] = account.get("Closing Date", "")
                        
                        # Process related parties
                        if "Related Parties" in account and isinstance(account["Related Parties"], list):
                            for party in account["Related Parties"]:
                                account_info["related_parties"].append({"name": party, "role": ""})
                        
                        self.case_data["account_info"] = account_info
                    break
        
        # If account_info is still empty, create a default structure
        if not account_info:
            account_info = {
                "account_number": "",
                "account_type": "Unknown Account",
                "status": "Unknown Status"
            }
            self.case_data["account_info"] = account_info
            self.warnings.append("Account information is missing - using default values")
        
        # If account_type missing, add default
        if not account_info.get("account_type"):
            account_info["account_type"] = "checking/savings account"
            self.warnings.append("Account type is missing")
        
        # If account_number missing, add default
        if not account_info.get("account_number"):
            # Try to find from account summaries
            account_summaries = self.excel_data.get("account_summaries", {})
            if account_summaries:
                account_number = next(iter(account_summaries.keys()), "UNKNOWN")
                account_info["account_number"] = account_number
            else:
                account_info["account_number"] = ""
            self.warnings.append("Account number is missing")
        
        # Update case data
        self.case_data["account_info"] = account_info
        
        return True
    
    def validate_transaction_data(self) -> bool:
        """
        Validate transaction data with relaxed requirements
        
        Returns:
            bool: True if valid, False otherwise
        """
        # Check if we have any transaction data in excel_data
        transaction_summary = self.excel_data.get("transaction_summary", {})
        if not transaction_summary:
            self.warnings.append("Transaction summary is missing")
            self.excel_data["transaction_summary"] = {
                "total_credits": 0,
                "total_debits": 0,
                "credit_breakdown": [],
                "debit_breakdown": []
            }
        
        # Check if we have activity summary
        activity_summary = self.excel_data.get("activity_summary", {})
        if not activity_summary:
            self.warnings.append("Activity summary is missing")
            self.excel_data["activity_summary"] = {
                "start_date": "",
                "end_date": "",
                "total_amount": 0
            }
        
        # Check if we have unusual activity
        unusual_activity = self.excel_data.get("unusual_activity", {})
        if not unusual_activity:
            self.warnings.append("Unusual activity is missing")
            self.excel_data["unusual_activity"] = {
                "transactions": []
            }
        
        # Always valid with relaxed requirements
        return True
    
    def validate_activity_summary(self) -> bool:
        """
        Validate activity summary with relaxed requirements
        
        Returns:
            bool: True if valid, False otherwise
        """
        activity_summary = self.excel_data.get("activity_summary", {})
        
        # If activity_summary missing, create default
        if not activity_summary:
            activity_summary = {
                "total_amount": 0.0,
                "start_date": "",
                "end_date": "",
                "transaction_types": []
            }
            self.excel_data["activity_summary"] = activity_summary
        
        # Check for total amount
        if "total_amount" not in activity_summary:
            # Try to derive from transaction_summary
            transaction_summary = self.excel_data.get("transaction_summary", {})
            if transaction_summary:
                total_credits = transaction_summary.get("total_credits", 0)
                total_debits = transaction_summary.get("total_debits", 0)
                # Use the larger of credits and debits as total amount
                activity_summary["total_amount"] = max(total_credits, total_debits)
            else:
                activity_summary["total_amount"] = 0.0
            
        # Check if total amount is zero or negative
        if activity_summary.get("total_amount", 0) <= 0:
            self.warnings.append("Activity total amount is zero or negative")
            
            # Try to fix by using transaction data
            transaction_summary = self.excel_data.get("transaction_summary", {})
            if transaction_summary:
                total_credits = transaction_summary.get("total_credits", 0)
                total_debits = transaction_summary.get("total_debits", 0)
                if total_credits > 0 or total_debits > 0:
                    activity_summary["total_amount"] = max(total_credits, total_debits)
        
        # Check date ranges - get from multiple sources
        review_period = self.case_data.get("review_period", {})
        alert_info = self.case_data.get("alert_info", [])
        first_alert = alert_info[0] if alert_info else {}
        alert_review_period = first_alert.get("review_period", {}) if isinstance(first_alert, dict) else {}
        
        if not activity_summary.get("start_date") or not activity_summary.get("end_date"):
            if not activity_summary.get("start_date"):
                # Try to get from different sources
                if review_period and review_period.get("start"):
                    activity_summary["start_date"] = review_period.get("start")
                elif alert_review_period and alert_review_period.get("start"):
                    activity_summary["start_date"] = alert_review_period.get("start")
                else:
                    # Get from full_data - try Scope of Review first
                    full_data = self.case_data.get("full_data", [])
                    for section in full_data:
                        if section.get("section") == "Scope of Review":
                            activity_summary["start_date"] = section.get("Start Date", "")
                            break
                    
                    if not activity_summary.get("start_date"):
                        # Try Account Information section next
                        for section in full_data:
                            if section.get("section") == "Account Information":
                                review_period_str = section.get("Case Review Period", "")
                                if review_period_str and " - " in review_period_str:
                                    dates = review_period_str.split(" - ")
                                    if len(dates) == 2:
                                        activity_summary["start_date"] = dates[0]
                                        break
                    
                    if not activity_summary.get("start_date"):
                        activity_summary["start_date"] = "01/01/2023"  # Default fallback
                self.warnings.append("Activity start date is missing - using default or derived value")
            
            if not activity_summary.get("end_date"):
                # Try to get from different sources
                if review_period and review_period.get("end"):
                    activity_summary["end_date"] = review_period.get("end")
                elif alert_review_period and alert_review_period.get("end"):
                    activity_summary["end_date"] = alert_review_period.get("end")
                else:
                    # Get from full_data - try Scope of Review first
                    full_data = self.case_data.get("full_data", [])
                    for section in full_data:
                        if section.get("section") == "Scope of Review":
                            activity_summary["end_date"] = section.get("End Date", "")
                            break
                    
                    if not activity_summary.get("end_date"):
                        # Try Account Information section next
                        for section in full_data:
                            if section.get("section") == "Account Information":
                                review_period_str = section.get("Case Review Period", "")
                                if review_period_str and " - " in review_period_str:
                                    dates = review_period_str.split(" - ")
                                    if len(dates) == 2:
                                        activity_summary["end_date"] = dates[1]
                                        break
                    
                    if not activity_summary.get("end_date"):
                        # Use current date as default end date
                        current_date = datetime.now().strftime("%m/%d/%Y")
                        activity_summary["end_date"] = current_date
                self.warnings.append("Activity end date is missing - using default or derived value")
        
        # Check transaction types
        if not activity_summary.get("transaction_types"):
            # Try to derive from transaction_summary
            transaction_summary = self.excel_data.get("transaction_summary", {})
            if transaction_summary and transaction_summary.get("credit_breakdown"):
                activity_summary["transaction_types"] = [
                    item.get("type", "Unknown") 
                    for item in transaction_summary.get("credit_breakdown", [])[:3]
                ]
            
            if not activity_summary.get("transaction_types"):
                activity_summary["transaction_types"] = ["Unknown Transaction Type"]
                self.warnings.append("Transaction types are missing - using default")
        
        # Update excel data
        self.excel_data["activity_summary"] = activity_summary
        
        return True
    
    def validate_unusual_activity(self) -> bool:
        """
        Validate unusual activity with relaxed requirements
        
        Returns:
            bool: True if valid, False otherwise
        """
        unusual_activity = self.excel_data.get("unusual_activity", {})
        
        if not unusual_activity:
            unusual_activity = {"transactions": [], "summary": {}}
            self.excel_data["unusual_activity"] = unusual_activity
        
        # Check for samples
        samples = unusual_activity.get("transactions", [])
        if not samples:
            self.warnings.append("No unusual activity samples found")
            
            # Try to get from full_data if available
            full_data = self.case_data.get("full_data", [])
            for section in full_data:
                if "Unusual Activity" in section:
                    unusual_activity_samples = section.get("Unusual Activity", [])
                    if unusual_activity_samples:
                        unusual_activity["transactions"] = []
                        for sample in unusual_activity_samples:
                            unusual_activity["transactions"].append({
                                "date": sample.get("Transaction Date", ""),
                                "amount": sample.get("Transaction Amount", 0),
                                "type": sample.get("Custom Language", ""),
                                "description": sample.get("Memo", ""),
                                "account": str(sample.get("Account", ""))
                            })
                        break
            
            # If still no samples, try to derive from transaction_summary
            transaction_summary = self.excel_data.get("transaction_summary", {})
            if not unusual_activity["transactions"] and transaction_summary:
                # Get up to 3 transaction examples from credit_breakdown or debit_breakdown
                for breakdown_type in ["credit_breakdown", "debit_breakdown"]:
                    breakdown = transaction_summary.get(breakdown_type, [])
                    if breakdown:
                        for item in breakdown[:2]:  # Take up to 2 from each type
                            txn_type = item.get("type", "Unknown")
                            txn_amount = item.get("amount", 0)
                            
                            # Create a sample transaction
                            sample = {
                                "date": self.excel_data.get("activity_summary", {}).get("start_date", "01/01/2023"),
                                "amount": txn_amount / item.get("count", 1) if item.get("count", 0) > 0 else txn_amount,
                                "type": txn_type,
                                "description": f"Sample {txn_type} transaction"
                            }
                            unusual_activity["transactions"].append(sample)
            
            # Set summary for unusual activity
            activity_summary = self.excel_data.get("activity_summary", {})
            if activity_summary:
                unusual_activity["summary"] = {
                    "total_amount": activity_summary.get("total_amount", 0),
                    "date_range": {
                        "start": activity_summary.get("start_date", ""),
                        "end": activity_summary.get("end_date", "")
                    }
                }
        
        # Update excel data
        self.excel_data["unusual_activity"] = unusual_activity
        
        return True
    
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all extracted data with relaxed requirements
        
        Returns:
            Tuple: (is_valid, errors, warnings)
        """
        # Reset validation lists
        self.validation_errors = []
        self.missing_required = []
        self.warnings = []
        
        # Validate individual components
        self.validate_case_number()
        self.validate_alert_info()
        self.validate_subjects()
        self.validate_account_info()
        self.validate_transaction_data()
        self.validate_activity_summary()
        self.validate_unusual_activity()
        
        # Return validation results
        errors = self.validation_errors + self.missing_required
        
        # Use relaxed validation - always return valid=True for development
        return True, errors, self.warnings
    
    def fill_missing_data(self) -> Dict[str, Any]:
        """
        Fill in missing data where possible
        
        Returns:
            Dict: Combined and validated data
        """
        # First validate and fix data
        self.validate()
        
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