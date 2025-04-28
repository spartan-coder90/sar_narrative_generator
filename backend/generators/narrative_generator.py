"""
SAR Narrative Generator
"""
from typing import Dict, List, Any, Optional
import re
from datetime import datetime

from backend.utils.logger import get_logger
from backend.config import TEMPLATES, ACTIVITY_TYPES
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
        
        # Use LLM to determine activity type
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
    
    def generate_introduction(self) -> str:
        """
        Generate introduction section
        
        Returns:
            str: Introduction section
        """
        # Get required data
        activity_type = self.determine_activity_type()
        account_info = self.data.get("account_info", {})
        activity_summary = self.data.get("activity_summary", {})
        alert_info = self.data.get("alert_info", {})
        
        # Format template variables
        template_vars = {
            "activity_type": activity_type.get("name", "suspicious activity"),
            "total_amount": self.format_currency(activity_summary.get("total_amount", 0)),
            "derived_from": activity_type.get("derived_from", ""),
            "subjects": self.format_subject_list(),
            "account_type": account_info.get("account_type", "checking/savings"),
            "account_number": account_info.get("account_number", ""),
            "start_date": self.format_date(activity_summary.get("start_date") or alert_info.get("review_period", {}).get("start")),
            "end_date": self.format_date(activity_summary.get("end_date") or alert_info.get("review_period", {}).get("end"))
        }
        
        try:
            return TEMPLATES["INTRODUCTION"].format(**template_vars)
        except KeyError as e:
            logger.error(f"Missing key in introduction template: {e}")
            # Use LLM to generate if template formatting fails
            return self.llm_client.generate_narrative(
                "Generate the introduction section for a SAR narrative using this data:\n{template_vars}",
                {"template_vars": str(template_vars)}
            )
    
    def generate_prior_cases(self) -> str:
        """
        Generate prior cases section
        
        Returns:
            str: Prior cases section
        """
        prior_cases = self.data.get("prior_cases", [])
        
        if not prior_cases:
            return "No prior SARs were identified for the subjects or account."
        
        prior_cases_text = []
        for case in prior_cases:
            template_vars = {
                "prior_case_number": case.get("case_number", ""),
                "prior_filing_date": self.format_date(case.get("filing_date", "")),
                "prior_description": case.get("summary", "suspicious activity")
            }
            
            try:
                case_text = TEMPLATES["PRIOR_CASES"].format(**template_vars)
                prior_cases_text.append(case_text)
            except KeyError as e:
                logger.error(f"Missing key in prior cases template: {e}")
                # Use simpler format if template fails
                case_text = f"Prior SAR ({case.get('case_number', 'unknown')}) was filed on {self.format_date(case.get('filing_date', ''))}."
                prior_cases_text.append(case_text)
        
        return " ".join(prior_cases_text)
    
    def generate_account_info(self) -> str:
        """
        Generate account information section
        
        Returns:
            str: Account information section
        """
        account_info = self.data.get("account_info", {})
        
        # Format template variables
        template_vars = {
            "account_type": account_info.get("account_type", "checking/savings"),
            "account_number": account_info.get("account_number", ""),
            "open_date": self.format_date(account_info.get("open_date", "")),
            "close_date": self.format_date(account_info.get("close_date", "")),
            "account_status": "closed" if account_info.get("status") == "CLOSED" else "remains open",
            "closure_reason": account_info.get("closure_reason", "suspicious activity"),
            "funds_destination": account_info.get("funds_destination", "unknown"),
            "transfer_date": self.format_date(account_info.get("transfer_date", ""))
        }
        
        try:
            # If account is open or closure details are missing, modify template
            if account_info.get("status") != "CLOSED" or not account_info.get("close_date"):
                # Simple version for open accounts
                return f"Personal {template_vars['account_type']} account {template_vars['account_number']} was opened on {template_vars['open_date']} and remains open."
            
            return TEMPLATES["ACCOUNT_INFO"].format(**template_vars)
        except KeyError as e:
            logger.error(f"Missing key in account info template: {e}")
            # Use LLM to generate if template formatting fails
            return self.llm_client.generate_narrative(
                "Generate the account information section for a SAR narrative using this data:\n{template_vars}",
                {"template_vars": str(template_vars)}
            )
    
    def generate_multi_account_section(self) -> str:
        """
        Generate section summarizing activity across multiple accounts
        
        Returns:
            str: Multi-account activity section
        """
        account_summaries = self.data.get("account_summaries", {})
        transfers = self.data.get("inter_account_transfers", [])
        
        # If we only have one account, skip this section
        if len(account_summaries) <= 1:
            return ""
        
        # Generate summary of multi-account activity
        section = f"This investigation reviewed activity across {len(account_summaries)} related accounts. "
        
        # Add summary of each account
        for account_number, summary in account_summaries.items():
            credits = self.format_currency(summary.get("total_credits", 0))
            debits = self.format_currency(summary.get("total_debits", 0))
            txn_count = summary.get("transaction_count", 0)
            
            section += f"Account {account_number} had {credits} in total credits and {debits} in total debits across {txn_count} transactions. "
        
        # Add brief summary of transfers between accounts
        internal_transfers = [t for t in transfers if t.get("to_account") != "external"]
        if internal_transfers:
            total_transfer_amount = sum(t.get('amount', 0) for t in internal_transfers)
            section += f"There were {len(internal_transfers)} transfers between related accounts totaling {self.format_currency(total_transfer_amount)}. "
        
        return section

    def generate_activity_summary(self) -> str:
        """
        Generate factual activity summary section
        
        Returns:
            str: Activity summary section
        """
        account_info = self.data.get("account_info", {})
        activity_summary = self.data.get("activity_summary", {})
        transaction_summary = self.data.get("transaction_summary", {})
        
        # Format activity description using data from calculations
        activity_description = ""
        
        # Add information about transaction breakdown
        if transaction_summary.get("credit_breakdown"):
            top_credits = transaction_summary["credit_breakdown"][:3]  # Top 3 credit types
            credit_types = ", ".join([
                f"{item['type']} (${item['amount']:.2f}, {item['count']} transactions, {item['percent']:.1f}%)" 
                for item in top_credits
            ])
            activity_description += f"The primary credit transaction types were {credit_types}. "
        
        if transaction_summary.get("debit_breakdown"):
            top_debits = transaction_summary["debit_breakdown"][:3]  # Top 3 debit types
            debit_types = ", ".join([
                f"{item['type']} (${item['amount']:.2f}, {item['count']} transactions, {item['percent']:.1f}%)" 
                for item in top_debits
            ])
            activity_description += f"The primary debit transaction types were {debit_types}. "
        
        # Add multi-account section if applicable
        multi_account_section = self.generate_multi_account_section()
        if multi_account_section:
            activity_description += multi_account_section
        
        # Get total amounts
        total_credits = transaction_summary.get("total_credits", 0)
        total_debits = transaction_summary.get("total_debits", 0)
        
        # Format template variables
        template_vars = {
            "account_number": account_info.get("account_number", ""),
            "start_date": self.format_date(activity_summary.get("start_date", "")),
            "end_date": self.format_date(activity_summary.get("end_date", "")),
            "activity_description": activity_description,
            "total_credits": self.format_currency(total_credits),
            "total_debits": self.format_currency(total_debits)
        }
        
        # Simple template to summarize activity without analysis
        factual_template = """The account activity for {account_number} from {start_date} to {end_date} included total credits of {total_credits} and total debits of {total_debits}. {activity_description}"""
        
        try:
            return factual_template.format(**template_vars)
        except KeyError as e:
            logger.error(f"Missing key in activity summary template: {e}")
            # Use LLM only if formatting fails
            return self.llm_client.generate_narrative(
                "Generate a factual summary of account activity using this data:\n{template_vars}",
                {"template_vars": str(template_vars)}
            )

    def generate_conclusion(self) -> str:
        """
        Generate conclusion section
        
        Returns:
            str: Conclusion section
        """
        # Format template variables
        template_vars = {
            "case_number": self.data.get("case_number", "")
        }
        
        try:
            return TEMPLATES["CONCLUSION"].format(**template_vars)
        except KeyError as e:
            logger.error(f"Missing key in conclusion template: {e}")
            # Use simple conclusion if template formatting fails
            return f"In conclusion, USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number {template_vars['case_number']}."
    
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
            self.generate_activity_summary(),
            self.generate_conclusion()
        ]
        
        # Combine sections
        narrative = "\n\n".join(sections)
        
        return narrative
    
    def generate_with_llm(self) -> str:
        """
        Generate complete SAR narrative using LLM
        
        Returns:
            str: Complete SAR narrative
        """