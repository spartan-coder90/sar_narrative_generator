"""
Transaction processor for extracting and calculating transaction summaries from case data
"""
from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime
from backend.utils.logger import get_logger

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
                "credits": {
                    "total_percent": 0,
                    "total_amount": 0,
                    "total_transactions": 0,
                    "min_amount": float('inf'),
                    "max_amount": 0,
                    "earliest_date": None,
                    "latest_date": None
                },
                "debits": {
                    "total_percent": 0,
                    "total_amount": 0,
                    "total_transactions": 0,
                    "min_amount": float('inf'),
                    "max_amount": 0,
                    "earliest_date": None,
                    "latest_date": None
                }
            }
        }
        
        # Try to find Activity Summary in full_data
        for section in self.case_data.get("full_data", []):
            if "Activity Summary" in section:
                summary_list = section.get("Activity Summary", [])
                if isinstance(summary_list, list):
                    for account_summary in summary_list:
                        account_num = str(account_summary.get("Account", ""))
                        
                        # Initialize account entry
                        if account_num not in activity_summary["accounts"]:
                            activity_summary["accounts"][account_num] = {
                                "credits": {
                                    "by_type": {},
                                    "total_percent": 0,
                                    "total_amount": 0,
                                    "total_transactions": 0,
                                    "min_amount": float('inf'),
                                    "max_amount": 0,
                                    "earliest_date": None,
                                    "latest_date": None
                                },
                                "debits": {
                                    "by_type": {},
                                    "total_percent": 0,
                                    "total_amount": 0,
                                    "total_transactions": 0,
                                    "min_amount": float('inf'),
                                    "max_amount": 0,
                                    "earliest_date": None,
                                    "latest_date": None
                                }
                            }
                        
                        # Process credits for this account
                        credits = account_summary.get("Credits", [])
                        for credit in credits:
                            # Extract values with proper type handling
                            custom_language = credit.get("Custom Language", "")
                            percent = self._to_float(credit.get("% of Credits", 0))
                            amount = self._to_float(credit.get("Total ", 0))
                            count = self._to_int(credit.get("# Transactions ", 0))
                            min_amount = self._to_float(credit.get("Min Credit Amt.", 0))
                            max_amount = self._to_float(credit.get("Max Credit Amt.", 0))
                            min_date = credit.get("Min Txn Date ", "")
                            max_date = credit.get("Max Txn Date ", "")
                            
                            # Add to account's by_type data
                            account_credits = activity_summary["accounts"][account_num]["credits"]
                            if custom_language not in account_credits["by_type"]:
                                account_credits["by_type"][custom_language] = {
                                    "percent": percent,
                                    "amount": amount,
                                    "count": count,
                                    "min_amount": min_amount,
                                    "max_amount": max_amount,
                                    "min_date": min_date,
                                    "max_date": max_date
                                }
                            else:
                                # Add to existing values
                                type_data = account_credits["by_type"][custom_language]
                                type_data["percent"] += percent
                                type_data["amount"] += amount
                                type_data["count"] += count
                                type_data["min_amount"] = min(type_data["min_amount"], min_amount)
                                type_data["max_amount"] = max(type_data["max_amount"], max_amount)
                                
                                # Update dates if needed
                                if self._compare_dates(min_date, type_data["min_date"]) < 0:
                                    type_data["min_date"] = min_date
                                if self._compare_dates(max_date, type_data["max_date"]) > 0:
                                    type_data["max_date"] = max_date
                            
                            # Add to account summary totals
                            account_credits["total_percent"] += percent
                            account_credits["total_amount"] += amount
                            account_credits["total_transactions"] += count
                            account_credits["min_amount"] = min(account_credits["min_amount"], min_amount)
                            account_credits["max_amount"] = max(account_credits["max_amount"], max_amount)
                            
                            # Update dates
                            if account_credits["earliest_date"] is None or self._compare_dates(min_date, account_credits["earliest_date"]) < 0:
                                account_credits["earliest_date"] = min_date
                            if account_credits["latest_date"] is None or self._compare_dates(max_date, account_credits["latest_date"]) > 0:
                                account_credits["latest_date"] = max_date
                            
                            # Add to global totals
                            global_credits = activity_summary["totals"]["credits"]
                            global_credits["total_percent"] += percent
                            global_credits["total_amount"] += amount
                            global_credits["total_transactions"] += count
                            if min_amount < global_credits["min_amount"]:
                                global_credits["min_amount"] = min_amount
                            if max_amount > global_credits["max_amount"]:
                                global_credits["max_amount"] = max_amount
                            
                            # Update global dates
                            if global_credits["earliest_date"] is None or self._compare_dates(min_date, global_credits["earliest_date"]) < 0:
                                global_credits["earliest_date"] = min_date
                            if global_credits["latest_date"] is None or self._compare_dates(max_date, global_credits["latest_date"]) > 0:
                                global_credits["latest_date"] = max_date
                        
                        # Process debits for this account
                        debits = account_summary.get("Debits", [])
                        for debit in debits:
                            # Extract values with proper type handling
                            custom_language = debit.get("Custom Language", "")
                            percent = self._to_float(debit.get("% of Debits", 0))
                            amount = self._to_float(debit.get("Total ", 0))
                            count = self._to_int(debit.get("# Transactions ", 0))
                            min_amount = self._to_float(debit.get("Min Debit Amt.", 0))
                            max_amount = self._to_float(debit.get("Max Debit Amt.", 0))
                            min_date = debit.get("Min Txn Date ", "")
                            max_date = debit.get("Max Txn Date ", "")
                            
                            # Add to account's by_type data
                            account_debits = activity_summary["accounts"][account_num]["debits"]
                            if custom_language not in account_debits["by_type"]:
                                account_debits["by_type"][custom_language] = {
                                    "percent": percent,
                                    "amount": amount,
                                    "count": count,
                                    "min_amount": min_amount,
                                    "max_amount": max_amount,
                                    "min_date": min_date,
                                    "max_date": max_date
                                }
                            else:
                                # Add to existing values
                                type_data = account_debits["by_type"][custom_language]
                                type_data["percent"] += percent
                                type_data["amount"] += amount
                                type_data["count"] += count
                                type_data["min_amount"] = min(type_data["min_amount"], min_amount)
                                type_data["max_amount"] = max(type_data["max_amount"], max_amount)
                                
                                # Update dates if needed
                                if self._compare_dates(min_date, type_data["min_date"]) < 0:
                                    type_data["min_date"] = min_date
                                if self._compare_dates(max_date, type_data["max_date"]) > 0:
                                    type_data["max_date"] = max_date
                            
                            # Add to account summary totals
                            account_debits["total_percent"] += percent
                            account_debits["total_amount"] += amount
                            account_debits["total_transactions"] += count
                            account_debits["min_amount"] = min(account_debits["min_amount"], min_amount)
                            account_debits["max_amount"] = max(account_debits["max_amount"], max_amount)
                            
                            # Update dates
                            if account_debits["earliest_date"] is None or self._compare_dates(min_date, account_debits["earliest_date"]) < 0:
                                account_debits["earliest_date"] = min_date
                            if account_debits["latest_date"] is None or self._compare_dates(max_date, account_debits["latest_date"]) > 0:
                                account_debits["latest_date"] = max_date
                            
                            # Add to global totals
                            global_debits = activity_summary["totals"]["debits"]
                            global_debits["total_percent"] += percent
                            global_debits["total_amount"] += amount
                            global_debits["total_transactions"] += count
                            if min_amount < global_debits["min_amount"]:
                                global_debits["min_amount"] = min_amount
                            if max_amount > global_debits["max_amount"]:
                                global_debits["max_amount"] = max_amount
                            
                            # Update global dates
                            if global_debits["earliest_date"] is None or self._compare_dates(min_date, global_debits["earliest_date"]) < 0:
                                global_debits["earliest_date"] = min_date
                            if global_debits["latest_date"] is None or self._compare_dates(max_date, global_debits["latest_date"]) > 0:
                                global_debits["latest_date"] = max_date
                    
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
                "credits": {
                    "total_percent": 0,
                    "total_amount": 0,
                    "total_transactions": 0,
                    "min_amount": float('inf'),
                    "max_amount": 0,
                    "earliest_date": None,
                    "latest_date": None
                },
                "debits": {
                    "total_percent": 0,
                    "total_amount": 0,
                    "total_transactions": 0,
                    "min_amount": float('inf'),
                    "max_amount": 0,
                    "earliest_date": None,
                    "latest_date": None
                }
            }
        }
        
        # Try to find Counterparties in full_data
        for section in self.case_data.get("full_data", []):
            if "Counterparties" in section:
                counterparties_list = section.get("Counterparties", [])
                if isinstance(counterparties_list, list):
                    for account_data in counterparties_list:
                        account_num = str(account_data.get("Account", ""))
                        
                        # Initialize account entry
                        if account_num not in counterparties["accounts"]:
                            counterparties["accounts"][account_num] = {
                                "credits": {
                                    "parties": {},
                                    "total_percent": 0,
                                    "total_amount": 0,
                                    "total_transactions": 0,
                                    "min_amount": float('inf'),
                                    "max_amount": 0,
                                    "earliest_date": None,
                                    "latest_date": None
                                },
                                "debits": {
                                    "parties": {},
                                    "total_percent": 0,
                                    "total_amount": 0,
                                    "total_transactions": 0,
                                    "min_amount": float('inf'),
                                    "max_amount": 0,
                                    "earliest_date": None,
                                    "latest_date": None
                                }
                            }
                        
                        # Process credits for this account
                        credits = account_data.get("Credits", [])
                        for credit in credits:
                            # Extract values with proper type handling
                            party_name = credit.get("Row Labels", "")
                            percent = self._to_float(credit.get("% of Credits", 0))
                            amount = self._to_float(credit.get("Total ", 0))
                            count = self._to_int(credit.get("# Transactions ", 0))
                            min_amount = self._to_float(credit.get("Min Credit Amt.", 0))
                            max_amount = self._to_float(credit.get("Max Credit Amt.", 0))
                            min_date = credit.get("Min Txn Date ", "")
                            max_date = credit.get("Max Txn Date ", "")
                            
                            # Add to account's parties data
                            account_credits = counterparties["accounts"][account_num]["credits"]
                            if party_name not in account_credits["parties"]:
                                account_credits["parties"][party_name] = {
                                    "percent": percent,
                                    "amount": amount,
                                    "count": count,
                                    "min_amount": min_amount,
                                    "max_amount": max_amount,
                                    "min_date": min_date,
                                    "max_date": max_date
                                }
                            else:
                                # Add to existing values
                                party_data = account_credits["parties"][party_name]
                                party_data["percent"] += percent
                                party_data["amount"] += amount
                                party_data["count"] += count
                                party_data["min_amount"] = min(party_data["min_amount"], min_amount)
                                party_data["max_amount"] = max(party_data["max_amount"], max_amount)
                                
                                # Update dates if needed
                                if self._compare_dates(min_date, party_data["min_date"]) < 0:
                                    party_data["min_date"] = min_date
                                if self._compare_dates(max_date, party_data["max_date"]) > 0:
                                    party_data["max_date"] = max_date
                            
                            # Add to account summary totals
                            account_credits["total_percent"] += percent
                            account_credits["total_amount"] += amount
                            account_credits["total_transactions"] += count
                            account_credits["min_amount"] = min(account_credits["min_amount"], min_amount)
                            account_credits["max_amount"] = max(account_credits["max_amount"], max_amount)
                            
                            # Update dates
                            if account_credits["earliest_date"] is None or self._compare_dates(min_date, account_credits["earliest_date"]) < 0:
                                account_credits["earliest_date"] = min_date
                            if account_credits["latest_date"] is None or self._compare_dates(max_date, account_credits["latest_date"]) > 0:
                                account_credits["latest_date"] = max_date
                            
                            # Add to global totals
                            global_credits = counterparties["totals"]["credits"]
                            global_credits["total_percent"] += percent
                            global_credits["total_amount"] += amount
                            global_credits["total_transactions"] += count
                            if min_amount < global_credits["min_amount"]:
                                global_credits["min_amount"] = min_amount
                            if max_amount > global_credits["max_amount"]:
                                global_credits["max_amount"] = max_amount
                            
                            # Update global dates
                            if global_credits["earliest_date"] is None or self._compare_dates(min_date, global_credits["earliest_date"]) < 0:
                                global_credits["earliest_date"] = min_date
                            if global_credits["latest_date"] is None or self._compare_dates(max_date, global_credits["latest_date"]) > 0:
                                global_credits["latest_date"] = max_date
                        
                        # Process debits for this account
                        debits = account_data.get("Debits", [])
                        for debit in debits:
                            # Extract values with proper type handling
                            party_name = debit.get("Row Labels", "")
                            percent = self._to_float(debit.get("% of Debits", 0))
                            amount = self._to_float(debit.get("Total ", 0))
                            count = self._to_int(debit.get("# Transactions ", 0))
                            min_amount = self._to_float(debit.get("Min Debit Amt.", 0))
                            max_amount = self._to_float(debit.get("Max Debit Amt.", 0))
                            min_date = debit.get("Min Txn Date ", "")
                            max_date = debit.get("Max Txn Date ", "")
                            
                            # Add to account's parties data
                            account_debits = counterparties["accounts"][account_num]["debits"]
                            if party_name not in account_debits["parties"]:
                                account_debits["parties"][party_name] = {
                                    "percent": percent,
                                    "amount": amount,
                                    "count": count,
                                    "min_amount": min_amount,
                                    "max_amount": max_amount,
                                    "min_date": min_date,
                                    "max_date": max_date
                                }
                            else:
                                # Add to existing values
                                party_data = account_debits["parties"][party_name]
                                party_data["percent"] += percent
                                party_data["amount"] += amount
                                party_data["count"] += count
                                party_data["min_amount"] = min(party_data["min_amount"], min_amount)
                                party_data["max_amount"] = max(party_data["max_amount"], max_amount)
                                
                                # Update dates if needed
                                if self._compare_dates(min_date, party_data["min_date"]) < 0:
                                    party_data["min_date"] = min_date
                                if self._compare_dates(max_date, party_data["max_date"]) > 0:
                                    party_data["max_date"] = max_date
                            
                            # Add to account summary totals
                            account_debits["total_percent"] += percent
                            account_debits["total_amount"] += amount
                            account_debits["total_transactions"] += count
                            account_debits["min_amount"] = min(account_debits["min_amount"], min_amount)
                            account_debits["max_amount"] = max(account_debits["max_amount"], max_amount)
                            
                            # Update dates
                            if account_debits["earliest_date"] is None or self._compare_dates(min_date, account_debits["earliest_date"]) < 0:
                                account_debits["earliest_date"] = min_date
                            if account_debits["latest_date"] is None or self._compare_dates(max_date, account_debits["latest_date"]) > 0:
                                account_debits["latest_date"] = max_date
                            
                            # Add to global totals
                            global_debits = counterparties["totals"]["debits"]
                            global_debits["total_percent"] += percent
                            global_debits["total_amount"] += amount
                            global_debits["total_transactions"] += count
                            if min_amount < global_debits["min_amount"]:
                                global_debits["min_amount"] = min_amount
                            if max_amount > global_debits["max_amount"]:
                                global_debits["max_amount"] = max_amount
                            
                            # Update global dates
                            if global_debits["earliest_date"] is None or self._compare_dates(min_date, global_debits["earliest_date"]) < 0:
                                global_debits["earliest_date"] = min_date
                            if global_debits["latest_date"] is None or self._compare_dates(max_date, global_debits["latest_date"]) > 0:
                                global_debits["latest_date"] = max_date
                    
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
            "grand_total": 0,
            "transaction_count": 0
        }
        
        # Try to find Transactions in full_data
        for section in self.case_data.get("full_data", []):
            if "Transactions" in section:
                transactions_list = section.get("Transactions", [])
                if isinstance(transactions_list, list):
                    for transaction in transactions_list:
                        # Extract values with proper type handling
                        account = str(transaction.get("Account", ""))
                        date = transaction.get("Transaction Date ", "")
                        debit_credit = transaction.get("Debit/Credit", "")
                        amount = self._to_float(transaction.get("Transaction Amount", 0))
                        custom_language = transaction.get("Custom Language", "")
                        branch = transaction.get("Branch / ATM", "")
                        sender = transaction.get("Sender or Remitter Name", "")
                        receiver = transaction.get("Receiver or Beneficiary Name", "")
                        memo = transaction.get("Memo", "")
                        
                        # Determine if credit or debit
                        is_credit = debit_credit.lower() in ["credit", "cr", "c", "+"]
                        
                        # Initialize by_type entry if needed
                        if custom_language not in transaction_details["by_type"]:
                            transaction_details["by_type"][custom_language] = {
                                "credits": {
                                    "amount": 0,
                                    "count": 0
                                },
                                "debits": {
                                    "amount": 0,
                                    "count": 0
                                },
                                "total": 0,
                                "count": 0,
                                "examples": []
                            }
                        
                        # Add to type summary
                        type_data = transaction_details["by_type"][custom_language]
                        if is_credit:
                            type_data["credits"]["amount"] += amount
                            type_data["credits"]["count"] += 1
                        else:
                            type_data["debits"]["amount"] += amount
                            type_data["debits"]["count"] += 1
                        
                        type_data["total"] += amount
                        type_data["count"] += 1
                        
                        # Add to examples (limit to 3 per type)
                        if len(type_data["examples"]) < 3:
                            type_data["examples"].append({
                                "account": account,
                                "date": date,
                                "amount": amount,
                                "is_credit": is_credit,
                                "sender": sender,
                                "receiver": receiver,
                                "memo": memo
                            })
                        
                        # Add to global totals
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
            "earliest_date": None,
            "latest_date": None
        }
        
        # Try to find Unusual Activity in full_data
        for section in self.case_data.get("full_data", []):
            if "Unusual Activity" in section:
                transactions_list = section.get("Unusual Activity", [])
                if isinstance(transactions_list, list):
                    for transaction in transactions_list:
                        # Extract values with proper type handling
                        account = str(transaction.get("Account", ""))
                        date = transaction.get("Transaction Date", "")
                        debit_credit = transaction.get("Debit/Credit", "")
                        amount = self._to_float(transaction.get("Transaction Amount", 0))
                        custom_language = transaction.get("Custom Language", "")
                        branch = transaction.get("Branch / ATM", "")
                        sender = transaction.get("Sender or Remitter Name", "")
                        receiver = transaction.get("Receiver or Beneficiary Name", "")
                        memo = transaction.get("Memo", "")
                        
                        # Determine if credit or debit
                        is_credit = debit_credit.lower() in ["credit", "cr", "c", "+"]
                        
                        # Initialize by_type entry if needed
                        if custom_language not in unusual_activity["by_type"]:
                            unusual_activity["by_type"][custom_language] = {
                                "credits": {
                                    "amount": 0,
                                    "count": 0
                                },
                                "debits": {
                                    "amount": 0,
                                    "count": 0
                                },
                                "total": 0,
                                "count": 0,
                                "earliest_date": None,
                                "latest_date": None,
                                "examples": []
                            }
                        
                        # Add to type summary
                        type_data = unusual_activity["by_type"][custom_language]
                        if is_credit:
                            type_data["credits"]["amount"] += amount
                            type_data["credits"]["count"] += 1
                        else:
                            type_data["debits"]["amount"] += amount
                            type_data["debits"]["count"] += 1
                        
                        type_data["total"] += amount
                        type_data["count"] += 1
                        
                        # Update dates
                        if type_data["earliest_date"] is None or self._compare_dates(date, type_data["earliest_date"]) < 0:
                            type_data["earliest_date"] = date
                        if type_data["latest_date"] is None or self._compare_dates(date, type_data["latest_date"]) > 0:
                            type_data["latest_date"] = date
                        
                        # Add to examples (limit to 3 per type)
                        if len(type_data["examples"]) < 3:
                            type_data["examples"].append({
                                "account": account,
                                "date": date,
                                "amount": amount,
                                "is_credit": is_credit,
                                "sender": sender,
                                "receiver": receiver,
                                "memo": memo
                            })
                        
                        # Add to global totals
                        if is_credit:
                            unusual_activity["credits"]["total_amount"] += amount
                            unusual_activity["credits"]["total_transactions"] += 1
                        else:
                            unusual_activity["debits"]["total_amount"] += amount
                            unusual_activity["debits"]["total_transactions"] += 1
                        
                        unusual_activity["grand_total"] += amount
                        unusual_activity["transaction_count"] += 1
                        
                        # Update global dates
                        if unusual_activity["earliest_date"] is None or self._compare_dates(date, unusual_activity["earliest_date"]) < 0:
                            unusual_activity["earliest_date"] = date
                        if unusual_activity["latest_date"] is None or self._compare_dates(date, unusual_activity["latest_date"]) > 0:
                            unusual_activity["latest_date"] = date
                    
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
            "earliest_date": None,
            "latest_date": None
        }
        
        # Try to find CTA Sample in full_data
        for section in self.case_data.get("full_data", []):
            if "CTA Sample" in section:
                transactions_list = section.get("CTA Sample", [])
                if isinstance(transactions_list, list):
                    for transaction in transactions_list:
                        # Extract values with proper type handling
                        account = str(transaction.get("Account", ""))
                        date = transaction.get("Transaction Date ", "")
                        debit_credit = transaction.get("Debit/Credit", "")
                        amount = self._to_float(transaction.get("Transaction Amount", 0))
                        custom_language = transaction.get("Custom Language", "")
                        
                        # Determine if credit or debit
                        is_credit = debit_credit.lower() in ["credit", "cr", "c", "+"]
                        
                        # Initialize by_type entry if needed
                        if custom_language not in cta_sample["by_type"]:
                            cta_sample["by_type"][custom_language] = {
                                "credits": {
                                    "amount": 0,
                                    "count": 0
                                },
                                "debits": {
                                    "amount": 0,
                                    "count": 0
                                },
                                "total": 0,
                                "count": 0,
                                "earliest_date": None,
                                "latest_date": None,
                                "examples": []
                            }
                        
                        # Add to type summary
                        type_data = cta_sample["by_type"][custom_language]
                        if is_credit:
                            type_data["credits"]["amount"] += amount
                            type_data["credits"]["count"] += 1
                        else:
                            type_data["debits"]["amount"] += amount
                            type_data["debits"]["count"] += 1
                        
                        type_data["total"] += amount
                        type_data["count"] += 1
                        
                        # Update dates
                        if type_data["earliest_date"] is None or self._compare_dates(date, type_data["earliest_date"]) < 0:
                            type_data["earliest_date"] = date
                        if type_data["latest_date"] is None or self._compare_dates(date, type_data["latest_date"]) > 0:
                            type_data["latest_date"] = date
                        
                        # Add to examples (limit to 3 per type)
                        if len(type_data["examples"]) < 3:
                            type_data["examples"].append({
                                "account": account,
                                "date": date,
                                "amount": amount,
                                "is_credit": is_credit
                            })
                        
                        # Add to global totals
                        if is_credit:
                            cta_sample["credits"]["total_amount"] += amount
                            cta_sample["credits"]["total_transactions"] += 1
                        else:
                            cta_sample["debits"]["total_amount"] += amount
                            cta_sample["debits"]["total_transactions"] += 1
                        
                        cta_sample["grand_total"] += amount
                        cta_sample["transaction_count"] += 1
                        
                        # Update global dates
                        if cta_sample["earliest_date"] is None or self._compare_dates(date, cta_sample["earliest_date"]) < 0:
                            cta_sample["earliest_date"] = date
                        if cta_sample["latest_date"] is None or self._compare_dates(date, cta_sample["latest_date"]) > 0:
                            cta_sample["latest_date"] = date
                    
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
            "earliest_date": None,
            "latest_date": None
        }
        
        # Try to find BIP Sample in full_data
        for section in self.case_data.get("full_data", []):
            if "BIP Sample" in section:
                transactions_list = section.get("BIP Sample", [])
                if isinstance(transactions_list, list):
                    for transaction in transactions_list:
                        # Extract values with proper type handling
                        account = str(transaction.get("Account", ""))
                        date = transaction.get("Transaction Date ", "")
                        debit_credit = transaction.get("Debit/Credit", "")
                        amount = self._to_float(transaction.get("Transaction Amount", 0))
                        custom_language = transaction.get("Custom Language", "")
                        
                        # Determine if credit or debit
                        is_credit = debit_credit.lower() in ["credit", "cr", "c", "+"]
                        
                        # Initialize by_type entry if needed
                        if custom_language not in bip_sample["by_type"]:
                            bip_sample["by_type"][custom_language] = {
                                "credits": {
                                    "amount": 0,
                                    "count": 0
                                },
                                "debits": {
                                    "amount": 0,
                                    "count": 0
                                },
                                "total": 0,
                                "count": 0,
                                "earliest_date": None,
                                "latest_date": None,
                                "examples": []
                            }
                        
                        # Add to type summary
                        type_data = bip_sample["by_type"][custom_language]
                        if is_credit:
                            type_data["credits"]["amount"] += amount
                            type_data["credits"]["count"] += 1
                        else:
                            type_data["debits"]["amount"] += amount
                            type_data["debits"]["count"] += 1
                        
                        type_data["total"] += amount
                        type_data["count"] += 1
                        
                        # Update dates
                        if type_data["earliest_date"] is None or self._compare_dates(date, type_data["earliest_date"]) < 0:
                            type_data["earliest_date"] = date
                        if type_data["latest_date"] is None or self._compare_dates(date, type_data["latest_date"]) > 0:
                            type_data["latest_date"] = date
                        
                        # Add to examples (limit to 3 per type)
                        if len(type_data["examples"]) < 3:
                            type_data["examples"].append({
                                "account": account,
                                "date": date,
                                "amount": amount,
                                "is_credit": is_credit
                            })
                        
                        # Add to global totals
                        if is_credit:
                            bip_sample["credits"]["total_amount"] += amount
                            bip_sample["credits"]["total_transactions"] += 1
                        else:
                            bip_sample["debits"]["total_amount"] += amount
                            bip_sample["debits"]["total_transactions"] += 1
                        
                        bip_sample["grand_total"] += amount
                        bip_sample["transaction_count"] += 1
                        
                        # Update global dates
                        if bip_sample["earliest_date"] is None or self._compare_dates(date, bip_sample["earliest_date"]) < 0:
                            bip_sample["earliest_date"] = date
                        if bip_sample["latest_date"] is None or self._compare_dates(date, bip_sample["latest_date"]) > 0:
                            bip_sample["latest_date"] = date
                    
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
        Calculate detailed alerting activity summary including credit and debit activity
        
        Returns:
            Dict: Alerting activity summary with detailed credit and debit information
        """
        # Initialize the summary object
        summary = {
            "alertInfo": {
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
        summary["alertInfo"]["alertingAccounts"] = f"{account_type} {account_number}"
        
        # Extract alert months and descriptions
        alert_months = []
        alert_descriptions = []
        
        for alert in alert_info:
            if isinstance(alert, dict):
                if alert.get("alert_month"):
                    alert_months.append(alert.get("alert_month"))
                if alert.get("description"):
                    alert_descriptions.append(alert.get("description"))
        
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
                if not credit_summary["minTransactionDate"] or self._compare_dates(credit_data.get("earliest_date"), credit_summary["minTransactionDate"]) < 0:
                    credit_summary["minTransactionDate"] = credit_data.get("earliest_date")
            
            if credit_data.get("latest_date"):
                if not credit_summary["maxTransactionDate"] or self._compare_dates(credit_data.get("latest_date"), credit_summary["maxTransactionDate"]) > 0:
                    credit_summary["maxTransactionDate"] = credit_data.get("latest_date")
            
            # Find credit type with highest percentage
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
                if not debit_summary["minTransactionDate"] or self._compare_dates(debit_data.get("earliest_date"), debit_summary["minTransactionDate"]) < 0:
                    debit_summary["minTransactionDate"] = debit_data.get("earliest_date")
            
            if debit_data.get("latest_date"):
                if not debit_summary["maxTransactionDate"] or self._compare_dates(debit_data.get("latest_date"), debit_summary["maxTransactionDate"]) > 0:
                    debit_summary["maxTransactionDate"] = debit_data.get("latest_date")
            
            # Find debit type with highest percentage
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
    # Helper methods
    
    def _to_float(self, value: Any) -> float:
        """Convert value to float with error handling"""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove currency symbols and commas
            cleaned_value = value.replace('$', '').replace(',', '')
            try:
                return float(cleaned_value)
            except ValueError:
                return 0.0
        
        return 0.0
    
    def _to_int(self, value: Any) -> int:
        """Convert value to int with error handling"""
        if isinstance(value, int):
            return value
        
        if isinstance(value, float):
            return int(value)
        
        if isinstance(value, str):
            # Remove non-numeric characters
            cleaned_value = re.sub(r'[^0-9]', '', value)
            try:
                return int(cleaned_value)
            except ValueError:
                return 0
        
        return 0
    
    def _compare_dates(self, date1: str, date2: str) -> int:
        """
        Compare two dates
        
        Args:
            date1: First date string
            date2: Second date string
            
        Returns:
            int: -1 if date1 < date2, 0 if equal, 1 if date1 > date2
        """
        if not date1 or not date2:
            return 0
        
        # Try to parse dates
        date1_obj = None
        date2_obj = None
        
        # Try different date formats
        date_formats = ['%m/%d/%Y', '%Y-%m-%d', '%m/%d/%y', '%d/%m/%Y']
        
        for fmt in date_formats:
            try:
                if not date1_obj:
                    date1_obj = datetime.strptime(date1, fmt)
                if not date2_obj:
                    date2_obj = datetime.strptime(date2, fmt)
                
                if date1_obj and date2_obj:
                    break
            except ValueError:
                continue
        
        # If parsing fails, compare as strings
        if not date1_obj or not date2_obj:
            return (date1 > date2) - (date1 < date2)
        
        # Compare datetime objects
        return (date1_obj > date2_obj) - (date1_obj < date2_obj)