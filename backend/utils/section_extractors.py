"""
Utility functions for extracting section data directly from case data
without relying on flattened representations.
"""
from typing import Dict, List, Any, Optional

def extract_alerting_activity_summary(case_data):
    """
    Extract alerting activity summary directly from raw case data
    
    Args:
        case_data: The raw case data array with nested sections
        
    Returns:
        Dict: Structured alerting activity summary
    """
    alerting_activity_summary = {
        "alertInfo": {
            "caseNumber": "",
            "alertingAccounts": "",
            "alertingMonths": "",
            "alertDescription": "",
            "alertID": "",
            "reviewPeriod": "",
            "transactionalActivityDescription": "",
            "alertDispositionSummary": ""
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
    
    # Extract case number
    for section in case_data:
        if isinstance(section, dict) and section.get("section") == "Case Information":
            alerting_activity_summary["alertInfo"]["caseNumber"] = section.get("Case Number", "")
            break
    
    # Initialize alert months and descriptions lists
    alert_months = []
    alert_descriptions = []
    
    # Extract alerts information from Alerting Details section
    for section in case_data:
        if isinstance(section, dict) and section.get("section") == "Alerting Details":
            alerts = section.get("alerts", [])
            if alerts and len(alerts) > 0:
                alert = alerts[0]  # Use the first alert
                
                # Extract all the alert information we want to display
                alerting_activity_summary["alertInfo"]["alertID"] = alert.get("Alert ID", "")
                alert_months.append(alert.get("Alert Month", ""))
                alert_descriptions.append(alert.get("Description", ""))
                alerting_activity_summary["alertInfo"]["reviewPeriod"] = alert.get("Review Period", "")
                alerting_activity_summary["alertInfo"]["transactionalActivityDescription"] = alert.get("Transactional Activity Description", "")
                alerting_activity_summary["alertInfo"]["alertDispositionSummary"] = alert.get("Alert Disposition Summary", "")
                alerting_activity_summary["alertInfo"]["alertingAccounts"] = alert.get("Alerting Account", "")
                alerting_activity_summary["account"] = alert.get("Alerting Account", "")
                
            break
    
    # Combine alert information
    alerting_activity_summary["alertInfo"]["alertingMonths"] = ", ".join(alert_months)
    alerting_activity_summary["alertInfo"]["alertDescription"] = "; ".join(alert_descriptions)
    
    # Rest of the function remains the same...
    
    # Extract account information
    account_number = ""
    account_type = ""
    
    for section in case_data:
        if section.get("section") == "Account Information":
            if "Accounts" in section and section["Accounts"]:
                account = section["Accounts"][0]  # Take first account
                account_number = account.get("Account Key", "")
                account_types = account.get("Account Type", [])
                if account_types:
                    if isinstance(account_types, list):
                        account_type = account_types[0] if len(account_types) > 0 else ""
                    else:
                        account_type = str(account_types)
                
                # Set account number in summary
                alerting_activity_summary["account"] = account_number
                
                # Update alerting accounts with type if not already set
                if not alerting_activity_summary["alertInfo"]["alertingAccounts"]:
                    alerting_activity_summary["alertInfo"]["alertingAccounts"] = f"{account_type} {account_number}".strip()
            
            break
    
    # Extract Activity Summary data - this is where credit and debit details come from
    for section in case_data:
        if section.get("section") == "Activity Summary":
            activity_summaries = section.get("Activity Summary", [])
            
            for activity in activity_summaries:
                account = activity.get("Account", "")
                
                # Process credit activity
                credits = activity.get("Credits", [])
                for credit in credits:
                    # Update credit summary totals
                    credit_percent = credit.get("% of Credits", 0)
                    credit_amount = credit.get("Total ", 0)
                    credit_count = credit.get("# Transactions ", 0)
                    min_credit = credit.get("Min Credit Amt.", float('inf'))
                    max_credit = credit.get("Max Credit Amt.", 0)
                    min_date = credit.get("Min Txn Date ", "")
                    max_date = credit.get("Max Txn Date ", "")
                    credit_type = credit.get("Custom Language", "")
                    
                    # Add to credit summary totals
                    alerting_activity_summary["creditSummary"]["percentTotal"] += credit_percent
                    alerting_activity_summary["creditSummary"]["amountTotal"] += credit_amount
                    alerting_activity_summary["creditSummary"]["transactionCount"] += credit_count
                    
                    # Update min/max
                    if min_credit < alerting_activity_summary["creditSummary"]["minCreditAmount"]:
                        alerting_activity_summary["creditSummary"]["minCreditAmount"] = min_credit
                    
                    if max_credit > alerting_activity_summary["creditSummary"]["maxCreditAmount"]:
                        alerting_activity_summary["creditSummary"]["maxCreditAmount"] = max_credit
                    
                    # Update date range
                    if min_date:
                        if not alerting_activity_summary["creditSummary"]["minTransactionDate"] or min_date < alerting_activity_summary["creditSummary"]["minTransactionDate"]:
                            alerting_activity_summary["creditSummary"]["minTransactionDate"] = min_date
                    
                    if max_date:
                        if not alerting_activity_summary["creditSummary"]["maxTransactionDate"] or max_date > alerting_activity_summary["creditSummary"]["maxTransactionDate"]:
                            alerting_activity_summary["creditSummary"]["maxTransactionDate"] = max_date
                    
                    # Check if this is the type with highest percentage
                    if credit_percent > alerting_activity_summary["creditSummary"]["highestPercentValue"]:
                        alerting_activity_summary["creditSummary"]["highestPercentValue"] = credit_percent
                        alerting_activity_summary["creditSummary"]["highestPercentType"] = credit_type
                
                # Process debit activity
                debits = activity.get("Debits", [])
                for debit in debits:
                    # Update debit summary totals
                    debit_percent = debit.get("% of Debits", 0)
                    debit_amount = debit.get("Total ", 0)
                    debit_count = debit.get("# Transactions ", 0)
                    min_debit = debit.get("Min Debit Amt.", float('inf'))
                    max_debit = debit.get("Max Debit Amt.", 0)
                    min_date = debit.get("Min Txn Date ", "")
                    max_date = debit.get("Max Txn Date ", "")
                    debit_type = debit.get("Custom Language", "")
                    
                    # Add to debit summary totals
                    alerting_activity_summary["debitSummary"]["percentTotal"] += debit_percent
                    alerting_activity_summary["debitSummary"]["amountTotal"] += debit_amount
                    alerting_activity_summary["debitSummary"]["transactionCount"] += debit_count
                    
                    # Update min/max
                    if min_debit < alerting_activity_summary["debitSummary"]["minDebitAmount"]:
                        alerting_activity_summary["debitSummary"]["minDebitAmount"] = min_debit
                    
                    if max_debit > alerting_activity_summary["debitSummary"]["maxDebitAmount"]:
                        alerting_activity_summary["debitSummary"]["maxDebitAmount"] = max_debit
                    
                    # Update date range
                    if min_date:
                        if not alerting_activity_summary["debitSummary"]["minTransactionDate"] or min_date < alerting_activity_summary["debitSummary"]["minTransactionDate"]:
                            alerting_activity_summary["debitSummary"]["minTransactionDate"] = min_date
                    
                    if max_date:
                        if not alerting_activity_summary["debitSummary"]["maxTransactionDate"] or max_date > alerting_activity_summary["debitSummary"]["maxTransactionDate"]:
                            alerting_activity_summary["debitSummary"]["maxTransactionDate"] = max_date
                    
                    # Check if this is the type with highest percentage
                    if debit_percent > alerting_activity_summary["debitSummary"]["highestPercentValue"]:
                        alerting_activity_summary["debitSummary"]["highestPercentValue"] = debit_percent
                        alerting_activity_summary["debitSummary"]["highestPercentType"] = debit_type
            
            break
    
    # Clean up infinity values
    if alerting_activity_summary["creditSummary"]["minCreditAmount"] == float('inf'):
        alerting_activity_summary["creditSummary"]["minCreditAmount"] = 0
    
    if alerting_activity_summary["debitSummary"]["minDebitAmount"] == float('inf'):
        alerting_activity_summary["debitSummary"]["minDebitAmount"] = 0
    
    return alerting_activity_summary

def generate_alerting_activity_prompt(alerting_activity_summary):
    """
    Generate LLM prompt for alerting activity section
    
    Args:
        alerting_activity_summary: The extracted alerting activity summary
        
    Returns:
        str: Formatted prompt for LLM
    """
    alert_info = alerting_activity_summary["alertInfo"]
    credit_summary = alerting_activity_summary["creditSummary"]
    debit_summary = alerting_activity_summary["debitSummary"]
    account = alerting_activity_summary["account"]
    
    # Format currency values
    credit_amount_total = "${:,.2f}".format(credit_summary["amountTotal"])
    credit_min_amount = "${:,.2f}".format(credit_summary["minCreditAmount"])
    credit_max_amount = "${:,.2f}".format(credit_summary["maxCreditAmount"])
    
    debit_amount_total = "${:,.2f}".format(debit_summary["amountTotal"])
    debit_min_amount = "${:,.2f}".format(debit_summary["minDebitAmount"])
    debit_max_amount = "${:,.2f}".format(debit_summary["maxDebitAmount"])
    
    # Create the prompt with the correct values filled in
    prompt = f"""Summarize this bank account alert information directly without any introductory phrases:

ALERT INFORMATION:
- Case Number: {alert_info["caseNumber"]}
- Alerting Account(s): {alert_info["alertingAccounts"]}
- Alerting Month(s): {alert_info["alertingMonths"]}
- Alert Description: {alert_info["alertDescription"]}

ACCOUNT: {account}

CREDITS:
- Total amount: {credit_amount_total}
- Number of transactions: {credit_summary["transactionCount"]}
- Date range: {credit_summary["minTransactionDate"]} to {credit_summary["maxTransactionDate"]}
- Transaction amounts: {credit_min_amount} to {credit_max_amount}
- Most common activity: {credit_summary["highestPercentType"]} ({credit_summary["highestPercentValue"]}%)

DEBITS:
- Total amount: {debit_amount_total}
- Number of transactions: {debit_summary["transactionCount"]}
- Date range: {debit_summary["minTransactionDate"]} to {debit_summary["maxTransactionDate"]}
- Transaction amounts: {debit_min_amount} to {debit_max_amount}
- Most common activity: {debit_summary["highestPercentType"]} ({debit_summary["highestPercentValue"]}%)

Write a clear summary in this exact format:

1. First paragraph: Start with the Case Number, then describe the alerting accounts, alerting months, and include a brief description of the alert activity.

2. Second paragraph: Summarize credit activity focusing on total amount, number of transactions, most common type of activity with its percentage, and range of amounts.

3. Third paragraph: Summarize debit activity focusing on total amount, number of transactions, most common type of activity with its percentage, and range of amounts.

Keep sentences short and simple. Do not use phrases like "Here is the summary" or "In conclusion." Start immediately with the case number and keep the summary factual without analysis beyond what's shown in the data."""
    
    return prompt

def extract_prior_cases_summary(case_data):
    """
    Extract prior cases information directly from raw case data
    
    Args:
        case_data: The raw case data array with nested sections
        
    Returns:
        List: List of prior case information
    """
    prior_cases = []
    
    # Find the Prior Cases/SARs section
    for section in case_data:
        if isinstance(section, dict) and section.get("section") == "Prior Cases/SARs":
            # Look for the priorCases key
            raw_prior_cases = section.get("priorCases", [])
            
            # Process each prior case
            for prior_case in raw_prior_cases:
                case_info = {
                    "case_number": prior_case.get("Case Number", ""),
                    "case_step": prior_case.get("Case Step", ""),
                    "alert_ids": [],
                    "alert_months": [],
                    "alerting_account": "",
                    "scope_of_review": {
                        "start": "",
                        "end": ""
                    },
                    "sar_details": {
                        "form_number": "",
                        "filing_date": "",
                        "amount_reported": 0,
                        "sar_summary": ""
                    },
                    "general_comments": prior_case.get("General Comments", "")
                }
                
                # Extract Alerting Information
                alerting_info = prior_case.get("Alerting Information", {})
                if alerting_info:
                    case_info["alert_ids"] = alerting_info.get("Alert IDs", [])
                    case_info["alert_months"] = alerting_info.get("Alert Months", [])
                    case_info["alerting_account"] = alerting_info.get("Alerting Account", "")
                
                # Extract Scope of Review
                scope = prior_case.get("Scope of Review", {})
                if scope:
                    case_info["scope_of_review"]["start"] = scope.get("start", "")
                    case_info["scope_of_review"]["end"] = scope.get("end", "")
                
                # Extract SAR Details
                sar_details = prior_case.get("SAR Details", {})
                if sar_details:
                    case_info["sar_details"]["form_number"] = sar_details.get("Form Number", "")
                    case_info["sar_details"]["filing_date"] = sar_details.get("Filing Date", "")
                    case_info["sar_details"]["amount_reported"] = sar_details.get("Amount Reported", 0)
                    case_info["sar_details"]["sar_summary"] = sar_details.get("SAR Summary", "")
                
                prior_cases.append(case_info)
            
            return prior_cases
    
    # If no Prior Cases/SARs section found
    return []

def generate_prior_cases_prompt(prior_cases):
    """
    Generate LLM prompt for prior case/SAR summary section
    
    Args:
        prior_cases: List of extracted prior case information
        
    Returns:
        str: Formatted prompt for LLM
    """
    # If no prior cases found
    if not prior_cases:
        return "Write a brief summary stating that no prior SARs were identified for this account or customer."
    
    # Create structured prompt for LLM
    prompt = """
Write a concise summary of the prior SAR case using the following detailed information:

CASE DETAILS:
- Case Number: {case_number}
- Case Step: {case_step}
- Alert IDs: {alert_ids}
- Alert Months: {alert_months}
- Alerting Account: {account}
- Review Period: {start_date} to {end_date}
- SAR Form Number: {sar_form}
- SAR Amount: ${sar_amount}
- SAR Filing Date: {filing_date}

SUMMARY:
{sar_summary}

CTA COMMENTS:
{comments}

Format your response professionally in one paragraph beginning with "Prior SAR:" and include all key details. Focus on the case number, alert details, account number, review period dates, SAR information (including amount and form number), and any CTA information.
""".format(
        case_number=prior_cases[0].get("case_number", ""),
        case_step=prior_cases[0].get("case_step", ""),
        alert_ids=", ".join(prior_cases[0].get("alert_ids", [])),
        alert_months=", ".join(prior_cases[0].get("alert_months", [])),
        account=prior_cases[0].get("alerting_account", ""),
        start_date=prior_cases[0].get("scope_of_review", {}).get("start", ""),
        end_date=prior_cases[0].get("scope_of_review", {}).get("end", ""),
        sar_form=prior_cases[0].get("sar_details", {}).get("form_number", ""),
        sar_amount=prior_cases[0].get("sar_details", {}).get("amount_reported", 0),
        filing_date=prior_cases[0].get("sar_details", {}).get("filing_date", ""),
        sar_summary=prior_cases[0].get("sar_details", {}).get("sar_summary", ""),
        comments=prior_cases[0].get("general_comments", "")
    )
    
    return prompt
    
    return prompt


def extract_scope_of_review(case_data):
    """
    Extract scope of review information directly from raw case data
    
    Args:
        case_data: The raw case data array with nested sections
        
    Returns:
        Dict: Scope of review information
    """
    scope_info = {
        "start_date": "",
        "end_date": "",
        "accounts": []
    }
    
    # Find the Scope of Review section
    for section in case_data:
        if section.get("section") == "Scope of Review":
            scope_info["start_date"] = section.get("Start Date", "")
            scope_info["end_date"] = section.get("End Date", "")
            break
    
    # If not found in dedicated section, check Alternative section: Case Review Period in Account Information
    if not scope_info["start_date"] or not scope_info["end_date"]:
        for section in case_data:
            if section.get("section") == "Account Information" and "Case Review Period" in section:
                review_period = section.get("Case Review Period", "")
                if review_period and " - " in review_period:
                    parts = review_period.split(" - ")
                    if len(parts) == 2:
                        scope_info["start_date"] = parts[0]
                        scope_info["end_date"] = parts[1]
                break
    
    # Extract account information
    for section in case_data:
        if section.get("section") == "Account Information" and "Accounts" in section:
            accounts = section.get("Accounts", [])
            for account in accounts:
                account_info = {
                    "account_number": account.get("Account Key", ""),
                    "account_type": ", ".join(account.get("Account Type", [])) if isinstance(account.get("Account Type"), list) else account.get("Account Type", ""),
                    "open_date": account.get("Account Opening Date & Branch", ""),
                    "close_date": account.get("Account Closing Date", "")
                }
                scope_info["accounts"].append(account_info)
            break
    
    return scope_info

def generate_scope_of_review_prompt(scope_info):
    """
    Generate LLM prompt for scope of review section
    
    Args:
        scope_info: Extracted scope of review information
        
    Returns:
        str: Formatted prompt for LLM
    """
    prompt = "Generate a Scope of Review section based on the following information:\n\n"
    prompt += f"Review Period Start Date: {scope_info['start_date']}\n"
    prompt += f"Review Period End Date: {scope_info['end_date']}\n\n"
    
    if scope_info["accounts"]:
        prompt += "Accounts Reviewed:\n"
        for account in scope_info["accounts"]:
            prompt += f"- Account Number: {account['account_number']}\n"
            prompt += f"  Account Type: {account['account_type']}\n"
            prompt += f"  Open Date: {account['open_date']}\n"
            if account['close_date']:
                prompt += f"  Close Date: {account['close_date']}\n"
            prompt += "\n"
    
    prompt += """
Write a brief Scope of Review section for a Suspicious Activity Report (SAR) recommendation that:

1. States the time period reviewed (start date to end date)
2. Mentions the accounts that were reviewed
3. Notes any accounts that were opened or closed during the review period

Example format: "Accounts were reviewed from [Start Date] to [End Date]. Account [Account Number] was opened on [Open Date]."

Keep this section brief and factual, typically 1-2 sentences. Avoid unnecessary explanations or analysis.
    """
    return prompt

def extract_unusual_activity_summary(case_data):
    """
    Extract and analyze unusual activity transactions from case data
    
    Args:
        case_data: The raw case data array with nested sections
        
    Returns:
        Dict: Transaction summary statistics
    """
    # Initialize the transaction summary structure
    txn_summary = {
        "totalAmountCredits": 0.0,
        "totalAmountDebits": 0.0,
        "countOfCredits": 0,
        "countOfDebits": 0,
        "totalAmountSAR": 0.0,
        "minDebitAmount": float('inf'),
        "maxDebitAmount": 0.0,
        "minCreditAmount": float('inf'),
        "maxCreditAmount": 0.0,
        "minTransactionDate": None,
        "maxTransactionDate": None,
        "customLanguage": {
            "highestCountCustomLanguageCredit": "",
            "highestCountCustomLanguageDebit": "",
            "highestAmountOfCustomLanguageDebit": 0.0,
            "highestAmountOfCustomLanguageCredit": 0.0,
            "highestCountOfCustomLanguageDebit": 0,
            "highestCountOfCustomLanguageCredit": 0
        }
    }
    
    # Track counts and amounts by custom language
    credit_by_custom_language = {}  # {custom_language: {"count": 0, "amount": 0.0}}
    debit_by_custom_language = {}   # {custom_language: {"count": 0, "amount": 0.0}}
    
    # Find the Unusual Activity section
    unusual_activity_transactions = []
    
    for section in case_data:
        if isinstance(section, dict) and "Unusual Activity" in section:
            unusual_activity_transactions = section.get("Unusual Activity", [])
            break
    
    # Process each transaction
    for txn in unusual_activity_transactions:
        if not isinstance(txn, dict):
            continue
            
        # Extract transaction details
        txn_date_str = txn.get("Transaction Date", "")
        debit_credit = txn.get("Debit/Credit", "")
        amount = float(txn.get("Transaction Amount", 0))
        custom_language = txn.get("Custom Language", "")
        
        # Convert transaction date to datetime for comparison
        try:
            # Try different date formats (MM/DD/YYYY or YYYY-MM-DD)
            txn_date = None
            for date_format in ["%m/%d/%Y", "%Y-%m-%d"]:
                try:
                    txn_date = datetime.strptime(txn_date_str, date_format)
                    break
                except ValueError:
                    continue
                    
            if txn_date:
                # Update min/max dates
                if txn_summary["minTransactionDate"] is None or txn_date < txn_summary["minTransactionDate"]:
                    txn_summary["minTransactionDate"] = txn_date
                
                if txn_summary["maxTransactionDate"] is None or txn_date > txn_summary["maxTransactionDate"]:
                    txn_summary["maxTransactionDate"] = txn_date
        except Exception:
            # Skip date processing if there are issues
            pass
        
        # Determine if credit or debit
        is_credit = debit_credit.lower() in ["credit", "cr", "c", "+"]
        
        # Update summary based on credit/debit
        if is_credit:
            txn_summary["totalAmountCredits"] += amount
            txn_summary["countOfCredits"] += 1
            
            # Update min/max credit amounts
            if amount < txn_summary["minCreditAmount"]:
                txn_summary["minCreditAmount"] = amount
            if amount > txn_summary["maxCreditAmount"]:
                txn_summary["maxCreditAmount"] = amount
                
            # Update custom language stats for credits
            if custom_language not in credit_by_custom_language:
                credit_by_custom_language[custom_language] = {"count": 0, "amount": 0.0}
            
            credit_by_custom_language[custom_language]["count"] += 1
            credit_by_custom_language[custom_language]["amount"] += amount
            
        else:  # Debit
            txn_summary["totalAmountDebits"] += amount
            txn_summary["countOfDebits"] += 1
            
            # Update min/max debit amounts
            if amount < txn_summary["minDebitAmount"]:
                txn_summary["minDebitAmount"] = amount
            if amount > txn_summary["maxDebitAmount"]:
                txn_summary["maxDebitAmount"] = amount
                
            # Update custom language stats for debits
            if custom_language not in debit_by_custom_language:
                debit_by_custom_language[custom_language] = {"count": 0, "amount": 0.0}
            
            debit_by_custom_language[custom_language]["count"] += 1
            debit_by_custom_language[custom_language]["amount"] += amount
    
    # Calculate total SAR amount
    txn_summary["totalAmountSAR"] = txn_summary["totalAmountCredits"] + txn_summary["totalAmountDebits"]
    
    # Find highest count and amount by custom language for credits
    highest_credit_count = 0
    highest_credit_amount = 0.0
    highest_credit_count_language = ""
    highest_credit_amount_language = ""
    
    for language, stats in credit_by_custom_language.items():
        if stats["count"] > highest_credit_count:
            highest_credit_count = stats["count"]
            highest_credit_count_language = language
            
        if stats["amount"] > highest_credit_amount:
            highest_credit_amount = stats["amount"]
            highest_credit_amount_language = language
    
    # Find highest count and amount by custom language for debits
    highest_debit_count = 0
    highest_debit_amount = 0.0
    highest_debit_count_language = ""
    highest_debit_amount_language = ""
    
    for language, stats in debit_by_custom_language.items():
        if stats["count"] > highest_debit_count:
            highest_debit_count = stats["count"]
            highest_debit_count_language = language
            
        if stats["amount"] > highest_debit_amount:
            highest_debit_amount = stats["amount"]
            highest_debit_amount_language = language
    
    # Update custom language summary
    txn_summary["customLanguage"]["highestCountCustomLanguageCredit"] = highest_credit_count_language
    txn_summary["customLanguage"]["highestCountCustomLanguageDebit"] = highest_debit_count_language
    txn_summary["customLanguage"]["highestAmountOfCustomLanguageCredit"] = highest_credit_amount
    txn_summary["customLanguage"]["highestAmountOfCustomLanguageDebit"] = highest_debit_amount
    txn_summary["customLanguage"]["highestCountOfCustomLanguageCredit"] = highest_credit_count
    txn_summary["customLanguage"]["highestCountOfCustomLanguageDebit"] = highest_debit_count
    
    # Format dates as strings if they exist
    if txn_summary["minTransactionDate"]:
        txn_summary["minTransactionDate"] = txn_summary["minTransactionDate"].strftime("%Y-%m-%d")
    else:
        txn_summary["minTransactionDate"] = ""
        
    if txn_summary["maxTransactionDate"]:
        txn_summary["maxTransactionDate"] = txn_summary["maxTransactionDate"].strftime("%Y-%m-%d")
    else:
        txn_summary["maxTransactionDate"] = ""
    
    # Handle cases where no credits or debits were found
    if txn_summary["minCreditAmount"] == float('inf'):
        txn_summary["minCreditAmount"] = 0.0
    if txn_summary["minDebitAmount"] == float('inf'):
        txn_summary["minDebitAmount"] = 0.0
    
    return {"txnSummary": txn_summary}

def generate_suspicious_activity_prompt(txn_summary, case_data):
    """
    Generate a prompt for the LLM to create Section 1 - Suspicious Activity Summary
    
    Args:
        txn_summary: Transaction summary statistics
        case_data: Case data for additional context
        
    Returns:
        str: Formatted prompt for LLM
    """
    # Extract customer/subject information
    subjects = []
    for section in case_data:
        if isinstance(section, dict) and section.get("section") == "Customer Information":
            if "US Bank Customer Information" in section:
                for customer in section["US Bank Customer Information"]:
                    subjects.append(customer.get("Primary Party", ""))
    
    # Get primary subject name or fallback
    primary_subject = subjects[0] if subjects else "the customer"
    
    # Get account information
    account_number = ""
    account_type = "account"
    for section in case_data:
        if isinstance(section, dict) and section.get("section") == "Account Information":
            if "Accounts" in section and section["Accounts"]:
                account = section["Accounts"][0]  # Take first account
                account_number = account.get("Account Key", "")
                account_type_list = account.get("Account Type", [])
                if account_type_list and len(account_type_list) > 0:
                    if isinstance(account_type_list, list):
                        account_type = account_type_list[1] if len(account_type_list) > 1 else account_type_list[0]
                    else:
                        account_type = account_type_list
    
    # Format amounts for the prompt
    total_amount = "${:,.2f}".format(txn_summary["txnSummary"]["totalAmountSAR"])
    
    # Determine activity type based on custom language with highest count/amount
    credit_custom_language = txn_summary["txnSummary"]["customLanguage"]["highestCountCustomLanguageCredit"]
    debit_custom_language = txn_summary["txnSummary"]["customLanguage"]["highestCountCustomLanguageDebit"]
    
    # If both credit and debit have significant activity, use both
    if (txn_summary["txnSummary"]["totalAmountCredits"] > 1000 and 
        txn_summary["txnSummary"]["totalAmountDebits"] > 1000):
        activity_type = f"{credit_custom_language} and {debit_custom_language}"
    # Otherwise use the one with higher amount
    elif txn_summary["txnSummary"]["totalAmountCredits"] > txn_summary["txnSummary"]["totalAmountDebits"]:
        activity_type = credit_custom_language
    else:
        activity_type = debit_custom_language
    
    # Create the prompt template
    prompt = f"""
    Generate Section 1 - Suspicious Activity Summary for a SAR Narrative using ONLY the transaction data provided below:
    
    Transaction Summary:
    - Total SAR Amount: {total_amount}
    - Total Credits: ${txn_summary["txnSummary"]["totalAmountCredits"]:,.2f} ({txn_summary["txnSummary"]["countOfCredits"]} transactions)
    - Total Debits: ${txn_summary["txnSummary"]["totalAmountDebits"]:,.2f} ({txn_summary["txnSummary"]["countOfDebits"]} transactions)
    - Credit Amount Range: ${txn_summary["txnSummary"]["minCreditAmount"]:,.2f} to ${txn_summary["txnSummary"]["maxCreditAmount"]:,.2f}
    - Debit Amount Range: ${txn_summary["txnSummary"]["minDebitAmount"]:,.2f} to ${txn_summary["txnSummary"]["maxDebitAmount"]:,.2f}
    - Activity Date Range: {txn_summary["txnSummary"]["minTransactionDate"]} to {txn_summary["txnSummary"]["maxTransactionDate"]}
    
    Most Common Transaction Types:
    - Credits: {credit_custom_language} (Count: {txn_summary["txnSummary"]["customLanguage"]["highestCountOfCustomLanguageCredit"]}, Amount: ${txn_summary["txnSummary"]["customLanguage"]["highestAmountOfCustomLanguageCredit"]:,.2f})
    - Debits: {debit_custom_language} (Count: {txn_summary["txnSummary"]["customLanguage"]["highestCountOfCustomLanguageDebit"]}, Amount: ${txn_summary["txnSummary"]["customLanguage"]["highestAmountOfCustomLanguageDebit"]:,.2f})
    
    Customer/Account Information:
    - Customer Name: {primary_subject}
    - Account Number: {account_number}
    - Account Type: {account_type}
    
    Write a detailed opening paragraph for a SAR Narrative that follows this exact structure:
    "U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report [type of activity] totaling [total amount] by [customer name] in [account type] account number [account number]. The suspicious [type of activity] were conducted from [start date] through [end date]."
    
    Replace the placeholders with the exact information provided above. The paragraph should be factual, precise, and begin exactly with "U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report...". Include all key transaction details, patterns, and amounts.
    """
    
    return prompt