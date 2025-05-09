"""
Enhanced SAR Narrative Generator with comprehensive recommendations and narrative sections
"""
from typing import Dict, List, Any, Optional, Tuple
import re
from datetime import datetime
import json

from backend.utils.logger import get_logger
from backend.config import TEMPLATES, ACTIVITY_TYPES, SAR_TEMPLATE, AML_RISK_INDICATORS
from backend.integrations.llm_client import LLMClient

logger = get_logger(__name__)

class NarrativeGenerator:
    """Generates SAR recommendations and narratives based on extracted and validated data"""
    
    def __init__(self, data: Dict[str, Any], llm_client: Optional[LLMClient] = None):
        """
        Initialize with validated data
        
        Args:
            data: Validated case and transaction data
            llm_client: Optional LLM client for enhanced generation
        """
        self.data = data
        self.llm_client = llm_client or LLMClient()
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
            amount = re.sub(r'[$,]', '', amount)
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
        date_match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', str(date))
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
                for fmt in ['%Y-%m-%d', '%m-%d-%Y', '%d-%m-%Y', '%Y/%m/%d']:
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
        Format list of subjects
        
        Args:
            include_relationship: Whether to include relationship information
        
        Returns:
            str: Formatted subject list
        """
        subjects = self.data.get("subjects", [])
        
        if not subjects:
            return "unknown subjects"
        
        formatted_subjects = []
        for subject in subjects:
            subject_text = subject.get("name", "unknown subject")
            
            if include_relationship and subject.get("account_relationship"):
                subject_text += f" ({subject['account_relationship']})"
            
            formatted_subjects.append(subject_text)
        
        # Join with commas, with "and" before the last item
        if len(formatted_subjects) == 1:
            return formatted_subjects[0]
        elif len(formatted_subjects) == 2:
            return f"{formatted_subjects[0]} and {formatted_subjects[1]}"
        else:
            return ", ".join(formatted_subjects[:-1]) + f", and {formatted_subjects[-1]}"
    
    # ======= SAR NARRATIVE SECTION METHODS =======
    
    def prepare_introduction_data(self) -> Dict[str, Any]:
        """
        Prepare data for the introduction section
        
        Returns:
            Dict: Formatted data for introduction section
        """
        # Get required data
        activity_type = self.determine_activity_type() or {}
        account_info = self.data.get("account_info", {})
        activity_summary = self.data.get("activity_summary", {})
        
        # Determine alert information
        alert_info = self.data.get("alert_info", [])
        if isinstance(alert_info, list) and alert_info:
            alert_info = alert_info[0]  # Use the first alert
        elif not isinstance(alert_info, dict):
            alert_info = {}
        
        # Get review period
        review_period = self.data.get("review_period", {})
        start_date = self.format_date(
            activity_summary.get("start_date") or 
            (review_period.get("start") if isinstance(review_period, dict) else "") or
            (alert_info.get("review_period", {}).get("start") if isinstance(alert_info, dict) else "")
        )
        end_date = self.format_date(
            activity_summary.get("end_date") or 
            (review_period.get("end") if isinstance(review_period, dict) else "") or
            (alert_info.get("review_period", {}).get("end") if isinstance(alert_info, dict) else "")
        )
        
        # Get total amount
        total_amount = activity_summary.get("total_amount", 0)
        if not total_amount and self.data.get("transaction_summary"):
            total_amount = self.data["transaction_summary"].get("total_credits", 0)
        
        # Prepare data for template or LLM
        return {
            "activity_type": activity_type.get("name", "suspicious activity"),
            "total_amount": self.format_currency(total_amount),
            "derived_from": activity_type.get("derived_from", ""),
            "subjects": self.format_subject_list(),
            "account_type": account_info.get("account_type", "checking/savings"),
            "account_number": account_info.get("account_number", ""),
            "start_date": start_date,
            "end_date": end_date
        }
    
    def generate_introduction(self) -> str:
        """
        Generate introduction section
        
        Returns:
            str: Introduction section
        """
        # Get formatted data
        template_vars = self.prepare_introduction_data()
        
        # Use the llm_client to generate content with enhanced PII protection
        intro_content = self.llm_client.generate_section("introduction", template_vars)
        if intro_content:
            return intro_content
        
        # Fallback to template-based approach if LLM fails
        template = SAR_TEMPLATE["SAR_NARRATIVE"]["INTRODUCTION"]
        
        try:
            return template.format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing key in introduction template: {e}")
            # Fallback to basic format
            return f"U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report {template_vars['activity_type']} totaling {template_vars['total_amount']} {template_vars.get('derived_from', 'derived from credits and debits')} by {template_vars['subjects']} in {template_vars['account_type']} account number {template_vars['account_number']}. The suspicious activity was conducted from {template_vars['start_date']} through {template_vars['end_date']}."
    
    def prepare_prior_cases_data(self) -> Dict[str, Any]:
        """
        Prepare data for the prior cases section
        
        Returns:
            Dict: Formatted data for prior cases section
        """
        prior_cases = self.data.get("prior_cases", [])
        prior_cases_text = []
        
        for case in prior_cases:
            case_text = f"Prior SAR (Case Number: {case.get('case_number', '')}) was filed on {self.format_date(case.get('filing_date', ''))} reporting {case.get('summary', 'suspicious activity')}."
            prior_cases_text.append(case_text)
        
        return {
            "prior_cases": prior_cases,
            "prior_cases_text": " ".join(prior_cases_text) if prior_cases_text else "No prior SARs were identified for the subjects or account."
        }
    
    def generate_prior_cases(self) -> str:
        """
        Generate prior cases section
        
        Returns:
            str: Prior cases section
        """
        # Get formatted data
        data = self.prepare_prior_cases_data()
        
        # Use the llm_client to generate content
        prior_cases_content = self.llm_client.generate_section("prior_cases", data)
        if prior_cases_content:
            return prior_cases_content
            
        # Fallback if LLM fails
        prior_cases = self.data.get("prior_cases", [])
        if not prior_cases:
            return "No prior SARs were identified for the subjects or account."
        
        prior_cases_text = []
        for case in prior_cases:
            try:
                template_vars = {
                    "prior_case_number": case.get("case_number", ""),
                    "prior_filing_date": self.format_date(case.get("filing_date", "")),
                    "prior_description": case.get("summary", "suspicious activity")
                }
                case_text = TEMPLATES["PRIOR_CASES"].format(**template_vars)
                prior_cases_text.append(case_text)
            except KeyError as e:
                logger.warning(f"Missing key in prior cases template: {e}")
                case_text = f"Prior SAR (Case Number: {case.get('case_number', '')}) was filed on {self.format_date(case.get('filing_date', ''))} reporting {case.get('summary', 'suspicious activity')}."
                prior_cases_text.append(case_text)
        
        return " ".join(prior_cases_text)
    
    def prepare_account_subject_info_data(self) -> Dict[str, Any]:
        """
        Prepare data for account and subject information section
        
        Returns:
            Dict: Formatted data for account and subject information
        """
        account_info = self.data.get("account_info", {})
        subjects = self.data.get("subjects", [])
        
        return {
            "account_type": account_info.get("account_type", "checking/savings"),
            "account_number": account_info.get("account_number", ""),
            "open_date": self.format_date(account_info.get("open_date", "")),
            "close_date": self.format_date(account_info.get("close_date", "")),
            "account_status": "closed" if account_info.get("status", "").upper() == "CLOSED" else "remains open",
            "closure_reason": account_info.get("closure_reason", ""),
            "subjects": subjects
        }
    
    def generate_account_info(self) -> str:
        """
        Generate account information section
        
        Returns:
            str: Account information section
        """
        data = self.prepare_account_subject_info_data()
        
        # Use the llm_client to generate content
        account_info_content = self.llm_client.generate_section("account_subject_info", data)
        if account_info_content:
            # Only take the account information part
            paragraphs = account_info_content.split("\n\n")
            if paragraphs:
                return paragraphs[0]
        
        # Fallback to template approach
        template_vars = {
            "account_type": data["account_type"],
            "account_number": data["account_number"],
            "open_date": data["open_date"],
            "close_date": data["close_date"],
            "account_status": data["account_status"],
            "closure_reason": data["closure_reason"]
        }
        
        try:
            # If account is open or closure details are missing, use a simple template
            if template_vars["account_status"] != "closed" or not template_vars["close_date"]:
                return f"Personal {template_vars['account_type']} account {template_vars['account_number']} was opened on {template_vars['open_date']} and remains open."
            
            # Otherwise use the full template
            return TEMPLATES["ACCOUNT_INFO"].format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing key in account info template: {e}")
            
            # Basic fallback format
            return f"Personal {template_vars['account_type']} account {template_vars['account_number']} was opened on {template_vars['open_date']} and {template_vars['account_status']}."
    
    def generate_subject_info(self) -> str:
        """
        Generate subject information section
        
        Returns:
            str: Subject information section
        """
        data = self.prepare_account_subject_info_data()
        
        # Use the llm_client to generate content
        subject_info_content = self.llm_client.generate_section("account_subject_info", data)
        if subject_info_content:
            # Only take the subject information part
            paragraphs = subject_info_content.split("\n\n")
            if len(paragraphs) > 1:
                return paragraphs[1]
        
        # Fallback approach
        subjects = data["subjects"]
        if not subjects:
            return "No subject information is available."
        
        subject_paragraphs = []
        
        for subject in subjects:
            name = subject.get("name", "")
            occupation = subject.get("occupation", "")
            employer = subject.get("employer", "")
            relationship = subject.get("account_relationship", "")
            
            # Create basic subject description using the template
            try:
                if occupation or employer:
                    template_vars = {
                        "name": name,
                        "occupation": occupation or "unknown occupation", 
                        "employer": employer or "unknown employer",
                        "relationship": relationship or "account holder"
                    }
                    subject_info = TEMPLATES["SUBJECT_INFO"].format(**template_vars)
                else:
                    subject_info = f"{name} is listed as {relationship or 'an account holder'} on the account."
                
                subject_paragraphs.append(subject_info)
            except KeyError as e:
                logger.warning(f"Missing key in subject info template: {e}")
                # Fallback to basic format
                subject_info = f"{name}"
                if occupation or employer:
                    subject_info += f" is employed as a {occupation}" if occupation else ""
                    subject_info += f" at {employer}" if employer else ""
                    subject_info += "."
                
                if relationship:
                    subject_info += f" {name} is listed as {relationship} on the account."
                
                subject_paragraphs.append(subject_info)
        
        return " ".join(subject_paragraphs)
    
    def prepare_activity_data(self) -> Dict[str, Any]:
        """
        Prepare transaction and activity data
        
        Returns:
            Dict: Formatted activity data
        """
        account_info = self.data.get("account_info", {})
        activity_summary = self.data.get("activity_summary", {})
        transaction_summary = self.data.get("transaction_summary", {})
        
        # Get activity dates
        start_date = self.format_date(activity_summary.get("start_date", ""))
        end_date = self.format_date(activity_summary.get("end_date", ""))
        
        # Create activity description
        activity_description = ""
        
        # Add credit breakdown info
        if transaction_summary.get("credit_breakdown"):
            top_credits = transaction_summary["credit_breakdown"][:3]  # Top 3 credit types
            credit_types = ", ".join([
                f"{item['type']} ({self.format_currency(item['amount'])}, {item['count']} transactions)"
                for item in top_credits
            ])
            activity_description += f"The primary credit transaction types were {credit_types}. "
        
        # Add debit breakdown info
        if transaction_summary.get("debit_breakdown"):
            top_debits = transaction_summary["debit_breakdown"][:3]  # Top 3 debit types
            debit_types = ", ".join([
                f"{item['type']} ({self.format_currency(item['amount'])}, {item['count']} transactions)" 
                for item in top_debits
            ])
            activity_description += f"The primary debit transaction types were {debit_types}. "
        
        # Get transaction samples
        unusual_activity = self.data.get("unusual_activity", {})
        samples = []
        
        if unusual_activity and unusual_activity.get("transactions"):
            for txn in unusual_activity["transactions"][:3]:  # Top 3 transactions
                date = self.format_date(txn.get("date", ""))
                amount = self.format_currency(txn.get("amount", 0))
                txn_type = txn.get("type", "")
                
                samples.append({
                    "date": date,
                    "amount": amount,
                    "type": txn_type
                })
        
        # Get AML risks based on detected activity type
        activity_type = self.determine_activity_type()
        aml_risks = ", ".join(activity_type.get("indicators", ["suspicious transactions"]))
        
        return {
            "account_number": account_info.get("account_number", ""),
            "start_date": start_date,
            "end_date": end_date,
            "activity_description": activity_description,
            "total_credits": self.format_currency(transaction_summary.get("total_credits", 0)),
            "total_debits": self.format_currency(transaction_summary.get("total_debits", 0)),
            "aml_risks": aml_risks,
            "transaction_samples": samples
        }
    
    def generate_activity_summary(self) -> str:
        """
        Generate activity summary section
        
        Returns:
            str: Activity summary section
        """
        data = self.prepare_activity_data()
        
        # Use the llm_client to generate content
        activity_summary_content = self.llm_client.generate_section("activity_summary", data)
        if activity_summary_content:
            return activity_summary_content
        
        # Fallback approach using templates
        try:
            return TEMPLATES["ACTIVITY_SUMMARY"].format(**data)
        except KeyError as e:
            logger.warning(f"Missing key in activity summary template: {e}")
            
            # Basic fallback format
            return f"The account activity for {data['account_number']} from {data['start_date']} to {data['end_date']} included total credits of {data['total_credits']} and total debits of {data['total_debits']}. {data['activity_description']} The AML risks associated with these transactions are as follows: {data['aml_risks']}."
    
    def generate_transaction_samples(self) -> str:
        """
        Generate a section with transaction samples
        
        Returns:
            str: Transaction samples section
        """
        unusual_activity = self.data.get("unusual_activity", {})
        transactions = unusual_activity.get("transactions", [])
        
        if not transactions:
            return ""
        
        # Prepare transaction data for LLM
        transaction_data = {
            "transactions": transactions
        }
        
        # Use the llm_client to generate content
        samples_content = self.llm_client.generate_section("transaction_samples", transaction_data)
        if samples_content:
            return samples_content
        
        # Fallback approach
        sample_count = min(5, len(transactions))
        sample_text = "A sample of the suspicious transactions includes:"
        
        for i, txn in enumerate(transactions[:sample_count]):
            date = self.format_date(txn.get("date", ""))
            amount = self.format_currency(txn.get("amount", 0))
            txn_type = txn.get("type", "")
            desc = txn.get("description", "")
            
            sample_text += f" {date}: {amount}"
            if txn_type:
                sample_text += f" ({txn_type})"
            if desc:
                sample_text += f" - {desc}"
            
            if i < sample_count - 1:
                sample_text += ";"
            else:
                sample_text += "."
        
        return sample_text
    
    def prepare_conclusion_data(self) -> Dict[str, Any]:
        """
        Prepare data for conclusion section
        
        Returns:
            Dict: Formatted data for conclusion
        """
        activity_type = self.determine_activity_type()
        account_info = self.data.get("account_info", {})
        activity_summary = self.data.get("activity_summary", {})
        review_period = self.data.get("review_period", {})
        
        # Get start and end dates
        start_date = self.format_date(
            activity_summary.get("start_date") or 
            (review_period.get("start") if isinstance(review_period, dict) else "")
        )
        
        end_date = self.format_date(
            activity_summary.get("end_date") or 
            (review_period.get("end") if isinstance(review_period, dict) else "")
        )
        
        return {
            "case_number": self.data.get("case_number", ""),
            "activity_type": activity_type.get("name", "suspicious activity"),
            "activity_appearance": activity_type.get("name", "suspicious activity"),
            "total_amount": activity_summary.get("total_amount", 0),
            "subjects": self.format_subject_list(include_relationship=False),
            "subject_name": self.format_subject_list(include_relationship=False),
            "account_type": account_info.get("account_type", "checking/savings"),
            "account_number": account_info.get("account_number", ""),
            "start_date": start_date,
            "end_date": end_date
        }
    
    def generate_conclusion(self) -> str:
        """
        Generate conclusion section
        
        Returns:
            str: Conclusion section
        """
        data = self.prepare_conclusion_data()
        
        # Format currency value for template
        data["total_amount"] = self.format_currency(data["total_amount"])
        
        # Use the llm_client to generate content
        conclusion_content = self.llm_client.generate_section("conclusion", data)
        if conclusion_content:
            return conclusion_content
        
        # Fallback approach using templates
        conclusion_template = SAR_TEMPLATE["SAR_NARRATIVE"]["CONCLUSION"]
        
        try:
            return conclusion_template.format(**data)
        except KeyError as e:
            logger.warning(f"Missing key in conclusion template: {e}")
            
            # Basic fallback format
            return f"In conclusion, USB is reporting {data['total_amount']} in {data['activity_type']} which gave the appearance of suspicious activity and were conducted by {data['subjects']} in account number {data['account_number']} from {data['start_date']} through {data['end_date']}. USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number {data['case_number']}."
    
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
        
        # Prepare data for LLM
        alert_data = {
            "case_number": case_number,
            "account_info": account_info,
            "alert_info": alert_info,
            "subject_names": self.format_subject_list(include_relationship=False)
        }
        
        # Use LLM to generate content
        alerting_activity_content = self.llm_client.generate_section("alert_summary", alert_data)
        if alerting_activity_content:
            return alerting_activity_content
        
        # Fallback approach
        if isinstance(alert_info, dict):
            alert_info = [alert_info]
        elif not isinstance(alert_info, list):
            alert_info = []
        
        if not alert_info:
            return f"{case_number}: Unknown alerting account alerted for unknown reason."
        
        # Format alert month and details
        alert_months = []
        alert_descriptions = []
        
        for alert in alert_info:
            if alert.get("alert_month"):
                alert_months.append(alert.get("alert_month"))
            if alert.get("description"):
                alert_descriptions.append(alert.get("description"))
        
        alert_month_text = ", ".join(alert_months) if alert_months else "unknown month"
        alert_desc_text = "; ".join(alert_descriptions) if alert_descriptions else "unknown reason"
        
        return f"{case_number}: {account_info.get('account_type', 'account')} {account_info.get('account_number', '')} alerted in {alert_month_text} for {alert_desc_text}."
    
    def generate_prior_sars_summary(self) -> str:
        """
        Generate prior SARs section for recommendation
        
        Returns:
            str: Prior SARs section
        """
        prior_cases = self.data.get("prior_cases", [])
        
        # Prepare data for LLM
        prior_case_data = {
            "prior_cases": prior_cases
        }
        
        # Use LLM to generate content
        prior_sars_content = self.llm_client.generate_section("prior_case_sar_summary", prior_case_data)
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
        
        # Prepare data for LLM
        review_data = {
            "review_period": review_period,
            "account_info": account_info
        }
        
        # Use LLM to generate content
        scope_content = self.llm_client.generate_section("scope_of_review", review_data)
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
        
        # Prepare data for LLM
        summary_data = {
            "account_summaries": account_summaries,
            "transaction_summary": transaction_summary
        }
        
        # Use LLM to generate content
        investigation_content = self.llm_client.generate_section("investigation_summary", summary_data)
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
        
        # Prepare data for LLM
        conclusion_data = {
            "is_sar": True,  # Default to SAR recommendation
            "account_info": account_info,
            "subject_names": self.format_subject_list(include_relationship=False),
            "activity_type": activity_type.get("name", "suspicious activity"),
            "derived_from": activity_type.get("derived_from", "derived from credits and debits"),
            "unusual_activity": unusual_activity
        }
        
        # Use LLM to generate content
        rec_conclusion_content = self.llm_client.generate_section("recommendation_conclusion", conclusion_data)
        if rec_conclusion_content:
            return rec_conclusion_content
        
        # Fallback approach
        start_date = self.format_date(unusual_activity.get("summary", {}).get("date_range", {}).get("start", ""))
        end_date = self.format_date(unusual_activity.get("summary", {}).get("date_range", {}).get("end", ""))
        total_amount = self.format_currency(unusual_activity.get("summary", {}).get("total_amount", 0))
        
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
        action = "close" if account_info.get("status", "").upper() == "CLOSED" else "retain"
        
        # Prepare data for LLM
        retain_close_data = {
            "action": action,
            "account_info": account_info,
            "subject_names": self.format_subject_list(include_relationship=False)
        }
        
        # Use LLM to generate content
        retain_close_content = self.llm_client.generate_section("retain_close", retain_close_data)
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
        
        # Prepare data for LLM
        cta_data = {
            "referral_type": "CTA",
            "account_info": account_info,
            "subject_names": self.format_subject_list(include_relationship=False),
            "unusual_activity": unusual_activity
        }
        
        # Use LLM to generate content
        cta_content = self.llm_client.generate_section("referral", cta_data)
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
        Generate complete SAR narrative
        
        Returns:
            str: Complete SAR narrative
        """
        sections = [
            self.generate_introduction(),
            self.generate_prior_cases(),
            self.generate_account_info(),
            self.generate_subject_info(),
            self.generate_activity_summary(),
            self.generate_transaction_samples(),
            self.generate_conclusion()
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
            "cta": self.generate_cta_section()
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
            "recommendation": recommendation
        }
    
    def _split_narrative_into_sections(self, narrative: str) -> Dict[str, Dict[str, str]]:
        """
        Split the narrative into sections for UI
        
        Args:
            narrative: Complete narrative text
            
        Returns:
            Dict: Sections with ID, title, and content
        """
        if not narrative:
            # Handle empty narrative
            return {
                "introduction": {"id": "introduction", "title": "Introduction", "content": ""},
                "prior_cases": {"id": "prior_cases", "title": "Prior Cases", "content": ""},
                "account_info": {"id": "account_info", "title": "Account Information", "content": ""},
                "subject_info": {"id": "subject_info", "title": "Subject Information", "content": ""},
                "activity_summary": {"id": "activity_summary", "title": "Activity Summary", "content": ""},
                "transaction_samples": {"id": "transaction_samples", "title": "Sample Transactions", "content": ""},
                "conclusion": {"id": "conclusion", "title": "Conclusion", "content": ""}
            }
        
        paragraphs = narrative.split('\n\n')
        
        # Define default sections
        sections = {
            "introduction": {
                "id": "introduction",
                "title": "Introduction",
                "content": paragraphs[0] if len(paragraphs) > 0 else ""
            },
            "prior_cases": {
                "id": "prior_cases",
                "title": "Prior Cases",
                "content": paragraphs[1] if len(paragraphs) > 1 else ""
            },
            "account_info": {
                "id": "account_info",
                "title": "Account Information",
                "content": paragraphs[2] if len(paragraphs) > 2 else ""
            },
            "subject_info": {
                "id": "subject_info",
                "title": "Subject Information",
                "content": paragraphs[3] if len(paragraphs) > 3 else ""
            },
            "activity_summary": {
                "id": "activity_summary",
                "title": "Activity Summary",
                "content": paragraphs[4] if len(paragraphs) > 4 else ""
            },
            "transaction_samples": {
                "id": "transaction_samples",
                "title": "Sample Transactions",
                "content": paragraphs[5] if len(paragraphs) > 5 else ""
            },
            "conclusion": {
                "id": "conclusion",
                "title": "Conclusion",
                "content": paragraphs[6] if len(paragraphs) > 6 else ""
            }
        }
        
        return sections