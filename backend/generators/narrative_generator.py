"""
Enhanced SAR Narrative Generator with updated template structure for AML/Fraud requirements
"""
from typing import Dict, List, Any, Optional
import re
from datetime import datetime
import json

from backend.utils.logger import get_logger
from backend.config import TEMPLATES, ACTIVITY_TYPES, SAR_TEMPLATE, AML_RISK_INDICATORS
from backend.integrations.llm_client import LLMClient

logger = get_logger(__name__)

class NarrativeGenerator:
    """Generates SAR narratives based on extracted and validated data"""
    
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
        
        # Use the SAR_TEMPLATE format from config
        template = SAR_TEMPLATE["SAR_NARRATIVE"]["INTRODUCTION"]
        
        # Try template formatting first
        try:
            return template.format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing key in introduction template: {e}")
            
            # Fall back to LLM as a second option
            return self.llm_client.generate_section("introduction", template_vars) or \
                f"U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report {template_vars['activity_type']} totaling {template_vars['total_amount']} {template_vars['derived_from']} by {template_vars['subjects']} in {template_vars['account_type']} account number {template_vars['account_number']}. The suspicious activity was conducted from {template_vars['start_date']} through {template_vars['end_date']}."
    
    def prepare_prior_cases_data(self) -> Dict[str, Any]:
        """
        Prepare data for the prior cases section
        
        Returns:
            Dict: Formatted data for prior cases section
        """
        prior_cases = self.data.get("prior_cases", [])
        
        if not prior_cases:
            return {"prior_cases_text": "No prior SARs were identified for the subjects or account."}
        
        prior_cases_text = []
        for case in prior_cases:
            case_text = f"Prior SAR (Case Number: {case.get('case_number', '')}) was filed on {self.format_date(case.get('filing_date', ''))} reporting {case.get('summary', 'suspicious activity')}."
            prior_cases_text.append(case_text)
        
        return {"prior_cases_text": " ".join(prior_cases_text)}
    
    def generate_prior_cases(self) -> str:
        """
        Generate prior cases section
        
        Returns:
            str: Prior cases section
        """
        prior_cases = self.data.get("prior_cases", [])
        
        if not prior_cases:
            return "No prior SARs were identified for the subjects or account."
        
        # Use the SAR_TEMPLATE format for prior cases
        template = TEMPLATES["PRIOR_CASES"]
        
        prior_cases_text = []
        for case in prior_cases:
            template_vars = {
                "prior_case_number": case.get("case_number", ""),
                "prior_filing_date": self.format_date(case.get("filing_date", "")),
                "prior_description": case.get("summary", "suspicious activity")
            }
            
            try:
                case_text = template.format(**template_vars)
                prior_cases_text.append(case_text)
            except KeyError as e:
                logger.warning(f"Missing key in prior cases template: {e}")
                case_text = f"Prior SAR (Case Number: {template_vars['prior_case_number']}) was filed on {template_vars['prior_filing_date']} reporting {template_vars['prior_description']}."
                prior_cases_text.append(case_text)
        
        # If template formatting failed, try LLM
        if not prior_cases_text:
            data = self.prepare_prior_cases_data()
            llm_result = self.llm_client.generate_section("prior_cases", data)
            return llm_result if llm_result else data["prior_cases_text"]
            
        return " ".join(prior_cases_text)
    
    def prepare_account_info_data(self) -> Dict[str, Any]:
        """
        Prepare data for the account information section
        
        Returns:
            Dict: Formatted data for account info section
        """
        account_info = self.data.get("account_info", {})
        
        return {
            "account_type": account_info.get("account_type", "checking/savings"),
            "account_number": account_info.get("account_number", ""),
            "open_date": self.format_date(account_info.get("open_date", "")),
            "close_date": self.format_date(account_info.get("close_date", "")),
            "account_status": "closed" if account_info.get("status", "").upper() == "CLOSED" else "remains open",
            "closure_reason": account_info.get("closure_reason", "suspicious activity"),
            "funds_destination": account_info.get("funds_destination", "unknown"),
            "transfer_date": self.format_date(account_info.get("transfer_date", ""))
        }
    
    def generate_account_info(self) -> str:
        """
        Generate account information section
        
        Returns:
            str: Account information section
        """
        template_vars = self.prepare_account_info_data()
        
        # Use appropriate template from SAR_TEMPLATE
        try:
            # If account is open or closure details are missing, use a simple template
            if template_vars["account_status"] != "closed" or not template_vars["close_date"]:
                return f"Personal {template_vars['account_type']} account {template_vars['account_number']} was opened on {template_vars['open_date']} and remains open."
            
            # Otherwise use the full template
            return TEMPLATES["ACCOUNT_INFO"].format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing key in account info template: {e}")
            
            # Fall back to LLM or a simple default
            return self.llm_client.generate_section("account_info", template_vars) or \
                   f"Personal {template_vars['account_type']} account {template_vars['account_number']} was opened on {template_vars['open_date']} and {template_vars['account_status']}."
    
    def prepare_subject_info_data(self) -> List[Dict[str, Any]]:
        """
        Prepare data for subject information
        
        Returns:
            List[Dict]: List of formatted subject data
        """
        subjects = self.data.get("subjects", [])
        formatted_subjects = []
        
        for subject in subjects:
            formatted_subjects.append({
                "name": subject.get("name", "unknown subject"),
                "occupation": subject.get("occupation", ""),
                "employer": subject.get("employer", ""),
                "relationship": subject.get("account_relationship", ""),
                "is_primary": subject.get("is_primary", False),
                "address": subject.get("address", "")
            })
            
        return formatted_subjects
    
    def generate_subject_info(self) -> str:
        """
        Generate subject information section
        
        Returns:
            str: Subject information section
        """
        formatted_subjects = self.prepare_subject_info_data()
        
        if not formatted_subjects:
            return "No subject information is available."
        
        subject_paragraphs = []
        
        for subject in formatted_subjects:
            name = subject["name"]
            occupation = subject["occupation"]
            employer = subject["employer"]
            relationship = subject["relationship"]
            
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
        template_vars = self.prepare_activity_data()
        
        # Use template from SAR_TEMPLATE
        try:
            return TEMPLATES["ACTIVITY_SUMMARY"].format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing key in activity summary template: {e}")
            
            # Fall back to LLM or a simple default
            return self.llm_client.generate_section("activity_summary", template_vars) or \
                   f"The account activity for {template_vars['account_number']} from {template_vars['start_date']} to {template_vars['end_date']} included total credits of {template_vars['total_credits']} and total debits of {template_vars['total_debits']}."
    
    def generate_transaction_samples(self) -> str:
        """
        Generate a section with transaction samples
        
        Returns:
            str: Transaction samples section
        """
        unusual_activity = self.data.get("unusual_activity", {})
        
        if not unusual_activity or not unusual_activity.get("transactions"):
            return ""
        
        # Get up to 5 transactions to showcase
        transactions = unusual_activity.get("transactions", [])
        sample_count = min(5, len(transactions))
        
        # Format sample list
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
        template_vars = self.prepare_conclusion_data()
        
        # Format currency value
        template_vars["total_amount"] = self.format_currency(template_vars["total_amount"]).replace("$", "")
        
        # Use the SAR_TEMPLATE conclusion format
        conclusion_template = SAR_TEMPLATE["SAR_NARRATIVE"]["CONCLUSION"]
        
        try:
            return conclusion_template.format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing key in conclusion template: {e}")
            
            # Fall back to LLM or a simple default
            return self.llm_client.generate_section("conclusion", template_vars) or \
                   f"In conclusion, USB is reporting ${template_vars['total_amount']} in {template_vars['activity_type']} which gave the appearance of suspicious activity and were conducted by {template_vars['subjects']} in account number {template_vars['account_number']} from {template_vars['start_date']} through {template_vars['end_date']}. USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number {template_vars['case_number']}."
    
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
        Generate SAR recommendation sections
        
        Returns:
            Dict[str, str]: Dictionary of recommendation sections
        """
        # Prepare template variables
        case_data = self.data
        alert_info = case_data.get("alert_info", [])
        if isinstance(alert_info, list) and alert_info:
            alert_info = alert_info[0]
        
        activity_type = self.determine_activity_type()
        account_info = case_data.get("account_info", {})
        activity_summary = self.data.get("activity_summary", {})
        
        # Format alerting activity
        account_types = account_info.get("account_type", "checking/savings")
        account_number = account_info.get("account_number", "")
        alerting_months = alert_info.get("alert_month", "") if isinstance(alert_info, dict) else ""
        alerting_description = alert_info.get("description", "") if isinstance(alert_info, dict) else ""
        
        alerting_vars = {
            "case_number": case_data.get("case_number", ""),
            "alerting_account_types": account_types,
            "alerting_account_numbers": account_number,
            "alerting_months": alerting_months,
            "alerting_description": alerting_description
        }
        
        # Format prior SARs
        prior_cases = case_data.get("prior_cases", [])
        if prior_cases:
            prior_sar_content = self.generate_prior_cases()
        else:
            prior_sar_content = "No prior SARs were identified for the subjects or account."
        
        # Format scope of review
        review_period = case_data.get("review_period", {})
        review_start = self.format_date(review_period.get("start", ""))
        review_end = self.format_date(review_period.get("end", ""))
        
        # Format conclusion
        conclusion_vars = {
            "unusual_activity_types": activity_type.get("name", "suspicious activity"),
            "unusual_activity_usb_accounts": account_info.get("account_number", ""),
            "sar_subjects": self.format_subject_list(include_relationship=False),
            "unusual_activity_total": self.format_currency(activity_summary.get("total_amount", 0)),
            "derived_from": activity_type.get("derived_from", "derived from credits and debits"),
            "unusual_activity_start_date": self.format_date(activity_summary.get("start_date", "")),
            "unusual_activity_end_date": self.format_date(activity_summary.get("end_date", ""))
        }
        
        # Generate recommendation sections
        try:
            alerting_activity = SAR_TEMPLATE["RECOMMENDATION"]["ALERTING_ACTIVITY"].format(**alerting_vars)
            prior_sars = SAR_TEMPLATE["RECOMMENDATION"]["PRIOR_SARS"].format(prior_sar_content=prior_sar_content)
            scope_of_review = SAR_TEMPLATE["RECOMMENDATION"]["SCOPE_OF_REVIEW"].format(
                review_start_date=review_start,
                review_end_date=review_end
            )
            # Summary of investigation requires user input, so we'll leave a placeholder
            summary_of_investigation = SAR_TEMPLATE["RECOMMENDATION"]["SUMMARY_OF_INVESTIGATION"].format(
                investigation_summary="[Investigator to input summary here]"
            )
            conclusion = SAR_TEMPLATE["RECOMMENDATION"]["CONCLUSION"].format(**conclusion_vars)
            
            return {
                "alerting_activity": alerting_activity,
                "prior_sars": prior_sars,
                "scope_of_review": scope_of_review,
                "summary_of_investigation": summary_of_investigation,
                "conclusion": conclusion
            }
        except KeyError as e:
            logger.warning(f"Missing key in recommendation template: {e}")
            
            # Fallback to simpler template
            return {
                "alerting_activity": f"**Alerting Activity:** {case_data.get('case_number', '')}: Account {account_number} alerted for suspicious activity.",
                "prior_sars": f"**Prior SARs:** {prior_sar_content}",
                "scope_of_review": f"**Scope of Review:** {review_start} - {review_end}",
                "summary_of_investigation": "**Summary of Investigation:** [Investigator to input summary here]",
                "conclusion": f"**Conclusion:** In conclusion, a SAR is recommended for suspicious activity totaling {self.format_currency(activity_summary.get('total_amount', 0))} conducted from {self.format_date(activity_summary.get('start_date', ''))} to {self.format_date(activity_summary.get('end_date', ''))}."
            }
    
    def generate_referrals(self) -> Dict[str, str]:
        """
        Generate referral templates based on case data
        
        Returns:
            Dict[str, str]: Dictionary of referral templates
        """
        # Placeholder for referral content - this would be populated based on the case data
        # and the specific requirements for different referral types
        
        referrals = {}
        
        # Check for potential indicators that might suggest referrals
        account_info = self.data.get("account_info", {})
        transaction_summary = self.data.get("transaction_summary", {})
        unusual_activity = self.data.get("unusual_activity", {})
        
        # Check for potential structuring (multiple transactions just under $10,000)
        if unusual_activity and unusual_activity.get("transactions"):
            transactions = unusual_activity.get("transactions", [])
            potential_structuring = any(
                9000 <= float(re.sub(r'[^\d.]', '', str(t.get("amount", 0)))) < 10000
                for t in transactions
            )
            
            if potential_structuring:
                # Format for AAD_FTS (First Time Structuring)
                account_number = account_info.get("account_number", "")
                subjects = self.format_subject_list(include_relationship=False)
                start_date = self.format_date(self.data.get("review_period", {}).get("start", ""))
                end_date = self.format_date(self.data.get("review_period", {}).get("end", ""))
                activity_start = self.format_date(unusual_activity.get("start_date", start_date))
                activity_end = self.format_date(unusual_activity.get("end_date", end_date))
                total_amount = self.format_currency(sum(float(re.sub(r'[^\d.]', '', str(t.get("amount", 0)))) for t in transactions))
                
                referrals["AAD_FTS"] = f"Account #{account_number}, held by {subjects}, was reviewed from {start_date} to {end_date} and identified potentially structured cash deposits/withdrawals conducted from {activity_start} to {activity_end} which totaled {total_amount}. A first time structuring letter will be sent to the customer."
        
        # Check for potential BIP (Business in Personal)
        if transaction_summary:
            business_keywords = ["LLC", "Inc", "Corp", "Company", "Business", "Enterprise"]
            credit_breakdown = transaction_summary.get("credit_breakdown", [])
            
            has_business_transactions = any(
                any(keyword in str(item.get("description", "")) for keyword in business_keywords)
                for item in credit_breakdown
            )
            
            if has_business_transactions:
                # Format for BIP
                account_number = account_info.get("account_number", "")
                subjects = self.format_subject_list(include_relationship=False)
                start_date = self.format_date(self.data.get("review_period", {}).get("start", ""))
                end_date = self.format_date(self.data.get("review_period", {}).get("end", ""))
                
                # Calculate total amount of business transactions
                business_transactions = [
                    item for item in credit_breakdown
                    if any(keyword in str(item.get("description", "")) for keyword in business_keywords)
                ]
                total_business_amount = self.format_currency(sum(float(re.sub(r'[^\d.]', '', str(item.get("amount", 0)))) for item in business_transactions))
                
                referrals["BIP"] = f"Account #{account_number}, held by {subjects}, was reviewed from {start_date} to {end_date} and identified potentially business in personal activity. The business in personal activity totaled {total_business_amount}. Please inform customer to cease all business in personal activity and open a business account."
        
        return referrals
    
    def generate_with_llm(self) -> str:
        """
        Generate complete SAR narrative using LLM in a minimized way
        
        Returns:
            str: Complete SAR narrative
        """
        # Generate each section separately
        intro_data = self.prepare_introduction_data()
        prior_cases_data = self.prepare_prior_cases_data()
        account_info_data = self.prepare_account_info_data()
        activity_data = self.prepare_activity_data()
        conclusion_data = self.prepare_conclusion_data()
        
        # Generate each section using the LLM
        intro = self.llm_client.generate_section("introduction", intro_data)
        prior_cases = self.llm_client.generate_section("prior_cases", prior_cases_data)
        account_info = self.llm_client.generate_section("account_info", account_info_data)
        activity_summary = self.llm_client.generate_section("activity_summary", activity_data)
        conclusion = self.llm_client.generate_section("conclusion", conclusion_data)
        
        # If any section failed, use the template-based approach
        if not intro or not conclusion:
            logger.warning("LLM generation failed for critical sections, falling back to template approach")
            return self.generate_narrative()
        
        # Combine sections
        sections = [
            intro,
            prior_cases,
            account_info,
            self.generate_subject_info(),  # Use template-based subject info
            activity_summary,
            self.generate_transaction_samples(),  # Use template-based transaction samples
            conclusion
        ]
        
        # Filter out empty sections
        sections = [section for section in sections if section]
        
        # Combine sections
        narrative = "\n\n".join(sections)
        
        return narrative