"""
Data validator for validating extracted data
"""
from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime
from backend.utils.sar_extraction_utils import extract_case_number, extract_subjects

from backend.utils.logger import get_logger

logger = get_logger(__name__)

class DataValidator:
    """Validates extracted data and handles missing information"""
    
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
        
        # Check format (assuming standard format is letters followed by numbers)
        if not re.match(r"^[A-Z]+\d+$", case_number):
            self.validation_errors.append(f"Case number format is invalid: {case_number}")
            return False
        
        return True
    
    def validate_alert_info(self) -> bool:
        """
        Validate alert information
        
        Returns:
            bool: True if valid, False otherwise
        """
        alert_info = self.case_data.get("alert_info", {})
        is_valid = True
        
        # Check required fields
        if not alert_info.get("alert_id", ""):
            self.missing_required.append("Alert ID is missing")
            is_valid = False
        
        # Check review period format
        review_period = alert_info.get("review_period", {})
        start_date = review_period.get("start", "")
        end_date = review_period.get("end", "")
        
        if not start_date or not end_date:
            self.warnings.append("Review period is incomplete")
        else:
            # Check date format
            date_pattern = r"^\d{1,2}/\d{1,2}/\d{2,4}$"
            if not re.match(date_pattern, start_date):
                self.validation_errors.append(f"Review period start date format is invalid: {start_date}")
                is_valid = False
            
            if not re.match(date_pattern, end_date):
                self.validation_errors.append(f"Review period end date format is invalid: {end_date}")
                is_valid = False
        
        return is_valid
    
    def validate_subjects(self) -> bool:
        """
        Validate subject information
        
        Returns:
            bool: True if valid, False otherwise
        """
        subjects = self.case_data.get("subjects", [])
        is_valid = True
        
        if not subjects:
            self.missing_required.append("Subject information is missing")
            return False
        
        # Check for primary subject
        has_primary = any(subject.get("is_primary", False) for subject in subjects)
        if not has_primary:
            self.warnings.append("No primary subject identified")
        
        # Check required fields for each subject
        for i, subject in enumerate(subjects):
            if not subject.get("name", ""):
                self.missing_required.append(f"Subject #{i+1} name is missing")
                is_valid = False
        
        return is_valid
    
    def validate_account_info(self) -> bool:
        """
        Validate account information
        
        Returns:
            bool: True if valid, False otherwise
        """
        account_info = self.case_data.get("account_info", {})
        is_valid = True
        
        # Check required fields
        if not account_info.get("account_number", ""):
            self.missing_required.append("Account number is missing")
            is_valid = False
        
        if not account_info.get("account_type", ""):
            self.warnings.append("Account type is missing")
        
        # Check date formats
        date_fields = ["open_date", "close_date"]
        date_pattern = r"^\d{1,2}/\d{1,2}/\d{2,4}$"
        
        for field in date_fields:
            value = account_info.get(field, "")
            if value and not re.match(date_pattern, value):
                self.validation_errors.append(f"Account {field} format is invalid: {value}")
                is_valid = False
        
        return is_valid
    
    def validate_activity_summary(self) -> bool:
        """
        Validate activity summary
        
        Returns:
            bool: True if valid, False otherwise
        """
        activity_summary = self.excel_data.get("activity_summary", {})
        is_valid = True
        
        # Check for total amount
        if "total_amount" not in activity_summary:
            self.warnings.append("Activity total amount is missing")
        elif activity_summary["total_amount"] <= 0:
            self.warnings.append("Activity total amount is zero or negative")
        
        # Check date ranges
        start_date = activity_summary.get("start_date")
        end_date = activity_summary.get("end_date")
        
        if not start_date or not end_date:
            self.warnings.append("Activity date range is incomplete")
        
        # Check transaction types
        if not activity_summary.get("transaction_types"):
            self.warnings.append("Transaction types are missing")
        
        return is_valid
    
    def validate_unusual_activity(self) -> bool:
        """
        Validate unusual activity
        
        Returns:
            bool: True if valid, False otherwise
        """
        unusual_activity = self.excel_data.get("unusual_activity", {})
        is_valid = True
        
        # Check for samples
        samples = unusual_activity.get("samples", [])
        if not samples:
            self.warnings.append("No unusual activity samples found")
        else:
            # Check sample completeness
            for i, sample in enumerate(samples):
                if "date" not in sample or not sample["date"]:
                    self.warnings.append(f"Sample #{i+1} is missing transaction date")
                
                if "amount" not in sample or not sample["amount"]:
                    self.warnings.append(f"Sample #{i+1} is missing transaction amount")
        
        return is_valid
    
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all extracted data
        
        Returns:
            Tuple: (is_valid, errors, warnings)
        """
        is_valid = True
        
        # Reset validation lists
        self.validation_errors = []
        self.missing_required = []
        self.warnings = []
        
        # Validate individual components
        if not self.validate_case_number():
            is_valid = False
        
        if not self.validate_alert_info():
            is_valid = False
        
        if not self.validate_subjects():
            is_valid = False
        
        if not self.validate_account_info():
            is_valid = False
        
        if not self.validate_activity_summary():
            # This doesn't invalidate the overall data, just adds warnings
            pass
        
        if not self.validate_unusual_activity():
            # This doesn't invalidate the overall data, just adds warnings
            pass
        
        # Combine errors
        errors = self.validation_errors + self.missing_required
        
        return is_valid, errors, self.warnings
    
    def fill_missing_data(self) -> Dict[str, Any]:
        """
        Fill in missing data where possible
        
        Returns:
            Dict: Combined and validated data
        """
        combined_data = {
            "case_number": self.case_data.get("case_number", ""),
            "alert_info": self.case_data.get("alert_info", {}),
            "subjects": self.case_data.get("subjects", []),
            "account_info": self.case_data.get("account_info", {}),
            "prior_cases": self.case_data.get("prior_cases", []),
            "database_searches": self.case_data.get("database_searches", {}),
            "activity_summary": self.excel_data.get("activity_summary", {}),
            "unusual_activity": self.excel_data.get("unusual_activity", {}),
            "cta_sample": self.excel_data.get("cta_sample", {}),
            "bip_sample": self.excel_data.get("bip_sample", {}),
            "transaction_summary": self.excel_data.get("transaction_summary", {}),
            "account_summaries": self.excel_data.get("account_summaries", {}),
            "inter_account_transfers": self.excel_data.get("inter_account_transfers", [])
        }
        
        # Fill missing review period from activity summary dates if available
        if not combined_data["alert_info"].get("review_period", {}).get("start") and combined_data["activity_summary"].get("start_date"):
            if "review_period" not in combined_data["alert_info"]:
                combined_data["alert_info"]["review_period"] = {}
            combined_data["alert_info"]["review_period"]["start"] = combined_data["activity_summary"]["start_date"]
        
        if not combined_data["alert_info"].get("review_period", {}).get("end") and combined_data["activity_summary"].get("end_date"):
            if "review_period" not in combined_data["alert_info"]:
                combined_data["alert_info"]["review_period"] = {}
            combined_data["alert_info"]["review_period"]["end"] = combined_data["activity_summary"]["end_date"]
        
        # Ensure primary subject exists
        if combined_data["subjects"] and not any(subject.get("is_primary") for subject in combined_data["subjects"]):
            combined_data["subjects"][0]["is_primary"] = True
            logger.warning(f"No primary subject found. Setting {combined_data['subjects'][0]['name']} as primary.")
        
        # If account number missing from case data but available in file name, extract it
        if not combined_data["account_info"].get("account_number") and combined_data["case_number"]:
            # Look for account number in any sample data
            for sample in combined_data["unusual_activity"].get("samples", []):
                if "account" in sample:
                    combined_data["account_info"]["account_number"] = sample["account"]
                    break
        
        return combined_data