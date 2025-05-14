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
    
    # Extract case number
    for section in case_data:
        if section.get("section") == "Case Information":
            alerting_activity_summary["alertInfo"]["caseNumber"] = section.get("Case Number", "")
            break
    
    # Extract alerts information
    alert_ids = []
    alert_months = []
    alert_descriptions = []
    
    for section in case_data:
        if section.get("section") == "Alerting Details" and "alerts" in section:
            alerts = section.get("alerts", [])
            for alert in alerts:
                if "Alert ID" in alert:
                    alert_ids.append(alert["Alert ID"])
                if "Alert Month" in alert:
                    alert_months.append(alert["Alert Month"])
                if "Description" in alert:
                    alert_descriptions.append(alert["Description"])
            
            # Add alerting account information
            if alerts and "Alerting Account" in alerts[0]:
                alerting_activity_summary["alertInfo"]["alertingAccounts"] = alerts[0]["Alerting Account"]
                
            break
    
    # Combine alert information
    alerting_activity_summary["alertInfo"]["alertingMonths"] = ", ".join(alert_months)
    alerting_activity_summary["alertInfo"]["alertDescription"] = "; ".join(alert_descriptions)
    
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
    Extract prior cases and SARs information directly from raw case data
    
    Args:
        case_data: The raw case data array with nested sections
        
    Returns:
        List: List of prior case information
    """
    prior_cases = []
    
    # Find the Prior Cases/SARs section
    for section in case_data:
        if section.get("section") == "Prior Cases/SARs" and "priorCases" in section:
            raw_prior_cases = section.get("priorCases", [])
            
            # Process each prior case
            for prior_case in raw_prior_cases:
                case_info = {
                    "case_number": prior_case.get("Case Number", ""),
                    "case_step": prior_case.get("Case Step", ""),
                    "alert_ids": [],
                    "alert_months": [],
                    "alerting_account": "",
                    "investigation_findings": prior_case.get("Investigative Findings", ""),
                    "scope_of_review": {
                        "start": "",
                        "end": ""
                    },
                    "investigation_summary": prior_case.get("Investigation Summary", ""),
                    "sar_details": {
                        "form_number": "",
                        "filing_date": "",
                        "amount_reported": 0,
                        "sar_summary": "",
                        "attachment": ""
                    },
                    "general_comments": prior_case.get("General Comments", "")
                }
                
                # Extract alerting information
                alerting_info = prior_case.get("Alerting Information", {})
                if alerting_info:
                    case_info["alert_ids"] = alerting_info.get("Alert IDs", [])
                    case_info["alert_months"] = alerting_info.get("Alert Months", [])
                    case_info["alerting_account"] = alerting_info.get("Alerting Account", "")
                
                # Extract scope of review
                scope = prior_case.get("Scope of Review", {})
                if scope:
                    case_info["scope_of_review"]["start"] = scope.get("start", "")
                    case_info["scope_of_review"]["end"] = scope.get("end", "")
                
                # Extract SAR details
                sar_details = prior_case.get("SAR Details", {})
                if sar_details:
                    case_info["sar_details"]["form_number"] = sar_details.get("Form Number", "")
                    case_info["sar_details"]["filing_date"] = sar_details.get("Filing Date", "")
                    case_info["sar_details"]["amount_reported"] = sar_details.get("Amount Reported", 0)
                    case_info["sar_details"]["sar_summary"] = sar_details.get("SAR Summary", "")
                    case_info["sar_details"]["attachment"] = sar_details.get("Attachment", "")
                    
                    # Extract filing date range if available
                    if "Filing Date Range" in sar_details:
                        filing_range = sar_details.get("Filing Date Range", {})
                        if filing_range:
                            case_info["sar_details"]["filing_date_start"] = filing_range.get("start", "")
                            case_info["sar_details"]["filing_date_end"] = filing_range.get("end", "")
                
                prior_cases.append(case_info)
            
            break
    
    return prior_cases

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
        return "Review the prior case and SAR information provided:\n\nNo prior cases or SARs were identified for this account or customer.\n\nWrite a brief sentence stating that no prior cases or SARs were identified."
    
    prompt = "Review the prior case and SAR information provided:\n\n"
    
    # Add details for each prior case
    for i, case in enumerate(prior_cases):
        prompt += f"PRIOR CASE {i+1}:\n"
        prompt += f"Case Number: {case['case_number']}\n"
        prompt += f"Case Step: {case['case_step']}\n"
        
        # Alert information
        prompt += f"Alert IDs: {', '.join(case['alert_ids'])}\n" if case['alert_ids'] else "Alert IDs: None\n"
        prompt += f"Alert Months: {', '.join(case['alert_months'])}\n" if case['alert_months'] else "Alert Months: None\n"
        prompt += f"Alerting Account: {case['alerting_account']}\n"
        
        # Scope of review
        prompt += f"Review Period: {case['scope_of_review']['start']} to {case['scope_of_review']['end']}\n"
        
        # SAR details
        prompt += f"SAR Form Number: {case['sar_details']['form_number']}\n"
        prompt += f"SAR Filing Date: {case['sar_details']['filing_date']}\n"
        prompt += f"SAR Amount: ${case['sar_details']['amount_reported']:,.2f}\n"
        
        if 'filing_date_start' in case['sar_details'] and 'filing_date_end' in case['sar_details']:
            prompt += f"SAR Date Range: {case['sar_details']['filing_date_start']} to {case['sar_details']['filing_date_end']}\n"
        
        # Add investigative findings or summary if available
        if case['investigation_findings']:
            prompt += f"Investigative Findings: {case['investigation_findings']}\n"
        
        if case['investigation_summary']:
            truncated_summary = case['investigation_summary'][:300] + "..." if len(case['investigation_summary']) > 300 else case['investigation_summary']
            prompt += f"Investigation Summary: {truncated_summary}\n"
        
        if case['sar_details']['sar_summary']:
            truncated_sar_summary = case['sar_details']['sar_summary'][:300] + "..." if len(case['sar_details']['sar_summary']) > 300 else case['sar_details']['sar_summary']
            prompt += f"SAR Summary: {truncated_sar_summary}\n"
        
        # Add general comments (usually includes CTA information)
        if case['general_comments']:
            prompt += f"General Comments / CTA: {case['general_comments']}\n"
        
        prompt += "\n"
    
    # Add formatting instructions
    prompt += """
Write a concise summary of the prior cases and SARs following these guidelines:

1. For each prior case, include:
   - Case number
   - Alerting account number
   - Review period (start and end dates)
   - Alert IDs and types of activity
   - Whether a SAR was filed (including form number if available)
   - SAR amount and date range if applicable
   - Brief summary of the suspicious activity identified

2. If a Customer Transaction Assessment (CTA) was conducted, include a brief mention of the outcome.

Format each prior case as: "Case # [case number]: Alerting account # [account number] reviewed from [start date] to [end date] due to [alerting activity]. SAR ID [form number] reported account # [account number] for activity totaling $[amount] conducted from [date range]. [Brief summary of SAR]."

If no SAR was filed, simply state: "Case # [case number]: Alerting account # [account number] reviewed from [start date] to [end date] due to [alerting activity]. No SAR was filed."

Keep your response concise and factual, focusing only on the relevant case details. Use 1-2 sentences per prior case.
    """
    
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