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
        Extract and structure transaction data using the standardized self.case_data.
        The helper methods (_get_scope_of_review, _get_case_subjects, etc.) are
        now refactored to use self.case_data directly.
        """
        # self.case_data is now the standardized dictionary, not a wrapper around "full_data".
        # The check for "full_data" is no longer needed.
        # Individual _get_* methods will handle missing data from self.case_data if necessary.

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
        Get scope of review dates from the standardized case data structure.
        
        Returns:
            Dict: Scope of review dates with "start" and "end" keys.
        """
        scope_of_review = {"start": "", "end": ""}
        
        case_info = self.case_data.get("caseInfo", {})
        review_period = case_info.get("reviewPeriod", {})
        
        if review_period:
            scope_of_review["start"] = review_period.get("startDate", "")
            scope_of_review["end"] = review_period.get("endDate", "")

        if not scope_of_review["start"] and not scope_of_review["end"]:
            logger.warning("Scope of review dates not found in case_data.caseInfo.reviewPeriod.")
            # Potentially log self.case_data structure if helpful for debugging, but be mindful of log size
            # logger.debug(f"Case data for scope of review issue: {self.case_data}")


        return scope_of_review
    
    def _get_case_subjects(self) -> List[Dict[str, Any]]:
        """
        Get case subjects from the standardized case data structure.
        
        Returns:
            List[Dict]: Case subjects information, mapping new fields to expected output structure.
        """
        processed_subjects = []
        subjects_in_case_data = self.case_data.get("subjects", [])
        
        if not subjects_in_case_data:
            logger.warning("No subjects found in case_data.subjects.")
            return []

        for subject in subjects_in_case_data:
            processed_subjects.append({
                "name": subject.get("name", ""),
                "party_key": subject.get("partyKey", ""), # Map partyKey from new structure
                "additional_info": { # Keep this field for structural consistency if needed downstream
                    "is_primary": subject.get("isPrimary", False),
                    "date_of_birth": subject.get("dateOfBirth", ""),
                    "occupation": subject.get("occupation", "")
                }
            })

        return processed_subjects
    
    def _get_activity_summary(self) -> Dict[str, Any]:
        """
        Get activity summary data with calculations from the standardized case data structure.
        Iterates through `self.case_data.accounts`, accessing `activitySummary` for each.
        
        Returns:
            Dict: Activity summary data.
        """
        activity_summary = {
            "accounts": {},
            "totals": {
                "credits": self._initialize_summary_dict(),
                "debits": self._initialize_summary_dict()
            }
        }

        accounts_data = self.case_data.get("accounts", [])
        if not accounts_data:
            logger.warning("No accounts found in case_data.accounts for activity summary.")
            return activity_summary

        for account_item in accounts_data:
            account_num = str(account_item.get("accountKey", ""))
            if not account_num:
                logger.warning("Account item found without an accountKey. Skipping.")
                continue

            account_activity_summary = account_item.get("activitySummary", {})
            if not account_activity_summary:
                logger.info(f"No activitySummary found for account {account_num}. Skipping.")
                continue

            # Initialize account entry if it's the first time seeing this account
            if account_num not in activity_summary["accounts"]:
                activity_summary["accounts"][account_num] = {
                    "credits": self._initialize_summary_dict(),
                    "debits": self._initialize_summary_dict()
                }
                activity_summary["accounts"][account_num]["credits"]["by_type"] = {}
                activity_summary["accounts"][account_num]["debits"]["by_type"] = {}

            # Process credits for this account
            credits_by_type_data = account_activity_summary.get("creditsByType", [])
            for credit_item in credits_by_type_data:
                custom_language = credit_item.get("type", "")
                percent = to_float(credit_item.get("percentOfTotal", 0))
                amount = to_float(credit_item.get("totalAmount", 0))
                count = to_int(credit_item.get("transactionCount", 0))
                min_amount_txn = to_float(credit_item.get("minTransactionAmount", 0))
                max_amount_txn = to_float(credit_item.get("maxTransactionAmount", 0))
                min_date_txn = credit_item.get("minTransactionDate", "")
                max_date_txn = credit_item.get("maxTransactionDate", "")

                account_credits_summary_struct = activity_summary["accounts"][account_num]["credits"]
                if custom_language not in account_credits_summary_struct["by_type"]:
                    account_credits_summary_struct["by_type"][custom_language] = self._initialize_transaction_group()

                type_data_agg = account_credits_summary_struct["by_type"][custom_language]
                type_data_agg["percent"] += percent # Assuming percentOfTotal is directly usable
                type_data_agg["amount"] += amount
                type_data_agg["count"] += count
                type_data_agg["min_amount"] = min(type_data_agg["min_amount"], min_amount_txn) if min_amount_txn is not None else type_data_agg["min_amount"]
                type_data_agg["max_amount"] = max(type_data_agg["max_amount"], max_amount_txn) if max_amount_txn is not None else type_data_agg["max_amount"]
                type_data_agg["min_date"] = compare_dates(min_date_txn, type_data_agg["min_date"], mode='earliest')
                type_data_agg["max_date"] = compare_dates(max_date_txn, type_data_agg["max_date"], mode='latest')

                # Aggregate data for overall credits for this account
                # Note: total_percent for account might become > 100 if summing 'percentOfTotal' directly.
                # This needs clarification: is 'percentOfTotal' of *this account's* total credits, or global?
                # Assuming 'percentOfTotal' is of this account's total credits, so summing them for account_credits_summary_struct["total_percent"] is okay.
                account_credits_summary_struct["total_percent"] += percent
                account_credits_summary_struct["total_amount"] += amount
                account_credits_summary_struct["total_transactions"] += count
                account_credits_summary_struct["min_amount"] = min(account_credits_summary_struct["min_amount"], min_amount_txn) if min_amount_txn is not None else account_credits_summary_struct["min_amount"]
                account_credits_summary_struct["max_amount"] = max(account_credits_summary_struct["max_amount"], max_amount_txn) if max_amount_txn is not None else account_credits_summary_struct["max_amount"]
                account_credits_summary_struct["earliest_date"] = compare_dates(min_date_txn, account_credits_summary_struct["earliest_date"], mode='earliest')
                account_credits_summary_struct["latest_date"] = compare_dates(max_date_txn, account_credits_summary_struct["latest_date"], mode='latest')

                # Aggregate data for global credit totals across all accounts
                global_credits_summary = activity_summary["totals"]["credits"]
                # global_credits_summary["total_percent"] += percent # This is problematic as percent is relative to account total. Recalculate later if needed.
                global_credits_summary["total_amount"] += amount
                global_credits_summary["total_transactions"] += count
                global_credits_summary["min_amount"] = min(global_credits_summary["min_amount"], min_amount_txn) if min_amount_txn is not None else global_credits_summary["min_amount"]
                global_credits_summary["max_amount"] = max(global_credits_summary["max_amount"], max_amount_txn) if max_amount_txn is not None else global_credits_summary["max_amount"]
                global_credits_summary["earliest_date"] = compare_dates(min_date_txn, global_credits_summary["earliest_date"], mode='earliest')
                global_credits_summary["latest_date"] = compare_dates(max_date_txn, global_credits_summary["latest_date"], mode='latest')

            # Process debits for this account (similar logic to credits)
            debits_by_type_data = account_activity_summary.get("debitsByType", [])
            for debit_item in debits_by_type_data:
                custom_language = debit_item.get("type", "")
                percent = to_float(debit_item.get("percentOfTotal", 0))
                amount = to_float(debit_item.get("totalAmount", 0))
                count = to_int(debit_item.get("transactionCount", 0))
                min_amount_txn = to_float(debit_item.get("minTransactionAmount", 0))
                max_amount_txn = to_float(debit_item.get("maxTransactionAmount", 0))
                min_date_txn = debit_item.get("minTransactionDate", "")
                max_date_txn = debit_item.get("maxTransactionDate", "")

                account_debits_summary_struct = activity_summary["accounts"][account_num]["debits"]
                if custom_language not in account_debits_summary_struct["by_type"]:
                    account_debits_summary_struct["by_type"][custom_language] = self._initialize_transaction_group()

                type_data_agg = account_debits_summary_struct["by_type"][custom_language]
                type_data_agg["percent"] += percent
                type_data_agg["amount"] += amount
                type_data_agg["count"] += count
                type_data_agg["min_amount"] = min(type_data_agg["min_amount"], min_amount_txn) if min_amount_txn is not None else type_data_agg["min_amount"]
                type_data_agg["max_amount"] = max(type_data_agg["max_amount"], max_amount_txn) if max_amount_txn is not None else type_data_agg["max_amount"]
                type_data_agg["min_date"] = compare_dates(min_date_txn, type_data_agg["min_date"], mode='earliest')
                type_data_agg["max_date"] = compare_dates(max_date_txn, type_data_agg["max_date"], mode='latest')

                account_debits_summary_struct["total_percent"] += percent
                account_debits_summary_struct["total_amount"] += amount
                account_debits_summary_struct["total_transactions"] += count
                account_debits_summary_struct["min_amount"] = min(account_debits_summary_struct["min_amount"], min_amount_txn) if min_amount_txn is not None else account_debits_summary_struct["min_amount"]
                account_debits_summary_struct["max_amount"] = max(account_debits_summary_struct["max_amount"], max_amount_txn) if max_amount_txn is not None else account_debits_summary_struct["max_amount"]
                account_debits_summary_struct["earliest_date"] = compare_dates(min_date_txn, account_debits_summary_struct["earliest_date"], mode='earliest')
                account_debits_summary_struct["latest_date"] = compare_dates(max_date_txn, account_debits_summary_struct["latest_date"], mode='latest')

                global_debits_summary = activity_summary["totals"]["debits"]
                # global_debits_summary["total_percent"] += percent # Problematic, recalculate later if needed.
                global_debits_summary["total_amount"] += amount
                global_debits_summary["total_transactions"] += count
                global_debits_summary["min_amount"] = min(global_debits_summary["min_amount"], min_amount_txn) if min_amount_txn is not None else global_debits_summary["min_amount"]
                global_debits_summary["max_amount"] = max(global_debits_summary["max_amount"], max_amount_txn) if max_amount_txn is not None else global_debits_summary["max_amount"]
                global_debits_summary["earliest_date"] = compare_dates(min_date_txn, global_debits_summary["earliest_date"], mode='earliest')
                global_debits_summary["latest_date"] = compare_dates(max_date_txn, global_debits_summary["latest_date"], mode='latest')

        # Recalculate total percentages for global credit/debit summaries if they are meaningful
        # This requires knowing the grand total of all credits and all debits across all accounts.
        # For now, the `total_percent` in `activity_summary.totals.credits/debits` will be the sum of account-level percentages, which is not ideal.
        # A better approach would be to sum all type_data_agg["amount"] for credits (and debits) within each account,
        # then if global_credits_summary["total_amount"] > 0, recalculate each type_data_agg["percent"] for global display.
        # However, the current structure stores 'percent' at the type level within each account.
        # The 'total_percent' at the global level might be best removed or explicitly defined as sum of account percents.

        # Clean up infinity values for min_amount
        if activity_summary["totals"]["credits"]["min_amount"] == float('inf'):
            activity_summary["totals"]["credits"]["min_amount"] = 0
        if activity_summary["totals"]["debits"]["min_amount"] == float('inf'):
            activity_summary["totals"]["debits"]["min_amount"] = 0

        for account_num_key in activity_summary["accounts"]:
            if activity_summary["accounts"][account_num_key]["credits"]["min_amount"] == float('inf'):
                activity_summary["accounts"][account_num_key]["credits"]["min_amount"] = 0
            if activity_summary["accounts"][account_num_key]["debits"]["min_amount"] == float('inf'):
                activity_summary["accounts"][account_num_key]["debits"]["min_amount"] = 0
            # Also clean up min_amount in by_type if needed (though _initialize_transaction_group sets it)
            for credit_type in activity_summary["accounts"][account_num_key]["credits"]["by_type"].values():
                if credit_type["min_amount"] == float('inf'): credit_type["min_amount"] = 0
            for debit_type in activity_summary["accounts"][account_num_key]["debits"]["by_type"].values():
                if debit_type["min_amount"] == float('inf'): debit_type["min_amount"] = 0

        return activity_summary
    
    def _get_counterparties(self) -> Dict[str, Any]:
        """
        Get counterparties data.
        NOTE: The new standardized JSON structure (as of the current understanding)
        does not provide pre-aggregated counterparty data in the same way as the old
        'full_data' structure. This method will return an initialized empty structure.
        Deriving counterparty data from raw transactions would be a new feature.
        
        Returns:
            Dict: Initialized counterparties data structure.
        """
        counterparties = {
            "accounts": {}, # Will remain empty for now
            "totals": {
                "credits": self._initialize_summary_dict(), # Will remain at initial values
                "debits": self._initialize_summary_dict()  # Will remain at initial values
            }
        }
        
        logger.info(
            "_get_counterparties: Standardized case data does not currently provide pre-aggregated counterparty summaries. "
            "Returning empty initialized structure. Downstream processing should handle this."
        )

        # Example of how one might initialize per-account structures if they were to be populated:
        # accounts_in_case = self.case_data.get("accounts", [])
        # for acc_item in accounts_in_case:
        #     acc_num = str(acc_item.get("accountKey", ""))
        #     if acc_num and acc_num not in counterparties["accounts"]:
        #         counterparties["accounts"][acc_num] = {
        #             "credits": self._initialize_summary_dict(),
        #             "debits": self._initialize_summary_dict()
        #         }
        #         counterparties["accounts"][acc_num]["credits"]["parties"] = {}
        #         counterparties["accounts"][acc_num]["debits"]["parties"] = {}

        # Clean up infinity values that were set by _initialize_summary_dict
        if counterparties["totals"]["credits"]["min_amount"] == float('inf'):
            counterparties["totals"]["credits"]["min_amount"] = 0
        if counterparties["totals"]["debits"]["min_amount"] == float('inf'):
            counterparties["totals"]["debits"]["min_amount"] = 0

        # If accounts were to be populated, similar cleanup for each account would be needed here.
        # for account_num_key in counterparties["accounts"]:
        #     if counterparties["accounts"][account_num_key]["credits"]["min_amount"] == float('inf'):
        #         counterparties["accounts"][account_num_key]["credits"]["min_amount"] = 0
        #     if counterparties["accounts"][account_num_key]["debits"]["min_amount"] == float('inf'):
        #         counterparties["accounts"][account_num_key]["debits"]["min_amount"] = 0
        
        return counterparties
    
    def _get_transaction_details(self) -> Dict[str, Any]:
        """
        Get transaction details with calculations grouped by transaction type (custom_language),
        sourced from `self.case_data.transactions.all`.
        
        Returns:
            Dict: Transaction details data.
        """
        transaction_details = {
            "by_type": {},
            "credits": {"total_amount": 0, "total_transactions": 0},
            "debits": {"total_amount": 0, "total_transactions": 0},
            "grand_total": 0,
            "transaction_count": 0
        }

        all_transactions = self.case_data.get("transactions", {}).get("all", [])
        if not all_transactions:
            logger.info("No transactions found in case_data.transactions.all for details processing.")
            return transaction_details

        for txn_item in all_transactions:
            account = str(txn_item.get("accountKey", ""))
            date = txn_item.get("date", "") # Assuming 'date' field exists
            # Assuming 'type' field indicates "Credit" or "Debit"
            debit_credit_indicator = txn_item.get("type", "").lower()
            amount = to_float(txn_item.get("amount", 0))
            # Using 'transactionType' as custom_language, fallback to 'description' if not present
            custom_language = txn_item.get("transactionType", txn_item.get("description", "N/A"))
            sender = txn_item.get("senderName", "") # Assuming new field name
            receiver = txn_item.get("receiverName", "") # Assuming new field name
            memo = txn_item.get("description", "") # Using description as memo if specific memo field is absent

            is_credit = debit_credit_indicator == "credit" # Standardize to 'credit' or 'debit'

            if custom_language not in transaction_details["by_type"]:
                transaction_details["by_type"][custom_language] = self._initialize_transaction_group(for_details=True)

            type_data_agg = transaction_details["by_type"][custom_language]
            if is_credit:
                type_data_agg["credits"]["amount"] += amount
                type_data_agg["credits"]["count"] += 1
            else: # Assumed to be debit if not credit
                type_data_agg["debits"]["amount"] += amount
                type_data_agg["debits"]["count"] += 1

            type_data_agg["total"] += amount
            type_data_agg["count"] += 1

            if len(type_data_agg["examples"]) < 3:
                type_data_agg["examples"].append({
                    "account": account,
                    "date": date,
                    "amount": amount,
                    "is_credit": is_credit,
                    "sender": sender,
                    "receiver": receiver,
                    "memo": memo # Ensure this 'memo' aligns with what NarrativeGenerator expects
                })

            if is_credit:
                transaction_details["credits"]["total_amount"] += amount
                transaction_details["credits"]["total_transactions"] += 1
            else:
                transaction_details["debits"]["total_amount"] += amount
                transaction_details["debits"]["total_transactions"] += 1

            transaction_details["grand_total"] += amount
            transaction_details["transaction_count"] += 1

        return transaction_details
    
    def _process_transaction_sample_list(self, sample_list: List[Dict[str, Any]], sample_name: str) -> Dict[str, Any]:
        """
        Helper function to process a list of transaction samples (e.g., unusual, CTA, BIP).
        
        Args:
            sample_list: List of transaction items from the case data.
            sample_name: Name of the sample being processed (for logging).

        Returns:
            Dict: Processed transaction sample data.
        """
        processed_sample = {
            "by_type": {},
            "credits": {"total_amount": 0, "total_transactions": 0},
            "debits": {"total_amount": 0, "total_transactions": 0},
            "grand_total": 0,
            "transaction_count": 0,
            "earliest_date": None,
            "latest_date": None
        }

        if not sample_list:
            logger.info(f"No transactions found in {sample_name} sample list.")
            return processed_sample

        for txn_item in sample_list:
            account = str(txn_item.get("accountKey", ""))
            date = txn_item.get("date", "")
            debit_credit_indicator = txn_item.get("type", "").lower()
            amount = to_float(txn_item.get("amount", 0))
            custom_language = txn_item.get("transactionType", txn_item.get("description", "N/A"))
            sender = txn_item.get("senderName", "")
            receiver = txn_item.get("receiverName", "")
            memo = txn_item.get("description", "")

            is_credit = debit_credit_indicator == "credit"

            if custom_language not in processed_sample["by_type"]:
                processed_sample["by_type"][custom_language] = self._initialize_transaction_group(for_unusual=True)

            type_data_agg = processed_sample["by_type"][custom_language]
            if is_credit:
                type_data_agg["credits"]["amount"] += amount
                type_data_agg["credits"]["count"] += 1
            else:
                type_data_agg["debits"]["amount"] += amount
                type_data_agg["debits"]["count"] += 1

            type_data_agg["total"] += amount
            type_data_agg["count"] += 1
            type_data_agg["earliest_date"] = compare_dates(date, type_data_agg["earliest_date"], mode='earliest')
            type_data_agg["latest_date"] = compare_dates(date, type_data_agg["latest_date"], mode='latest')

            if len(type_data_agg["examples"]) < 3:
                example_data = {
                    "account": account,
                    "date": date,
                    "amount": amount,
                    "is_credit": is_credit,
                    "memo": memo # Generic memo for all sample types
                }
                # Add sender/receiver only if it's not a CTA/BIP sample where it might be less relevant
                # or if the specific sample type needs it. For unusual_activity, it's often relevant.
                if sample_name == "unusualActivitySample": # Or a more generic condition
                    example_data["sender"] = sender
                    example_data["receiver"] = receiver
                type_data_agg["examples"].append(example_data)

            if is_credit:
                processed_sample["credits"]["total_amount"] += amount
                processed_sample["credits"]["total_transactions"] += 1
            else:
                processed_sample["debits"]["total_amount"] += amount
                processed_sample["debits"]["total_transactions"] += 1

            processed_sample["grand_total"] += amount
            processed_sample["transaction_count"] += 1
            processed_sample["earliest_date"] = compare_dates(date, processed_sample["earliest_date"], mode='earliest')
            processed_sample["latest_date"] = compare_dates(date, processed_sample["latest_date"], mode='latest')

        return processed_sample

    def _get_unusual_activity(self) -> Dict[str, Any]:
        """
        Get unusual activity, sourced from `self.case_data.transactions.unusualActivitySample`.
        """
        unusual_activity_list = self.case_data.get("transactions", {}).get("unusualActivitySample", [])
        return self._process_transaction_sample_list(unusual_activity_list, "unusualActivitySample")
    
    def _get_cta_sample(self) -> Dict[str, Any]:
        """
        Get CTA sample data, sourced from `self.case_data.transactions.ctaSample`.
        """
        cta_sample_list = self.case_data.get("transactions", {}).get("ctaSample", [])
        # For CTA/BIP, sender/receiver might be less emphasized in examples by default
        # The helper _process_transaction_sample_list adds sender/receiver for "unusualActivitySample"
        return self._process_transaction_sample_list(cta_sample_list, "ctaSample")
    
    def _get_bip_sample(self) -> Dict[str, Any]:
        """
        Get BIP sample data, sourced from `self.case_data.transactions.bipSample`.
        """
        bip_sample_list = self.case_data.get("transactions", {}).get("bipSample", [])
        return self._process_transaction_sample_list(bip_sample_list, "bipSample")
    
    def get_alert_summary_data(self) -> Dict[str, Any]:
        """
        Get data for Section 1 - Alert Summary, adapted for new case_data structure.
        
        Returns:
            Dict: Combined data for alert summary
        """
        summary_data = {}
        case_info_data = self.case_data.get("caseInfo", {})
        accounts_list = self.case_data.get("accounts", [])
        primary_account_info = accounts_list[0] if accounts_list else {}

        summary_data["case_number"] = case_info_data.get("caseNumber", "")
        summary_data["alert_info"] = self.case_data.get("alerts", []) # Uses the main alerts list

        # Map relevant fields from the first account to the old "account_info" structure
        summary_data["account_info"] = {
            "account_number": primary_account_info.get("accountKey", ""),
            "account_type": ", ".join(primary_account_info.get("accountTypes", [])), # Assuming accountTypes is a list
            "account_title": primary_account_info.get("accountTitle", ""),
            "open_date": primary_account_info.get("openingDate", ""),
            "status": primary_account_info.get("statusDescription", "")
            # Add other fields if they were part of the old account_info and are needed
        }
        
        # Uses the processed subjects from transaction_data for consistency
        summary_data["subjects"] = self.transaction_data.get("subjects", [])
        
        summary_data["activity_summary"] = self.transaction_data.get("activity_summary", {})
        
        return summary_data
    
    def get_investigation_summary_data(self) -> Dict[str, Any]:
        """
        Get data for Section 4 - Summary of Investigation, adapted for new case_data structure.
        
        Returns:
            Dict: Combined data for investigation summary
        """
        investigation_data = {}
        accounts_list = self.case_data.get("accounts", [])
        primary_account_info = accounts_list[0] if accounts_list else {}

        investigation_data["account_info"] = {
            "account_number": primary_account_info.get("accountKey", ""),
            "account_type": ", ".join(primary_account_info.get("accountTypes", [])),
            "account_title": primary_account_info.get("accountTitle", ""),
        }
        
        investigation_data["subjects"] = self.transaction_data.get("subjects", [])
        investigation_data["transactions"] = self.transaction_data.get("transactions", {})
        investigation_data["counterparties"] = self.transaction_data.get("counterparties", {})
        investigation_data["activity_summary"] = self.transaction_data.get("activity_summary", {})
        
        return investigation_data
    
    def get_conclusion_data(self) -> Dict[str, Any]:
        """
        Get data for Section 6 - Conclusion, adapted for new case_data structure.
        
        Returns:
            Dict: Combined data for conclusion
        """
        conclusion_data = {}
        case_info_data = self.case_data.get("caseInfo", {})
        accounts_list = self.case_data.get("accounts", [])
        primary_account_info = accounts_list[0] if accounts_list else {}

        conclusion_data["case_number"] = case_info_data.get("caseNumber", "")
        conclusion_data["account_info"] = {
            "account_number": primary_account_info.get("accountKey", ""),
            # Add other relevant fields if needed by conclusion template
        }
        
        conclusion_data["subjects"] = self.transaction_data.get("subjects", [])
        conclusion_data["unusual_activity"] = self.transaction_data.get("unusual_activity", {})
        conclusion_data["scope_of_review"] = self.transaction_data.get("scope_of_review", {})
        
        return conclusion_data
    
    def get_referral_data(self) -> Dict[str, Any]:
        """
        Get data for Section 2 - Referral, adapted for new case_data structure.
        
        Returns:
            Dict: Combined data for referral
        """
        referral_data = {}
        accounts_list = self.case_data.get("accounts", [])
        primary_account_info = accounts_list[0] if accounts_list else {}

        referral_data["account_info"] = {
            "account_number": primary_account_info.get("accountKey", ""),
            "account_title": primary_account_info.get("accountTitle", ""),
            # Add other relevant fields if needed
        }
        
        referral_data["subjects"] = self.transaction_data.get("subjects", [])
        referral_data["cta_sample"] = self.transaction_data.get("cta_sample", {})
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
        case_info_data = self.case_data.get("caseInfo", {})
        summary["alertInfo"]["caseNumber"] = case_info_data.get("caseNumber", "")

        # Get account information (assuming primary/first account is the alerting account context here)
        accounts_list = self.case_data.get("accounts", [])
        primary_account_info = accounts_list[0] if accounts_list else {}
        
        account_type_str = ", ".join(primary_account_info.get("accountTypes", []))
        account_number_str = primary_account_info.get("accountKey", "")
        
        summary["account"] = account_number_str
        summary["alertInfo"]["alertingAccounts"] = f"{account_type_str} {account_number_str}".strip()
        
        # Extract alert months and descriptions from the main alerts list
        alert_info_list = self.case_data.get("alerts", [])
        alert_months = []
        alert_descriptions = []
        
        for alert in alert_info_list: # Iterating the main alerts list
            if isinstance(alert, dict):
                # Assuming new alert structure has 'alertMonth' and 'description'
                if alert.get("alertMonth"):
                    alert_months.append(str(alert.get("alertMonth")))
                if alert.get("description"):
                    alert_descriptions.append(str(alert.get("description")))
        
        summary["alertInfo"]["alertingMonths"] = ", ".join(list(set(alert_months))) if alert_months else ""
        summary["alertInfo"]["alertDescription"] = "; ".join(list(set(alert_descriptions))) if alert_descriptions else ""
        
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