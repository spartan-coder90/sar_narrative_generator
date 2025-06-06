"""
Module for processing transaction data from raw case information.

This module defines the `TransactionProcessor` class, which is responsible for
extracting, structuring, and calculating various transaction summaries from the
`full_data` section of a case object. These summaries are essential for
populating different parts of a SAR narrative and recommendation. The processor
handles aggregation of credits and debits, identifies counterparties, details
individual transactions, and samples unusual activities, CTA (Customer Transaction
Assessment), and BIP (Business Intelligence Profile) transactions.
It utilizes utility functions for data type conversions and date comparisons.
"""
from typing import Dict, List, Any, Optional
import re
from datetime import datetime
from backend.utils.logger import get_logger
from backend.utils.data_utils import to_float, to_int, compare_dates

logger = get_logger(__name__)

class TransactionProcessor:
    """
    Processes transaction data from case objects to calculate summaries for SAR narrative
    """
    
    def __init__(self, case_data: Dict[str, Any]):
        """
        Initialize with case data that contains transaction information
        
        Args:
            case_data: Case data containing transaction information
        """
        self.case_data = case_data
        self.transaction_data = {}
        
        # Extract transaction data from case data
        self._extract_transaction_data()
    
    def _extract_transaction_data(self):
        """
        Extract transaction data from case data
        """
        # Check if case data has full_data field
        if not self.case_data.get("full_data"):
            logger.warning("Case data does not contain full_data field")
            return
        
        # Build transaction data dictionary
        transactions = {}
        
        # Get review period dates
        scope_of_review = self._get_scope_of_review()
        transactions["scope_of_review"] = scope_of_review
        
        # Get case subjects
        subjects = self._get_case_subjects()
        transactions["subjects"] = subjects
        
        # Get activity summaries
        activity_summary = self._get_activity_summary()
        transactions["activity_summary"] = activity_summary
        
        # Get counterparties
        counterparties = self._get_counterparties()
        transactions["counterparties"] = counterparties
        
        # Get transaction details
        transaction_details = self._get_transaction_details()
        transactions["transactions"] = transaction_details
        
        # Get unusual activity
        unusual_activity = self._get_unusual_activity()
        transactions["unusual_activity"] = unusual_activity
        
        # Get CTA sample
        cta_sample = self._get_cta_sample()
        transactions["cta_sample"] = cta_sample
        
        # Get BIP sample
        bip_sample = self._get_bip_sample()
        transactions["bip_sample"] = bip_sample
        
        # Store the transaction data
        self.transaction_data = transactions

    def _initialize_summary_dict(self) -> Dict[str, Any]:
        """
        Initializes a dictionary with a common structure for credit/debit summaries.
        """
        return {
            "total_percent": 0,
            "total_amount": 0,
            "total_transactions": 0,
            "min_amount": float('inf'),
            "max_amount": 0,
            "earliest_date": None,
            "latest_date": None
        }

    def _initialize_transaction_group(self, for_counterparty: bool = False, for_details: bool = False, for_unusual: bool = False) -> Dict[str, Any]:
        """
        Initializes a dictionary for grouping transactions by type or party.
        Structure can vary slightly based on the context (activity, counterparty, details, unusual).
        """
        group = {
            "amount": 0,
            "count": 0,
        }
        if for_counterparty: # Used in _get_counterparties
            group["percent"] = 0
            group["min_amount"] = float('inf')
            group["max_amount"] = 0
            group["min_date"] = None
            group["max_date"] = None
        elif for_details: # Used in _get_transaction_details
            group["credits"] = {"amount": 0, "count": 0}
            group["debits"] = {"amount": 0, "count": 0}
            group["total"] = 0 # total amount for this group
            # 'count' here will be total transactions for this group
            group["examples"] = []
        elif for_unusual: # Used in _get_unusual_activity, _get_cta_sample, _get_bip_sample
            group["credits"] = {"amount": 0, "count": 0}
            group["debits"] = {"amount": 0, "count": 0}
            group["total"] = 0 # total amount for this group
            # 'count' here will be total transactions for this group
            group["earliest_date"] = None
            group["latest_date"] = None
            group["examples"] = []
        else: # Default for _get_activity_summary by_type
            group["percent"] = 0
            group["min_amount"] = float('inf')
            group["max_amount"] = 0
            group["min_date"] = None
            group["max_date"] = None
        return group
    
    def _get_scope_of_review(self) -> Dict[str, str]:
        """
        Get scope of review dates
        
        Returns:
            Dict: Scope of review dates
        """
        scope_of_review = {"start": "", "end": ""}
        
        # Try to find Scope of Review in full_data
        for section in self.case_data.get("full_data", []):
            if "Scope of Review" in section:
                scope = section.get("Scope of Review", {})
                if isinstance(scope, dict):
                    scope_of_review["start"] = scope.get("Start Date", "")
                    scope_of_review["end"] = scope.get("End Date", "")
                    return scope_of_review
        
        # If not found, check alternative locations
        for section in self.case_data.get("full_data", []):
            if "Case Review Period" in section:
                review_period = section.get("Case Review Period", "")
                if isinstance(review_period, str) and " - " in review_period:
                    dates = review_period.split(" - ")
                    if len(dates) == 2:
                        scope_of_review["start"] = dates[0]
                        scope_of_review["end"] = dates[1]
                        return scope_of_review
        
        return scope_of_review
    
    def _get_case_subjects(self) -> List[Dict[str, Any]]:
        """
        Get case subjects
        
        Returns:
            List[Dict]: Case subjects information
        """
        subjects = []
        
        # Try to find Hogan Search in full_data
        for section in self.case_data.get("full_data", []):
            if "Hogan Search" in section:
                hogan_search = section.get("Hogan Search", [])
                if isinstance(hogan_search, list):
                    for subject in hogan_search:
                        subjects.append({
                            "name": subject.get("Case Subject", ""),
                            "party_key": subject.get("Primary Party Key", ""),
                            "additional_search": subject.get("Was an additional demographic search in Hogan completed for this subject?", "")
                        })
                    
                    return subjects
        
        # If not found, try to use subjects from case_data
        case_subjects = self.case_data.get("subjects", [])
        if case_subjects:
            for subject in case_subjects:
                subjects.append({
                    "name": subject.get("name", ""),
                    "party_key": subject.get("party_key", ""),
                    "additional_info": {}
                })
        
        return subjects
    
    def _get_activity_summary(self) -> Dict[str, Any]:
        """
        Get activity summary data with calculations
        
        Returns:
            Dict: Activity summary data
        """
        activity_summary = {
            "accounts": {},
            "totals": {
                "credits": self._initialize_summary_dict(),
                "debits": self._initialize_summary_dict()
            }
        }
        
        # Try to find Activity Summary in full_data. This section typically contains aggregated
        # transaction data per account, broken down by credit and debit types.
        for section in self.case_data.get("full_data", []):
            if "Activity Summary" in section:
                summary_list = section.get("Activity Summary", []) # Data is usually a list of account summaries
                if isinstance(summary_list, list):
                    for account_summary_item in summary_list: # Each item represents one account's summary
                        account_num = str(account_summary_item.get("Account", "")) # Get account number
                        
                        # Initialize account entry if it's the first time seeing this account
                        if account_num not in activity_summary["accounts"]:
                            activity_summary["accounts"][account_num] = {
                                "credits": self._initialize_summary_dict(),
                                "debits": self._initialize_summary_dict()
                            }
                            # Add 'by_type' structure for credits and debits within this account
                            activity_summary["accounts"][account_num]["credits"]["by_type"] = {}
                            activity_summary["accounts"][account_num]["debits"]["by_type"] = {}
                        
                        # Process credits for this account
                        credits_data = account_summary_item.get("Credits", []) # Credits are usually a list
                        for credit_item in credits_data:
                            # Extract credit transaction details. Key names like "Total " (with space)
                            # are specific to the input data format.
                            custom_language = credit_item.get("Custom Language", "") # Type of credit
                            percent = to_float(credit_item.get("% of Credits", 0))
                            amount = to_float(credit_item.get("Total ", 0)) # Note the space in "Total "
                            count = to_int(credit_item.get("# Transactions ", 0)) # Note the space
                            min_amount_txn = to_float(credit_item.get("Min Credit Amt.", 0))
                            max_amount_txn = to_float(credit_item.get("Max Credit Amt.", 0))
                            min_date_txn = credit_item.get("Min Txn Date ", "") # Note the space
                            max_date_txn = credit_item.get("Max Txn Date ", "") # Note the space
                            
                            account_credits_summary = activity_summary["accounts"][account_num]["credits"]
                            # Initialize this credit type if not seen before for this account
                            if custom_language not in account_credits_summary["by_type"]:
                                account_credits_summary["by_type"][custom_language] = self._initialize_transaction_group()
                            
                            # Aggregate data for this specific credit type
                            type_data_agg = account_credits_summary["by_type"][custom_language]
                            type_data_agg["percent"] += percent
                            type_data_agg["amount"] += amount
                            type_data_agg["count"] += count
                            type_data_agg["min_amount"] = min(type_data_agg["min_amount"], min_amount_txn)
                            type_data_agg["max_amount"] = max(type_data_agg["max_amount"], max_amount_txn)
                            type_data_agg["min_date"] = compare_dates(min_date_txn, type_data_agg["min_date"], mode='earliest')
                            type_data_agg["max_date"] = compare_dates(max_date_txn, type_data_agg["max_date"], mode='latest')
                            
                            # Aggregate data for overall credits for this account
                            account_credits_summary["total_percent"] += percent
                            account_credits_summary["total_amount"] += amount
                            account_credits_summary["total_transactions"] += count
                            account_credits_summary["min_amount"] = min(account_credits_summary["min_amount"], min_amount_txn)
                            account_credits_summary["max_amount"] = max(account_credits_summary["max_amount"], max_amount_txn)
                            account_credits_summary["earliest_date"] = compare_dates(min_date_txn, account_credits_summary["earliest_date"], mode='earliest')
                            account_credits_summary["latest_date"] = compare_dates(max_date_txn, account_credits_summary["latest_date"], mode='latest')
                            
                            # Aggregate data for global credit totals across all accounts
                            global_credits_summary = activity_summary["totals"]["credits"]
                            global_credits_summary["total_percent"] += percent # Note: total_percent sum might exceed 100 if summing percentages from different base totals
                            global_credits_summary["total_amount"] += amount
                            global_credits_summary["total_transactions"] += count
                            global_credits_summary["min_amount"] = min(global_credits_summary["min_amount"], min_amount_txn)
                            global_credits_summary["max_amount"] = max(global_credits_summary["max_amount"], max_amount_txn)
                            global_credits_summary["earliest_date"] = compare_dates(min_date_txn, global_credits_summary["earliest_date"], mode='earliest')
                            global_credits_summary["latest_date"] = compare_dates(max_date_txn, global_credits_summary["latest_date"], mode='latest')
                        
                        # Process debits for this account (similar logic to credits)
                        debits_data = account_summary_item.get("Debits", [])
                        for debit_item in debits_data:
                            custom_language = debit_item.get("Custom Language", "")
                            percent = to_float(debit_item.get("% of Debits", 0))
                            amount = to_float(debit_item.get("Total ", 0))
                            count = to_int(debit_item.get("# Transactions ", 0))
                            min_amount_txn = to_float(debit_item.get("Min Debit Amt.", 0))
                            max_amount_txn = to_float(debit_item.get("Max Debit Amt.", 0))
                            min_date_txn = debit_item.get("Min Txn Date ", "")
                            max_date_txn = debit_item.get("Max Txn Date ", "")
                            
                            account_debits_summary = activity_summary["accounts"][account_num]["debits"]
                            if custom_language not in account_debits_summary["by_type"]:
                                account_debits_summary["by_type"][custom_language] = self._initialize_transaction_group()
                                
                            type_data_agg = account_debits_summary["by_type"][custom_language]
                            type_data_agg["percent"] += percent
                            type_data_agg["amount"] += amount
                            type_data_agg["count"] += count
                            type_data_agg["min_amount"] = min(type_data_agg["min_amount"], min_amount_txn)
                            type_data_agg["max_amount"] = max(type_data_agg["max_amount"], max_amount_txn)
                            type_data_agg["min_date"] = compare_dates(min_date_txn, type_data_agg["min_date"], mode='earliest')
                            type_data_agg["max_date"] = compare_dates(max_date_txn, type_data_agg["max_date"], mode='latest')
                            
                            account_debits_summary["total_percent"] += percent
                            account_debits_summary["total_amount"] += amount
                            account_debits_summary["total_transactions"] += count
                            account_debits_summary["min_amount"] = min(account_debits_summary["min_amount"], min_amount_txn)
                            account_debits_summary["max_amount"] = max(account_debits_summary["max_amount"], max_amount_txn)
                            account_debits_summary["earliest_date"] = compare_dates(min_date_txn, account_debits_summary["earliest_date"], mode='earliest')
                            account_debits_summary["latest_date"] = compare_dates(max_date_txn, account_debits_summary["latest_date"], mode='latest')
                            
                            global_debits_summary = activity_summary["totals"]["debits"]
                            global_debits_summary["total_percent"] += percent
                            global_debits_summary["total_amount"] += amount
                            global_debits_summary["total_transactions"] += count
                            global_debits_summary["min_amount"] = min(global_debits_summary["min_amount"], min_amount_txn)
                            global_debits_summary["max_amount"] = max(global_debits_summary["max_amount"], max_amount_txn)
                            global_debits_summary["earliest_date"] = compare_dates(min_date_txn, global_debits_summary["earliest_date"], mode='earliest')
                            global_debits_summary["latest_date"] = compare_dates(max_date_txn, global_debits_summary["latest_date"], mode='latest')
                    
                    # Clean up infinity values for min_amount
                    if activity_summary["totals"]["credits"]["min_amount"] == float('inf'):
                        activity_summary["totals"]["credits"]["min_amount"] = 0
                    if activity_summary["totals"]["debits"]["min_amount"] == float('inf'):
                        activity_summary["totals"]["debits"]["min_amount"] = 0
                    
                    for account_num in activity_summary["accounts"]:
                        if activity_summary["accounts"][account_num]["credits"]["min_amount"] == float('inf'):
                            activity_summary["accounts"][account_num]["credits"]["min_amount"] = 0
                        if activity_summary["accounts"][account_num]["debits"]["min_amount"] == float('inf'):
                            activity_summary["accounts"][account_num]["debits"]["min_amount"] = 0
                    
                    return activity_summary
        
        return activity_summary
    
    def _get_counterparties(self) -> Dict[str, Any]:
        """
        Get counterparties data with calculations
        
        Returns:
            Dict: Counterparties data
        """
        counterparties = {
            "accounts": {},
            "totals": {
                "credits": self._initialize_summary_dict(),
                "debits": self._initialize_summary_dict()
            }
        }
        
        # Try to find Counterparties in full_data. This section details transactions
        # grouped by the other party involved (sender/receiver).
        for section in self.case_data.get("full_data", []):
            if "Counterparties" in section:
                counterparties_list_data = section.get("Counterparties", []) # Data is usually a list per account
                if isinstance(counterparties_list_data, list):
                    for account_counterparty_data in counterparties_list_data: # Each item is for one account
                        account_num = str(account_counterparty_data.get("Account", ""))
                        
                        # Initialize account entry if new
                        if account_num not in counterparties["accounts"]:
                            counterparties["accounts"][account_num] = {
                                "credits": self._initialize_summary_dict(),
                                "debits": self._initialize_summary_dict()
                            }
                            # 'parties' will store data for each counterparty
                            counterparties["accounts"][account_num]["credits"]["parties"] = {}
                            counterparties["accounts"][account_num]["debits"]["parties"] = {}
                        
                        # Process credits for this account, grouped by counterparty
                        credits_data = account_counterparty_data.get("Credits", [])
                        for credit_item in credits_data:
                            party_name = credit_item.get("Row Labels", "") # Name of the counterparty
                            percent = to_float(credit_item.get("% of Credits", 0))
                            amount = to_float(credit_item.get("Total ", 0))
                            count = to_int(credit_item.get("# Transactions ", 0))
                            min_amount_txn = to_float(credit_item.get("Min Credit Amt.", 0))
                            max_amount_txn = to_float(credit_item.get("Max Credit Amt.", 0))
                            min_date_txn = credit_item.get("Min Txn Date ", "")
                            max_date_txn = credit_item.get("Max Txn Date ", "")
                            
                            account_credits_summary = counterparties["accounts"][account_num]["credits"]
                            # Initialize this counterparty if not seen before for this account's credits
                            if party_name not in account_credits_summary["parties"]:
                                account_credits_summary["parties"][party_name] = self._initialize_transaction_group(for_counterparty=True)
                            
                            # Aggregate data for this specific counterparty (credits)
                            party_data_agg = account_credits_summary["parties"][party_name]
                            party_data_agg["percent"] += percent
                            party_data_agg["amount"] += amount
                            party_data_agg["count"] += count
                            party_data_agg["min_amount"] = min(party_data_agg["min_amount"], min_amount_txn)
                            party_data_agg["max_amount"] = max(party_data_agg["max_amount"], max_amount_txn)
                            party_data_agg["min_date"] = compare_dates(min_date_txn, party_data_agg["min_date"], mode='earliest')
                            party_data_agg["max_date"] = compare_dates(max_date_txn, party_data_agg["max_date"], mode='latest')
                            
                            # Aggregate data for overall credits for this account
                            account_credits_summary["total_percent"] += percent
                            account_credits_summary["total_amount"] += amount
                            account_credits_summary["total_transactions"] += count
                            account_credits_summary["min_amount"] = min(account_credits_summary["min_amount"], min_amount_txn)
                            account_credits_summary["max_amount"] = max(account_credits_summary["max_amount"], max_amount_txn)
                            account_credits_summary["earliest_date"] = compare_dates(min_date_txn, account_credits_summary["earliest_date"], mode='earliest')
                            account_credits_summary["latest_date"] = compare_dates(max_date_txn, account_credits_summary["latest_date"], mode='latest')
                            
                            # Aggregate data for global credit totals across all accounts
                            global_credits_summary = counterparties["totals"]["credits"]
                            global_credits_summary["total_percent"] += percent
                            global_credits_summary["total_amount"] += amount
                            global_credits_summary["total_transactions"] += count
                            global_credits_summary["min_amount"] = min(global_credits_summary["min_amount"], min_amount_txn)
                            global_credits_summary["max_amount"] = max(global_credits_summary["max_amount"], max_amount_txn)
                            global_credits_summary["earliest_date"] = compare_dates(min_date_txn, global_credits_summary["earliest_date"], mode='earliest')
                            global_credits_summary["latest_date"] = compare_dates(max_date_txn, global_credits_summary["latest_date"], mode='latest')
                        
                        # Process debits for this account, grouped by counterparty (similar logic to credits)
                        debits_data = account_counterparty_data.get("Debits", [])
                        for debit_item in debits_data:
                            party_name = debit_item.get("Row Labels", "")
                            percent = to_float(debit_item.get("% of Debits", 0))
                            amount = to_float(debit_item.get("Total ", 0))
                            count = to_int(debit_item.get("# Transactions ", 0))
                            min_amount_txn = to_float(debit_item.get("Min Debit Amt.", 0))
                            max_amount_txn = to_float(debit_item.get("Max Debit Amt.", 0))
                            min_date_txn = debit_item.get("Min Txn Date ", "")
                            max_date_txn = debit_item.get("Max Txn Date ", "")
                            
                            account_debits_summary = counterparties["accounts"][account_num]["debits"]
                            if party_name not in account_debits_summary["parties"]:
                                account_debits_summary["parties"][party_name] = self._initialize_transaction_group(for_counterparty=True)
                            
                            party_data_agg = account_debits_summary["parties"][party_name]
                            party_data_agg["percent"] += percent
                            party_data_agg["amount"] += amount
                            party_data_agg["count"] += count
                            party_data_agg["min_amount"] = min(party_data_agg["min_amount"], min_amount_txn)
                            party_data_agg["max_amount"] = max(party_data_agg["max_amount"], max_amount_txn)
                            party_data_agg["min_date"] = compare_dates(min_date_txn, party_data_agg["min_date"], mode='earliest')
                            party_data_agg["max_date"] = compare_dates(max_date_txn, party_data_agg["max_date"], mode='latest')
                            
                            account_debits_summary["total_percent"] += percent
                            account_debits_summary["total_amount"] += amount
                            account_debits_summary["total_transactions"] += count
                            account_debits_summary["min_amount"] = min(account_debits_summary["min_amount"], min_amount_txn)
                            account_debits_summary["max_amount"] = max(account_debits_summary["max_amount"], max_amount_txn)
                            account_debits_summary["earliest_date"] = compare_dates(min_date_txn, account_debits_summary["earliest_date"], mode='earliest')
                            account_debits_summary["latest_date"] = compare_dates(max_date_txn, account_debits_summary["latest_date"], mode='latest')
                            
                            global_debits_summary = counterparties["totals"]["debits"]
                            global_debits_summary["total_percent"] += percent
                            global_debits_summary["total_amount"] += amount
                            global_debits_summary["total_transactions"] += count
                            global_debits_summary["min_amount"] = min(global_debits_summary["min_amount"], min_amount_txn)
                            global_debits_summary["max_amount"] = max(global_debits_summary["max_amount"], max_amount_txn)
                            global_debits_summary["earliest_date"] = compare_dates(min_date_txn, global_debits_summary["earliest_date"], mode='earliest')
                            global_debits_summary["latest_date"] = compare_dates(max_date_txn, global_debits_summary["latest_date"], mode='latest')
                    
                    # Clean up infinity values for min_amount
                    if counterparties["totals"]["credits"]["min_amount"] == float('inf'):
                        counterparties["totals"]["credits"]["min_amount"] = 0
                    if counterparties["totals"]["debits"]["min_amount"] == float('inf'):
                        counterparties["totals"]["debits"]["min_amount"] = 0
                    
                    for account_num in counterparties["accounts"]:
                        if counterparties["accounts"][account_num]["credits"]["min_amount"] == float('inf'):
                            counterparties["accounts"][account_num]["credits"]["min_amount"] = 0
                        if counterparties["accounts"][account_num]["debits"]["min_amount"] == float('inf'):
                            counterparties["accounts"][account_num]["debits"]["min_amount"] = 0
                    
                    return counterparties
        
        return counterparties
    
    def _get_transaction_details(self) -> Dict[str, Any]:
        """
        Get transaction details with calculations grouped by custom language
        
        Returns:
            Dict: Transaction details data
        """
        transaction_details = {
            "by_type": {},
            "credits": {
                "total_amount": 0,
                "total_transactions": 0
            },
            "debits": {
                "total_amount": 0,
                "total_transactions": 0
            },
            "grand_total": 0, # Grand total amount of all transactions
            "transaction_count": 0 # Grand total count of all transactions
        }
        
        # Try to find "Transactions" section in full_data. This section usually contains
        # a flat list of all individual transactions.
        for section in self.case_data.get("full_data", []):
            if "Transactions" in section:
                transactions_list_data = section.get("Transactions", [])
                if isinstance(transactions_list_data, list):
                    for transaction_item in transactions_list_data:
                        # Extract individual transaction details
                        account = str(transaction_item.get("Account", ""))
                        date = transaction_item.get("Transaction Date ", "") # Note space
                        debit_credit_indicator = transaction_item.get("Debit/Credit", "")
                        amount = to_float(transaction_item.get("Transaction Amount", 0))
                        custom_language = transaction_item.get("Custom Language", "") # Type of transaction
                        # branch = transaction_item.get("Branch / ATM", "") # Currently unused
                        sender = transaction_item.get("Sender or Remitter Name", "")
                        receiver = transaction_item.get("Receiver or Beneficiary Name", "")
                        memo = transaction_item.get("Memo", "")
                        
                        is_credit = debit_credit_indicator.lower() in ["credit", "cr", "c", "+"]
                        
                        # Initialize entry for this transaction type if it's new
                        if custom_language not in transaction_details["by_type"]:
                            transaction_details["by_type"][custom_language] = self._initialize_transaction_group(for_details=True)
                        
                        # Aggregate data for this transaction type
                        type_data_agg = transaction_details["by_type"][custom_language]
                        if is_credit:
                            type_data_agg["credits"]["amount"] += amount
                            type_data_agg["credits"]["count"] += 1
                        else:
                            type_data_agg["debits"]["amount"] += amount
                            type_data_agg["debits"]["count"] += 1
                        
                        type_data_agg["total"] += amount # Total amount for this specific type
                        type_data_agg["count"] += 1      # Total count for this specific type
                        
                        # Add a few examples for this transaction type (up to 3)
                        if len(type_data_agg["examples"]) < 3:
                            type_data_agg["examples"].append({
                                "account": account,
                                "date": date,
                                "amount": amount,
                                "is_credit": is_credit,
                                "sender": sender,
                                "receiver": receiver,
                                "memo": memo
                            })
                        
                        # Aggregate global totals
                        if is_credit:
                            transaction_details["credits"]["total_amount"] += amount
                            transaction_details["credits"]["total_transactions"] += 1
                        else:
                            transaction_details["debits"]["total_amount"] += amount
                            transaction_details["debits"]["total_transactions"] += 1
                        
                        transaction_details["grand_total"] += amount
                        transaction_details["transaction_count"] += 1
                    
                    return transaction_details
        
        return transaction_details
    
    def _get_unusual_activity(self) -> Dict[str, Any]:
        """
        Get unusual activity with calculations grouped by custom language
        
        Returns:
            Dict: Unusual activity data
        """
        unusual_activity = {
            "by_type": {},
            "credits": {
                "total_amount": 0,
                "total_transactions": 0
            },
            "debits": {
                "total_amount": 0,
                "total_transactions": 0
            },
            "grand_total": 0,
            "transaction_count": 0,
            "earliest_date": None, # Earliest transaction date in unusual activity
            "latest_date": None   # Latest transaction date in unusual activity
        }
        
        # Try to find "Unusual Activity" section in full_data. This section typically lists
        # transactions flagged as unusual or suspicious.
        for section in self.case_data.get("full_data", []):
            if "Unusual Activity" in section:
                transactions_list_data = section.get("Unusual Activity", [])
                if isinstance(transactions_list_data, list):
                    for transaction_item in transactions_list_data:
                        # Extract individual transaction details
                        account = str(transaction_item.get("Account", ""))
                        date = transaction_item.get("Transaction Date", "") # No space here
                        debit_credit_indicator = transaction_item.get("Debit/Credit", "")
                        amount = to_float(transaction_item.get("Transaction Amount", 0))
                        custom_language = transaction_item.get("Custom Language", "") # Type of transaction
                        # branch = transaction_item.get("Branch / ATM", "") # Unused variable
                        # branch = transaction_item.get("Branch / ATM", "") # Unused variable
                        sender = transaction_item.get("Sender or Remitter Name", "")
                        receiver = transaction_item.get("Receiver or Beneficiary Name", "")
                        memo = transaction_item.get("Memo", "")
                        
                        is_credit = debit_credit_indicator.lower() in ["credit", "cr", "c", "+"]
                        
                        # Initialize entry for this transaction type if it's new
                        if custom_language not in unusual_activity["by_type"]:
                            unusual_activity["by_type"][custom_language] = self._initialize_transaction_group(for_unusual=True)
                        
                        # Aggregate data for this transaction type
                        type_data_agg = unusual_activity["by_type"][custom_language]
                        if is_credit:
                            type_data_agg["credits"]["amount"] += amount
                            type_data_agg["credits"]["count"] += 1
                        else:
                            type_data_agg["debits"]["amount"] += amount
                            type_data_agg["debits"]["count"] += 1
                        
                        type_data_agg["total"] += amount # Total amount for this specific type
                        type_data_agg["count"] += 1      # Total count for this specific type
                        
                        # Update earliest and latest dates for this transaction type
                        type_data_agg["earliest_date"] = compare_dates(date, type_data_agg["earliest_date"], mode='earliest')
                        type_data_agg["latest_date"] = compare_dates(date, type_data_agg["latest_date"], mode='latest')
                        
                        # Add a few examples for this transaction type (up to 3)
                        if len(type_data_agg["examples"]) < 3:
                            type_data_agg["examples"].append({
                                "account": account,
                                "date": date,
                                "amount": amount,
                                "is_credit": is_credit,
                                "sender": sender,
                                "receiver": receiver,
                                "memo": memo
                            })
                        
                        # Aggregate global totals for unusual activity
                        if is_credit:
                            unusual_activity["credits"]["total_amount"] += amount
                            unusual_activity["credits"]["total_transactions"] += 1
                        else:
                            unusual_activity["debits"]["total_amount"] += amount
                            unusual_activity["debits"]["total_transactions"] += 1
                        
                        unusual_activity["grand_total"] += amount
                        unusual_activity["transaction_count"] += 1
                        
                        # Update global earliest and latest dates for unusual activity
                        unusual_activity["earliest_date"] = compare_dates(date, unusual_activity["earliest_date"], mode='earliest')
                        unusual_activity["latest_date"] = compare_dates(date, unusual_activity["latest_date"], mode='latest')
                    
                    return unusual_activity
        
        return unusual_activity
    
    def _get_cta_sample(self) -> Dict[str, Any]:
        """
        Get CTA sample data with calculations
        
        Returns:
            Dict: CTA sample data
        """
        cta_sample = {
            "by_type": {},
            "credits": {
                "total_amount": 0,
                "total_transactions": 0
            },
            "debits": {
                "total_amount": 0,
                "total_transactions": 0
            },
            "grand_total": 0,
            "transaction_count": 0,
            "earliest_date": None, # Earliest transaction date in CTA sample
            "latest_date": None   # Latest transaction date in CTA sample
        }
        
        # Try to find "CTA Sample" in full_data. This section provides a sample of transactions
        # relevant for Customer Transaction Assessment.
        for section in self.case_data.get("full_data", []):
            if "CTA Sample" in section:
                transactions_list_data = section.get("CTA Sample", [])
                if isinstance(transactions_list_data, list):
                    for transaction_item in transactions_list_data:
                        # Extract transaction details
                        account = str(transaction_item.get("Account", ""))
                        date = transaction_item.get("Transaction Date ", "") # Note space
                        debit_credit_indicator = transaction_item.get("Debit/Credit", "")
                        amount = to_float(transaction_item.get("Transaction Amount", 0))
                        custom_language = transaction_item.get("Custom Language", "")
                        
                        is_credit = debit_credit_indicator.lower() in ["credit", "cr", "c", "+"]
                        
                        # Initialize entry for this transaction type if new
                        if custom_language not in cta_sample["by_type"]:
                            cta_sample["by_type"][custom_language] = self._initialize_transaction_group(for_unusual=True) # Similar structure to unusual
                        
                        # Aggregate data for this transaction type
                        type_data_agg = cta_sample["by_type"][custom_language]
                        if is_credit:
                            type_data_agg["credits"]["amount"] += amount
                            type_data_agg["credits"]["count"] += 1
                        else:
                            type_data_agg["debits"]["amount"] += amount
                            type_data_agg["debits"]["count"] += 1
                        
                        type_data_agg["total"] += amount
                        type_data_agg["count"] += 1
                        
                        # Update earliest and latest dates for this type
                        type_data_agg["earliest_date"] = compare_dates(date, type_data_agg["earliest_date"], mode='earliest')
                        type_data_agg["latest_date"] = compare_dates(date, type_data_agg["latest_date"], mode='latest')
                        
                        # Add examples for this type (up to 3)
                        if len(type_data_agg["examples"]) < 3:
                            type_data_agg["examples"].append({
                                "account": account,
                                "date": date,
                                "amount": amount,
                                "is_credit": is_credit
                            })
                        
                        # Aggregate global totals for CTA sample
                        if is_credit:
                            cta_sample["credits"]["total_amount"] += amount
                            cta_sample["credits"]["total_transactions"] += 1
                        else:
                            cta_sample["debits"]["total_amount"] += amount
                            cta_sample["debits"]["total_transactions"] += 1
                        
                        cta_sample["grand_total"] += amount
                        cta_sample["transaction_count"] += 1
                        
                        # Update global earliest and latest dates for CTA sample
                        cta_sample["earliest_date"] = compare_dates(date, cta_sample["earliest_date"], mode='earliest')
                        cta_sample["latest_date"] = compare_dates(date, cta_sample["latest_date"], mode='latest')
                    
                    return cta_sample
        
        return cta_sample
    
    def _get_bip_sample(self) -> Dict[str, Any]:
        """
        Get BIP sample data with calculations
        
        Returns:
            Dict: BIP sample data
        """
        bip_sample = {
            "by_type": {},
            "credits": {
                "total_amount": 0,
                "total_transactions": 0
            },
            "debits": {
                "total_amount": 0,
                "total_transactions": 0
            },
            "grand_total": 0,
            "transaction_count": 0,
            "earliest_date": None, # Earliest transaction date in BIP sample
            "latest_date": None   # Latest transaction date in BIP sample
        }
        
        # Try to find "BIP Sample" in full_data. This section provides a sample of transactions
        # relevant for Business Intelligence Profile or similar analysis.
        for section in self.case_data.get("full_data", []):
            if "BIP Sample" in section:
                transactions_list_data = section.get("BIP Sample", [])
                if isinstance(transactions_list_data, list):
                    for transaction_item in transactions_list_data:
                        # Extract transaction details
                        account = str(transaction_item.get("Account", ""))
                        date = transaction_item.get("Transaction Date ", "") # Note space
                        debit_credit_indicator = transaction_item.get("Debit/Credit", "")
                        amount = to_float(transaction_item.get("Transaction Amount", 0))
                        custom_language = transaction_item.get("Custom Language", "")
                        
                        is_credit = debit_credit_indicator.lower() in ["credit", "cr", "c", "+"]
                        
                        # Initialize entry for this transaction type if new
                        if custom_language not in bip_sample["by_type"]:
                            bip_sample["by_type"][custom_language] = self._initialize_transaction_group(for_unusual=True) # Similar structure
                        
                        # Aggregate data for this transaction type
                        type_data_agg = bip_sample["by_type"][custom_language]
                        if is_credit:
                            type_data_agg["credits"]["amount"] += amount
                            type_data_agg["credits"]["count"] += 1
                        else:
                            type_data_agg["debits"]["amount"] += amount
                            type_data_agg["debits"]["count"] += 1
                        
                        type_data_agg["total"] += amount
                        type_data_agg["count"] += 1
                        
                        # Update earliest and latest dates for this type
                        type_data_agg["earliest_date"] = compare_dates(date, type_data_agg["earliest_date"], mode='earliest')
                        type_data_agg["latest_date"] = compare_dates(date, type_data_agg["latest_date"], mode='latest')
                        
                        # Add examples for this type (up to 3)
                        if len(type_data_agg["examples"]) < 3:
                            type_data_agg["examples"].append({
                                "account": account,
                                "date": date,
                                "amount": amount,
                                "is_credit": is_credit
                            })
                        
                        # Aggregate global totals for BIP sample
                        if is_credit:
                            bip_sample["credits"]["total_amount"] += amount
                            bip_sample["credits"]["total_transactions"] += 1
                        else:
                            bip_sample["debits"]["total_amount"] += amount
                            bip_sample["debits"]["total_transactions"] += 1
                        
                        bip_sample["grand_total"] += amount
                        bip_sample["transaction_count"] += 1
                        
                        # Update global earliest and latest dates for BIP sample
                        bip_sample["earliest_date"] = compare_dates(date, bip_sample["earliest_date"], mode='earliest')
                        bip_sample["latest_date"] = compare_dates(date, bip_sample["latest_date"], mode='latest')
                    
                    return bip_sample
        
        return bip_sample
    
    def get_alert_summary_data(self) -> Dict[str, Any]:
        """
        Get data for Section 1 - Alert Summary
        
        Returns:
            Dict: Combined data for alert summary
        """
        summary_data = {}
        
        # Get case number and alert info
        summary_data["case_number"] = self.case_data.get("case_number", "")
        summary_data["alert_info"] = self.case_data.get("alert_info", [])
        
        # Get account info
        summary_data["account_info"] = self.case_data.get("account_info", {})
        
        # Get subjects
        summary_data["subjects"] = self.case_data.get("subjects", [])
        
        # Get activity summary data
        summary_data["activity_summary"] = self.transaction_data.get("activity_summary", {})
        
        return summary_data
    
    def get_investigation_summary_data(self) -> Dict[str, Any]:
        """
        Get data for Section 4 - Summary of Investigation
        
        Returns:
            Dict: Combined data for investigation summary
        """
        investigation_data = {}
        
        # Get account info
        investigation_data["account_info"] = self.case_data.get("account_info", {})
        
        # Get subjects
        investigation_data["subjects"] = self.case_data.get("subjects", [])
        
        # Get transaction details
        investigation_data["transactions"] = self.transaction_data.get("transactions", {})
        
        # Get counterparties data
        investigation_data["counterparties"] = self.transaction_data.get("counterparties", {})
        
        # Get activity summary data
        investigation_data["activity_summary"] = self.transaction_data.get("activity_summary", {})
        
        return investigation_data
    
    def get_conclusion_data(self) -> Dict[str, Any]:
        """
        Get data for Section 6 - Conclusion
        
        Returns:
            Dict: Combined data for conclusion
        """
        conclusion_data = {}
        
        # Get case info
        conclusion_data["case_number"] = self.case_data.get("case_number", "")
        
        # Get account info
        conclusion_data["account_info"] = self.case_data.get("account_info", {})
        
        # Get subjects
        conclusion_data["subjects"] = self.case_data.get("subjects", [])
        
        # Get unusual activity data
        conclusion_data["unusual_activity"] = self.transaction_data.get("unusual_activity", {})
        
        # Get scope of review
        conclusion_data["scope_of_review"] = self.transaction_data.get("scope_of_review", {})
        
        return conclusion_data
    
    def get_referral_data(self) -> Dict[str, Any]:
        """
        Get data for Section 2 - Referral
        
        Returns:
            Dict: Combined data for referral
        """
        referral_data = {}
        
        # Get account info
        referral_data["account_info"] = self.case_data.get("account_info", {})
        
        # Get subjects
        referral_data["subjects"] = self.case_data.get("subjects", [])
        
        # Get CTA sample data
        referral_data["cta_sample"] = self.transaction_data.get("cta_sample", {})
        
        # Get BIP sample data
        referral_data["bip_sample"] = self.transaction_data.get("bip_sample", {})
        
        return referral_data
    
    def get_all_transaction_data(self) -> Dict[str, Any]:
        """
        Get all the processed transaction data including alerting activity summary
        
        Returns:
            Dict: All processed transaction data
        """
        # Calculate the alerting activity summary
        alerting_activity_summary = self.calculate_alerting_activity_summary()
        
        # Add the summary to the transaction data
        self.transaction_data["alerting_activity_summary"] = alerting_activity_summary
        
        return self.transaction_data
    
    """
    Add new function to calculate alerting activity summary
    """

    def calculate_alerting_activity_summary(self) -> Dict[str, Any]:
        """
        Calculate detailed alerting activity summary including credit and debit activity.
        This method aggregates data from previously processed transaction summaries and case information
        to create a focused summary related to the specific alert conditions.
        
        Returns:
            Dict: Alerting activity summary with detailed credit and debit information.
        """
        # Initialize the summary object structure
        summary = {
            "alertInfo": { # Information about the alert itself
                "caseNumber": "",
                "alertingAccounts": "",
                "alertingMonths": "",
                "alertDescription": ""
            },
            "account": "",
            "creditSummary": {
                "percentTotal": 0,
                "amountTotal": 0,
                "transactionCount": 0,
                "minCreditAmount": float('inf'),
                "maxCreditAmount": 0,
                "minTransactionDate": "",
                "maxTransactionDate": "",
                "highestPercentType": "",
                "highestPercentValue": 0
            },
            "debitSummary": {
                "percentTotal": 0,
                "amountTotal": 0,
                "transactionCount": 0,
                "minDebitAmount": float('inf'),
                "maxDebitAmount": 0,
                "minTransactionDate": "",
                "maxTransactionDate": "",
                "highestPercentType": "",
                "highestPercentValue": 0
            }
        }
        
        # Extract alert information
        alert_info = self.case_data.get("alert_info", [])
        if isinstance(alert_info, dict):
            alert_info = [alert_info]
        
        # Get case number
        summary["alertInfo"]["caseNumber"] = self.case_data.get("case_number", "")
        
        # Get account information
        account_info = self.case_data.get("account_info", {})
        account_type = account_info.get("account_type", "")
        account_number = account_info.get("account_number", "")
        
        summary["account"] = account_number
        summary["alertInfo"]["alertingAccounts"] = f"{account_type} {account_number}".strip()
        
        # Extract alert months and descriptions
        alert_months = []
        alert_descriptions = []
        
        for alert in alert_info:
            if isinstance(alert, dict):
                if alert.get("alert_month"):
                    alert_months.append(str(alert.get("alert_month")))
                if alert.get("description"):
                    alert_descriptions.append(str(alert.get("description")))
        
        summary["alertInfo"]["alertingMonths"] = ", ".join(alert_months) if alert_months else ""
        summary["alertInfo"]["alertDescription"] = "; ".join(alert_descriptions) if alert_descriptions else ""
        
        # Calculate credit and debit summaries from activity data
        activity_summary = self.transaction_data.get("activity_summary", {})
        for account_num, account_data in activity_summary.get("accounts", {}).items():
            # Process credits
            credit_data = account_data.get("credits", {})
            credit_summary = summary["creditSummary"]
            
            credit_summary["percentTotal"] = credit_data.get("total_percent", 0)
            credit_summary["amountTotal"] = credit_data.get("total_amount", 0)
            credit_summary["transactionCount"] = credit_data.get("total_transactions", 0)
            
            if credit_data.get("min_amount", float('inf')) < credit_summary["minCreditAmount"]:
                credit_summary["minCreditAmount"] = credit_data.get("min_amount", float('inf'))
            
            if credit_data.get("max_amount", 0) > credit_summary["maxCreditAmount"]:
                credit_summary["maxCreditAmount"] = credit_data.get("max_amount", 0)
            
            if credit_data.get("earliest_date"):
                credit_summary["minTransactionDate"] = compare_dates(credit_data.get("earliest_date"), credit_summary["minTransactionDate"], mode='earliest')
            
            if credit_data.get("latest_date"):
                credit_summary["maxTransactionDate"] = compare_dates(credit_data.get("latest_date"), credit_summary["maxTransactionDate"], mode='latest')
            
            # Find credit type with highest percentage from the 'by_type' breakdown
            # in the previously computed activity_summary for this account.
            highest_percent = 0
            highest_type = ""
            for txn_type, txn_data in credit_data.get("by_type", {}).items():
                percent = txn_data.get("percent", 0)
                if percent > highest_percent:
                    highest_percent = percent
                    highest_type = txn_type
            
            credit_summary["highestPercentType"] = highest_type
            credit_summary["highestPercentValue"] = highest_percent
            
            # Process debits
            debit_data = account_data.get("debits", {})
            debit_summary = summary["debitSummary"]
            
            debit_summary["percentTotal"] = debit_data.get("total_percent", 0)
            debit_summary["amountTotal"] = debit_data.get("total_amount", 0)
            debit_summary["transactionCount"] = debit_data.get("total_transactions", 0)
            
            if debit_data.get("min_amount", float('inf')) < debit_summary["minDebitAmount"]:
                debit_summary["minDebitAmount"] = debit_data.get("min_amount", float('inf'))
            
            if debit_data.get("max_amount", 0) > debit_summary["maxDebitAmount"]:
                debit_summary["maxDebitAmount"] = debit_data.get("max_amount", 0)
            
            if debit_data.get("earliest_date"):
                debit_summary["minTransactionDate"] = compare_dates(debit_data.get("earliest_date"), debit_summary["minTransactionDate"], mode='earliest')
            
            if debit_data.get("latest_date"):
                debit_summary["maxTransactionDate"] = compare_dates(debit_data.get("latest_date"), debit_summary["maxTransactionDate"], mode='latest')
            
            # Find debit type with highest percentage, similar to credits.
            highest_percent = 0
            highest_type = ""
            for txn_type, txn_data in debit_data.get("by_type", {}).items():
                percent = txn_data.get("percent", 0)
                if percent > highest_percent:
                    highest_percent = percent
                    highest_type = txn_type
            
            debit_summary["highestPercentType"] = highest_type
            debit_summary["highestPercentValue"] = highest_percent
        
        # Clean up any infinity values
        if summary["creditSummary"]["minCreditAmount"] == float('inf'):
            summary["creditSummary"]["minCreditAmount"] = 0
        
        if summary["debitSummary"]["minDebitAmount"] == float('inf'):
            summary["debitSummary"]["minDebitAmount"] = 0
        
        return summary