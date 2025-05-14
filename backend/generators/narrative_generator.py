"""
Updated SAR Narrative Generator with sections aligned to requirements document
"""
from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime
import json

from backend.utils.logger import get_logger
from backend.config import TEMPLATES, ACTIVITY_TYPES, SAR_TEMPLATE, AML_RISK_INDICATORS
from backend.utils.section_extractors import (
    extract_unusual_activity_summary,
    generate_suspicious_activity_prompt,
)

logger = get_logger(__name__)

# Define new section IDs to match requirements
SECTION_IDS = {
    "SUSPICIOUS_ACTIVITY_SUMMARY": "suspicious_activity_summary",
    "PRIOR_CASES": "prior_cases",
    "ACCOUNT_SUBJECT_INFO": "account_subject_info",
    "SUSPICIOUS_ACTIVITY_ANALYSIS": "suspicious_activity_analysis",
    "CONCLUSION": "conclusion",
}

# Define section titles to match requirements
SECTION_TITLES = {
    SECTION_IDS[
        "SUSPICIOUS_ACTIVITY_SUMMARY"
    ]: "Section 1 - Suspicious Activity Summary",
    SECTION_IDS["PRIOR_CASES"]: "Section 2 - Prior Cases/SARs",
    SECTION_IDS["ACCOUNT_SUBJECT_INFO"]: "Section 3 - Account/Subject Information",
    SECTION_IDS[
        "SUSPICIOUS_ACTIVITY_ANALYSIS"
    ]: "Section 4 - Suspicious Activity Analysis",
    SECTION_IDS["CONCLUSION"]: "Section 5 - Conclusion",
}


