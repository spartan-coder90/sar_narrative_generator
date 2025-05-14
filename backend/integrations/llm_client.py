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