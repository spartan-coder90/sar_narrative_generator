import logging
import os
from typing import Dict, Any, Optional

from backend.utils.logger import get_logger
import backend.config as config

# Langchain imports
from langchain_community.chat_models import ChatOpenAI, AzureChatOpenAI
from langchain_ollama import OllamaLLM

from langchain.schema import HumanMessage, SystemMessage
from langchain.callbacks.base import BaseCallbackHandler


def get_llm_callback_handler() -> BaseCallbackHandler:
    # Your implementation of a callback handler, if any
    return None


class LLMClient:
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """
        Initialize your LLM client (ChatOpenAI, AzureChatOpenAI, OllamaLLM)

        Args:
            model: Which model to load (e.g., "gpt-4", "llama3-8b")
            api_key: API key for the model
            endpoint: API endpoint for the model
        """
        logger = get_logger(__name__)

        self.model = model or config.DEFAULT_LLM_MODEL
        # Use provided api_key or fallback to environment variable
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
        # Use provided endpoint or fallback to environment variable
        self.endpoint = endpoint or os.getenv('OPENAI_API_BASE', '')
        self.callback_handler = get_llm_callback_handler()

        # Initialize the langchain client based on model type
        self.llm_client = self._initialize_llm_client()

        logger.info(f"Initialized LLM client with model: {self.model}")

    def _initialize_llm_client(self):
        """
        Instantiates ChatOpenAI, AzureChatOpenAI, or OllamaLLM based on model.
        """
        if self.model.startswith("llama"):
            return OllamaLLM(
                model=self.model,
                api_key=self.api_key,
                endpoint=self.endpoint,
                callback_handler=self.callback_handler,
            )
        elif self.endpoint.startswith("https://azure"):  # adjust detection logic as needed
            return AzureChatOpenAI(
                engine=self.model,
                openai_api_key=self.api_key,
                openai_api_base=self.endpoint,
                callback_handler=self.callback_handler,
            )
        else:
            return ChatOpenAI(
                model_name=self.model,
                openai_api_key=self.api_key,
                request_timeout=getattr(config, 'LLM_TIMEOUT_SECONDS', 60),
                callback_handler=self.callback_handler,
            )

    def generate_content(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.2,
    ) -> str:
        """
        Generate content for SAR narratives.

        Args:
            prompt: The prompt to send to the LLM
            max_tokens: Maximum tokens in the response
            temperature: Temperature setting

        Returns:
            str: Generated text
        """
        logger = get_logger(__name__)
        try:
            # Build system & human messages for chat models
            system_message = (
                "You are an expert in generating SAR (Suspicious Activity Report) documentation."
            )
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=prompt),
            ]

            # Configure generation parameters
            if hasattr(self.llm_client, 'temperature'):
                self.llm_client.temperature = temperature
            if hasattr(self.llm_client, 'max_tokens'):
                self.llm_client.max_tokens = max_tokens
            if hasattr(self.llm_client, 'num_predict'):
                self.llm_client.num_predict = max_tokens

            # Generate response
            if hasattr(self.llm_client, 'invoke'):
                # Chat-style LLM (ChatOpenAI, AzureChatOpenAI, OllamaLLM, etc.)
                result = self.llm_client.invoke(messages)
                response_text = result.content if hasattr(result, 'content') else str(result)
            else:
                # Classic completion LLM that accept a single string prompt
                response_text = self.llm_client.predict(prompt)

            return response_text

        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            return "Error generating content. Please try again."

    
    def generate_section(self, section_type: str, data: Dict[str, Any]) -> str:
        """
        Generate a specific section of the SAR narrative or recommendation
        
        Args:
            section_type: Type of section to generate
            data: Preprocessed data for the section
            
        Returns:
            str: Generated section text
        """
        try:
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
            
            # Generate content without PII protection
            return self.generate_content(prompt, max_tokens=1000, temperature=0.2)
        
        except Exception as e:
            # Log the error with detailed information
            logger.error(f"Error generating section '{section_type}': {str(e)}", exc_info=True)
            logger.debug(f"Input data for section '{section_type}': {json.dumps(data, default=str)}")
            
            # Return an empty string or error message rather than crashing
            return f"Error generating {section_type} section: {str(e)}"

    # SAR NARRATIVE SECTION PROMPTS

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
        
        # Check if subjects is a list or convert it if it's a string
        if isinstance(subjects, str):
            # Handle case where subjects is a string
            subject_text = f"Name: {subjects}\n\n"
        else:
            # Process list of subject dictionaries
            for subject in subjects:
                # Check if subject is a dictionary, otherwise convert to a simple name
                if isinstance(subject, dict):
                    subject_text += f"Name: {subject.get('name', '')}\n"
                    subject_text += f"Occupation: {subject.get('occupation', '')}\n"
                    subject_text += f"Employer: {subject.get('employer', '')}\n"
                    subject_text += f"Relationship: {subject.get('account_relationship', '')}\n"
                    subject_text += f"Nationality: {subject.get('nationality', '')}\n\n"
                else:
                    # Handle case where subject is a string or other non-dict type
                    subject_text += f"Name: {str(subject)}\n\n"
        
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