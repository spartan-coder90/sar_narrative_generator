"""
Test data processor for validating SAR data and handling edge cases
"""
import re
import json
from typing import Dict, List, Any, Tuple
from datetime import datetime

class TestDataProcessor:
    """
    Processes test case data to validate it and prepare for narrative generation
    """
    
    def __init__(self, case_data: Dict[str, Any], excel_data: Dict[str, Any]):
        """
        Initialize with case and Excel data
        
        Args:
            case_data: Extracted case document data
            excel_data: Extracted Excel data
        """
        self.case_data = case_data
        self.excel_data = excel_data
        self.errors = []
        self.warnings = []
        self.combined_data = {}
        
    def validate_required_fields(self) -> bool:
        """
        Validate that all required fields are present
        
        Returns:
            bool: True if all required fields are present, False otherwise
        """
        required_fields = {
            "case_data": ["case_number", "subjects"],
            "excel_data": ["activity_summary"],
            "subject": ["name"],
            "account_info": ["account_number"]
        }
        
        valid = True
        
        # Check case data fields
        for field in required_fields["case_data"]:
            if field not in self.case_data or not self.case_data[field]:
                self.errors.append(f"Missing required field in case data: {field}")
                valid = False
        
        # Check Excel data fields
        for field in required_fields["excel_data"]:
            if field not in self.excel_data or not self.excel_data[field]:
                self.errors.append(f"Missing required field in Excel data: {field}")
                valid = False
        
        # Check subject fields
        for subject in self.case_data.get("subjects", []):
            for field in required_fields["subject"]:
                if field not in subject or not subject[field]:
                    self.errors.append(f"Missing required field in subject data: {field}")
                    valid = False
        
        # Check account info fields
        account_info = self.case_data.get("account_info", {})
        for field in required_fields["account_info"]:
            if field not in account_info or not account_info[field]:
                self.errors.append(f"Missing required field in account info: {field}")
                valid = False
        
        return valid
    
    def validate_date_formats(self) -> bool:
        """
        Validate that all dates are in a valid format or can be converted
        
        Returns:
            bool: True if all dates are valid, False otherwise
        """
        valid = True
        date_fields = {
            "activity_summary": ["start_date", "end_date"],
            "account_info": ["open_date", "close_date"],
            "alert_info": ["review_period.start", "review_period.end"]
        }
        
        # Helper function to check if a date is valid
        def is_valid_date(date_str):
            if not date_str:
                return True  # Empty date is considered valid
            
            date_formats = [
                '%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d/%m/%Y', '%Y/%m/%d',
                '%m/%d/%y', '%d/%m/%y', '%y-%m-%d'
            ]
            
            for fmt in date_formats:
                try:
                    datetime.strptime(date_str, fmt)
                    return True
                except (ValueError, TypeError):
                    pass
            
            return False
        
        # Check activity summary dates
        activity_summary = self.excel_data.get("activity_summary", {})
        for field in date_fields["activity_summary"]:
            if field in activity_summary and not is_valid_date(activity_summary[field]):
                self.errors.append(f"Invalid date format in activity summary: {field} = {activity_summary[field]}")
                valid = False
        
        # Check account info dates
        account_info = self.case_data.get("account_info", {})
        for field in date_fields["account_info"]:
            if field in account_info and not is_valid_date(account_info[field]):
                self.errors.append(f"Invalid date format in account info: {field} = {account_info[field]}")
                valid = False
        
        # Check alert info dates
        alert_info = self.case_data.get("alert_info", {})
        if isinstance(alert_info, list) and alert_info:
            alert_info = alert_info[0]  # Use first alert
        
        for field in date_fields["alert_info"]:
            parts = field.split('.')
            if len(parts) == 2:
                parent, child = parts
                if parent in alert_info and isinstance(alert_info[parent], dict) and child in alert_info[parent]:
                    if not is_valid_date(alert_info[parent][child]):
                        self.errors.append(f"Invalid date format in alert info: {field} = {alert_info[parent][child]}")
                        valid = False
        
        return valid
    
    def validate_numeric_fields(self) -> bool:
        """
        Validate that all numeric fields are valid
        
        Returns:
            bool: True if all numeric fields are valid, False otherwise
        """
        valid = True
        numeric_fields = {
            "activity_summary": ["total_amount"],
            "transaction_summary": ["total_credits", "total_debits"]
        }
        
        # Helper function to check if a value is numeric or can be converted
        def is_numeric(value):
            if value is None:
                return True  # None is considered valid
            
            if isinstance(value, (int, float)):
                return True
            
            if isinstance(value, str):
                # Remove $ and commas
                clean_value = value.replace('$', '').replace(',', '')
                try:
                    float(clean_value)
                    return True
                except ValueError:
                    return False
            
            return False
        
        # Check activity summary numeric fields
        activity_summary = self.excel_data.get("activity_summary", {})
        for field in numeric_fields["activity_summary"]:
            if field in activity_summary and not is_numeric(activity_summary[field]):
                self.errors.append(f"Invalid numeric value in activity summary: {field} = {activity_summary[field]}")
                valid = False
        
        # Check transaction summary numeric fields
        transaction_summary = self.excel_data.get("transaction_summary", {})
        for field in numeric_fields["transaction_summary"]:
            if field in transaction_summary and not is_numeric(transaction_summary[field]):
                self.errors.append(f"Invalid numeric value in transaction summary: {field} = {transaction_summary[field]}")
                valid = False
        
        return valid
    
    def check_for_inconsistencies(self) -> bool:
        """
        Check for inconsistencies in the data
        
        Returns:
            bool: True if data is consistent, False otherwise
        """
        consistent = True
        
        # Check account numbers
        account_numbers = set()
        
        # Add main account number
        account_info = self.case_data.get("account_info", {})
        main_account = account_info.get("account_number")
        if main_account:
            account_numbers.add(main_account)
        
        # Add account numbers from accounts list
        for account in self.case_data.get("accounts", []):
            account_number = account.get("account_number")
            if account_number:
                account_numbers.add(account_number)
        
        # Check account numbers in transaction data
        account_summaries = self.excel_data.get("account_summaries", {})
        for account_number in account_summaries.keys():
            if account_number not in account_numbers:
                self.warnings.append(f"Transaction data includes account {account_number} not found in case data")
        
        # Check for date inconsistencies
        activity_summary = self.excel_data.get("activity_summary", {})
        start_date = activity_summary.get("start_date")
        end_date = activity_summary.get("end_date")
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%m/%d/%Y')
                end = datetime.strptime(end_date, '%m/%d/%Y')
                if start > end:
                    self.errors.append(f"Start date {start_date} is after end date {end_date}")
                    consistent = False
            except (ValueError, TypeError):
                # Date format validation is handled elsewhere
                pass
        
        return consistent
    
    def generate_test_data_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the test data
        
        Returns:
            Dict: Summary of test data
        """
        # Count sections
        sections = {
            "subjects": len(self.case_data.get("subjects", [])),
            "accounts": len(self.case_data.get("accounts", [])),
            "prior_cases": len(self.case_data.get("prior_cases", [])),
            "transactions": 0
        }
        
        # Count transactions
        unusual_activity = self.excel_data.get("unusual_activity", {})
        if unusual_activity and "transactions" in unusual_activity:
            sections["transactions"] = len(unusual_activity["transactions"])
        
        # Get total amount
        activity_summary = self.excel_data.get("activity_summary", {})
        total_amount = activity_summary.get("total_amount", 0)
        
        # Format as currency
        if isinstance(total_amount, str):
            total_amount = total_amount.replace('$', '').replace(',', '')
            try:
                total_amount = float(total_amount)
            except ValueError:
                total_amount = 0
        
        formatted_amount = "${:,.2f}".format(total_amount)
        
        # Get date range
        start_date = activity_summary.get("start_date", "")
        end_date = activity_summary.get("end_date", "")
        
        return {
            "case_number": self.case_data.get("case_number", ""),
            "sections": sections,
            "total_amount": formatted_amount,
            "date_range": f"{start_date} to {end_date}" if start_date and end_date else "N/A"
        }
    
    def process_data(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Process the test data
        
        Returns:
            Tuple: (is_valid, processed_data)
        """
        # Reset errors and warnings
        self.errors = []
        self.warnings = []
        
        # Validate data
        required_fields_valid = self.validate_required_fields()
        date_formats_valid = self.validate_date_formats()
        numeric_fields_valid = self.validate_numeric_fields()
        consistency_valid = self.check_for_inconsistencies()
        
        # Combine data
        self.combined_data = {
            "case_number": self.case_data.get("case_number", ""),
            "alert_info": self.case_data.get("alert_info", []),
            "subjects": self.case_data.get("subjects", []),
            "account_info": self.case_data.get("account_info", {}),
            "accounts": self.case_data.get("accounts", []),
            "prior_cases": self.case_data.get("prior_cases", []),
            "database_searches": self.case_data.get("database_searches", {}),
            "activity_summary": self.excel_data.get("activity_summary", {}),
            "unusual_activity": self.excel_data.get("unusual_activity", {}),
            "transaction_summary": self.excel_data.get("transaction_summary", {}),
            "account_summaries": self.excel_data.get("account_summaries", {}),
            "cta_sample": self.excel_data.get("cta_sample", {}),
            "bip_sample": self.excel_data.get("bip_sample", {}),
            "inter_account_transfers": self.excel_data.get("inter_account_transfers", []),
            "review_period": self.case_data.get("review_period", {})
        }
        
        # Determine validity
        is_valid = required_fields_valid and numeric_fields_valid and consistency_valid
        
        # Add summary information
        self.combined_data["test_summary"] = self.generate_test_data_summary()
        self.combined_data["validation"] = {
            "is_valid": is_valid,
            "errors": self.errors,
            "warnings": self.warnings
        }
        
        return is_valid, self.combined_data