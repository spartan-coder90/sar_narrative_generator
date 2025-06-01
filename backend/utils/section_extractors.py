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
    # case_data is now the new standardized case object (a dictionary)
    output_summary = {
        "alertInfo": {
            "caseNumber": "", "alertingAccounts": "", "alertingMonths": "",
            "alertDescription": "", "alertID": "", "reviewPeriod": "",
            "transactionalActivityDescription": "N/A", # Default as not in new structure
            "alertDispositionSummary": "N/A" # Default as not in new structure
        },
        "account": "", # Primary account number
        "creditSummary": {
            "percentTotal": 0, "amountTotal": 0, "transactionCount": 0,
            "minCreditAmount": float('inf'), "maxCreditAmount": 0,
            "minTransactionDate": "", "maxTransactionDate": "",
            "highestPercentType": "", "highestPercentValue": 0
        },
        "debitSummary": {
            "percentTotal": 0, "amountTotal": 0, "transactionCount": 0,
            "minDebitAmount": float('inf'), "maxDebitAmount": 0,
            "minTransactionDate": "", "maxTransactionDate": "",
            "highestPercentType": "", "highestPercentValue": 0
        }
    }

    case_info = case_data.get("caseInfo", {})
    output_summary["alertInfo"]["caseNumber"] = case_info.get("caseNumber", "")

    alerts_new_struct = case_data.get("alerts", [])
    alert_months_list = []
    alert_descriptions_list = []

    if alerts_new_struct:
        first_alert_new = alerts_new_struct[0] if isinstance(alerts_new_struct[0], dict) else {}
        output_summary["alertInfo"]["alertID"] = first_alert_new.get("alertId", "")

        first_alert_review_period = first_alert_new.get("reviewPeriod", {})
        start_date = first_alert_review_period.get("startDate", "")
        end_date = first_alert_review_period.get("endDate", "")
        if start_date and end_date:
            output_summary["alertInfo"]["reviewPeriod"] = f"{start_date} to {end_date}"
        elif start_date:
            output_summary["alertInfo"]["reviewPeriod"] = f"From {start_date}"
        elif end_date:
            output_summary["alertInfo"]["reviewPeriod"] = f"Until {end_date}"
        else: # Fallback to caseInfo review period if alert-specific is incomplete
            case_review_period = case_info.get("reviewPeriod", {})
            start_date_case = case_review_period.get("startDate", "")
            end_date_case = case_review_period.get("endDate", "")
            if start_date_case and end_date_case:
                 output_summary["alertInfo"]["reviewPeriod"] = f"{start_date_case} to {end_date_case}"


        for alert_item in alerts_new_struct:
            if isinstance(alert_item, dict):
                if alert_item.get("alertMonth"):
                    alert_months_list.append(str(alert_item["alertMonth"]))
                if alert_item.get("description"):
                    alert_descriptions_list.append(alert_item["description"])
    
    output_summary["alertInfo"]["alertingMonths"] = ", ".join(list(set(alert_months_list)))
    output_summary["alertInfo"]["alertDescription"] = "; ".join(list(set(alert_descriptions_list)))

    accounts_new_struct = case_data.get("accounts", [])
    primary_account_info = {}
    if accounts_new_struct and isinstance(accounts_new_struct, list) and accounts_new_struct[0]:
        primary_account_info = accounts_new_struct[0] if isinstance(accounts_new_struct[0], dict) else {}
    
    account_key = primary_account_info.get("accountKey", "")
    account_types_list = primary_account_info.get("accountTypes", [])
    account_type_str = ", ".join(account_types_list) if account_types_list else ""
    
    output_summary["account"] = account_key
    output_summary["alertInfo"]["alertingAccounts"] = f"{account_type_str} {account_key}".strip()

    # Extract Activity Summary data from the primary account's activitySummary
    account_activity_summary = primary_account_info.get("activitySummary", {})
    
    # Process credits
    credits_by_type = account_activity_summary.get("creditsByType", [])
    for credit_item in credits_by_type:
        percent = credit_item.get("percentOfTotal", 0)
        amount = credit_item.get("totalAmount", 0)
        count = credit_item.get("transactionCount", 0)
        min_val = credit_item.get("minTransactionAmount") # Can be None
        max_val = credit_item.get("maxTransactionAmount") # Can be None
        min_date = credit_item.get("minTransactionDate", "")
        max_date = credit_item.get("maxTransactionDate", "")
        item_type = credit_item.get("type", "")

        output_summary["creditSummary"]["percentTotal"] += percent # This sum might exceed 100 if percentOfTotal is of account total.
        output_summary["creditSummary"]["amountTotal"] += amount
        output_summary["creditSummary"]["transactionCount"] += count
        if min_val is not None and min_val < output_summary["creditSummary"]["minCreditAmount"]:
            output_summary["creditSummary"]["minCreditAmount"] = min_val
        if max_val is not None and max_val > output_summary["creditSummary"]["maxCreditAmount"]:
            output_summary["creditSummary"]["maxCreditAmount"] = max_val
        if min_date and (not output_summary["creditSummary"]["minTransactionDate"] or min_date < output_summary["creditSummary"]["minTransactionDate"]):
            output_summary["creditSummary"]["minTransactionDate"] = min_date
        if max_date and (not output_summary["creditSummary"]["maxTransactionDate"] or max_date > output_summary["creditSummary"]["maxTransactionDate"]):
            output_summary["creditSummary"]["maxTransactionDate"] = max_date
        if percent > output_summary["creditSummary"]["highestPercentValue"]:
            output_summary["creditSummary"]["highestPercentValue"] = percent
            output_summary["creditSummary"]["highestPercentType"] = item_type
            
    # Process debits
    debits_by_type = account_activity_summary.get("debitsByType", [])
    for debit_item in debits_by_type:
        percent = debit_item.get("percentOfTotal", 0)
        amount = debit_item.get("totalAmount", 0)
        count = debit_item.get("transactionCount", 0)
        min_val = debit_item.get("minTransactionAmount") # Can be None
        max_val = debit_item.get("maxTransactionAmount") # Can be None
        min_date = debit_item.get("minTransactionDate", "")
        max_date = debit_item.get("maxTransactionDate", "")
        item_type = debit_item.get("type", "")

        output_summary["debitSummary"]["percentTotal"] += percent # Similar concern as credits percentTotal
        output_summary["debitSummary"]["amountTotal"] += amount
        output_summary["debitSummary"]["transactionCount"] += count
        if min_val is not None and min_val < output_summary["debitSummary"]["minDebitAmount"]:
            output_summary["debitSummary"]["minDebitAmount"] = min_val
        if max_val is not None and max_val > output_summary["debitSummary"]["maxDebitAmount"]:
            output_summary["debitSummary"]["maxDebitAmount"] = max_val
        if min_date and (not output_summary["debitSummary"]["minTransactionDate"] or min_date < output_summary["debitSummary"]["minTransactionDate"]):
            output_summary["debitSummary"]["minTransactionDate"] = min_date
        if max_date and (not output_summary["debitSummary"]["maxTransactionDate"] or max_date > output_summary["debitSummary"]["maxTransactionDate"]):
            output_summary["debitSummary"]["maxTransactionDate"] = max_date
        if percent > output_summary["debitSummary"]["highestPercentValue"]:
            output_summary["debitSummary"]["highestPercentValue"] = percent
            output_summary["debitSummary"]["highestPercentType"] = item_type

    # Clean up infinity values
    if output_summary["creditSummary"]["minCreditAmount"] == float('inf'):
        output_summary["creditSummary"]["minCreditAmount"] = 0
    if output_summary["debitSummary"]["minDebitAmount"] == float('inf'):
        output_summary["debitSummary"]["minDebitAmount"] = 0
    
    return output_summary

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
    # case_data is now the new standardized case object (a dictionary)
    prior_sars_new_struct = case_data.get('priorSars', [])
    
    extracted_prior_cases = []
    
    if not prior_sars_new_struct:
        return [] # Return empty list if no priorSars in the new structure

    for prior_sar_item in prior_sars_new_struct:
        if not isinstance(prior_sar_item, dict):
            continue # Skip if item is not a dictionary

        # Map fields from new structure to the old structure expected by the prompt generator
        # The old structure was quite detailed. The new 'priorSars' is simpler.
        # We will only map what's available and keep the rest as default/empty.
        case_info = {
            "case_number": prior_sar_item.get("caseNumber", ""),
            "case_step": "", # Not available in new simple priorSars structure
            "alert_ids": [], # Not available
            "alert_months": [], # Not available
            "alerting_account": "", # Not available
            "scope_of_review": { # Not available
                "start": "",
                "end": ""
            },
            "sar_details": {
                "form_number": prior_sar_item.get("formNumber", ""), # Assuming new field name
                "filing_date": prior_sar_item.get("filingDate", ""),
                "amount_reported": prior_sar_item.get("amountReported", 0), # Assuming new field name
                "sar_summary": prior_sar_item.get("summary", "")
            },
            "general_comments": "" # Not available
        }
        extracted_prior_cases.append(case_info)

    return extracted_prior_cases

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