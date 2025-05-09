"""
Enhanced LLM Client with robust PII/PCI protection and fact preservation
"""
import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
import requests
from hashlib import md5

from backend.utils.logger import get_logger
import backend.config as config

logger = get_logger(__name__)

class LLMClient:
    """Client for interacting with language models with enhanced PII/PCI protection and fact preservation"""
    
    # Patterns for detecting PII/PCI data with more precise matching
    PII_PATTERNS = {
        "account_number": r'(?<!\w)(\d{10,})(?!\w)|(?<!\w)([A-Z0-9]{16,})(?!\w)',  # Account numbers (digits or alphanumeric)
        "name": r'(?<!\w)([A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+)(?!\w)',  # Names in ALL CAPS
        "address": r'(?<!\w)(\d+\s+[A-Z][A-Za-z\s,\.]+(?:ST|AVE|RD|LN|DR|BLVD|STREET|AVENUE|ROAD))(?!\w)',  # Addresses
        "phone": r'(?<!\w)(\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4})(?!\w)',  # Phone numbers
        "ssn": r'(?<!\w)(\d{3}[-\.\s]?\d{2}[-\.\s]?\d{4})(?!\w)',  # SSNs
        "email": r'(?<!\w)([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(?!\w)',  # Email addresses
        "case_number": r'(?<!\w)(C[0-9]{7,}|CC[0-9]{10,}|AML[0-9]{7,})(?!\w)'  # Case numbers
    }
    
    # Patterns for critical data that must be preserved
    PRESERVE_PATTERNS = {
        "money_amount": r'\$[\d,]+\.\d{2}|\$[\d,]+|\d+\s+dollars|\d+\s+USD',  # Money amounts
        "percentage": r'\d+(?:\.\d+)?%',  # Percentages
        "date": r'\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',  # Dates
        "transaction_count": r'(?<!\w)(\d+)\s+transactions?(?!\w)',  # Transaction counts
        "alert_id": r'(?<!\w)(AMLR\d+|AMLC\d+|SAM\d+-\d+|IRF_\d+)(?!\w)'  # Alert IDs
    }
    
    def __init__(self, model: str = None, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        """
        Initialize the LLM client with configurable model
        
        Args:
            model: LLM model identifier ('llama3-8b', 'gpt-3.5-turbo', 'gpt-4')
            api_key: API key for the model
            endpoint: API endpoint for the model
        """
        self.model = model or config.DEFAULT_LLM_MODEL
        self.api_key = api_key or self._get_api_key_for_model(self.model)
        self.endpoint = endpoint or self._get_endpoint_for_model(self.model)
        
        logger.info(f"Initialized LLM client with model: {self.model}")
        
    def _get_api_key_for_model(self, model: str) -> str:
        """Get appropriate API key based on selected model"""
        if model.startswith('gpt'):
            return config.AZURE_OPENAI_API_KEY
        else:
            return config.LLAMA_API_KEY
    
    def _get_endpoint_for_model(self, model: str) -> str:
        """Get appropriate endpoint based on selected model"""
        if model.startswith('gpt'):
            return config.AZURE_OPENAI_ENDPOINT
        else:
            return config.LLAMA_API_ENDPOINT
    
    def _extract_and_protect_data(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Extract and protect both PII/PCI and critical data
        
        Args:
            text: Text containing data to protect
            
        Returns:
            Tuple: (processed_text, placeholder_map)
        """
        placeholder_map = {}
        processed_text = text
        
        # First, identify and protect critical data to preserve
        for data_type, pattern in self.PRESERVE_PATTERNS.items():
            matches = re.finditer(pattern, processed_text)
            for match in matches:
                original_value = match.group(0)
                hash_key = md5(original_value.encode()).hexdigest()[:8]
                placeholder = f"<<PRESERVE_{data_type.upper()}_{hash_key}>>"
                placeholder_map[placeholder] = original_value
                processed_text = processed_text.replace(original_value, placeholder)
        
        # Then, identify and protect PII data
        for data_type, pattern in self.PII_PATTERNS.items():
            matches = re.finditer(pattern, processed_text)
            for match in matches:
                original_value = match.group(0)
                hash_key = md5(original_value.encode()).hexdigest()[:8]
                placeholder = f"<<PII_{data_type.upper()}_{hash_key}>>"
                placeholder_map[placeholder] = original_value
                processed_text = processed_text.replace(original_value, placeholder)
        
        return processed_text, placeholder_map
    
    def _restore_data(self, text: str, placeholder_map: Dict[str, str]) -> str:
        """
        Restore all protected data from placeholders
        
        Args:
            text: Text with placeholders
            placeholder_map: Map of placeholders to original values
            
        Returns:
            str: Text with original values restored
        """
        restored_text = text
        
        # Replace each placeholder with its original value
        for placeholder, original in placeholder_map.items():
            restored_text = restored_text.replace(placeholder, original)
        
        return restored_text
    
    def _call_llama_api(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """
        Call Llama 3:8B API
        
        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens in the response
            temperature: Temperature setting (lower is more deterministic)
            
        Returns:
            str: Generated text
        """
        if not self.endpoint or not self.api_key:
            logger.warning("Llama API not configured, returning empty result")
            return ""
            
        # Prepare request payload
        payload = {
            "model": "llama3-8b",
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.95
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Make API request
        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result.get("choices", [{}])[0].get("text", "").strip()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Llama API: {str(e)}")
            return ""
    
    def _call_azure_openai_api(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """
        Call Azure OpenAI API (GPT 3.5 or GPT 4)
        
        Args:
            prompt: The prompt to send to the model
            max_tokens: Maximum tokens in the response
            temperature: Temperature setting (lower is more deterministic)
            
        Returns:
            str: Generated text
        """
        if not self.endpoint or not self.api_key:
            logger.warning("Azure OpenAI API not configured, returning empty result")
            return ""
            
        # Extract deployment name from model
        deployment_name = "gpt-35-turbo"
        if self.model == "gpt-4":
            deployment_name = "gpt-4"
        
        # Prepare request payload for chat completion
        payload = {
            "messages": [
                {"role": "system", "content": "You are an expert assistant for generating SAR narratives and recommendations. Keep all financial data, dates, amounts, transaction counts, and other factual details exactly as provided. Do not invent or alter any facts."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.95
        }
        
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Azure OpenAI endpoint structure
        url = f"{self.endpoint}openai/deployments/{deployment_name}/chat/completions?api-version=2023-03-15-preview"
        
        # Make API request
        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract text from chat completion
            return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Azure OpenAI API: {str(e)}")
            return ""
    
    def generate_content(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """
        Generate content with PII/PCI protection and fact preservation
        
        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in the response
            temperature: Temperature setting
            
        Returns:
            str: Generated text with PII/PCI and critical data restored
        """
        # Extract and protect PII/PCI and critical data
        processed_prompt, placeholder_map = self._extract_and_protect_data(prompt)
        
        # Enhance prompt with instructions to preserve placeholders
        enhanced_prompt = (
            f"IMPORTANT: This prompt contains special placeholder codes like <<PRESERVE_DATE_12345678>> and <<PII_ACCOUNT_NUMBER_12345678>>. "
            f"These placeholder codes MUST be preserved exactly as they appear in your response. "
            f"Do not modify, replace, or remove any placeholder code. \n\n"
            f"{processed_prompt}"
        )
        
        # Select appropriate API based on model
        if self.model.startswith('gpt'):
            response = self._call_azure_openai_api(enhanced_prompt, max_tokens, temperature)
        else:
            response = self._call_llama_api(enhanced_prompt, max_tokens, temperature)
        
        # Restore PII/PCI and critical data in response
        restored_response = self._restore_data(response, placeholder_map)
        
        return restored_response
    
    def generate_section(self, section_type: str, data: Dict[str, Any]) -> str:
        """
        Generate a specific section of the SAR narrative or recommendation
        
        Args:
            section_type: Type of section to generate
            data: Preprocessed data for the section
            
        Returns:
            str: Generated section text
        """
        # Define focused prompts for each section type
        prompts = {
            # SAR Narrative Sections
            "introduction": self._create_introduction_prompt(data),
            "prior_cases": self._create_prior_cases_prompt(data),
            "account_subject_info": self._create_account_subject_info_prompt(data),
            "activity_summary": self._create_activity_summary_prompt(data),
            "transaction_samples": self._create_transaction_samples_prompt(data),
            "conclusion": self._create_conclusion_prompt(data),
            
            # Recommendation Sections
            "alert_summary": self._create_alert_summary_prompt(data),
            "prior_case_sar_summary": self._create_prior_case_sar_summary_prompt(data),
            "scope_of_review": self._create_scope_of_review_prompt(data),
            "investigation_summary": self._create_investigation_summary_prompt(data),
            "activity_analysis": self._create_activity_analysis_prompt(data),
            "recommendation_conclusion": self._create_recommendation_conclusion_prompt(data),
            "escalation": self._create_escalation_prompt(data),
            "referral": self._create_referral_prompt(data),
            "retain_close": self._create_retain_close_prompt(data)
        }
        
        # Get prompt for the requested section
        prompt = prompts.get(section_type, "")
        if not prompt:
            logger.warning(f"No prompt template defined for section type: {section_type}")
            return ""
        
        # Generate content with PII/PCI protection
        return self.generate_content(prompt, max_tokens=1000, temperature=0.2)

    # SAR NARRATIVE SECTION PROMPTS

    def _create_introduction_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for SAR narrative introduction section"""
        return f"""
        Write the first paragraph of a SAR (Suspicious Activity Report) narrative following EXACTLY this format:

        "U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report [type of activity] totaling [total amount] by [customer name] in [account type] account number [account number]. The suspicious activity was conducted from [start date] through [end date]."

        Use ONLY these exact details:
        - Activity type: {data.get('activity_type', 'suspicious activity')}
        - Total amount: {data.get('total_amount', '$0.00')}
        - Customer name: {data.get('subjects', 'unknown subjects')}
        - Account type: {data.get('account_type', 'checking/savings')}
        - Account number: {data.get('account_number', '')}
        - Start date: {data.get('start_date', '')}
        - End date: {data.get('end_date', '')}

        If acronyms like ACH are used, spell them out on first use, e.g., "Automated Clearing House (ACH)".
        Include the AML indicators if available: {data.get('aml_indicators', '')}

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    def _create_prior_cases_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for prior cases section"""
        prior_cases = data.get('prior_cases', [])
        prior_cases_text = ""
        
        if prior_cases:
            for case in prior_cases:
                prior_cases_text += f"Case Number: {case.get('case_number', '')}\n"
                prior_cases_text += f"Filing Date: {case.get('filing_date', '')}\n"
                prior_cases_text += f"Summary: {case.get('summary', '')}\n\n"
        
        return f"""
        Write a paragraph about prior SARs (Suspicious Activity Reports) based ONLY on the following information:

        {prior_cases_text or "No prior cases found."}

        If there are no prior cases, write exactly: "No prior SARs were identified for the subjects or account."

        If there are prior cases, format each one as: "Prior SAR (Case Number: [case number]) was filed on [filing date] reporting [summary]."

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    def _create_account_subject_info_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for account and subject information section"""
        account_info = data.get('account_info', {})
        subjects = data.get('subjects', [])
        
        subject_text = ""
        for subject in subjects:
            subject_text += f"Name: {subject.get('name', '')}\n"
            subject_text += f"Occupation: {subject.get('occupation', '')}\n"
            subject_text += f"Employer: {subject.get('employer', '')}\n"
            subject_text += f"Relationship: {subject.get('account_relationship', '')}\n"
            subject_text += f"Nationality: {subject.get('nationality', '')}\n\n"
        
        return f"""
        Write two paragraphs: one for account information and one for subject information, using ONLY the details provided below.

        ACCOUNT INFORMATION:
        Account type: {account_info.get('account_type', '')}
        Account number: {account_info.get('account_number', '')}
        Open date: {account_info.get('open_date', '')}
        Close date: {account_info.get('close_date', '')}
        Status: {account_info.get('status', '')}
        Closure reason: {account_info.get('closure_reason', '')}

        SUBJECT INFORMATION:
        {subject_text}

        For the account paragraph, follow this format:
        "Personal [account type] account [account number] was opened on [open date] and [remains open OR was closed on (close date)]." 
        If the account is closed, add: "The account was closed due to [closure reason]."

        For the subject paragraph, include each subject's name, occupation, employer, and relationship to the account.
        Sample format: "[Name] is employed as a [occupation] at [employer]. [Name] is listed as [relationship] on the account."
        
        For subjects with foreign nationality, add: "The following foreign nationalities and identifications were identified for [Name]: [Nationality]."

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    def _create_activity_summary_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for activity summary section"""
        transaction_summary = data.get('transaction_summary', {})
        credit_breakdown = transaction_summary.get('credit_breakdown', [])
        debit_breakdown = transaction_summary.get('debit_breakdown', [])
        
        credit_text = ", ".join([
            f"{item.get('type', '')} (${item.get('amount', 0):,.2f}, {item.get('count', 0)} transactions)"
            for item in credit_breakdown[:3]  # Top 3 types
        ])
        
        debit_text = ", ".join([
            f"{item.get('type', '')} (${item.get('amount', 0):,.2f}, {item.get('count', 0)} transactions)"
            for item in debit_breakdown[:3]  # Top 3 types
        ])
        
        return f"""
        Write a paragraph summarizing suspicious activity for a SAR (Suspicious Activity Report) using ONLY the information provided below.

        Account number: {data.get('account_number', '')}
        Start date: {data.get('start_date', '')}
        End date: {data.get('end_date', '')}
        Total credits: {data.get('total_credits', '$0.00')}
        Total debits: {data.get('total_debits', '$0.00')}

        Credit transaction types: {credit_text or "None"}
        Debit transaction types: {debit_text or "None"}
        
        AML risk indicators: {data.get('aml_risks', '')}

        The paragraph should begin with: "The suspicious activity identified in account [account number] was conducted from [start date] to [end date] and consisted of..."

        Include a sentence about the AML risks: "The AML risks associated with these transactions are as follows: [risk indicators]."

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    def _create_transaction_samples_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for transaction samples section"""
        transactions = data.get('transactions', [])
        
        if not transactions:
            return "Write: 'No suspicious transaction samples were identified.'"
        
        sample_text = ""
        for i, txn in enumerate(transactions[:5]):  # Limit to 5 examples
            sample_text += f"Transaction {i+1}:\n"
            sample_text += f"Date: {txn.get('date', '')}\n"
            sample_text += f"Amount: {txn.get('amount', '')}\n"
            sample_text += f"Type: {txn.get('type', '')}\n"
            sample_text += f"Description: {txn.get('description', '')}\n\n"
        
        return f"""
        Create a list of suspicious transaction examples using ONLY the information provided below:

        {sample_text}

        Begin with: "A sample of the suspicious transactions includes:"
        
        Format each transaction as: "[Date]: [Amount] ([Type]) - [Description]"
        
        Separate each transaction with a semicolon, and end the list with a period.
        Example: "A sample of the suspicious transactions includes: 01/15/2023: $9,500.00 (Cash Deposit) - Branch ABC; 01/16/2023: $9,400.00 (Cash Deposit) - Branch XYZ."

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    def _create_conclusion_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for conclusion section"""
        return f"""
        Write the conclusion paragraph for a SAR (Suspicious Activity Report) narrative following EXACTLY this format:

        "In conclusion, USB is reporting [total amount] in [activity type] which gave the appearance of [activity type] and were conducted by [customer name] in [account type] account number [account number] from [start date] through [end date]. USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequestsml@usbank.com referencing AML case number [case number]."

        Use ONLY these exact details:
        - Total amount: {data.get('total_amount', '$0.00')}
        - Activity type: {data.get('activity_type', 'suspicious activity')}
        - Customer name: {data.get('subjects', 'unknown subjects')}
        - Account type: {data.get('account_type', 'checking/savings')}
        - Account number: {data.get('account_number', '')}
        - Start date: {data.get('start_date', '')}
        - End date: {data.get('end_date', '')}
        - Case number: {data.get('case_number', '')}

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    # RECOMMENDATION SECTION PROMPTS

    def _create_alert_summary_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for alert summary section"""
        alert_info = data.get('alert_info', [])
        
        if isinstance(alert_info, dict):
            alert_info = [alert_info]
        
        alert_text = ""
        for alert in alert_info:
            alert_text += f"Alert ID: {alert.get('alert_id', '')}\n"
            alert_text += f"Alert Month: {alert.get('alert_month', '')}\n"
            alert_text += f"Description: {alert.get('description', '')}\n\n"
        
        return f"""
        Create an Alert Summary section for a SAR recommendation following this format:

        "[Case Number]: [Account Type] and [Account Number] alerted in [Alert Month] for [Alert Description]."

        Use ONLY these exact details:
        - Case number: {data.get('case_number', '')}
        - Account type: {data.get('account_info', {}).get('account_type', 'checking/savings')}
        - Account number: {data.get('account_info', {}).get('account_number', '')}
        - Account holders: {data.get('subject_names', '')}
        
        Alert information:
        {alert_text}

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        If there are multiple alerts, combine them in a single summary by account.
        """

    def _create_prior_case_sar_summary_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for prior case/SAR summary section"""
        prior_cases = data.get('prior_cases', [])
        
        if not prior_cases:
            return "Write: 'No prior cases or SARs were identified.'"
        
        prior_cases_text = ""
        for case in prior_cases:
            prior_cases_text += f"Case Number: {case.get('case_number', '')}\n"
            prior_cases_text += f"Alert IDs: {', '.join(case.get('alert_id', []))}\n"
            prior_cases_text += f"Review Period: {case.get('review_period', {}).get('start', '')} to {case.get('review_period', {}).get('end', '')}\n"
            prior_cases_text += f"SAR Form Number: {case.get('sar_form_number', '')}\n"
            prior_cases_text += f"Filing Date: {case.get('filing_date', '')}\n"
            prior_cases_text += f"Summary: {case.get('summary', '')}\n\n"
        
        return f"""
        Create a Prior Cases/SARs summary section for a SAR recommendation using ONLY the information provided below:

        {prior_cases_text}

        For each prior case, include:
        "Case [Case Number]: Account [Account Number] reviewed from [Review Period Start] to [Review Period End] due to [Alert Description]."

        If the case resulted in a SAR filing, add:
        "SAR Form [SAR Form Number] was filed on [Filing Date] reporting [Summary]."

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    def _create_scope_of_review_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for scope of review section"""
        review_period = data.get('review_period', {})
        
        start_date = review_period.get('start', '')
        end_date = review_period.get('end', '')
        
        account_info = data.get('account_info', {})
        open_date = account_info.get('open_date', '')
        close_date = account_info.get('close_date', '')
        account_number = account_info.get('account_number', '')
        
        return f"""
        Create a Scope of Review section for a SAR recommendation following this format:

        "Accounts were reviewed from [Start Date] to [End Date]."

        If any account was opened or closed during the review period, add:
        "Account [Account Number] was opened on [Open Date]." or "Account [Account Number] was closed on [Close Date]."

        Use ONLY these exact details:
        - Start date: {start_date}
        - End date: {end_date}
        - Account number: {account_number}
        - Open date: {open_date}
        - Close date: {close_date}

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    def _create_investigation_summary_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for investigation summary section"""
        account_summaries = data.get('account_summaries', {})
        
        account_text = ""
        for acct_num, summary in account_summaries.items():
            account_text += f"Account {acct_num}:\n"
            account_text += f"Total credits: ${summary.get('total_credits', 0):,.2f}\n"
            account_text += f"Total debits: ${summary.get('total_debits', 0):,.2f}\n"
            
            # Add credit types
            credit_types = []
            for txn_type, type_summary in summary.get('transactions_by_type', {}).items():
                if type_summary.get('credits', 0) > 0:
                    credit_types.append(f"{txn_type} (${type_summary.get('credits', 0):,.2f})")
            
            if credit_types:
                account_text += f"Credit types: {', '.join(credit_types)}\n"
            
            # Add debit types
            debit_types = []
            for txn_type, type_summary in summary.get('transactions_by_type', {}).items():
                if type_summary.get('debits', 0) > 0:
                    debit_types.append(f"{txn_type} (${type_summary.get('debits', 0):,.2f})")
            
            if debit_types:
                account_text += f"Debit types: {', '.join(debit_types)}\n"
            
            account_text += "\n"
        
        return f"""
        Create a Summary of Investigation section for a SAR recommendation using ONLY the information provided below:

        {account_text}

        For each account, write:
        "Account [Account Number] consisted of the following top credit activity: [credit types with amounts]. Account [Account Number] consisted of the following top debit activity: [debit types with amounts]."

        If there are significant or alerting transactions, add:
        "The alerting or significant identified transactions consisted of [transaction type] conducted from [date range] totaling [amount]."

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        Limit your response to factual details from the provided data.
        """

    def _create_activity_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for activity analysis section"""
        is_sar = data.get('is_sar', True)
        activity_type = data.get('activity_type', '')
        
        if is_sar:
            return """
            Write a prompt for the investigator to analyze suspicious activity:

            "The following AML concerns were identified:"

            This will be completed by the investigator with their analysis of suspicious activity patterns.
            """
        else:
            return """
            Write a prompt for the investigator to explain why the activity is not suspicious:

            "The following mitigations of the alerting or notable activity are as follows:"

            This will be completed by the investigator with their analysis of why the activity is not suspicious.
            """

    def _create_recommendation_conclusion_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for recommendation conclusion section"""
        is_sar = data.get('is_sar', True)
        
        if not is_sar:
            return "Write: 'No SAR recommended at this time.'"
        
        account_info = data.get('account_info', {})
        unusual_activity = data.get('unusual_activity', {})
        
        return f"""
        Create a Conclusion section for a SAR recommendation following this format:

        "In conclusion a SAR is recommended to report unusual [Activity Type] activity involving USB accounts [Account Number] and subjects [Subject Names]. The unusual activity totaled [Total Amount] [Derived From] between [Start Date] and [End Date]."

        Use ONLY these exact details:
        - Account number: {account_info.get('account_number', '')}
        - Subject names: {data.get('subject_names', '')}
        - Activity type: {data.get('activity_type', 'suspicious activity')}
        - Total amount: {unusual_activity.get('summary', {}).get('total_amount', '$0.00')}
        - Derived from: {data.get('derived_from', 'derived from credits and debits')}
        - Start date: {unusual_activity.get('summary', {}).get('date_range', {}).get('start', '')}
        - End date: {unusual_activity.get('summary', {}).get('date_range', {}).get('end', '')}

        IMPORTANT: Do not alter, estimate, or make up any information not provided above.
        """

    def _create_escalation_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for escalation section"""
        needs_escalation = data.get('needs_escalation', False)
        is_significant = data.get('is_significant', False)
        total_amount = data.get('total_amount', 0)
        
        if not needs_escalation:
            return "Write: 'A review of the customer, their information, and transactional activity did not meet any criteria for an escalation.'"
        
        if is_significant or total_amount > 10000000:  # $10 million
            return f"""
            Write an escalation section for a SAR recommendation:

            "Case {data.get('case_number', '')} will be escalated to senior management due to criteria that meets significant case escalation requirements."

            IMPORTANT: Do not alter, estimate, or make up any information not provided.
            """
        
        return "Write: 'This case requires escalation. [Investigator to provide escalation details.]'"

    def _create_referral_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for referral section"""
        referral_type = data.get('referral_type', '')
        
        if not referral_type:
            return "Write: 'No referral to EDD or CDDO: A review of the customer, their information, and transactional activity did not meet any criteria for referral to EDD or CDDO as a potential SRC.'"
        
        account_info = data.get('account_info', {})
        unusual_activity = data.get('unusual_activity', {})
        
        if referral_type == "EDD" or referral_type == "CDDO":
            return f"""
            Write a referral section for a SAR recommendation:

            "An {referral_type} referral will be recommended. [Investigator to provide reasoning for {referral_type} referral]."

            IMPORTANT: Do not alter, estimate, or make up any information not provided.
            """
        
        if referral_type == "FTS":
            return f"""
            Write a First Time Structuring (FTS) referral based ONLY on the information provided:

            Account number: {account_info.get('account_number', '')}
            Account holders: {data.get('subject_names', '')}
            Review period: {unusual_activity.get('summary', {}).get('date_range', {}).get('start', '')} to {unusual_activity.get('summary', {}).get('date_range', {}).get('end', '')}
            Activity type: Potentially structured cash deposits/withdrawals
            Activity total: {unusual_activity.get('summary', {}).get('total_amount', '$0.00')}

            Format as:
            "Account [account number], held by [signers], was reviewed from [start date] to [end date] and identified potentially structured cash deposits/withdrawals conducted from [activity start date] to [activity end date] which totaled [total amount]. A first time structuring letter will be sent to the customer."

            IMPORTANT: Do not alter, estimate, or make up any information not provided above.
            """
        
        if referral_type == "CTA":
            return f"""
            Write a Customer Transaction Assessment (CTA) referral based ONLY on the information provided:

            Account number: {account_info.get('account_number', '')}
            Account holders: {data.get('subject_names', '')}
            Review period: {unusual_activity.get('summary', {}).get('date_range', {}).get('start', '')} to {unusual_activity.get('summary', {}).get('date_range', {}).get('end', '')}
            Activity total: {unusual_activity.get('summary', {}).get('total_amount', '$0.00')}

            Format as:
            "Account [account number], held by [signers], was reviewed from [start date] to [end date] and identified potentially unusual activity conducted from [activity start date] to [activity end date] which totaled [total amount]. The activity consisted of [transaction types and amounts]. [Investigator to input analysis of activity/reason for CTA]. A sample of the activity is as follows: [Sample transactions]. Please ask the customer the following questions relating to the activity: [Investigator to insert questions]"

            IMPORTANT: Do not alter, estimate, or make up any information not provided above.
            """
        
        # Add other referral types as needed
        
        return f"Write: 'This case requires a {referral_type} referral. [Investigator to provide details.]'"

    def _create_retain_close_prompt(self, data: Dict[str, Any]) -> str:
        """Create prompt for retain or close section"""
        action = data.get('action', 'retain')
        
        if action == 'retain':
            return f"""
            Write a Retain Customer Relationship section for a SAR recommendation:

            "Retain Customer Relationship(s): Accounts and relationships related to {data.get('subject_names', '')} are recommended to remain open."

            IMPORTANT: Do not alter, estimate, or make up any information not provided.
            """
        
        return f"""
        Write a Close Customer Relationship section for a SAR recommendation:

        "Close Customer Relationship(s): Account and relationships related to {data.get('account_info', {}).get('account_number', '')} and {data.get('subject_names', '')} are recommended to close. The following risks were identified with this customer: [Investigator to insert the unusual activity analysis here]"

        IMPORTANT: Do not alter, estimate, or make up any information not provided.
        """
        
    def determine_activity_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine type of suspicious activity from data
        
        Args:
            data: Case and transaction data
            
        Returns:
            Dict: Activity type information
        """
        # This function now does the determination entirely in Python
        # without relying on the LLM
        
        # Simple determination based on keywords in available data
        activity_indicators = {
            "STRUCTURING": ["structure", "ctr", "cash deposit", "multiple deposit", "9000", "below 10000"],
            "UNUSUAL_ACH": ["ach", "wire", "transfer", "electronic", "payment", "zelle", "venmo"],
            "UNUSUAL_CASH": ["cash", "atm", "withdraw", "deposit", "currency", "dollar bill"],
            "MONEY_LAUNDERING": ["launder", "shell", "funnel", "layering", "money laundering", "suspicious"]
        }
        
        # Extract relevant information for detection
        alert_info = data.get("alert_info", {})
        alert_desc = ""
        
        # Handle alert info in different formats
        if isinstance(alert_info, list) and alert_info:
            for alert in alert_info:
                if isinstance(alert, dict):
                    alert_desc += alert.get("description", "").lower() + " "
        elif isinstance(alert_info, dict):
            alert_desc = alert_info.get("description", "").lower()
        
        activity_desc = data.get("activity_summary", {}).get("description", "").lower()
        
        # Count matches for each activity type
        scores = {activity: 0 for activity in activity_indicators}
        
        for activity, keywords in activity_indicators.items():
            for keyword in keywords:
                if keyword in alert_desc:
                    scores[activity] += 2
                if keyword in activity_desc:
                    scores[activity] += 1
        
        # Look for transaction patterns
        transaction_summary = data.get("transaction_summary", {})
        
        # Check if there are cash transactions
        credit_breakdown = transaction_summary.get("credit_breakdown", [])
        debit_breakdown = transaction_summary.get("debit_breakdown", [])
        
        for breakdown in credit_breakdown + debit_breakdown:
            txn_type = breakdown.get("type", "").lower()
            
            # Check for cash-related keywords
            if any(cash_word in txn_type for cash_word in ["cash", "atm", "currency"]):
                scores["UNUSUAL_CASH"] += 2
            
            # Check for ACH/wire-related keywords
            if any(ach_word in txn_type for ach_word in ["ach", "wire", "transfer"]):
                scores["UNUSUAL_ACH"] += 2
        
        # Check for structuring patterns
        unusual_activity = data.get("unusual_activity", {})
        transactions = unusual_activity.get("transactions", [])
        
        # Look for multiple transactions below CTR threshold ($10,000)
        below_threshold_count = sum(1 for txn in transactions 
                                  if isinstance(txn.get("amount"), (int, float)) and 
                                  txn.get("amount") > 8000 and txn.get("amount") < 10000)
        
        if below_threshold_count >= 2:
            scores["STRUCTURING"] += 3
        
        # Get activity type with highest score, default to UNUSUAL_ACH
        best_match = max(scores.items(), key=lambda x: x[1])[0] if any(scores.values()) else "UNUSUAL_ACH"
        
        # Return the activity type information from config
        return config.ACTIVITY_TYPES.get(best_match, config.ACTIVITY_TYPES["UNUSUAL_ACH"])