class NarrativeGenerator:
    """Generates SAR recommendations and narratives based on extracted and validated data"""

    def __init__(
        self, data: Dict[str, Any], llm_client: Optional[Any] = None, model: str = None
    ):
        """
        Initialize with validated data

        Args:
            data: Validated case and transaction data
            llm_client: Optional LLM client for enhanced generation
            model: Model name to use for generation
        """
        self.data = data
        # Pass the model parameter when creating a new LLMClient
        if not llm_client:
            # Import here to avoid circular import
            from backend.integrations.llm_client import LLMClient

            self.llm_client = LLMClient(model=model)
        else:
            self.llm_client = llm_client
        self.activity_type = None

    def determine_activity_type(self) -> Dict[str, Any]:
        """
        Determine type of suspicious activity

        Returns:
            Dict: Activity type information
        """
        if self.activity_type:
            return self.activity_type

        # Use the LLM client's method to determine activity type
        self.activity_type = self.llm_client.determine_activity_type(self.data)
        return self.activity_type

    def format_currency(self, amount: Any) -> str:
        """
        Format currency values

        Args:
            amount: Currency amount

        Returns:
            str: Formatted currency amount
        """
        if not amount:
            return "$0.00"

        # Convert string to float if needed
        if isinstance(amount, str):
            # Remove currency symbols and commas
            amount = re.sub(r"[$,]", "", amount)
            try:
                amount = float(amount)
            except ValueError:
                return "$0.00"

        # Format with commas and 2 decimal places
        return "${:,.2f}".format(amount)

    def format_date(self, date: Any) -> str:
        """
        Format date to MM/DD/YYYY

        Args:
            date: Date to format

        Returns:
            str: Formatted date
        """
        if date is None or date == "":
            return ""

        if isinstance(date, datetime):
            return date.strftime("%m/%d/%Y")

        # Check if already in correct format
        date_match = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", str(date))
        if date_match:
            month, day, year = date_match.groups()

            # Ensure 4-digit year
            if len(year) == 2:
                year = f"20{year}" if int(year) < 50 else f"19{year}"

            # Format with leading zeros
            return f"{int(month):02d}/{int(day):02d}/{year}"

        # Try to parse string as date
        try:
            if isinstance(date, str):
                # Try different formats
                for fmt in ["%Y-%m-%d", "%m-%d-%Y", "%d-%m-%Y", "%Y/%m/%d"]:
                    try:
                        parsed_date = datetime.strptime(date, fmt)
                        return parsed_date.strftime("%m/%d/%Y")
                    except ValueError:
                        continue
        except:
            pass

        return str(date)

    def format_subject_list(self, include_relationship: bool = True) -> str:
        """
        Format list of subjects with improved type checking

        Args:
            include_relationship: Whether to include relationship information

        Returns:
            str: Formatted subject list
        """
        subjects = self.data.get("subjects", [])

        # Handle the case where subjects is a string
        if isinstance(subjects, str):
            return subjects

        # Handle empty subjects
        if not subjects:
            return "unknown subjects"

        formatted_subjects = []
        for subject in subjects:
            # Handle the case where subject is a dictionary or a string
            if isinstance(subject, dict):
                subject_text = subject.get("name", "unknown subject")

                if include_relationship and subject.get("account_relationship"):
                    subject_text += f" ({subject['account_relationship']})"
            else:
                # If subject is a string or other type, convert to string
                subject_text = str(subject)

            formatted_subjects.append(subject_text)

        # Join with commas, with "and" before the last item
        if len(formatted_subjects) == 1:
            return formatted_subjects[0]
        elif len(formatted_subjects) == 2:
            return f"{formatted_subjects[0]} and {formatted_subjects[1]}"
        else:
            return (
                ", ".join(formatted_subjects[:-1]) + f", and {formatted_subjects[-1]}"
            )

    # ======= SAR NARRATIVE SECTION METHODS =======

    def generate_suspicious_activity_summary(self) -> str:
        """
        Generate Section 1 - Suspicious Activity Summary with enhanced transaction analysis

        Returns:
            str: Suspicious activity summary section
        """
        # Extract case data for full analysis
        case_data = self.data.get("full_data", [])

        # Calculate transaction summary stats
        txn_summary = extract_unusual_activity_summary(case_data)

        # Generate prompt for LLM
        prompt = generate_suspicious_activity_prompt(txn_summary, case_data)

        # Get required data for fallback
        activity_type = self.determine_activity_type() or {}
        account_info = self.data.get("account_info", {})
        activity_summary = self.data.get("activity_summary", {})

        # Generate content using LLM
        summary_content = self.llm_client.generate_content(
            prompt, max_tokens=500, temperature=0.1
        )
        if summary_content:
            return summary_content

        # Fallback to template-based approach if LLM generation fails
        subjects = self.format_subject_list()
        account_type = account_info.get("account_type", "checking/savings")
        account_number = account_info.get("account_number", "")

        # Get date range
        start_date = txn_summary["txnSummary"][
            "minTransactionDate"
        ] or activity_summary.get("start_date", "")
        end_date = txn_summary["txnSummary"][
            "maxTransactionDate"
        ] or activity_summary.get("end_date", "")

        # Get the dominant activity type
        credit_type = txn_summary["txnSummary"]["customLanguage"][
            "highestCountCustomLanguageCredit"
        ]
        debit_type = txn_summary["txnSummary"]["customLanguage"][
            "highestCountCustomLanguageDebit"
        ]
        activity_description = (
            f"{credit_type} and {debit_type}"
            if credit_type and debit_type
            else activity_type.get("name", "suspicious activity")
        )

        # Format total amount
        total_amount = self.format_currency(txn_summary["txnSummary"]["totalAmountSAR"])

        return f"U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report {activity_description} totaling {total_amount} by {subjects} in {account_type} account number {account_number}. The suspicious activity was conducted from {start_date} through {end_date}. This SAR contains an attached Comma Separated Value (CSV) file that provides additional details of the suspicious transactions being reported in this SAR."

    def generate_prior_cases(self) -> str:
        """
        Generate Section 2 - Prior Cases/SARs

        Returns:
            str: Prior cases section
        """
        prior_cases = self.data.get("prior_cases", [])

        # Create the prompt for prior cases
        prior_cases_prompt = f"""
            Write a paragraph about prior SARs (Suspicious Activity Reports) based ONLY on the following information:
            
            {json.dumps(prior_cases) if prior_cases else "No prior cases found."}
            
            If there are no prior cases, write exactly: "No prior SARs were identified for the subjects or account."
            
            If there are prior cases, for each case, include:
            - Case number
            - Any alert IDs associated with the case
            - Review period (start and end dates)
            - SAR form number if available
            - Filing date if available
            - Brief summary of the case
            
            Format each prior case as: "Case # [case number]: Alerting account # [account number] reviewed from [start date] to [end date] due to [alerting activity]. SAR filed on [filing date]: [summary]"
            """

        # Try to generate with LLM
        prior_cases_content = self.llm_client.generate_content(
            prior_cases_prompt, max_tokens=500, temperature=0.1
        )
        if prior_cases_content:
            return prior_cases_content

        # Fallback to basic formatting
        if not prior_cases:
            return "No prior SARs were identified for the subjects or account."

        prior_cases_text = ""
        for case in prior_cases:
            case_number = case.get("case_number", "")
            filing_date = case.get("filing_date", "")
            summary = case.get("summary", "")
            alert_ids = case.get("alert_id", [])
            review_period = case.get("review_period", {})

            prior_cases_text += f"Case # {case_number}: Alerting account # reviewed from {review_period.get('start', '')} to {review_period.get('end', '')} due to {', '.join(alert_ids) if alert_ids else 'unknown alerting activity'}.\n"
            prior_cases_text += f"SAR filed on {filing_date}: {summary}\n\n"

        return prior_cases_text

    def generate_account_subject_info(self) -> str:
        """
        Generate Section 3 - Account/Subject Information

        Returns:
            str: Combined account and subject information
        """
        account_info = self.data.get("account_info", {})
        subjects = self.data.get("subjects", [])

        # Create account information section
        account_text = f"Personal {account_info.get('account_type', 'checking/savings')} account {account_info.get('account_number', '')} was opened on {account_info.get('open_date', '')} and "

        if account_info.get("close_date"):
            account_text += f"was closed on {account_info.get('close_date')}. "
            account_text += f"The account was closed due to {account_info.get('closure_reason', '[INVESTIGATOR TO INSERT CLOSURE REASON]')}. "
            account_text += f"The account closure funds were moved to [INVESTIGATOR TO INSERT DESTINATION] on [INVESTIGATOR TO INSERT DATE] via [INVESTIGATOR TO INSERT METHOD]."
        else:
            account_text += "remains open."

        # Create subject information section
        subject_text = "\n\n"
        foreign_subjects = []

        for subject in subjects:
            if not isinstance(subject, dict):
                continue

            subject_name = subject.get("name", "")
            occupation = subject.get("occupation", "")
            employer = subject.get("employer", "")
            relationship = subject.get("account_relationship", "")
            nationality = subject.get("nationality", "")

            subject_text += (
                f"{subject_name} is employed as a {occupation} at {employer}. "
            )

            if relationship:
                subject_text += (
                    f"{subject_name} is listed as {relationship} on the account. "
                )

            subject_text += "\n\n"

            # Track foreign nationals for separate section
            if nationality and nationality not in ["US", "USA", "United States"]:
                foreign_subjects.append(subject)

        # Add section for foreign nationals if any
        if foreign_subjects:
            subject_text += "The following foreign nationalities and identifications were identified:\n\n"

            for subject in foreign_subjects:
                subject_name = subject.get("name", "")
                nationality = subject.get("nationality", "")

                subject_text += f"{subject_name}: {nationality}, [INVESTIGATOR TO INSERT ID TYPE] # [INVESTIGATOR TO INSERT ID NUMBER] issued on [ISSUE DATE] and expires on [EXPIRATION DATE].\n\n"

        # Create the prompt for account-subject info
        prompt = f"""
        Write Section 3 - Account/Subject Information based ONLY on the following information:
        
        ACCOUNT INFORMATION:
        {account_text}
        
        SUBJECT INFORMATION:
        {subject_text}
        
        Your response should include:
        1. Account details including type, number, opening date, and status (open or closed)
        2. If closed, the reason, where funds were moved, and method
        3. Information about all subjects including name, occupation, employer, and relationship to account
        4. Detailed information about any foreign nationals including their nationality and identification documents
        
        Organize the section clearly with account information first, followed by subject information, and finally foreign national details if applicable.
        """

        # Try to generate with LLM
        account_subject_content = self.llm_client.generate_content(
            prompt, max_tokens=750, temperature=0.1
        )
        if account_subject_content:
            return account_subject_content

        # Fallback to template approach
        return account_text + subject_text

    def generate_suspicious_activity_analysis(self) -> str:
        """
        Generate Section 4 - Suspicious Activity Analysis

        Returns:
            str: Suspicious activity analysis section
        """
        # Get account and transaction information
        account_info = self.data.get("account_info", {})
        activity_summary = self.data.get("activity_summary", {})
        transaction_summary = self.data.get("transaction_summary", {})

        # Get review period
        review_period = self.data.get("review_period", {})
        start_date = self.format_date(
            activity_summary.get("start_date")
            or (review_period.get("start") if isinstance(review_period, dict) else "")
        )
        end_date = self.format_date(
            activity_summary.get("end_date")
            or (review_period.get("end") if isinstance(review_period, dict) else "")
        )

        # Get transaction types and amounts
        credit_breakdown = transaction_summary.get("credit_breakdown", [])
        debit_breakdown = transaction_summary.get("debit_breakdown", [])

        transaction_types_text = ""

        if credit_breakdown:
            credit_types = []
            for item in credit_breakdown[:3]:  # Top 3 types
                if "type" in item and "amount" in item:
                    credit_types.append(
                        f"{item['type']} totaling {self.format_currency(item['amount'])}"
                    )

            if credit_types:
                transaction_types_text += ", ".join(credit_types)

        if debit_breakdown:
            debit_types = []
            for item in debit_breakdown[:3]:  # Top 3 types
                if "type" in item and "amount" in item:
                    debit_types.append(
                        f"{item['type']} totaling {self.format_currency(item['amount'])}"
                    )

            if debit_types:
                if transaction_types_text:
                    transaction_types_text += ", and "
                transaction_types_text += ", ".join(debit_types)

        # Get AML risks
        activity_type = self.determine_activity_type() or {}
        aml_risks = activity_type.get("indicators", ["suspicious transactions"])
        aml_risks_text = ", ".join(aml_risks)

        # Get transaction samples
        unusual_activity = self.data.get("unusual_activity", {})
        transactions = unusual_activity.get("transactions", [])

        transaction_samples = ""
        if transactions:
            transaction_samples = "A sample of the suspicious transactions includes:"
            sample_count = min(5, len(transactions))

            for i, txn in enumerate(transactions[:sample_count]):
                date = self.format_date(txn.get("date", ""))
                amount = self.format_currency(txn.get("amount", 0))
                txn_type = txn.get("type", "")
                desc = txn.get("description", "")

                transaction_samples += f" {date}: {amount}"
                if txn_type:
                    transaction_samples += f" ({txn_type})"
                if desc:
                    transaction_samples += f" - {desc}"

                if i < sample_count - 1:
                    transaction_samples += ";"
                else:
                    transaction_samples += "."

        # Create the prompt for activity analysis
        prompt = f"""
        Write Section 4 - Suspicious Activity Analysis based ONLY on the following information:
        
        Account Number: {account_info.get('account_number', '')}
        Date Range: {start_date} to {end_date}
        Transaction Types: {transaction_types_text}
        AML Risk Indicators: {aml_risks_text}
        
        Transaction Samples:
        {transaction_samples}
        
        Your response should begin with:
        "The suspicious activity identified in account [account number] was conducted from [start date] to [end date] and consisted of [transaction types and amounts]. The AML risks associated with these transactions are as follows: [risk indicators]."
        
        Then include the transaction samples section.
        
        Add a placeholder for the investigator to add additional analysis: "[Investigator to provide additional analysis of the transactions and AML risks]"
        """

        # Try to generate with LLM
        analysis_content = self.llm_client.generate_content(
            prompt, max_tokens=750, temperature=0.1
        )
        if analysis_content:
            return analysis_content

        # Fallback to template approach
        return f"The suspicious activity identified in account {account_info.get('account_number', '')} was conducted from {start_date} to {end_date} and consisted of {transaction_types_text}. The AML risks associated with these transactions are as follows: {aml_risks_text}.\n\n{transaction_samples}\n\n[Investigator to provide additional analysis of the transactions and AML risks]"

    def generate_conclusion(self) -> str:
        """
        Generate Section 5 - Conclusion

        Returns:
            str: Conclusion section
        """
        # Get case number
        case_number = self.data.get("case_number", "")

        # Create the prompt for conclusion
        prompt = f"""
        Write Section 5 - Conclusion for a SAR (Suspicious Activity Report) with the following information:
        
        Case Number: {case_number}
        
        The conclusion should simply state:
        "In conclusion, USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequestaml@usbank.com referencing AML case number [case number]."
        
        Use ONLY the exact case number provided. Do not add or change anything else.
        """

        # Try to generate with LLM
        conclusion_content = self.llm_client.generate_content(
            prompt, max_tokens=200, temperature=0.1
        )
        if conclusion_content:
            return conclusion_content

        # Fallback to template approach
        return f"In conclusion, USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequestaml@usbank.com referencing AML case number {case_number}."

    # ======= RECOMMENDATION SECTION METHODS =======

    def generate_alerting_activity(self) -> str:
        """
        Generate alerting activity section for recommendation

        Returns:
            str: Alerting activity section
        """
        case_number = self.data.get("case_number", "")
        account_info = self.data.get("account_info", {})
        alert_info = self.data.get("alert_info", [])
        alerting_activity_summary = self.data.get("alerting_activity_summary", {})

        # Check if we have the alerting activity summary
        if alerting_activity_summary and isinstance(alerting_activity_summary, dict):
            # Use the summary to create a more detailed section
            alert_info_data = alerting_activity_summary.get("alertInfo", {})
            account = alerting_activity_summary.get("account", "")
            credit_summary = alerting_activity_summary.get("creditSummary", {})
            debit_summary = alerting_activity_summary.get("debitSummary", {})

            # Format the data for the LLM
            formatted_template_data = {
                "case_number": alert_info_data.get("caseNumber", case_number),
                "alerting_accounts": alert_info_data.get("alertingAccounts", ""),
                "alerting_months": alert_info_data.get("alertingMonths", ""),
                "alert_description": alert_info_data.get("alertDescription", ""),
                "account_number": account,
                "credit_amount_total": self.format_currency(
                    credit_summary.get("amountTotal", 0)
                ),
                "credit_transaction_count": credit_summary.get("transactionCount", 0),
                "credit_min_date": credit_summary.get("minTransactionDate", ""),
                "credit_max_date": credit_summary.get("maxTransactionDate", ""),
                "credit_min_amount": self.format_currency(
                    credit_summary.get("minCreditAmount", 0)
                ),
                "credit_max_amount": self.format_currency(
                    credit_summary.get("maxCreditAmount", 0)
                ),
                "credit_highest_percent_type": credit_summary.get(
                    "highestPercentType", ""
                ),
                "credit_highest_percent_value": credit_summary.get(
                    "highestPercentValue", 0
                ),
                "debit_amount_total": self.format_currency(
                    debit_summary.get("amountTotal", 0)
                ),
                "debit_transaction_count": debit_summary.get("transactionCount", 0),
                "debit_min_date": debit_summary.get("minTransactionDate", ""),
                "debit_max_date": debit_summary.get("maxTransactionDate", ""),
                "debit_min_amount": self.format_currency(
                    debit_summary.get("minDebitAmount", 0)
                ),
                "debit_max_amount": self.format_currency(
                    debit_summary.get("maxDebitAmount", 0)
                ),
                "debit_highest_percent_type": debit_summary.get(
                    "highestPercentType", ""
                ),
                "debit_highest_percent_value": debit_summary.get(
                    "highestPercentValue", 0
                ),
            }

            # Create prompt for LLM directly in this method
            alerting_activity_prompt = f"""Summarize this bank account alert information directly without any introductory phrases:

    ALERT INFORMATION:
    - Case Number: {formatted_template_data["case_number"]}
    - Alerting Account(s): {formatted_template_data["alerting_accounts"]}
    - Alerting Month(s): {formatted_template_data["alerting_months"]}
    - Alert Description: {formatted_template_data["alert_description"]}

    ACCOUNT: {formatted_template_data["account_number"]}

    CREDITS:
    - Total amount: {formatted_template_data["credit_amount_total"]}
    - Number of transactions: {formatted_template_data["credit_transaction_count"]}
    - Date range: {formatted_template_data["credit_min_date"]} to {formatted_template_data["credit_max_date"]}
    - Transaction amounts: {formatted_template_data["credit_min_amount"]} to {formatted_template_data["credit_max_amount"]}
    - Most common activity: {formatted_template_data["credit_highest_percent_type"]} ({formatted_template_data["credit_highest_percent_value"]}%)

    DEBITS:
    - Total amount: {formatted_template_data["debit_amount_total"]}
    - Number of transactions: {formatted_template_data["debit_transaction_count"]}
    - Date range: {formatted_template_data["debit_min_date"]} to {formatted_template_data["debit_max_date"]}
    - Transaction amounts: {formatted_template_data["debit_min_amount"]} to {formatted_template_data["debit_max_amount"]}
    - Most common activity: {formatted_template_data["debit_highest_percent_type"]} ({formatted_template_data["debit_highest_percent_value"]}%)

    Write a clear summary in this exact format:

    1. First paragraph: Start with the Case Number, then describe the alerting accounts, alerting months, and include a brief description of the alert activity.

    2. Second paragraph: Summarize credit activity focusing on total amount, number of transactions, most common type of activity with its percentage, and range of amounts.

    3. Third paragraph: Summarize debit activity focusing on total amount, number of transactions, most common type of activity with its percentage, and range of amounts.

    Keep sentences short and simple. Do not use phrases like "Here is the summary" or "In conclusion." Start immediately with the case number and keep the summary factual without analysis beyond what's shown in the data."""

            # Generate content using LLM directly
            alerting_activity_content = self.llm_client.generate_content(
                alerting_activity_prompt, max_tokens=600, temperature=0.2
            )
            if alerting_activity_content:
                return alerting_activity_content

        # Fall back to simpler approach if alerting activity summary is not available
        # Create a direct prompt
        alert_summary_prompt = f"""
        Create an Alert Summary section for a SAR recommendation following this format:

        "[Case Number]: [Account Type] and [Account Number] alerted in [Alert Month] for [Alert Description]."

        Use ONLY these exact details:
        - Case number: {case_number}
        - Account type: {account_info.get('account_type', 'checking/savings')}
        - Account number: {account_info.get('account_number', '')}
        - Account holders: {self.format_subject_list(include_relationship=False)}
        
        Alert information:
        {json.dumps(alert_info) if isinstance(alert_info, list) else json.dumps(alert_info) if isinstance(alert_info, dict) else "No alert information available."}

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        If there are multiple alerts, combine them in a single summary by account.
        """

        alerting_activity_content = self.llm_client.generate_content(
            alert_summary_prompt, max_tokens=400, temperature=0.1
        )
        if alerting_activity_content:
            return alerting_activity_content

        # Fallback approach
        if isinstance(alert_info, dict):
            alert_info = [alert_info]
        elif not isinstance(alert_info, list):
            alert_info = []

        if not alert_info:
            return (
                f"{case_number}: Unknown alerting account alerted for unknown reason."
            )

        # Format alert month and details
        alert_months = []
        alert_descriptions = []

        for alert in alert_info:
            if alert.get("alert_month"):
                alert_months.append(alert.get("alert_month"))
            if alert.get("description"):
                alert_descriptions.append(alert.get("description"))

        alert_month_text = ", ".join(alert_months) if alert_months else "unknown month"
        alert_desc_text = (
            "; ".join(alert_descriptions) if alert_descriptions else "unknown reason"
        )

        return f"{case_number}: {account_info.get('account_type', 'account')} {account_info.get('account_number', '')} alerted in {alert_month_text} for {alert_desc_text}."

    def generate_prior_sars_summary(self) -> str:
        """
        Generate prior SARs section for recommendation

        Returns:
            str: Prior SARs section
        """
        prior_cases = self.data.get("prior_cases", [])

        # Create a direct prompt for prior cases summary
        prior_case_sar_prompt = f"""
        Create a Prior Cases/SARs summary section for a SAR recommendation using ONLY the information provided below:

        {json.dumps(prior_cases) if prior_cases else "No prior cases found."}

        If there are no prior cases, write exactly: "No prior SARs were identified for the subjects or account."
        
        For each prior case, include:
        "Case [Case Number]: Account [Account Number] reviewed from [Review Period Start] to [Review Period End] due to [Alert Description]."

        If the case resulted in a SAR filing, add:
        "SAR Form [SAR Form Number] was filed on [Filing Date] reporting [Summary]."

        IMPORTANT: Do not alter, estimate, or make up any information not provided.
        """

        prior_sars_content = self.llm_client.generate_content(
            prior_case_sar_prompt, max_tokens=600, temperature=0.1
        )
        if prior_sars_content:
            return prior_sars_content

        # Fallback approach
        if not prior_cases:
            return "No prior cases or SARs were identified."

        prior_case_summaries = []

        for case in prior_cases:
            case_number = case.get("case_number", "")
            filing_date = self.format_date(case.get("filing_date", ""))
            sar_form = case.get("sar_form_number", "")
            summary = case.get("summary", "")

            case_text = f"Case {case_number}"
            if filing_date:
                case_text += f" filed on {filing_date}"
            if sar_form:
                case_text += f" (SAR Form {sar_form})"
            if summary:
                case_text += f": {summary}"

            prior_case_summaries.append(case_text)

        return "Prior SARs: " + "; ".join(prior_case_summaries) + "."

    def generate_scope_of_review(self) -> str:
        """
        Generate scope of review section for recommendation

        Returns:
            str: Scope of review section
        """
        review_period = self.data.get("review_period", {})
        account_info = self.data.get("account_info", {})

        # Create a direct prompt for scope of review
        scope_of_review_prompt = f"""
        Create a Scope of Review section for a SAR recommendation following this format:

        "Accounts were reviewed from [Start Date] to [End Date]."

        If any account was opened or closed during the review period, add:
        "Account [Account Number] was opened on [Open Date]." or "Account [Account Number] was closed on [Close Date]."

        Use ONLY these exact details:
        - Start date: {review_period.get('start', '')}
        - End date: {review_period.get('end', '')}
        - Account number: {account_info.get('account_number', '')}
        - Open date: {account_info.get('open_date', '')}
        - Close date: {account_info.get('close_date', '')}

        IMPORTANT: Do not alter, estimate, or make up any information not provided.
        """

        scope_content = self.llm_client.generate_content(
            scope_of_review_prompt, max_tokens=200, temperature=0.1
        )
        if scope_content:
            return scope_content

        # Fallback approach
        start_date = self.format_date(review_period.get("start", ""))
        end_date = self.format_date(review_period.get("end", ""))

        if start_date and end_date:
            return f"{start_date} - {end_date}"
        else:
            return "Review period not specified."

    def generate_investigation_summary(self) -> str:
        """
        Generate investigation summary section for recommendation

        Returns:
            str: Investigation summary section
        """
        account_summaries = self.data.get("account_summaries", {})
        transaction_summary = self.data.get("transaction_summary", {})

        # Create a direct prompt for investigation summary
        investigation_summary_prompt = f"""
        Create a Summary of Investigation section for a SAR recommendation using ONLY the information provided below:

        {json.dumps(account_summaries)}

        Transaction Summary:
        {json.dumps(transaction_summary)}

        For each account, write:
        "Account [Account Number] consisted of the following top credit activity: [credit types with amounts]. Account [Account Number] consisted of the following top debit activity: [debit types with amounts]."

        If there are significant or alerting transactions, add:
        "The alerting or significant identified transactions consisted of [transaction type] conducted from [date range] totaling [amount]."

        IMPORTANT: Do not alter, estimate, or make up any information not provided.
        Limit your response to factual details from the provided data.
        """

        investigation_content = self.llm_client.generate_content(
            investigation_summary_prompt, max_tokens=750, temperature=0.1
        )
        if investigation_content:
            return investigation_content

        # Fallback approach - placeholder for investigator input
        return "[Investigator to provide summary of investigation findings, including identified suspicious activity patterns and supporting evidence.]"

    def generate_recommendation_conclusion(self) -> str:
        """
        Generate recommendation conclusion section

        Returns:
            str: Recommendation conclusion section
        """
        account_info = self.data.get("account_info", {})
        subjects = self.data.get("subjects", [])
        activity_type = self.determine_activity_type()
        unusual_activity = self.data.get("unusual_activity", {})

        # Create a direct prompt for recommendation conclusion
        recommendation_conclusion_prompt = f"""
        Create a Conclusion section for a SAR recommendation following this format:

        "In conclusion a SAR is recommended to report unusual [Activity Type] activity involving USB accounts [Account Number] and subjects [Subject Names]. The unusual activity totaled [Total Amount] [Derived From] between [Start Date] and [End Date]."

        Use ONLY these exact details:
        - Account number: {account_info.get('account_number', '')}
        - Subject names: {self.format_subject_list(include_relationship=False)}
        - Activity type: {activity_type.get('name', 'suspicious activity')}
        - Total amount: {self.format_currency(unusual_activity.get('summary', {}).get('total_amount', 0))}
        - Derived from: {activity_type.get('derived_from', 'derived from credits and debits')}
        - Start date: {unusual_activity.get('summary', {}).get('date_range', {}).get('start', '')}
        - End date: {unusual_activity.get('summary', {}).get('date_range', {}).get('end', '')}

        IMPORTANT: Do not alter, estimate, or make up any information not provided.
        """

        rec_conclusion_content = self.llm_client.generate_content(
            recommendation_conclusion_prompt, max_tokens=400, temperature=0.1
        )
        if rec_conclusion_content:
            return rec_conclusion_content

        # Fallback approach
        start_date = self.format_date(
            unusual_activity.get("summary", {}).get("date_range", {}).get("start", "")
        )
        end_date = self.format_date(
            unusual_activity.get("summary", {}).get("date_range", {}).get("end", "")
        )
        total_amount = self.format_currency(
            unusual_activity.get("summary", {}).get("total_amount", 0)
        )

        return f"In conclusion a SAR is recommended to report unusual {activity_type.get('name', 'suspicious activity')} activity involving USB accounts {account_info.get('account_number', '')} and subjects {self.format_subject_list(include_relationship=False)}. The unusual activity totaled {total_amount} {activity_type.get('derived_from', 'derived from credits and debits')} between {start_date} and {end_date}."

    def generate_retain_close(self) -> str:
        """
        Generate retain or close section for recommendation

        Returns:
            str: Retain or close section
        """
        subjects = self.data.get("subjects", [])
        account_info = self.data.get("account_info", {})

        # Determine action based on account status
        action = (
            "close" if account_info.get("status", "").upper() == "CLOSED" else "retain"
        )

        # Create direct prompt for retain/close
        retain_close_prompt = f"""
        Write a {"Retain" if action == "retain" else "Close"} Customer Relationship section for a SAR recommendation:

        "{"Retain" if action == "retain" else "Close"} Customer Relationship(s): {"Accounts and relationships related to " + self.format_subject_list(include_relationship=False) + " are recommended to remain open." if action == "retain" else "Account and relationships related to " + account_info.get('account_number', '') + " and " + self.format_subject_list(include_relationship=False) + " are recommended to close. The following risks were identified with this customer: [Investigator to insert the unusual activity analysis here]"}"

        IMPORTANT: Do not alter, estimate, or make up any information not provided.
        """

        retain_close_content = self.llm_client.generate_content(
            retain_close_prompt, max_tokens=400, temperature=0.1
        )
        if retain_close_content:
            return retain_close_content

        # Fallback approach
        if action == "retain":
            return "Retain: No further action is necessary at this time. The customer relationship(s) can remain open."
        else:
            return f"Closure: Requesting closure for USB customer(s) {self.format_subject_list(include_relationship=False)} due to suspicious activity.\n\nThe risk factors are as follows: [Investigator to list risk factors]\n\n[Investigator to provide closure summary]"

    def generate_cta_section(self) -> str:
        """
        Generate CTA (Customer Transaction Assessment) section

        Returns:
            str: CTA section
        """
        account_info = self.data.get("account_info", {})
        unusual_activity = self.data.get("unusual_activity", {})

        # Create a direct prompt for CTA
        cta_prompt = f"""
        Write a Customer Transaction Assessment (CTA) referral based ONLY on the information provided:

        Account number: {account_info.get('account_number', '')}
        Account holders: {self.format_subject_list(include_relationship=False)}
        Review period: {unusual_activity.get('summary', {}).get('date_range', {}).get('start', '')} to {unusual_activity.get('summary', {}).get('date_range', {}).get('end', '')}
        Activity total: {self.format_currency(unusual_activity.get('summary', {}).get('total_amount', 0))}

        Format as:
        "Account [account number], held by [signers], was reviewed from [start date] to [end date] and identified potentially unusual activity conducted from [activity start date] to [activity end date] which totaled [total amount]. The activity consisted of [transaction types and amounts]. [Investigator to input analysis of activity/reason for CTA]."

        IMPORTANT: Do not alter, estimate, or make up any information not provided.
        """

        cta_content = self.llm_client.generate_content(
            cta_prompt, max_tokens=600, temperature=0.1
        )
        if cta_content:
            return cta_content

        # Fallback approach
        return """CTA Request Type:

What is our customer's current or most recent occupation(s) and employer? If the customer is a student, what is their field of study and what school is being attended?

What is the nature of the customer's business? If available, please provide the customer's website as well as any physical addresses for their business locations.

What is the source of the customer's account credit activity (cash, wires, other transactions) as described in the summary?

What is the purpose of the customer's account debit activity as described in the summary?

Does the customer expect to have similar transactions (cash, wires or other activity described in the summary) in the future? If yes, what is the anticipated frequency, amount(s) and purpose of the activity?

What is the purpose of the wire transactions occurring in the customer's accounts? What is our customer's relationship to the wire originators and/or wire beneficiaries referenced in the summary?"""

    # ======= COMPLETE GENERATION METHODS =======

    def generate_narrative(self) -> str:
        """
        Generate complete SAR narrative according to requirements

        Returns:
            str: Complete SAR narrative
        """
        sections = [
            self.generate_suspicious_activity_summary(),
            self.generate_prior_cases(),
            self.generate_account_subject_info(),
            self.generate_suspicious_activity_analysis(),
            self.generate_conclusion(),
        ]

        # Filter out empty sections
        sections = [section for section in sections if section]

        # Combine sections
        narrative = "\n\n".join(sections)

        return narrative

    def generate_recommendation(self) -> Dict[str, str]:
        """
        Generate complete SAR recommendation

        Returns:
            Dict: All recommendation sections
        """
        recommendation = {
            "alerting_activity": self.generate_alerting_activity(),
            "prior_sars": self.generate_prior_sars_summary(),
            "scope_of_review": self.generate_scope_of_review(),
            "investigation_summary": self.generate_investigation_summary(),
            "conclusion": self.generate_recommendation_conclusion(),
            "retain_close": self.generate_retain_close(),
            "cta": self.generate_cta_section(),
        }

        return recommendation

    def generate_all(self) -> Dict[str, Any]:
        """
        Generate both SAR narrative and recommendation

        Returns:
            Dict: Complete data with narrative and recommendation
        """
        narrative = self.generate_narrative()
        recommendation = self.generate_recommendation()
        sections = self._split_narrative_into_sections(narrative)

        return {
            "narrative": narrative,
            "sections": sections,
            "recommendation": recommendation,
        }

    def _split_narrative_into_sections(
        self, narrative: str
    ) -> Dict[str, Dict[str, str]]:
        """
        Split the narrative into sections for UI according to requirements document

        Args:
            narrative: Complete narrative text

        Returns:
            Dict: Sections with ID, title, and content
        """
        if not narrative:
            # Handle empty narrative
            return {
                SECTION_IDS["SUSPICIOUS_ACTIVITY_SUMMARY"]: {
                    "id": SECTION_IDS["SUSPICIOUS_ACTIVITY_SUMMARY"],
                    "title": SECTION_TITLES[SECTION_IDS["SUSPICIOUS_ACTIVITY_SUMMARY"]],
                    "content": "",
                },
                SECTION_IDS["PRIOR_CASES"]: {
                    "id": SECTION_IDS["PRIOR_CASES"],
                    "title": SECTION_TITLES[SECTION_IDS["PRIOR_CASES"]],
                    "content": "",
                },
                SECTION_IDS["ACCOUNT_SUBJECT_INFO"]: {
                    "id": SECTION_IDS["ACCOUNT_SUBJECT_INFO"],
                    "title": SECTION_TITLES[SECTION_IDS["ACCOUNT_SUBJECT_INFO"]],
                    "content": "",
                },
                SECTION_IDS["SUSPICIOUS_ACTIVITY_ANALYSIS"]: {
                    "id": SECTION_IDS["SUSPICIOUS_ACTIVITY_ANALYSIS"],
                    "title": SECTION_TITLES[
                        SECTION_IDS["SUSPICIOUS_ACTIVITY_ANALYSIS"]
                    ],
                    "content": "",
                },
                SECTION_IDS["CONCLUSION"]: {
                    "id": SECTION_IDS["CONCLUSION"],
                    "title": SECTION_TITLES[SECTION_IDS["CONCLUSION"]],
                    "content": "",
                },
            }

        paragraphs = narrative.split("\n\n")

        # Define new sections based on the requirements document
        sections = {
            SECTION_IDS["SUSPICIOUS_ACTIVITY_SUMMARY"]: {
                "id": SECTION_IDS["SUSPICIOUS_ACTIVITY_SUMMARY"],
                "title": SECTION_TITLES[SECTION_IDS["SUSPICIOUS_ACTIVITY_SUMMARY"]],
                "content": paragraphs[0] if len(paragraphs) > 0 else "",
            },
            SECTION_IDS["PRIOR_CASES"]: {
                "id": SECTION_IDS["PRIOR_CASES"],
                "title": SECTION_TITLES[SECTION_IDS["PRIOR_CASES"]],
                "content": paragraphs[1] if len(paragraphs) > 1 else "",
            },
            SECTION_IDS["ACCOUNT_SUBJECT_INFO"]: {
                "id": SECTION_IDS["ACCOUNT_SUBJECT_INFO"],
                "title": SECTION_TITLES[SECTION_IDS["ACCOUNT_SUBJECT_INFO"]],
                "content": paragraphs[2] if len(paragraphs) > 2 else "",
            },
            SECTION_IDS["SUSPICIOUS_ACTIVITY_ANALYSIS"]: {
                "id": SECTION_IDS["SUSPICIOUS_ACTIVITY_ANALYSIS"],
                "title": SECTION_TITLES[SECTION_IDS["SUSPICIOUS_ACTIVITY_ANALYSIS"]],
                "content": paragraphs[3] if len(paragraphs) > 3 else "",
            },
            SECTION_IDS["CONCLUSION"]: {
                "id": SECTION_IDS["CONCLUSION"],
                "title": SECTION_TITLES[SECTION_IDS["CONCLUSION"]],
                "content": paragraphs[4] if len(paragraphs) > 4 else "",
            },
        }

        return sections
