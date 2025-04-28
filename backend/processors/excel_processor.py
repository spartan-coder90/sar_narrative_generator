"""
Excel processor for extracting transaction data from Excel files
"""
import pandas as pd
import numpy as np
from datetime import datetime
import re
from typing import Dict, List, Any, Optional
import os

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
            "unusual_activity": {},
            "cta_sample": {},
            "bip_sample": {}
        }
        
    def load_workbook(self) -> bool:
        """
        Load the Excel workbook
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Try to read all sheets in the workbook
            xlsx = pd.ExcelFile(self.file_path)
            sheet_names = xlsx.sheet_names
            
            # Load identified sheets
            for sheet_name in sheet_names:
                # Look for key sheets by checking partial matches
                sheet_key = None
                if "activity summ" in sheet_name.lower():
                    sheet_key = "activity_summary"
                elif "unusual" in sheet_name.lower() and "activity" in sheet_name.lower():
                    sheet_key = "unusual_activity"
                elif "cta" in sheet_name.lower() or "sample" in sheet_name.lower():
                    sheet_key = "cta_sample"
                elif "bip" in sheet_name.lower() or "business" in sheet_name.lower():
                    sheet_key = "bip_sample"
                
                if sheet_key:
                    self.sheets[sheet_key] = pd.read_excel(xlsx, sheet_name)
            
            logger.info(f"Successfully loaded workbook: {os.path.basename(self.file_path)}")
            logger.info(f"Found sheets: {list(self.sheets.keys())}")
            return True
        except Exception as e:
            logger.error(f"Error loading Excel file: {str(e)}")
            return False
    
    def process_activity_summary(self) -> Dict[str, Any]:
        """
        Process Activity Summary tab
        
        Returns:
            Dict: Extracted activity summary data
        """
        if "activity_summary" not in self.sheets:
            logger.warning("Activity Summary sheet not found")
            return {}
        
        df = self.sheets["activity_summary"]
        
        # Default values
        activity_summary = {
            "total_amount": 0.0,
            "start_date": None,
            "end_date": None,
            "transaction_types": [],
            "description": "",
            "indicators": []
        }
        
        try:
            # Look for total amounts (credits and debits)
            # First try to find exact column names
            if 'Total Amount' in df.columns:
                # Sum all numeric values in Total Amount column
                total_amount = df['Total Amount'].replace('[\$,]', '', regex=True).astype(float).sum()
                activity_summary["total_amount"] = total_amount
            else:
                # Try to find columns that contain 'total'
                total_cols = [col for col in df.columns if 'total' in col.lower()]
                if total_cols:
                    for col in total_cols:
                        # Convert to string, remove $ and commas, then to float
                        df[col] = pd.to_numeric(df[col].astype(str).str.replace('[\$,]', '', regex=True), errors='coerce')
                    
                    # Sum all total columns
                    activity_summary["total_amount"] = df[total_cols].sum().sum()
            
            # Find date range
            date_cols = [col for col in df.columns if 'date' in col.lower()]
            
            # First check for date range columns
            date_range_cols = [col for col in df.columns if 'date range' in col.lower()]
            if date_range_cols and not pd.isna(df[date_range_cols[0]].iloc[0]):
                # Extract start and end date from range string
                date_range = str(df[date_range_cols[0]].iloc[0])
                dates = re.findall(r'(\d{1,2}/\d{1,2}/\d{2,4})', date_range)
                if len(dates) >= 2:
                    activity_summary["start_date"] = dates[0]
                    activity_summary["end_date"] = dates[1]
            
            # If date range not found, look for earliest and latest dates
            if not activity_summary["start_date"] and date_cols:
                # Combine all date columns into one series
                all_dates = pd.Series()
                for col in date_cols:
                    if 'start' in col.lower():
                        activity_summary["start_date"] = min(df[col].dropna()).strftime('%m/%d/%Y')
                    elif 'end' in col.lower():
                        activity_summary["end_date"] = max(df[col].dropna()).strftime('%m/%d/%Y') 
                    else:
                        all_dates = pd.concat([all_dates, df[col].dropna()])
                
                # If still no dates, use all collected dates
                if not activity_summary["start_date"] and not all_dates.empty:
                    activity_summary["start_date"] = min(all_dates).strftime('%m/%d/%Y')
                    activity_summary["end_date"] = max(all_dates).strftime('%m/%d/%Y')
            
            # Extract transaction types
            type_cols = [col for col in df.columns if 'type' in col.lower()]
            if type_cols:
                # Get all unique values from type columns, excluding NaN
                all_types = set()
                for col in type_cols:
                    all_types.update(df[col].dropna().unique())
                
                # Filter out common non-type values
                non_types = ['total', 'credit', 'debit', 'sum', 'amount']
                activity_summary["transaction_types"] = [
                    t for t in all_types 
                    if isinstance(t, str) and not any(nt in t.lower() for nt in non_types)
                ]
            
            # Try to extract indicators (this would likely be in a specific field or based on keywords)
            # This is just a placeholder - adjust based on actual data
            indicator_keywords = ["structuring", "layering", "cash", "ach", "wire", "foreign", "rapid", "unusual"]
            
            # Look for these keywords in all string columns
            for col in df.select_dtypes(include=['object']).columns:
                for idx, value in df[col].dropna().items():
                    if isinstance(value, str):
                        for keyword in indicator_keywords:
                            if keyword in value.lower() and keyword not in activity_summary["indicators"]:
                                activity_summary["indicators"].append(keyword)
            
            logger.info(f"Successfully processed Activity Summary: {activity_summary}")
            return activity_summary
            
        except Exception as e:
            logger.error(f"Error processing Activity Summary: {str(e)}")
            return activity_summary
    
    def process_unusual_activity(self) -> Dict[str, Any]:
        """
        Process Unusual Activity tab
        
        Returns:
            Dict: Extracted unusual activity data
        """
        if "unusual_activity" not in self.sheets:
            logger.warning("Unusual Activity sheet not found")
            return {"samples": []}
        
        df = self.sheets["unusual_activity"]
        
        unusual_activity = {
            "description": "",
            "samples": []
        }
        
        try:
            # Look for description fields
            desc_cols = [col for col in df.columns if 'desc' in col.lower()]
            if desc_cols:
                descriptions = df[desc_cols[0]].dropna().tolist()
                if descriptions:
                    unusual_activity["description"] = " ".join(descriptions[:3])  # Take first few descriptions
            
            # Extract transaction samples (up to 5)
            # First, identify required columns
            date_col = next((col for col in df.columns if 'date' in col.lower()), None)
            type_col = next((col for col in df.columns if 'type' in col.lower()), None)
            amount_col = next((col for col in df.columns if 'amount' in col.lower()), None)
            location_col = next((col for col in df.columns 
                              if any(loc in col.lower() for loc in ['location', 'branch', 'place'])), None)
            
            if date_col and amount_col:  # Minimum required columns
                # Get up to 5 samples
                for idx, row in df.head(5).iterrows():
                    sample = {
                        "date": row[date_col] if not pd.isna(row[date_col]) else None,
                        "amount": row[amount_col] if not pd.isna(row[amount_col]) else 0.0,
                        "type": row[type_col] if type_col and not pd.isna(row[type_col]) else "transaction",
                        "location": row[location_col] if location_col and not pd.isna(row[location_col]) else "N/A"
                    }
                    
                    # Format date if it's a datetime object
                    if isinstance(sample["date"], datetime):
                        sample["date"] = sample["date"].strftime('%m/%d/%Y')
                    
                    # Format amount if it's a string with $ or commas
                    if isinstance(sample["amount"], str):
                        sample["amount"] = float(re.sub(r'[\$,]', '', sample["amount"]))
                    
                    unusual_activity["samples"].append(sample)
            
            logger.info(f"Successfully processed Unusual Activity: {len(unusual_activity['samples'])} samples")
            return unusual_activity
            
        except Exception as e:
            logger.error(f"Error processing Unusual Activity: {str(e)}")
            return {"samples": []}
    
    def process_cta_sample(self) -> Dict[str, Any]:
        """
        Process CTA Sample tab
        
        Returns:
            Dict: Extracted CTA sample data
        """
        if "cta_sample" not in self.sheets:
            logger.warning("CTA Sample sheet not found")
            return {}
        
        df = self.sheets["cta_sample"]
        
        cta_sample = {
            "customer_name": "",
            "interview_date": "",
            "summary": ""
        }
        
        try:
            # Look for customer name field
            name_cols = [col for col in df.columns 
                      if any(n in col.lower() for n in ['customer name', 'name', 'customer'])]
            if name_cols and not df[name_cols[0]].empty:
                cta_sample["customer_name"] = df[name_cols[0]].iloc[0]
            
            # Look for interview date field
            date_cols = [col for col in df.columns 
                      if any(d in col.lower() for n in ['interview date', 'date', 'conducted'])]
            if date_cols and not df[date_cols[0]].empty:
                date_val = df[date_cols[0]].iloc[0]
                if isinstance(date_val, datetime):
                    cta_sample["interview_date"] = date_val.strftime('%m/%d/%Y')
                else:
                    cta_sample["interview_date"] = str(date_val)
            
            # Look for summary field
            summary_cols = [col for col in df.columns 
                         if any(s in col.lower() for s in ['summary', 'notes', 'details', 'findings'])]
            if summary_cols and not df[summary_cols[0]].empty:
                cta_sample["summary"] = df[summary_cols[0]].iloc[0]
            
            logger.info(f"Successfully processed CTA Sample: {cta_sample}")
            return cta_sample
            
        except Exception as e:
            logger.error(f"Error processing CTA Sample: {str(e)}")
            return cta_sample
    
    def process_bip_sample(self) -> Dict[str, Any]:
        """
        Process BIP Sample tab
        
        Returns:
            Dict: Extracted BIP sample data
        """
        if "bip_sample" not in self.sheets:
            logger.warning("BIP Sample sheet not found")
            return {}
        
        df = self.sheets["bip_sample"]
        
        bip_sample = {
            "business_name": "",
            "business_type": "",
            "summary": ""
        }
        
        try:
            # Look for business name field
            name_cols = [col for col in df.columns 
                      if any(n in col.lower() for n in ['business name', 'name', 'business'])]
            if name_cols and not df[name_cols[0]].empty:
                bip_sample["business_name"] = df[name_cols[0]].iloc[0]
            
            # Look for business type field
            type_cols = [col for col in df.columns 
                      if any(t in col.lower() for t in ['business type', 'type', 'industry'])]
            if type_cols and not df[type_cols[0]].empty:
                bip_sample["business_type"] = df[type_cols[0]].iloc[0]
            
            # Look for summary field
            summary_cols = [col for col in df.columns 
                         if any(s in col.lower() for s in ['summary', 'notes', 'details', 'findings'])]
            if summary_cols and not df[summary_cols[0]].empty:
                bip_sample["summary"] = df[summary_cols[0]].iloc[0]
            
            logger.info(f"Successfully processed BIP Sample: {bip_sample}")
            return bip_sample
            
        except Exception as e:
            logger.error(f"Error processing BIP Sample: {str(e)}")
            return bip_sample
    
    # Adding to the existing ExcelProcessor class

    def summarize_transactions(self, sheet_data):
        """
        Summarize transaction data without analysis of patterns
        
        Args:
            sheet_data: DataFrame containing transaction data
            
        Returns:
            Dict: Summary of transaction data including totals and breakdowns
        """
        # Initialize summary structure
        summary = {
            "total_credits": 0.0,
            "total_debits": 0.0,
            "credit_breakdown": [],
            "debit_breakdown": [],
            "transaction_count": 0
        }
        
        # Try to identify key columns
        amount_col = self._find_column(sheet_data, ['amount', 'transaction amount'])
        type_col = self._find_column(sheet_data, ['type', 'transaction type'])
        debit_credit_col = self._find_column(sheet_data, ['debit/credit', 'dr/cr'])
        
        if not amount_col:
            logger.warning("Could not find transaction amount column")
            return summary
        
        # If no explicit debit/credit column, check for separate debit and credit columns
        debit_col = None
        credit_col = None
        if not debit_credit_col:
            debit_col = self._find_column(sheet_data, ['debit', 'dr'])
            credit_col = self._find_column(sheet_data, ['credit', 'cr'])
        
        # Process transactions
        try:
            # Create dictionaries to track totals by type
            credit_totals = {}
            debit_totals = {}
            credit_counts = {}
            debit_counts = {}
            
            for _, row in sheet_data.iterrows():
                # Skip rows with missing amount
                if amount_col not in row or pd.isna(row[amount_col]):
                    continue
                    
                # Get transaction amount as float
                amount = row[amount_col]
                if isinstance(amount, str):
                    amount = float(re.sub(r'[$,]', '', amount))
                
                # Get transaction type
                txn_type = "Unknown"
                if type_col and type_col in row and not pd.isna(row[type_col]):
                    txn_type = row[type_col]
                
                # Determine if credit or debit
                is_credit = False
                
                if debit_credit_col and debit_credit_col in row:
                    is_credit = str(row[debit_credit_col]).lower() in ['credit', 'cr', '+']
                elif debit_col and credit_col:
                    # Check if amount is in credit column
                    if credit_col in row and not pd.isna(row[credit_col]):
                        is_credit = True
                else:
                    # Fallback: Try to determine from type
                    if type_col and isinstance(txn_type, str):
                        is_credit = '+' in txn_type or 'credit' in txn_type.lower()
                    else:
                        # Default assumption based on amount sign
                        is_credit = amount > 0
                
                # Add to appropriate total
                if is_credit:
                    summary["total_credits"] += amount
                    if txn_type in credit_totals:
                        credit_totals[txn_type] += amount
                        credit_counts[txn_type] += 1
                    else:
                        credit_totals[txn_type] = amount
                        credit_counts[txn_type] = 1
                else:
                    summary["total_debits"] += amount
                    if txn_type in debit_totals:
                        debit_totals[txn_type] += amount
                        debit_counts[txn_type] += 1
                    else:
                        debit_totals[txn_type] = amount
                        debit_counts[txn_type] = 1
                
                summary["transaction_count"] += 1
            
            # Calculate percentages and build breakdown
            for txn_type, total in credit_totals.items():
                percent = (total / summary["total_credits"] * 100) if summary["total_credits"] > 0 else 0
                summary["credit_breakdown"].append({
                    "type": txn_type,
                    "amount": total,
                    "percent": percent,
                    "count": credit_counts[txn_type]
                })
            
            for txn_type, total in debit_totals.items():
                percent = (total / summary["total_debits"] * 100) if summary["total_debits"] > 0 else 0
                summary["debit_breakdown"].append({
                    "type": txn_type,
                    "amount": total,
                    "percent": percent, 
                    "count": debit_counts[txn_type]
                })
            
            # Sort breakdowns by amount descending
            summary["credit_breakdown"] = sorted(summary["credit_breakdown"], key=lambda x: x["amount"], reverse=True)
            summary["debit_breakdown"] = sorted(summary["debit_breakdown"], key=lambda x: x["amount"], reverse=True)
            
            logger.info(f"Summarized {summary['transaction_count']} transactions")
            logger.info(f"Total credits: ${summary['total_credits']:.2f}, Total debits: ${summary['total_debits']:.2f}")
            
            return summary
        
        except Exception as e:
            logger.error(f"Error summarizing transactions: {str(e)}")
            return summary

    def _find_column(self, df, possible_names):
        """
        Find a column in DataFrame that matches one of the possible names
        
        Args:
            df: DataFrame to search
            possible_names: List of possible column name patterns
            
        Returns:
            str: Matching column name or None if not found
        """
        if df is None or df.empty:
            return None
            
        # Try exact matches first
        for col in df.columns:
            if any(name == col.lower() for name in possible_names):
                return col
        
        # Try partial matches
        for col in df.columns:
            if any(name in col.lower() for name in possible_names):
                return col
        
        return None
    
    def summarize_multi_account_transactions(self):
        """
        Summarize transactions across multiple accounts without analyzing patterns
        
        Returns:
            Dict: Transaction summaries grouped by account and consolidated totals
        """
        # Results structure
        results = {
            "accounts": {},           # Account-specific summaries
            "consolidated": {          # Consolidated across all accounts
                "total_credits": 0.0,
                "total_debits": 0.0,
                "credit_breakdown": [],
                "debit_breakdown": [],
                "transaction_count": 0
            },
            "inter_account_transfers": []  # Simple listing of transfers between accounts
        }
        
        # Identify all transaction tabs
        transaction_tabs = []
        for sheet_name in self.sheets:
            # Look for transaction-related tabs
            if any(keyword in sheet_name.lower() for keyword in ['transaction', 'activity', 'sample']):
                transaction_tabs.append(sheet_name)
        
        # Combine all transaction data
        all_transactions = pd.DataFrame()
        for tab in transaction_tabs:
            if tab in self.sheets:
                df = self.sheets[tab]
                # Add source tab column if not present
                if 'source_tab' not in df.columns:
                    df['source_tab'] = tab
                all_transactions = pd.concat([all_transactions, df])
        
        if all_transactions.empty:
            logger.warning("No transaction data found in workbook")
            return results
        
        # Identify account column
        account_col = self._find_column(all_transactions, ['account', 'account number', 'acct'])
        if not account_col:
            logger.warning("Could not identify account column, assuming single account")
            # Process as single account using the account from case data
            single_account_summary = self.summarize_transactions(all_transactions)
            
            # Use the account number from first row if available, otherwise "unknown"
            account_number = "unknown"
            for col in all_transactions.columns:
                if "account" in col.lower() and not all_transactions[col].empty:
                    account_number = str(all_transactions[col].iloc[0])
                    break
            
            results["accounts"][account_number] = single_account_summary
            results["consolidated"] = single_account_summary
            return results
        
        # Get unique accounts
        unique_accounts = all_transactions[account_col].dropna().unique()
        logger.info(f"Found {len(unique_accounts)} unique accounts in transaction data")
        
        # Process transactions for each account
        for account in unique_accounts:
            account_transactions = all_transactions[all_transactions[account_col] == account]
            account_summary = self.summarize_transactions(account_transactions)
            
            # Add to results
            account_str = str(account)
            results["accounts"][account_str] = account_summary
            
            # Add to consolidated totals
            results["consolidated"]["total_credits"] += account_summary["total_credits"]
            results["consolidated"]["total_debits"] += account_summary["total_debits"]
            results["consolidated"]["transaction_count"] += account_summary["transaction_count"]
        
        # Aggregate breakdown categories across accounts
        credit_types = {}
        debit_types = {}
        
        for account, summary in results["accounts"].items():
            for credit in summary.get("credit_breakdown", []):
                txn_type = credit["type"]
                if txn_type in credit_types:
                    credit_types[txn_type]["amount"] += credit["amount"]
                    credit_types[txn_type]["count"] += credit["count"]
                else:
                    credit_types[txn_type] = {
                        "amount": credit["amount"],
                        "count": credit["count"]
                    }
            
            for debit in summary.get("debit_breakdown", []):
                txn_type = debit["type"]
                if txn_type in debit_types:
                    debit_types[txn_type]["amount"] += debit["amount"]
                    debit_types[txn_type]["count"] += debit["count"]
                else:
                    debit_types[txn_type] = {
                        "amount": debit["amount"],
                        "count": debit["count"]
                    }
        
        # Calculate percentages and format breakdowns
        for txn_type, data in credit_types.items():
            percent = (data["amount"] / results["consolidated"]["total_credits"] * 100) if results["consolidated"]["total_credits"] > 0 else 0
            results["consolidated"]["credit_breakdown"].append({
                "type": txn_type,
                "amount": data["amount"],
                "percent": percent,
                "count": data["count"]
            })
        
        for txn_type, data in debit_types.items():
            percent = (data["amount"] / results["consolidated"]["total_debits"] * 100) if results["consolidated"]["total_debits"] > 0 else 0
            results["consolidated"]["debit_breakdown"].append({
                "type": txn_type,
                "amount": data["amount"],
                "percent": percent,
                "count": data["count"]
            })
        
        # Sort breakdowns by amount descending
        results["consolidated"]["credit_breakdown"] = sorted(
            results["consolidated"]["credit_breakdown"], 
            key=lambda x: x["amount"], 
            reverse=True
        )
        results["consolidated"]["debit_breakdown"] = sorted(
            results["consolidated"]["debit_breakdown"], 
            key=lambda x: x["amount"], 
            reverse=True
        )
        
        # Simply identify inter-account transfers without analysis
        self._list_inter_account_transfers(all_transactions, results)
        
        return results
    
    def _list_inter_account_transfers(self, transactions, results):
        """
        List transfers between accounts without analyzing patterns
        
        Args:
            transactions: DataFrame containing all transactions
            results: Results dictionary to update with transfer info
        """
        # Find relevant columns
        account_col = self._find_column(transactions, ['account', 'account number', 'acct'])
        type_col = self._find_column(transactions, ['type', 'transaction type'])
        amount_col = self._find_column(transactions, ['amount', 'transaction amount'])
        date_col = self._find_column(transactions, ['date', 'transaction date'])
        counterparty_col = self._find_column(transactions, ['counterparty', 'recipient', 'sender', 'beneficiary'])
        
        if not account_col or not type_col or not amount_col:
            return
        
        # Look for transfers
        transfer_keywords = ['transfer', 'wire', 'payment to', 'payment from']
        potential_transfers = transactions[
            transactions[type_col].astype(str).str.lower().apply(
                lambda x: any(keyword in x for keyword in transfer_keywords)
            )
        ]
        
        if potential_transfers.empty:
            return
        
        # Just list the transfers between known accounts
        transfers = []
        unique_accounts = list(results["accounts"].keys())
        
        for _, transfer in potential_transfers.iterrows():
            source_account = str(transfer[account_col])
            amount = float(transfer[amount_col]) if isinstance(transfer[amount_col], (int, float)) else 0
            date = transfer[date_col] if date_col and date_col in transfer else "unknown"
            
            # If we have counterparty information, check for matches to other accounts
            target_account = "external"
            if counterparty_col and counterparty_col in transfer:
                counterparty = str(transfer[counterparty_col])
                # Check if counterparty matches any known account
                for account in unique_accounts:
                    if account != source_account and (account in counterparty or counterparty in account):
                        target_account = account
                        break
            
            # Add to transfers list
            transfers.append({
                "date": date,
                "from_account": source_account,
                "to_account": target_account,
                "amount": amount,
                "type": transfer[type_col]
            })
        
        # Sort by date
        transfers = sorted(transfers, key=lambda x: x["date"])
        results["inter_account_transfers"] = transfers
    
    def process(self) -> Dict[str, Any]:
        """
        Process all tabs in the workbook
        
        Returns:
            Dict: All extracted data from Excel file
        """
        if not self.load_workbook():
            return self.data
        
        # Process standard tabs
        self.data["activity_summary"] = self.process_activity_summary()
        self.data["unusual_activity"] = self.process_unusual_activity()
        self.data["cta_sample"] = self.process_cta_sample()
        self.data["bip_sample"] = self.process_bip_sample()
        
        # Process transaction summaries with multi-account awareness
        multi_account_summary = self.summarize_multi_account_transactions()
        self.data["transaction_summary"] = multi_account_summary.get("consolidated", {})
        self.data["account_summaries"] = multi_account_summary.get("accounts", {})
        self.data["inter_account_transfers"] = multi_account_summary.get("inter_account_transfers", [])
        
        return self.data