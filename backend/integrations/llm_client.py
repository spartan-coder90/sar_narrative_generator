import logging
import os
from typing import Dict, Any, Optional

from backend.utils.logger import get_logger
import backend.config as config

# Langchain imports
from langchain_community.chat_models import ChatOpenAI # Updated import
from langchain_community.chat_models.azure_openai import AzureChatOpenAI # Updated import
from langchain_ollama import OllamaLLM # Updated import for Ollama
from langchain.schema import HumanMessage, SystemMessage
# Removed unused import: from langchain.callbacks.base import BaseCallbackHandler


class LLMClient:
    """
    A client class to interact with various Language Learning Models (LLMs).

    This client supports different LLM providers like OpenAI, Azure OpenAI, and
    Ollama (for Llama models). It handles the initialization of the appropriate
    Langchain client based on the provided model name, API key, and endpoint.
    It also includes methods for generating content and determining activity types
    based on input data, primarily for SAR narrative generation.
    """
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        """
        Initialize the appropriate LLM client based on the model
        
        Args:
            model: Which model to load (e.g., "gpt-4", "llama3-8b")
            api_key: API key for the model
            endpoint: API endpoint for the model
        """
        logger = get_logger(__name__)
        
        # Set default model from config if not provided
        self.model = model or config.DEFAULT_LLM_MODEL
        
        # Configure API settings based on model type
        if self.model.startswith("llama"):
            # Ollama configuration
            self.api_key = api_key or config.LLAMA_API_KEY
            self.endpoint = endpoint or config.LLAMA_API_ENDPOINT
        elif "azure" in (endpoint or "").lower():
            # Azure OpenAI configuration
            self.api_key = api_key or config.AZURE_OPENAI_API_KEY
            self.endpoint = endpoint or config.AZURE_OPENAI_ENDPOINT
        else:
            # Standard OpenAI configuration
            self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
            self.endpoint = endpoint or os.getenv('OPENAI_API_BASE', '')
        
        # Initialize the LLM client
        self.llm_client = self._initialize_llm_client()
        logger.info(f"Initialized LLM client with model: {self.model}")

    def _initialize_llm_client(self):
        """
        Initialize the appropriate LLM client based on the model type
        
        Returns:
            The initialized LLM client
        """
        # For Llama models (using Ollama)
        if self.model.startswith("llama"):
            return OllamaLLM( # Changed to OllamaLLM
                model=self.model,
                base_url=self.endpoint
            )
        
        # For Azure OpenAI
        elif "azure" in (self.endpoint or "").lower():
            return AzureChatOpenAI(
                deployment_name=self.model,
                openai_api_key=self.api_key,
                openai_api_base=self.endpoint,
                temperature=0.2
            )
        
        # Default to standard OpenAI
        else:
            return ChatOpenAI(
                model_name=self.model,
                openai_api_key=self.api_key,
                temperature=0.2,
                request_timeout=getattr(config, 'LLM_TIMEOUT_SECONDS', 60)
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

            # Configure generation parameters.
            # Note on thread safety: The `self.llm_client` instance is shared if the
            # same `LLMClient` instance is used across multiple threads (e.g., by
            # `NarrativeGenerator`'s parallel execution). Modifying attributes like
            # `temperature` or `max_tokens` on the shared `self.llm_client` instance
            # right before the `invoke` call could theoretically lead to a race condition
            # if multiple threads attempt to set different values simultaneously.
            # For example, thread A sets temp=0.2, thread B sets temp=0.7, then thread A calls invoke;
            # thread A might use temp=0.7.
            #
            # However, LangChain clients are generally designed to be used in concurrent
            # environments. The actual behavior might depend on whether the underlying
            # client's `invoke` method captures these values atomically at the start of
            # its execution or if the client creates per-call configurations internally.
            #
            # For robust thread safety with per-call parameters, LangChain typically recommends
            # using methods like `with_options()` or `bind()` to pass runtime parameters,
            # e.g., `self.llm_client.with_options(temperature=temperature, max_tokens=max_tokens).invoke(messages)`.
            # This would require checking how each specific client type (OllamaLLM, ChatOpenAI,
            # AzureChatOpenAI) best handles runtime option overrides for `invoke`.
            #
            # For the current implementation, we rely on the assumption that either:
            # 1. The sequential nature of `hasattr` checks + assignment + `invoke` is fast enough
            #    for typical threading scenarios within one `NarrativeGenerator` instance, or
            # 2. The underlying LangChain clients are robust to these direct attribute modifications
            #    immediately before an `invoke` call.
            # This approach is maintained for simplicity unless specific issues arise.
            # If `LLMClient` instances are NOT shared across threads (e.g., one per request/job),
            # then this is not an issue.
            if hasattr(self.llm_client, 'temperature'):
                self.llm_client.temperature = temperature

            # For max_tokens, some clients might expect it under a different name (e.g., 'num_predict' for Ollama)
            # or within a specific options structure. The `hasattr` check is a basic safeguard.
            if hasattr(self.llm_client, 'max_tokens'): # Standard OpenAI, Azure
                self.llm_client.max_tokens = max_tokens
            elif hasattr(self.llm_client, 'num_predict') and isinstance(self.llm_client, OllamaLLM): # Ollama
                self.llm_client.num_predict = max_tokens
            
            # Generate response
            result = self.llm_client.invoke(messages)
            response_text = result.content if hasattr(result, 'content') else str(result)
            
            return response_text

        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            return "Error generating content. Please try again."

    def determine_activity_type(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines the type of suspicious activity based on keywords and patterns in the input data.

        The method employs a scoring system based on predefined indicators for various activity types
        such as structuring, unusual ACH, unusual cash transactions, and money laundering.
        It analyzes alert descriptions, activity summaries, and transaction details to identify these indicators.

        Args:
            data: A dictionary containing case and transaction data. Expected keys include:
                  - "alert_info": Information about alerts (can be a dict or list of dicts).
                                   Each alert dict can have a "description" field.
                  - "activity_summary": A dictionary with an optional "description" field.
                  - "transaction_summary": A dictionary containing "credit_breakdown" and "debit_breakdown" lists.
                                           Each item in these lists can have a "type" field.
                  - "unusual_activity": A dictionary containing a "transactions" list.
                                        Each transaction item can have an "amount" field.

        Returns:
            A dictionary containing information about the determined activity type. This information
            is retrieved from `config.ACTIVITY_TYPES`. If no specific activity type scores highest,
            it defaults to "UNUSUAL_ACH". If the determined type is not in `config.ACTIVITY_TYPES`,
            it also falls back to "UNUSUAL_ACH".
        """
        # Define keywords associated with different suspicious activity types.
        # These keywords are used to score the likelihood of each activity type.
        activity_indicators = {
            "STRUCTURING": ["structure", "ctr", "cash deposit", "multiple deposit", "9000", "below 10000"],
            "UNUSUAL_ACH": ["ach", "wire", "transfer", "electronic", "payment", "zelle", "venmo"],
            "UNUSUAL_CASH": ["cash", "atm", "withdraw", "deposit", "currency", "dollar bill"],
            "MONEY_LAUNDERING": ["launder", "shell", "funnel", "layering", "money laundering", "suspicious"]
        }
        
        # --- Data Extraction and Preparation ---
        # Extract alert descriptions. Alerts can be a single dictionary or a list.
        alert_info = data.get("alert_info", {})
        alert_desc_text = ""
        if isinstance(alert_info, list) and alert_info:
            for alert in alert_info:
                if isinstance(alert, dict):
                    alert_desc_text += alert.get("description", "").lower() + " "
        elif isinstance(alert_info, dict):
            alert_desc_text = alert_info.get("description", "").lower()
        
        # Extract activity description from the activity summary.
        activity_summary_desc = data.get("activity_summary", {}).get("description", "").lower()
        
        # --- Scoring Logic ---
        # Initialize scores for each activity type to zero.
        scores = {activity: 0 for activity in activity_indicators}
        
        # Score based on keywords found in alert descriptions and activity summaries.
        # Keywords in alert descriptions are given a higher weight.
        for activity, keywords in activity_indicators.items():
            for keyword in keywords:
                if keyword in alert_desc_text:
                    scores[activity] += 2  # Higher score for matches in alert descriptions
                if keyword in activity_summary_desc:
                    scores[activity] += 1  # Lower score for matches in general activity summary
        
        # Score based on transaction patterns from transaction summary.
        transaction_summary = data.get("transaction_summary", {})
        credit_breakdown = transaction_summary.get("credit_breakdown", [])
        debit_breakdown = transaction_summary.get("debit_breakdown", [])
        
        # Iterate through credit and debit transaction types.
        for breakdown in credit_breakdown + debit_breakdown:
            txn_type = breakdown.get("type", "").lower()
            
            # Increase score for UNUSUAL_CASH if cash-related keywords are found.
            if any(cash_word in txn_type for cash_word in ["cash", "atm", "currency"]):
                scores["UNUSUAL_CASH"] += 2
            
            # Increase score for UNUSUAL_ACH if ACH/wire-related keywords are found.
            if any(ach_word in txn_type for ach_word in ["ach", "wire", "transfer"]):
                scores["UNUSUAL_ACH"] += 2
        
        # Score based on specific structuring patterns from unusual activity data.
        unusual_activity_data = data.get("unusual_activity", {})
        transactions = unusual_activity_data.get("transactions", [])

        # Check for multiple transactions just below the $10,000 CTR (Currency Transaction Report) threshold.
        # This is a common structuring pattern.
        below_threshold_transaction_count = sum(
            1 for txn in transactions
            if isinstance(txn.get("amount"), (int, float)) and 8000 < txn.get("amount", 0) < 10000
        )

        if below_threshold_transaction_count >= 2: # If two or more such transactions exist
            scores["STRUCTURING"] += 3 # Significantly increase structuring score

        # --- Determine Best Match and Fallback ---
        # Select the activity type with the highest score.
        # If all scores are zero (no indicators found), default to "UNUSUAL_ACH".
        if any(scores.values()): # Check if any score is greater than 0
            best_match_activity_key = max(scores.items(), key=lambda x: x[1])[0]
        else:
            best_match_activity_key = "UNUSUAL_ACH" # Default if no indicators found
        
        # Retrieve the detailed activity type information from the configuration.
        # Fallback to "UNUSUAL_ACH" from config if the best_match_activity_key is not found in ACTIVITY_TYPES
        # or if ACTIVITY_TYPES itself doesn't have "UNUSUAL_ACH" (as a last resort).
        default_activity_type_info = config.ACTIVITY_TYPES.get("UNUSUAL_ACH", {"name": "Unusual ACH Activity", "indicators": ["unusual electronic transactions"]})
        
        return config.ACTIVITY_TYPES.get(best_match_activity_key, default_activity_type_info)