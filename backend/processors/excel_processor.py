"""
Excel processor for extracting transaction data from Excel files
"""
import pandas as pd
import numpy as np
from datetime import datetime
import re
from typing import Dict, List, Any, Optional, Tuple
import os
from backend.utils.math_utils import safe_divide
from backend.utils.logger import get_logger
logger = get_logger(__name__)

class ExcelProcessor:
    """Processes transaction Excel files to extract relevant data for SAR narratives"""
    
    def __init__(self, file_path: str):
        """
        Initialize with path to Excel file
        
        Args:
            file_path: Path to Excel file with transaction data
        """
        self.file_path = file_path
        self.workbook = None
        self.sheets = {}
        self.data = {
            "activity_summary": {},
            "unusual_activity": {"summary": {}, "transactions": []},
            "cta_sample": {"summary": {}, "transactions": []},
            "bip_sample": {"summary": {}, "transactions": []},
            "transaction_summary": {},
            "account_summaries": {},
            "inter_account_transfers": []
        }
    
    def load_workbook(self) -> bool:
        """
        Load the Excel workbook
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if file exists first
            if not os.path.exists(self.file_path):
                logger.error(f"File does not exist: {self.file_path}")
                return False
                
            # Try to read all sheets in the workbook
            xlsx = pd.ExcelFile(self.file_path)
            sheet_names = xlsx.sheet_names
            
            # Load all sheets
            for sheet_name in sheet_names:
                # Simply load all sheets with original names
                try:
                    self.sheets[sheet_name] = pd.read_excel(xlsx, sheet_name)
                    logger.info(f"Loaded sheet: {sheet_name}")
                except Exception as e:
                    logger.warning(f"Failed to load sheet {sheet_name}: {str(e)}")
            
            logger.info(f"Successfully loaded workbook: {os.path.basename(self.file_path)}")
            logger.info(f"Found sheets: {list(self.sheets.keys())}")
            return True
        except Exception as e:
            logger.error(f"Error loading Excel file: {str(e)}")
            return False
    
    def _access_cell(self, row, col_idx):
        """
        Safely access a cell using positional indexing
        
        Args:
            row: DataFrame row
            col_idx: Column index
            
        Returns:
            Cell value or None if invalid
        """
        try:
            if col_idx < len(row):
                return row.iloc[col_idx]
            return None
        except:
            return None

    def _find_header_row(self, df, header_keywords):
        """
        Find header row containing specified keywords
        
        Args:
            df: DataFrame to search
            header_keywords: List of keywords to look for
            
        Returns:
            tuple: (header_row_idx, header_cols_map) or (None, None)
        """
        for idx, row in df.iterrows():
            # Skip rows with too few non-null values (probably not a header)
            if row.count() < 3:
                continue
                
            # Convert row to string values and join
            row_values = [str(val).lower() for val in row if not pd.isna(val)]
            row_text = ' '.join(row_values)
            
            # Check if any pair of keywords exists in the row
            keyword_pairs = [(k1, k2) for k1 in header_keywords for k2 in header_keywords if k1 != k2]
            if any(k1 in row_text and k2 in row_text for k1, k2 in keyword_pairs):
                # Found header row, now map column indices
                header_cols = {}
                
                for i in range(len(row)):
                    cell_value = self._access_cell(row, i)
                    if pd.isna(cell_value):
                        continue
                    
                    cell_text = str(cell_value).lower()
                    
                    # Map common column types
                    if any(kw in cell_text for kw in ['account', 'acct']):
                        header_cols['account'] = i
                    elif any(kw in cell_text for kw in ['transaction date', 'date']):
                        header_cols['date'] = i
                    elif any(kw in cell_text for kw in ['debit/credit', 'dr/cr']):
                        header_cols['debit_credit'] = i
                    elif any(kw in cell_text for kw in ['amount', 'sum']):
                        header_cols['amount'] = i
                    elif any(kw in cell_text for kw in ['custom language', 'category', 'type']):
                        header_cols['custom_language'] = i
                    elif any(kw in cell_text for kw in ['description', 'memo', 'note']):
                        header_cols['description'] = i
                
                # Only return if we found essential columns
                if 'date' in header_cols or 'amount' in header_cols:
                    return idx, header_cols
        
        return None, None
    
    def process_activity_summary(self) -> Dict[str, Any]:
        """
        Process Activity Summary tab
        
        Returns:
            Dict: Extracted activity summary data
        """
        # Look in all sheets for any that might contain activity summary
        activity_summary = {
            "total_amount": 0.0,
            "start_date": None,
            "end_date": None,
            "transaction_types": [],
            "description": "",
            "indicators": []
        }
        
        for sheet_name, df in self.sheets.items():
            # Skip if sheet is too small
            if df.shape[0] < 5 or df.shape[1] < 5:
                continue
                
            # Look for key terms in the first 10 rows
            found_activity_summary = False
            total_amount_found = False
            for idx, row in df.iloc[:10].iterrows():
                row_text = ' '.join([str(val) for val in row if not pd.isna(val)]).lower()
                if 'activity summary' in row_text or 'total amount' in row_text or 'transaction summary' in row_text:
                    found_activity_summary = True
                    
                    # Try to extract total amount
                    total_amount_pattern = r'(?:total amount|total suspicious amount|amount).*?[$]?([0-9,.]+)'
                    match = re.search(total_amount_pattern, row_text)
                    if match:
                        try:
                            total_amount = float(match.group(1).replace(',', ''))
                            activity_summary["total_amount"] = total_amount
                            total_amount_found = True
                        except:
                            pass
            
            if found_activity_summary:
                logger.info(f"Found activity summary in sheet: {sheet_name}")
                
                # Look for date range
                for idx, row in df.iterrows():
                    row_text = ' '.join([str(val) for val in row if not pd.isna(val)]).lower()
                    date_range_pattern = r'(?:date range|period).*?(\d{1,2}/\d{1,2}/\d{2,4}).*?(\d{1,2}/\d{1,2}/\d{2,4})'
                    match = re.search(date_range_pattern, row_text)
                    if match:
                        activity_summary["start_date"] = match.group(1)
                        activity_summary["end_date"] = match.group(2)
                        break
                
                # If sheet had activity summary data, break from loop
                if total_amount_found or activity_summary["start_date"]:
                    break
        
        # If no date range found, try to find dates from actual transaction data
        if not activity_summary["start_date"] or not activity_summary["end_date"]:
            all_dates = []
            for sheet_name, df in self.sheets.items():
                header_row_idx, header_cols = self._find_header_row(df, ['date', 'transaction'])
                if header_row_idx is not None and 'date' in header_cols:
                    for row_idx in range(header_row_idx + 1, len(df)):
                        row = df.iloc[row_idx]
                        date_value = self._access_cell(row, header_cols['date'])
                        if not pd.isna(date_value):
                            try:
                                if isinstance(date_value, datetime):
                                    all_dates.append(date_value)
                                else:
                                    # Try to parse string date
                                    date_str = str(date_value)
                                    for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y']:
                                        try:
                                            date_obj = datetime.strptime(date_str, fmt)
                                            all_dates.append(date_obj)
                                            break
                                        except:
                                            pass
                            except:
                                pass
            
            if all_dates:
                # Set start and end dates from transaction dates
                start_date = min(all_dates).strftime('%m/%d/%Y')
                end_date = max(all_dates).strftime('%m/%d/%Y')
                
                if not activity_summary["start_date"]:
                    activity_summary["start_date"] = start_date
                if not activity_summary["end_date"]:
                    activity_summary["end_date"] = end_date
        
        return activity_summary
    
    def process_all_transactions(self) -> Dict[str, Any]:
        """
        Process all transaction data across sheets
        
        Returns:
            Dict: All transactions and summaries
        """
        # Find all transaction data across all sheets
        transactions_result = {
            "all_transactions": [],
            "account_transactions": {},
            "transaction_types": [],
            "summary": {
                "total_credits": 0.0,
                "total_debits": 0.0,
                "total_amount": 0.0,
                "transaction_count": 0
            }
        }
        
        # Process each sheet
        for sheet_name, df in self.sheets.items():
            # Skip if sheet is too small
            if df.shape[0] < 5 or df.shape[1] < 3:
                continue
                
            # Find header row for transactions
            header_keywords = ['account', 'date', 'amount', 'transaction', 'debit', 'credit']
            header_row_idx, header_cols = self._find_header_row(df, header_keywords)
            
            if header_row_idx is not None:
                logger.info(f"Found transaction data in sheet: {sheet_name}")
                
                # Process transactions from this sheet
                sheet_transactions = []
                
                for row_idx in range(header_row_idx + 1, len(df)):
                    row = df.iloc[row_idx]
                    
                    # Skip rows without essential data
                    date_value = self._access_cell(row, header_cols.get('date')) if 'date' in header_cols else None
                    amount_value = self._access_cell(row, header_cols.get('amount')) if 'amount' in header_cols else None
                    
                    if pd.isna(date_value) and pd.isna(amount_value):
                        continue
                    
                    # Basic transaction data
                    transaction = {
                        "source_sheet": sheet_name
                    }
                    
                    # Extract date
                    if 'date' in header_cols and not pd.isna(date_value):
                        transaction["date"] = date_value
                        # Format date if needed
                        if isinstance(transaction["date"], datetime):
                            transaction["date"] = transaction["date"].strftime('%m/%d/%Y')
                    
                    # Extract amount (this is critical - only add to all_transactions if we have an amount)
                    if 'amount' in header_cols and not pd.isna(amount_value):
                        amount_value = self._parse_amount(amount_value)
                        if amount_value != 0:  # Skip zero amounts
                            transaction["amount"] = amount_value
                        else:
                            continue  # Skip this transaction if amount is zero
                    else:
                        continue  # Skip this transaction if no amount
                    
                    # Extract account
                    if 'account' in header_cols:
                        account_value = self._access_cell(row, header_cols['account'])
                        if not pd.isna(account_value):
                            transaction["account"] = str(account_value)
                    
                    # Extract debit/credit indicator
                    if 'debit_credit' in header_cols:
                        dc_value = self._access_cell(row, header_cols['debit_credit'])
                        if not pd.isna(dc_value):
                            transaction["debit_credit"] = str(dc_value)
                            # Determine if credit transaction
                            is_credit = str(dc_value).lower() in ['credit', 'cr', 'c', '+']
                            transaction["is_credit"] = is_credit
                    
                    # Extract description or memo
                    if 'description' in header_cols:
                        desc_value = self._access_cell(row, header_cols['description'])
                        if not pd.isna(desc_value):
                            transaction["description"] = str(desc_value)
                    
                    # Extract transaction type or custom language
                    if 'custom_language' in header_cols:
                        cl_value = self._access_cell(row, header_cols['custom_language'])
                        if not pd.isna(cl_value):
                            transaction["custom_language"] = str(cl_value)
                            
                            # Add to transaction types list
                            txn_type = str(cl_value)
                            if txn_type not in transactions_result["transaction_types"]:
                                transactions_result["transaction_types"].append(txn_type)
                    
                    # Now that we've verified this transaction has an amount, add it to our results
                    sheet_transactions.append(transaction)
                    transactions_result["all_transactions"].append(transaction)
                    
                    # Update summary data
                    amount = transaction["amount"]  # We know this exists now
                    transactions_result["summary"]["total_amount"] += amount
                    
                    if transaction.get("is_credit", False):
                        transactions_result["summary"]["total_credits"] += amount
                    else:
                        transactions_result["summary"]["total_debits"] += amount
                    
                    transactions_result["summary"]["transaction_count"] += 1
                    
                    # Group by account
                    if "account" in transaction:
                        account = transaction["account"]
                        if account not in transactions_result["account_transactions"]:
                            transactions_result["account_transactions"][account] = []
                        
                        transactions_result["account_transactions"][account].append(transaction)
                
                logger.info(f"Extracted {len(sheet_transactions)} transactions from sheet: {sheet_name}")
        
        # Summarize account transactions
        account_summaries = {}
        
        for account, txns in transactions_result["account_transactions"].items():
            account_summary = {
                "total_credits": sum(t.get("amount", 0) for t in txns if t.get("is_credit", False)),
                "total_debits": sum(t.get("amount", 0) for t in txns if not t.get("is_credit", False)),
                "total_amount": sum(t.get("amount", 0) for t in txns),
                "transaction_count": len(txns),
                "transactions_by_type": {}
            }
            
            # Group by transaction type
            for txn in txns:
                txn_type = txn.get("custom_language", "Other")
                if txn_type not in account_summary["transactions_by_type"]:
                    account_summary["transactions_by_type"][txn_type] = {
                        "count": 0,
                        "total": 0.0,
                        "credits": 0.0,
                        "debits": 0.0
                    }
                
                amount = txn["amount"]
                type_summary = account_summary["transactions_by_type"][txn_type]
                type_summary["count"] += 1
                type_summary["total"] += amount
                
                if txn.get("is_credit", False):
                    type_summary["credits"] += amount
                else:
                    type_summary["debits"] += amount
            
            # Add transaction type summary
            for txn in txns:
                if "amount" not in txn:
                    continue
                    
                txn_type = txn.get("custom_language", "Other")
                if txn_type not in account_summary["transactions_by_type"]:
                    account_summary["transactions_by_type"][txn_type] = {
                        "count": 0,
                        "total": 0.0,
                        "credits": 0.0,
                        "debits": 0.0
                    }
                
                type_summary = account_summary["transactions_by_type"][txn_type]
                type_summary["count"] += 1
                type_summary["total"] += txn["amount"]
                
                if txn.get("is_credit", False):
                    type_summary["credits"] += txn["amount"]
                else:
                    type_summary["debits"] += txn["amount"]
            
            # Assign to account summaries
            account_summaries[account] = account_summary
        
        # Categorize transactions by type
        category_summary = self._summarize_by_transaction_category(transactions_result["all_transactions"])
        transactions_result["category_summary"] = category_summary
        
        # Set global account summaries
        self.data["account_summaries"] = account_summaries
        
        return transactions_result
    
    def _parse_amount(self, amount_value: Any) -> float:
        """
        Parse amount value to float
        
        Args:
            amount_value: Amount value to parse
            
        Returns:
            float: Parsed amount
        """
        if pd.isna(amount_value):
            return 0.0
        
        if isinstance(amount_value, (int, float)):
            return float(amount_value)
        
        # Handle string values with $ and commas
        if isinstance(amount_value, str):
            # Remove $ and commas
            cleaned = amount_value.replace('$', '').replace(',', '')
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        
        return 0.0
    
    def _summarize_by_transaction_category(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Summarize transactions by category
        
        Args:
            transactions: List of transaction dictionaries
            
        Returns:
            Dict: Summary of transaction data
        """
        # Prepare summary structure
        summary = {
            "categories": [],
            "total_credits": 0,
            "total_debits": 0,
            "total_credit_transactions": 0,
            "total_debit_transactions": 0
        }
        
        # Filter transactions with amount field
        valid_transactions = [t for t in transactions if "amount" in t]
        if not valid_transactions:
            logger.warning("No transactions with amount field found for summary")
            return summary
        
        # Group by category and debit/credit
        grouped_data = {}
        
        for transaction in valid_transactions:
            amount = transaction["amount"]
            
            # Determine category
            category = transaction.get("custom_language", "Other")
            if not category:
                category = "Other"
            
            # Determine if credit or debit
            is_credit = False
            if "is_credit" in transaction:
                is_credit = transaction["is_credit"]
            elif "debit_credit" in transaction:
                is_credit = transaction["debit_credit"].lower() in ['credit', 'cr', 'c', '+']
            
            # Initialize category if not exists
            if category not in grouped_data:
                grouped_data[category] = {
                    "credit_amount": 0,
                    "debit_amount": 0,
                    "credit_count": 0,
                    "debit_count": 0
                }
            
            # Add to totals
            if is_credit:
                grouped_data[category]["credit_amount"] += amount
                grouped_data[category]["credit_count"] += 1
                summary["total_credits"] += amount
                summary["total_credit_transactions"] += 1
            else:
                grouped_data[category]["debit_amount"] += amount
                grouped_data[category]["debit_count"] += 1
                summary["total_debits"] += amount
                summary["total_debit_transactions"] += 1
        
        # Format the categories for output
        for category, data in grouped_data.items():
            summary["categories"].append({
                "Custom Language Transaction Category": category,
                "Credits ($ Total)": data["credit_amount"],
                "Debits ($ Total)": data["debit_amount"],
                "Credits (# Transactions)": data["credit_count"],
                "Debits (# Transactions)": data["debit_count"]
            })
        
        return summary
    
    def _identify_inter_account_transfers(self, all_transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify transfers between accounts
        
        Args:
            all_transactions: List of all transactions
            
        Returns:
            List: Identified inter-account transfers
        """
        # Get unique accounts
        accounts = set()
        for txn in all_transactions:
            if "account" in txn:
                accounts.add(txn["account"])
        
        # Skip if only one account
        if len(accounts) <= 1:
            return []
        
        # Look for transfers
        transfers = []
        
        # Group transactions by date
        txns_by_date = {}
        for txn in all_transactions:
            if "date" not in txn or "amount" not in txn:
                continue
                
            date = txn["date"]
            if date not in txns_by_date:
                txns_by_date[date] = []
            
            txns_by_date[date].append(txn)
        
        # Look for pairs of transactions on the same day with opposite directions
        for date, date_txns in txns_by_date.items():
            if len(date_txns) < 2:
                continue
                
            # Find potential transfers
            for i, txn1 in enumerate(date_txns):
                amount1 = txn1.get("amount", 0)
                is_credit1 = txn1.get("is_credit", False)
                account1 = txn1.get("account", "")
                
                if not account1 or amount1 == 0:
                    continue
                
                # Look for matching opposite transaction
                for j, txn2 in enumerate(date_txns):
                    if i == j:
                        continue
                        
                    amount2 = txn2.get("amount", 0)
                    is_credit2 = txn2.get("is_credit", False)
                    account2 = txn2.get("account", "")
                    
                    if not account2 or account1 == account2:
                        continue
                    
                    # Check if amounts match and directions are opposite
                    if abs(amount1 - amount2) < 0.01 and is_credit1 != is_credit2:
                        # Found likely transfer
                        transfers.append({
                            "date": date,
                            "from_account": account1 if not is_credit1 else account2,
                            "to_account": account2 if not is_credit1 else account1,
                            "amount": amount1,
                            "description": txn1.get("description", "") or txn2.get("description", ""),
                            "custom_language": txn1.get("custom_language", "") or txn2.get("custom_language", "")
                        })
                        break
        
        return transfers
    
    def process(self) -> Dict[str, Any]:
        """
        Process all tabs in the workbook
        
        Returns:
            Dict: All extracted data from Excel file
        """
        if not self.load_workbook():
            return self.data
        
        # Process activity summary
        logger.info("Processing Activity Summary...")
        self.data["activity_summary"] = self.process_activity_summary()
        
        # Process all transaction data
        logger.info("Processing all transaction data...")
        transaction_results = self.process_all_transactions()
        
        # Store results in data structure
        self.data["unusual_activity"]["transactions"] = transaction_results["all_transactions"]
        self.data["unusual_activity"]["summary"] = {
            "total_amount": transaction_results["summary"]["total_amount"],
            "date_range": {
                "start": self.data["activity_summary"].get("start_date", ""),
                "end": self.data["activity_summary"].get("end_date", "")
            }
        }
        
        # Set transaction summary
        self.data["transaction_summary"] = {
            "total_credits": transaction_results["summary"]["total_credits"],
            "total_debits": transaction_results["summary"]["total_debits"],
            "transaction_count": transaction_results["summary"]["transaction_count"],
            "credit_breakdown": [],
            "debit_breakdown": []
        }
        
        # Format credit and debit breakdowns
        for category in transaction_results["category_summary"]["categories"]:
            category_name = category["Custom Language Transaction Category"]
            credit_amount = category["Credits ($ Total)"]
            debit_amount = category["Debits ($ Total)"]
            credit_count = category["Credits (# Transactions)"]
            debit_count = category["Debits (# Transactions)"]
            
            if credit_amount > 0:
                self.data["transaction_summary"]["credit_breakdown"].append({
                    "type": category_name,
                    "amount": credit_amount,
                    "count": credit_count,
                    "percent": safe_divide(credit_amount, transaction_results["summary"]["total_credits"], 0) * 100
                })
            
            if debit_amount > 0:
                self.data["transaction_summary"]["debit_breakdown"].append({
                    "type": category_name,
                    "amount": debit_amount,
                    "count": debit_count,
                    "percent": safe_divide(debit_amount, transaction_results["summary"]["total_debits"], 0) * 100
                })
        
        # Sort breakdowns
        self.data["transaction_summary"]["credit_breakdown"] = sorted(
            self.data["transaction_summary"]["credit_breakdown"], key=lambda x: x["amount"], reverse=True)
        self.data["transaction_summary"]["debit_breakdown"] = sorted(
            self.data["transaction_summary"]["debit_breakdown"], key=lambda x: x["amount"], reverse=True)
        
        # Identify inter-account transfers
        logger.info("Identifying inter-account transfers...")
        self.data["inter_account_transfers"] = self._identify_inter_account_transfers(transaction_results["all_transactions"])
        
        return self.data