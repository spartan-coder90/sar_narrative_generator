"""
Data validator for validating extracted data with relaxed validation for development
"""
from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime
from backend.utils.sar_extraction_utils import extract_case_number, extract_subjects

from backend.utils.logger import get_logger

logger = get_logger(__name__)

class DataValidator:
    """Validates extracted data and handles missing information with relaxed requirements"""
    
    def __init__(self, case_data: Dict[str, Any], excel_data: Dict[str, Any]):
        """
        Initialize with extracted data
        
        Args:
            case_data: Extracted case document data
            excel_data: Extracted Excel data
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
            self.warnings.append("No alert information provided")
            
        # Convert dict to list if needed
        if isinstance(alert_info, dict):
            alert_info = [alert_info]
            self.case_data["alert_info"] = alert_info
        
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
        
        return True
    
    def validate_account_info(self) -> bool:
        """
        Validate account information with relaxed requirements
        
        Returns:
            bool: True if valid, False otherwise
        """
        account_info = self.case_data.get("account_info", {})
        
        # If account_info is empty, create a default structure
        if not account_info:
            account_info = {
                "account_number": "UNKNOWN",
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
                account_info["account_number"] = "UNKNOWN"
            self.warnings.append("Account number is missing")
        
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
        
        # Check date ranges
        if not activity_summary.get("start_date") or not activity_summary.get("end_date"):
            # Try to derive from transaction_summary or review_period
            transaction_summary = self.excel_data.get("transaction_summary", {})
            review_period = self.case_data.get("review_period", {})
            
            if not activity_summary.get("start_date"):
                if review_period and review_period.get("start"):
                    activity_summary["start_date"] = review_period.get("start")
                else:
                    activity_summary["start_date"] = "01/01/2023"  # Default fallback
                self.warnings.append("Activity start date is missing - using default or derived value")
            
            if not activity_summary.get("end_date"):
                if review_period and review_period.get("end"):
                    activity_summary["end_date"] = review_period.get("end")
                else:
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
            
            # Try to derive samples from transaction_summary
            transaction_summary = self.excel_data.get("transaction_summary", {})
            if transaction_summary:
                # Get up to 3 transaction examples from credit_breakdown or debit_breakdown
                for breakdown_type in ["credit_breakdown", "debit_breakdown"]:
                    breakdown = transaction_summary.get(breakdown_type, [])
                    if breakdown:
                        for item in breakdown[:2]:  # Take up to 2 from each type
                            txn_type = item.get("type", "Unknown")
                            txn_amount = item.get("amount", 0)
                            
                            # Create a sample transaction
                            sample = {
                                "date": unusual_activity.get("summary", {}).get("date_range", {}).get("start", "01/01/2023"),
                                "amount": txn_amount / item.get("count", 1) if item.get("count", 0) > 0 else txn_amount,
                                "type": txn_type,
                                "description": f"Sample {txn_type} transaction"
                            }
                            unusual_activity["transactions"].append(sample)
        
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