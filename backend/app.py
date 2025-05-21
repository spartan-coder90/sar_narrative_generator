"""
Main Flask application for SAR Narrative Generator with case selection support
"""
import os
import uuid
import sys
import re
import json
import tempfile
from datetime import datetime
# from werkzeug.utils import secure_filename # Unused import
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

# Add the parent directory to Python path so imports work
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import config module and other modules
import backend.config as config
from backend.utils.logger import get_logger
from backend.processors.data_validator import DataValidator
from backend.processors.transaction_processor import TransactionProcessor
from backend.generators.narrative_generator import NarrativeGenerator, SECTION_IDS, SECTION_TITLES
from backend.utils.json_utils import save_to_json_file, load_from_json_file
from backend.integrations.llm_client import LLMClient
from backend.data.case_repository import get_case, get_full_case, get_available_cases
from backend.utils.section_extractors import (
    extract_alerting_activity_summary, generate_alerting_activity_prompt,
    extract_prior_cases_summary, generate_prior_cases_prompt
    # Removed unused: extract_scope_of_review, generate_scope_of_review_prompt
)

# Set up logging
logger = get_logger(__name__)

# Initialize app
app = Flask(__name__)

# --- Flask App Configuration ---
# Populate Flask app configuration directly from the project's `config` module.
# This allows centralized management of settings like upload directories, debug modes, etc.
app.config['UPLOAD_FOLDER'] = config.UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload limit for files.
app.config['SECRET_KEY'] = os.urandom(24)  # Secure random key for session management and other security features.

# Set Flask's DEBUG mode based on API_DEBUG from the config module, defaulting to False if not set.
if hasattr(config, 'API_DEBUG'):
    app.config['DEBUG'] = config.API_DEBUG
else:
    app.config['DEBUG'] = False

CORS(app)  # Enable Cross-Origin Resource Sharing (CORS) for all routes.

# Create required directories
os.makedirs(config.UPLOAD_DIR, exist_ok=True)  # Using UPLOAD_DIR

# Valid section IDs for narrative - updated to match new section format
VALID_SECTION_IDS = list(SECTION_IDS.values())

# Valid recommendation section IDs
VALID_RECOMMENDATION_SECTIONS = [
    "alerting_activity", "prior_sars", "scope_of_review", 
    "investigation_summary", "conclusion", "cta", "retain_close"
]


def _load_session_data(session_id: str, upload_folder_path: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, str]], Optional[int]]:
    """
    Loads and validates session data from a JSON file.

    Args:
        session_id: The unique identifier for the session.
        upload_folder_path: The base path of the upload folder.

    Returns:
        A tuple (loaded_data, error_response, status_code):
        - loaded_data: The dictionary parsed from data.json if successful.
        - error_response: A dictionary with 'status' and 'message' if an error occurs.
        - status_code: The HTTP status code corresponding to the error.
        If successful, error_response and status_code will be None.
    """
    # Validate session ID format to prevent directory traversal or invalid inputs.
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return None, {"status": "error", "message": "Invalid session ID format"}, 400
        
    data_path = os.path.join(upload_folder_path, session_id, 'data.json')
    
    # Check if the session data file exists.
    if not os.path.exists(data_path):
        return None, {"status": "error", "message": "Session not found"}, 404
    
    # Check if the session data file is empty.
    if os.path.getsize(data_path) == 0:
        logger.warning(f"Empty data file found: {data_path}")
        # Frontend might expect a 200 with specific error structure for some cases.
        # Adjust status code if a different error handling is preferred for empty files.
        return None, {"status": "error", "message": "Empty data file"}, 200 
            
    try:
        # Load and parse the JSON data from the file.
        loaded_data = load_from_json_file(data_path)
        return loaded_data, None, None
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in file {data_path}: {str(e)}")
        return None, {"status": "error", "message": f"Invalid JSON in data file: {str(e)}"}, 500
    except Exception as e:
        logger.error(f"Error loading session data from {data_path}: {str(e)}")
        return None, {"status": "error", "message": f"Error loading session data: {str(e)}"}, 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    Provides a simple status check for the application.
    
    Returns:
        JSON response with application status and version.
    """
    return jsonify({
        "status": "healthy",
        "version": "1.0.0" # Example version
    }), 200

@app.route('/api/cases', methods=['GET'])
def get_available_case_list():
    """
    Retrieves a list of available cases for UI selection.
    Calls `get_available_cases` from the case repository.
    
    Returns:
        JSON response containing a list of case summaries or an error message.
    """
    try:
        cases = get_available_cases()
        return jsonify({
            "status": "success",
            "cases": cases
        }), 200
    except Exception as e:
        logger.error(f"Error retrieving available cases: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error retrieving available cases: {str(e)}"
        }), 500

@app.route('/api/generate-from-case', methods=['POST'])
def generate_from_case():
    """
    Processes a selected case by its case number to generate a SAR narrative and recommendation.
    
    Request JSON Body:
    - `case_number` (str): The unique identifier for the case to process.
    - `model` (str, optional): The identifier for the LLM model to be used for generation 
                               (e.g., 'llama3:8b', 'gpt-4'). Defaults if not provided or invalid.
    
    Key Processing Steps:
    1. Retrieves case data using `get_case` and `get_full_case` from the case repository.
    2. Creates a unique session ID and folder to store processed data.
    3. Initializes `TransactionProcessor` to process transactions within the case data.
    4. Structures `excel_data` (simulating data typically from an Excel file).
    5. Validates the combined data using `DataValidator` and fills missing information.
    6. Initializes `LLMClient` with the selected model.
    7. Uses `NarrativeGenerator` to generate all narrative sections and recommendations.
    8. Saves all processed data, including generated content, to `data.json` within the session folder.
    
    Returns:
        JSON response containing:
        - `sessionId`: Unique ID for this processing session.
        - `caseNumber`, `accountNumber`, `dateGenerated`.
        - `warnings`: Any warnings from the data validation process.
        - `sections`: Dictionary of generated narrative sections.
        - `recommendation`: Dictionary of generated recommendation sections.
        - `case_data`, `excel_data`, `combined_data`, `transaction_data` for context.
        - `prior_cases` summary.
        Returns an error JSON response if processing fails at any step.
    """
    data = request.get_json() or {}
    case_number = data.get('case_number')
    
    if not case_number:
        return jsonify({
            "status": "error",
            "message": "Case number is required"
        }), 400
    
    # Get selected model (default to llama3:8b if not specified)
    selected_model = data.get('model', 'llama3:8b')
    
    # Validate model selection
    valid_models = ['llama3:8b', 'gpt-3.5-turbo', 'gpt-4']
    if selected_model not in valid_models:
        selected_model = 'llama3:8b'  # Default to Llama 3 if invalid
    
    # Retrieve case data from repository
    try:
        case_data = get_case(case_number)
        full_case_data = get_full_case(case_number)
        
        if not case_data:
            return jsonify({
                "status": "error",
                "message": f"Case number {case_number} not found"
            }), 404
            
        # Add full case data to the case_data response if available
        if full_case_data:
            case_data["full_data"] = full_case_data
            
    except Exception as e:
        logger.error(f"Error retrieving case data: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error retrieving case data: {str(e)}"
        }), 500
    
    # Create a unique session folder for this request
    session_id = str(uuid.uuid4())
    upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    os.makedirs(upload_folder, exist_ok=True)
    
    try:
        # Process transaction data
        logger.info(f"Processing transaction data for case: {case_number}")
        transaction_processor = TransactionProcessor(case_data)
        transaction_data = transaction_processor.get_all_transaction_data()
        
        # --- Structure excel_data (simulating data typically from an Excel/structured file) ---
        # This part normalizes data from transaction_processor into a structure
        # that DataValidator and NarrativeGenerator expect for "excel-like" inputs.
        excel_data = {
            "activity_summary": transaction_data.get("activity_summary", {}), # Overall activity summary
            "unusual_activity": transaction_data.get("unusual_activity", {}), # Details of unusual transactions
            "transaction_summary": { # Summary of credits and debits
                "total_credits": transaction_data.get("activity_summary", {}).get("totals", {}).get("credits", {}).get("total_amount", 0),
                "total_debits": transaction_data.get("activity_summary", {}).get("totals", {}).get("debits", {}).get("total_amount", 0),
                "credit_breakdown": [], # To be populated below
                "debit_breakdown": []   # To be populated below
            },
            "account_summaries": transaction_data.get("activity_summary", {}).get("accounts", {}), # Per-account activity
            "cta_sample": transaction_data.get("cta_sample", {}), # Sample for Customer Transaction Assessment
            "bip_sample": transaction_data.get("bip_sample", {}), # Sample for Business Intelligence Profile
            "inter_account_transfers": [] # Placeholder for inter-account transfers if available
        }
        
        # Populate credit_breakdown and debit_breakdown in excel_data.transaction_summary
        # This iterates over the per-account activity summaries processed by TransactionProcessor.
        for account_num, account_data_summary in transaction_data.get("activity_summary", {}).get("accounts", {}).items():
            # Populate credit breakdown from each account's 'by_type' credit data
            for txn_type, txn_data in account_data_summary.get("credits", {}).get("by_type", {}).items():
                excel_data["transaction_summary"]["credit_breakdown"].append({
                    "type": txn_type,
                    "amount": txn_data.get("amount", 0),
                    "count": txn_data.get("count", 0)
                })
            
            # Populate debit breakdown from each account's 'by_type' debit data
            for txn_type, txn_data in account_data_summary.get("debits", {}).get("by_type", {}).items():
                excel_data["transaction_summary"]["debit_breakdown"].append({
                    "type": txn_type,
                    "amount": txn_data.get("amount", 0),
                    "count": txn_data.get("count", 0)
                })
        
        # --- Validate and Combine Data ---
        validator = DataValidator(case_data, excel_data)
        is_valid, errors, warnings = validator.validate()
        
        if not is_valid and errors:
            return jsonify({
                "status": "error",
                "message": "Validation failed",
                "errors": errors,
                "warnings": warnings
            }), 400
        
        # Fill missing data and get combined result
        combined_data = validator.fill_missing_data()
        
        # Add the transaction data to the combined data
        combined_data.update({
            "activity_summary": transaction_data.get("activity_summary", {}),
            "transactions": transaction_data.get("transactions", {}),
            "unusual_activity": transaction_data.get("unusual_activity", {}),
            "counterparties": transaction_data.get("counterparties", {}),
            "cta_sample": transaction_data.get("cta_sample", {}),
            "bip_sample": transaction_data.get("bip_sample", {})
        })
        
        # Generate narrative and recommendations
        try:
            # Initialize LLM client with selected model
            llm_client = LLMClient(model=selected_model)
            
            # Generate narrative and recommendation sections
            narrative_generator = NarrativeGenerator(combined_data, llm_client)
            generated_data = narrative_generator.generate_all()
            
            narrative = generated_data["narrative"]
            sections = generated_data["sections"]
            recommendation = generated_data["recommendation"]
            
        except Exception as e:
            logger.error(f"Error generating narrative: {str(e)}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"Error in narrative generation: {str(e)}"
            }), 500
        
        # Create response with session ID for future reference
        response = {
            "status": "success",
            "sessionId": session_id,
            "caseNumber": case_data.get("case_number", ""),
            "accountNumber": case_data.get("account_info", {}).get("account_number", ""),
            "dateGenerated": datetime.now().isoformat(),
            "warnings": warnings,
            "sections": sections,
            "recommendation": recommendation
        }
        
        # Include case and excel data for complete context
        response["case_data"] = case_data
        response["excel_data"] = excel_data
        response["combined_data"] = combined_data
        response["transaction_data"] = transaction_data
        
        # Extract prior cases for future reference
        response["prior_cases"] = extract_prior_cases_summary(full_case_data) if full_case_data else []
        
        # Save a copy of the processed data for later use
        save_to_json_file({
            "case_data": case_data,
            "excel_data": excel_data,
            "combined_data": combined_data,
            "transaction_data": transaction_data,
            "narrative": narrative,
            "sections": sections,
            "recommendation": recommendation,
            "prior_cases": response["prior_cases"]
        }, os.path.join(upload_folder, 'data.json'))
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error generating narrative: {str(e)}", exc_info=True)
        # Clean up upload folder on error
        try:
            import shutil
            shutil.rmtree(upload_folder)
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up temporary files: {str(cleanup_error)}")
            
        return jsonify({
            "status": "error",
            "message": f"Error generating narrative: {str(e)}"
        }), 500

@app.route('/api/sections/<session_id>', methods=['GET'])
def get_sections(session_id):
    """
    Retrieves all generated narrative sections and related data for a given session ID.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.

    Key Processing Steps:
    1. Loads session data (which includes pre-generated sections, case data, etc.)
       using `_load_session_data`.
    2. Extracts the correct account number using `get_correct_account_number`.
    3. Constructs a response object containing sections, recommendations, case data,
       Excel data (simulated), transaction data, and case info.

    Returns:
        JSON response with all narrative sections, recommendations, and associated data,
        or an error JSON response if the session is not found or data loading fails.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        return jsonify(error_response), status_code
    
    try:
        # Ensure essential keys are present (data integrity check, though _load_session_data handles file issues)
        if not data or "sections" not in data or "case_data" not in data:
            logger.error(f"Essential data missing in session {session_id}")
            return jsonify({"status": "error", "message": "Corrupted session data"}), 500
        
        # Create response with all necessary data for frontend
        response = {
            "status": "success",
            "sections": data["sections"],
            "recommendation": data.get("recommendation", {}),
            "case_data": data["case_data"],
            "excel_data": data["excel_data"],
            "transaction_data": data.get("transaction_data", {})
        }
        
        # Extract account number from the correct source
        case_data = data["case_data"]
        account_number = get_correct_account_number(case_data)
        
        # Create case info object with correct account number
        response["caseInfo"] = {
            "caseNumber": case_data.get("case_number", ""),
            "accountNumber": account_number,
            "dateGenerated": data.get("dateGenerated", datetime.now().isoformat())
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"Error fetching sections: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error fetching sections: {str(e)}"
        }), 500

def get_correct_account_number(case_data):
    """
    Extracts the primary account number from the `case_data` dictionary.

    This function attempts to find an account number by checking various
    locations within the `case_data` structure, following a specific priority:
    1.  **`case_data.full_data` ("Case Information" section -> "Relevant Accounts" list)**:
        It iterates through the `full_data` (original list of sections). If a section
        named "Case Information" is found and it contains a non-empty "Relevant Accounts"
        list, the first account number from this list is used.
    2.  **`case_data.account_info.account_number`**: If not found in "Relevant Accounts",
        it checks if `case_data` has an `account_info` dictionary with an `account_number` key.
    3.  **`case_data.accounts[0].account_number`**: If still not found, it checks if
        `case_data` has an `accounts` list and attempts to get the `account_number`
        from the first element of this list.

    If no account number can be extracted through these methods, a warning is logged,
    and the function returns "Unknown".

    Args:
        case_data: The case data dictionary, typically the "flattened" representation
                   which might also contain `full_data`.

    Returns:
        str: The extracted account number, or "Unknown" if not found.
    """
    account_number = ""
    
    # Priority 1: Extract from "Relevant Accounts" in the "Case Information" section of `full_data`.
    # `full_data` holds the original, non-flattened list of case sections.
    if case_data.get("full_data") and isinstance(case_data["full_data"], list):
        for section in case_data["full_data"]:
            if isinstance(section, dict) and section.get("section") == "Case Information":
                relevant_accounts = section.get("Relevant Accounts")
                if relevant_accounts and isinstance(relevant_accounts, list) and len(relevant_accounts) > 0:
                    account_number = str(relevant_accounts[0]) # Use the first relevant account.
                    logger.debug(f"Using account number '{account_number}' from 'Relevant Accounts'.")
                    break # Found, no need to check other sections for this source.
    
    # Priority 2: Extract from `case_data.account_info.account_number`.
    # `account_info` in the flattened structure usually stores the primary account details.
    if not account_number: # If not found in Priority 1
        account_info_dict = case_data.get("account_info")
        if isinstance(account_info_dict, dict) and account_info_dict.get("account_number"):
            account_number = str(account_info_dict["account_number"])
            logger.debug(f"Using account number '{account_number}' from 'case_data.account_info'.")
    
    # Priority 3: Extract from the first element of `case_data.accounts` list.
    # The `accounts` list in the flattened structure contains all accounts associated with the case.
    if not account_number: # If not found in Priority 1 or 2
        accounts_list = case_data.get("accounts")
        if isinstance(accounts_list, list) and len(accounts_list) > 0:
            first_account_dict = accounts_list[0]
            if isinstance(first_account_dict, dict) and first_account_dict.get("account_number"):
                account_number = str(first_account_dict["account_number"])
                logger.debug(f"Using account number '{account_number}' from the first item in 'case_data.accounts' list.")
    
    # Fallback: If no account number is found after checking all prioritized locations.
    if not account_number:
        logger.warning(f"Could not determine account number for case '{case_data.get('case_number', 'unknown')}'. Defaulting to 'Unknown'.")
        account_number = "Unknown" # Default value.
    
    return account_number

@app.route('/api/alerting-activity/<session_id>', methods=['GET'])
def get_alerting_activity(session_id: str):
    """
    Retrieves or generates the alerting activity summary for a given session.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.

    Key Processing Steps:
    1. Loads session data using `_load_session_data`.
    2. Extracts `case_data` and `full_case_data` (original case structure).
    3. Uses `extract_alerting_activity_summary` to get structured alert data from `full_case_data`.
       If `full_case_data` is unavailable, it attempts to build a basic summary from `case_data.alert_info`.
    4. Checks if a summary was previously generated and stored in `data['recommendation']['alerting_activity']`.
    5. If no pre-existing summary, it generates a new one using `LLMClient` and `generate_alerting_activity_prompt`.
       The newly generated summary is then saved back to the session's `data.json`.

    Returns:
        JSON response containing:
        - `alertingActivitySummary`: Structured data about the alert(s).
        - `generatedSummary`: The textual summary (either pre-existing or newly generated).
        Returns an error JSON response if session/data loading fails or during generation.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        # Handle cases where _load_session_data returns an error with a 200 status (e.g., empty file)
        # by ensuring a consistent error structure for the frontend if needed.
        if status_code == 200 and error_response.get("status") == "error":
             return jsonify({
                "status": "error",
                "message": error_response.get("message", "Failed to load session data."),
                "alertingActivitySummary": {"alertInfo": {"caseNumber": "", "alertDescription": ""}},
                "generatedSummary": ""
            }), 200 # Or a more appropriate error code like 400/500 if frontend handles it
        return jsonify(error_response), status_code
    
    # Proceed if data is loaded successfully.
    try:
        if not data: # Should be caught by _load_session_data, but as a safeguard.
             return jsonify({"status": "error", "message": "Session data is unexpectedly empty."}), 500

            
        case_data = data.get("case_data", {})
        
        # Get the original full case data to extract alerts properly
        full_case_data = case_data.get("full_data", [])
        if not full_case_data and case_data.get("case_number"):
            # Try to fetch from repository if not in the data
            full_case_data = get_full_case(case_data.get("case_number"))
        
        # Extract alerting activity summary from the case data
        if full_case_data:
            alerting_activity_summary = extract_alerting_activity_summary(full_case_data)
        else:
            # Create a default structure if case data not available
            alerting_activity_summary = {
                "alertInfo": {
                    "caseNumber": case_data.get("case_number", ""),
                    "alertingAccounts": "",
                    "alertingMonths": "",
                    "alertDescription": "",
                    "alertID": "",
                    "reviewPeriod": "",
                    "transactionalActivityDescription": "",
                    "alertDispositionSummary": ""
                },
                "account": "",
                "creditSummary": {"amountTotal": 0},
                "debitSummary": {"amountTotal": 0}
            }
            
            # Try to extract some basic alert info from alert_info
            alert_info = case_data.get("alert_info", [])
            if isinstance(alert_info, list) and alert_info:
                alert = alert_info[0]
                if isinstance(alert, dict):
                    alerting_activity_summary["alertInfo"]["alertID"] = alert.get("alert_id", "")
                    alerting_activity_summary["alertInfo"]["alertingMonths"] = alert.get("alert_month", "")
                    alerting_activity_summary["alertInfo"]["alertDescription"] = alert.get("description", "")
                    if alert.get("review_period") and isinstance(alert["review_period"], dict):
                        start = alert["review_period"].get("start", "")
                        end = alert["review_period"].get("end", "")
                        if start and end:
                            alerting_activity_summary["alertInfo"]["reviewPeriod"] = f"{start} to {end}"
        
        # Get account information regardless of source
        account_info = case_data.get("account_info", {})
        if account_info:
            account_type = account_info.get("account_type", "")
            account_number = account_info.get("account_number", "")
            if not alerting_activity_summary["alertInfo"]["alertingAccounts"]:
                alerting_activity_summary["alertInfo"]["alertingAccounts"] = f"{account_type} {account_number}".strip()
            if not alerting_activity_summary["account"]:
                alerting_activity_summary["account"] = account_number
        
        # Get existing generated summary if available
        generated_summary = ""
        if "recommendation" in data and "alerting_activity" in data["recommendation"]:
            generated_summary = data["recommendation"]["alerting_activity"]
        
        # Generate a new summary if none exists
        if not generated_summary:
            try:
                # Initialize LLM client
                llm_client = LLMClient()
                
                # Create a prompt using the actual alert data
                prompt = generate_alerting_activity_prompt(alerting_activity_summary)
                
                # Generate the summary
                generated_summary = llm_client.generate_content(prompt, max_tokens=500, temperature=0.1)
                
                # Update recommendation with generated summary
                if "recommendation" not in data:
                    data["recommendation"] = {}
                
                data["recommendation"]["alerting_activity"] = generated_summary
                save_to_json_file(data, data_path)
            except Exception as e:
                logger.error(f"Error generating alerting activity summary: {str(e)}", exc_info=True)
                generated_summary = "Error generating summary. Please try regenerating the section."
        
        # Create the response data
        response_data = {
            "status": "success",
            "alertingActivitySummary": alerting_activity_summary,
            "generatedSummary": generated_summary
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching alerting activity summary: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Error fetching alerting activity summary: {str(e)}",
            "alertingActivitySummary": {
                "alertInfo": {
                    "caseNumber": "",
                    "alertingAccounts": "",
                    "alertingMonths": "",
                    "alertDescription": ""
                }
            },
            "generatedSummary": ""
        }), 200  # Return 200 with error info for graceful handling

@app.route('/api/regenerate/<session_id>/<section_id>', methods=['POST'])
def regenerate_section(session_id, section_id):
    """
    Regenerates the content for a specific narrative or recommendation section.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.
    - `section_id` (str): The ID of the section to regenerate (must be in `VALID_SECTION_IDS` or `VALID_RECOMMENDATION_SECTIONS`).

    Request JSON Body:
    - (Optional) May include model selection or other parameters if regeneration logic is extended.

    Key Processing Steps:
    1. Loads session data using `_load_session_data`.
    2. Retrieves `combined_data` (used as input for `NarrativeGenerator`).
    3. Initializes `LLMClient` and `NarrativeGenerator`.
    4. Determines if the `section_id` refers to a narrative or recommendation section.
    5. Calls the appropriate generation method on `NarrativeGenerator` (e.g., `generate_suspicious_activity_summary`, `generate_alerting_activity`).
    6. Updates the corresponding section in the session's `data.json` with the new content.
       If it's a narrative section, the full narrative text is also rebuilt.
    7. Saves the updated session data.

    Returns:
        JSON response with the regenerated section's details (`id`, `content`, `type`),
        or an error JSON response if regeneration fails.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        return jsonify(error_response), status_code

    # Validate section ID against known valid narrative and recommendation section IDs.
    if section_id not in VALID_SECTION_IDS and section_id not in VALID_RECOMMENDATION_SECTIONS:
        return jsonify({"status": "error", "message": "Invalid section ID"}), 400
    
    try:
        if not data or "combined_data" not in data:
             return jsonify({"status": "error", "message": "Corrupted or incomplete session data for regeneration."}), 500
        
        # Get the combined data for generation
        combined_data = data["combined_data"]
        
        # Initialize LLM client
        llm_client = LLMClient()
        
        # Initialize NarrativeGenerator
        narrative_generator = NarrativeGenerator(combined_data, llm_client)
        
        # Determine if it's a narrative section or recommendation section
        is_recommendation = section_id in VALID_RECOMMENDATION_SECTIONS
        
        # Generate section content based on section ID
        if is_recommendation:
            # Handle recommendation sections
            method_name = f"generate_{section_id}"
            if hasattr(narrative_generator, method_name):
                method = getattr(narrative_generator, method_name)
                section_content = method()
            else:
                # Special handling for sections that don't have direct method mappings
                if section_id == "alerting_activity":
                    section_content = narrative_generator.generate_alerting_activity()
                elif section_id == "prior_sars":
                    section_content = narrative_generator.generate_prior_sars_summary()
                else:
                    # Fallback - unknown section
                    return jsonify({
                        "status": "error",
                        "message": f"Unknown recommendation section: {section_id}"
                    }), 400
            
            # Update recommendation section in data
            if "recommendation" not in data:
                data["recommendation"] = {}
            
            data["recommendation"][section_id] = section_content
            
            # Return the content in the expected format
            section_details = {
                "id": section_id,
                "content": section_content,
                "type": "recommendation"
            }
        else:
            # Handle narrative sections
            method_name = f"generate_{section_id}"
            if hasattr(narrative_generator, method_name):
                method = getattr(narrative_generator, method_name)
                section_content = method()
            else:
                # Try to map section ID to generator method
                section_method_mapping = {
                    SECTION_IDS["SUSPICIOUS_ACTIVITY_SUMMARY"]: narrative_generator.generate_suspicious_activity_summary,
                    SECTION_IDS["PRIOR_CASES"]: narrative_generator.generate_prior_cases,
                    SECTION_IDS["ACCOUNT_SUBJECT_INFO"]: narrative_generator.generate_account_subject_info,
                    SECTION_IDS["SUSPICIOUS_ACTIVITY_ANALYSIS"]: narrative_generator.generate_suspicious_activity_analysis,
                    SECTION_IDS["CONCLUSION"]: narrative_generator.generate_conclusion
                }
                
                if section_id in section_method_mapping:
                    section_content = section_method_mapping[section_id]()
                else:
                    # Fallback - unknown section
                    return jsonify({
                        "status": "error",
                        "message": f"Unknown narrative section: {section_id}"
                    }), 400
            
            # Update section in data
            if "sections" not in data:
                data["sections"] = {}
            
            data["sections"][section_id] = {
                "id": section_id,
                "title": SECTION_TITLES.get(section_id, section_id.replace("_", " ").title()),
                "content": section_content
            }
            
            # Rebuild full narrative
            narrative = narrative_generator.generate_narrative()
            data["narrative"] = narrative
            
            # Return the content in the expected format
            section_details = {
                "id": section_id,
                "content": section_content,
                "type": "narrative"
            }
        
        # Save updated data
        save_to_json_file(data, data_path)
        
        return jsonify({
            "status": "success",
            "section": section_details
        }), 200
    
    except Exception as e:
        logger.error(f"Error regenerating section: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error regenerating section: {str(e)}"
        }), 500
        
@app.route('/api/sections/<session_id>/<section_id>', methods=['PUT'])
def update_section(session_id, section_id):
    """
    Updates the content of a specific narrative section for a given session.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.
    - `section_id` (str): The ID of the narrative section to update (must be in `VALID_SECTION_IDS`).

    Request JSON Body:
    - `content` (str): The new textual content for the section.

    Key Processing Steps:
    1. Loads session data using `_load_session_data`.
    2. Validates that the provided `section_id` is a valid narrative section ID.
    3. Updates the content of the specified section in `data['sections']`.
    4. Rebuilds the full narrative text using `NarrativeGenerator` (though typically,
       the full narrative might be rebuilt from the updated `sections` dict directly
       or when exporting, depending on how `data['narrative']` is used).
    5. Saves the updated session data to `data.json`.

    Returns:
        JSON response indicating success or failure of the update operation.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        return jsonify(error_response), status_code

    # Validate that the section_id is for a narrative section.
    if section_id not in VALID_SECTION_IDS:
        return jsonify({"status": "error", "message": "Invalid narrative section ID for update"}), 400
    
    request_payload = request.get_json()
    if not request_payload or 'content' not in request_payload: # Ensure content is provided.
        return jsonify({"status": "error", "message": "Content is required in request body"}), 400
    content = request_payload['content']
    
    try:
        if not data or "sections" not in data or section_id not in data["sections"]:
             return jsonify({"status": "error", "message": "Section or session data not found for update."}), 404
        
        # Update section content
        data["sections"][section_id]["content"] = content
        
        # Rebuild full narrative
        narrative_generator = NarrativeGenerator(data["combined_data"])
        narrative = narrative_generator.generate_narrative()
        data["narrative"] = narrative
        
        # Save updated data
        save_to_json_file(data, data_path)
        
        return jsonify({
            "status": "success",
            "message": "Section updated successfully"
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating section: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error updating section: {str(e)}"
        }), 500

@app.route('/api/recommendations/<session_id>/<section_id>', methods=['PUT'])
def update_recommendation_section(session_id, section_id):
    """
    Updates the content of a specific recommendation section for a given session.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.
    - `section_id` (str): The ID of the recommendation section to update (must be in `VALID_RECOMMENDATION_SECTIONS`).

    Request JSON Body:
    - `content` (str): The new textual content for the recommendation section.

    Key Processing Steps:
    1. Loads session data using `_load_session_data`.
    2. Validates that the `section_id` is a valid recommendation section ID.
    3. Updates the content of the specified section in `data['recommendation']`.
    4. Saves the updated session data to `data.json`.

    Returns:
        JSON response indicating success or failure of the update operation.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        return jsonify(error_response), status_code

    # Validate that the section_id is for a recommendation section.
    if section_id not in VALID_RECOMMENDATION_SECTIONS:
        return jsonify({"status": "error", "message": "Invalid recommendation section ID for update"}), 400
    
    request_payload = request.get_json()
    if not request_payload or 'content' not in request_payload: # Ensure content is provided.
        return jsonify({"status": "error", "message": "Content is required in request body"}), 400
    content = request_payload['content']
    
    try:
        if not data: # Should be caught by _load_session_data, but as a safeguard.
             return jsonify({"status": "error", "message": "Session data could not be loaded."}), 500
        
        # Ensure recommendation object exists
        if "recommendation" not in data:
            data["recommendation"] = {}
        
        # Update recommendation section content
        data["recommendation"][section_id] = content
        
        # Save updated data
        save_to_json_file(data, data_path)
        
        return jsonify({
            "status": "success",
            "message": "Recommendation section updated successfully"
        }), 200
    
    except Exception as e:
        logger.error(f"Error updating recommendation section: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error updating recommendation section: {str(e)}"
        }), 500

@app.route('/api/prior-cases/<session_id>', methods=['GET'])
def get_prior_cases_summary(session_id):
    """
    Retrieves or generates a summary of prior cases/SARs for a given session.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.

    Key Processing Steps:
    1. Loads session data using `_load_session_data`.
    2. Attempts to retrieve `prior_cases` from the loaded session data.
    3. If not found in session, it tries to extract them from `case_data` (either from
       `full_data` if present, or by fetching `full_case_data` from the repository).
       The extracted prior cases are then saved back to the session data.
    4. Generates a prompt for LLM summarization using `generate_prior_cases_prompt`.
    5. Checks if a summary was previously generated and stored in `data['recommendation']['prior_sars']`.
    6. If no pre-existing summary and prior cases exist, it generates a new one using `LLMClient`.
       The newly generated summary is saved back to the session data.

    Returns:
        JSON response containing:
        - `priorCases`: List of structured prior case data.
        - `prompt`: The prompt used for LLM generation.
        - `generatedSummary`: The textual summary of prior cases.
        Returns an error JSON response (but with HTTP 200 for graceful UI handling) if processing fails.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        # For this specific route, the original code returns 200 on error for UI handling.
        if status_code != 200 : # If _load_session_data had a real error (400, 404, 500)
             return jsonify(error_response), status_code
        # If it was a 200 with error message (e.g. empty file from _load_session_data)
        return jsonify({
            "status": "success", # Original code returns success for UI
            "message": error_response.get("message", "Error loading session data."),
            "priorCases": [],
            "prompt": "Write a brief summary stating that no prior SARs were identified for this account or customer.",
            "generatedSummary": "No prior SARs were identified for the subjects or account."
        }), 200

    try:
        if not data: # Safeguard
             return jsonify({"status": "error", "message": "Session data is unexpectedly empty."}), 500
        
        # Try to get prior cases from session data
        prior_cases = data.get("prior_cases", [])
        
        # If no prior cases, try to extract them from case data
        if not prior_cases and "case_data" in data:
            case_data = data["case_data"]
            case_number = case_data.get("case_number", "")
            full_data = case_data.get("full_data", [])
            
            if full_data:
                prior_cases = extract_prior_cases_summary(full_data)
            elif case_number:
                # Try to retrieve from repository
                full_case_data = get_full_case(case_number)
                if full_case_data:
                    prior_cases = extract_prior_cases_summary(full_case_data)
            
            # Save prior cases in session data
            data["prior_cases"] = prior_cases
            save_to_json_file(data, data_path)
        
        # Generate prompt for LLM
        prompt = generate_prior_cases_prompt(prior_cases)
        
        # Get existing generated summary
        generated_summary = ""
        if "recommendation" in data and "prior_sars" in data["recommendation"]:
            generated_summary = data["recommendation"]["prior_sars"]
        
        # Generate summary if none exists
        if not generated_summary and prior_cases:
            # Initialize LLM client
            llm_client = LLMClient()
            
            # Generate summary
            generated_summary = llm_client.generate_content(prompt, max_tokens=500, temperature=0.1)
            
            # Save generated summary
            if "recommendation" not in data:
                data["recommendation"] = {}
            
            data["recommendation"]["prior_sars"] = generated_summary
            save_to_json_file(data, data_path)
        
        return jsonify({
            "status": "success",
            "priorCases": prior_cases,
            "prompt": prompt,
            "generatedSummary": generated_summary
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching prior cases summary: {str(e)}")
        return jsonify({
            "status": "success",  # Still return success for graceful UI handling
            "message": f"Error fetching prior cases summary: {str(e)}",
            "priorCases": [],
            "prompt": "Write a brief summary stating that no prior SARs were identified for this account or customer.",
            "generatedSummary": "No prior SARs were identified for the subjects or account."
        }), 200

@app.route('/api/regenerate-prior-cases/<session_id>', methods=['POST'])
def regenerate_prior_cases(session_id):
    """
    Regenerates the prior cases/SARs summary for a given session using an LLM.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.

    Key Processing Steps:
    1. Loads session data using `_load_session_data`.
    2. Retrieves `prior_cases` data (potentially fetching from `full_case_data` if not directly in session).
    3. Generates a prompt suitable for LLM summarization using `generate_prior_cases_prompt`.
    4. Initializes `LLMClient` and generates a new textual summary.
    5. Updates `data['recommendation']['prior_sars']` with the new summary.
    6. Saves the updated session data.

    Returns:
        JSON response containing the (potentially updated) `priorCases` list, the `prompt`,
        and the newly `generatedSummary`, or an error JSON response if regeneration fails.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        return jsonify(error_response), status_code
    
    try:
        if not data: # Safeguard
             return jsonify({"status": "error", "message": "Session data is unexpectedly empty."}), 500
        
        # Get case number and try to retrieve updated prior cases
        case_data = data.get("case_data", {})
        case_number = case_data.get("case_number", "")
        
        # Try to get prior cases from various sources
        prior_cases = data.get("prior_cases", [])
        
        if not prior_cases and case_number:
            # Try to get from full case data
            full_case_data = get_full_case(case_number)
            if full_case_data:
                prior_cases = extract_prior_cases_summary(full_case_data)
                data["prior_cases"] = prior_cases
        
        # Generate prompt
        prompt = generate_prior_cases_prompt(prior_cases)
        
        # Initialize LLM client
        llm_client = LLMClient()
        
        # Generate new summary
        generated_summary = llm_client.generate_content(prompt, max_tokens=500, temperature=0.1)
        
        # Update recommendation
        if "recommendation" not in data:
            data["recommendation"] = {}
        
        data["recommendation"]["prior_sars"] = generated_summary
        save_to_json_file(data, data_path)
        
        return jsonify({
            "status": "success",
            "priorCases": prior_cases,
            "prompt": prompt,
            "generatedSummary": generated_summary
        }), 200
        
    except Exception as e:
        logger.error(f"Error regenerating prior cases summary: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error regenerating prior cases summary: {str(e)}"
        }), 500

@app.route('/api/export/<session_id>', methods=['GET'])
def export_narrative(session_id):
    """
    Exports the generated SAR narrative as a text file for a given session.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.

    Key Processing Steps:
    1. Loads session data using `_load_session_data`.
    2. Retrieves `case_data` and `sections` (generated narrative content).
    3. Reconstructs the full narrative text by concatenating content from `sections`
       based on the order defined by `SECTION_IDS`.
    4. Creates a temporary text file.
    5. Writes a header (case number, generation date) and the narrative to the file.
    6. Sends the file to the client for download.

    Returns:
        A Flask `send_file` response to download the text file,
        or a JSON error response if processing fails.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        return jsonify(error_response), status_code

    try:
        if not data or "case_data" not in data or "sections" not in data:
             return jsonify({"status": "error", "message": "Required data for export missing in session."}), 500
        
        case_data = data["case_data"]
        sections = data["sections"]
        
        # Rebuild the narrative from sections using the updated section IDs
        narrative = "\n\n".join([
            sections.get(SECTION_IDS["SUSPICIOUS_ACTIVITY_SUMMARY"], {}).get("content", ""),
            sections.get(SECTION_IDS["PRIOR_CASES"], {}).get("content", ""),
            sections.get(SECTION_IDS["ACCOUNT_SUBJECT_INFO"], {}).get("content", ""),
            sections.get(SECTION_IDS["SUSPICIOUS_ACTIVITY_ANALYSIS"], {}).get("content", ""),
            sections.get(SECTION_IDS["CONCLUSION"], {}).get("content", "")
        ])
        
        # Create a temporary file for export
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            case_number = case_data.get("case_number", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Write header
            tmp.write(f"SAR Narrative - Case {case_number}\n".encode('utf-8'))
            tmp.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n".encode('utf-8'))
            
            # Write Section 7 narrative
            tmp.write("====================== SECTION 7: SAR NARRATIVE ======================\n\n".encode('utf-8'))
            tmp.write(narrative.encode('utf-8'))
            
            # Add footer
            tmp.write("\n\n===================================================================\n".encode('utf-8'))
            tmp.write("Generated by SAR Narrative Generator".encode('utf-8'))
            
            tmp_path = tmp.name
        
        # Generate filename for download
        filename = f"SAR_Narrative_{case_number}_{timestamp}.txt"
        
        # Send file for download
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    
    except Exception as e:
        logger.error(f"Error exporting narrative: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error exporting narrative: {str(e)}"
        }), 500

@app.route('/api/export-recommendation/<session_id>', methods=['GET'])
def export_recommendation(session_id):
    """
    Exports the generated SAR recommendation as a text file for a given session.

    URL Parameters:
    - `session_id` (str): The unique identifier for the session.

    Key Processing Steps:
    1. Loads session data using `_load_session_data`.
    2. Retrieves `case_data` and `recommendation` (generated recommendation content).
    3. Constructs the recommendation text by iterating through `ordered_sections`
       (a predefined order of recommendation parts) and formatting each section's content.
    4. Creates a temporary text file.
    5. Writes a header and the formatted recommendation text to the file.
    6. Sends the file to the client for download.

    Returns:
        A Flask `send_file` response to download the text file,
        or a JSON error response if processing fails or recommendation data is missing.
    """
    # Load session data using the helper function.
    data, error_response, status_code = _load_session_data(session_id, app.config['UPLOAD_FOLDER'])
    if error_response:
        return jsonify(error_response), status_code

    try:
        if not data or "case_data" not in data or "recommendation" not in data:
             return jsonify({"status": "error", "message": "Required data for recommendation export missing in session."}), 404
        
        case_data = data["case_data"]
        
        # Check if recommendation exists
        if "recommendation" not in data:
            return jsonify({
                "status": "error",
                "message": "Recommendation not found"
            }), 404
        
        recommendation = data["recommendation"]
        
        # Build recommendation text
        ordered_sections = [
            "alerting_activity",
            "prior_sars",
            "scope_of_review",
            "investigation_summary",
            "conclusion",
            "cta",
            "retain_close"
        ]
        
        recommendation_text = "7. Recommendations\n\nB. SAR/No SAR Recommendation\n\n"
        
        for section_id in ordered_sections:
            if section_id in recommendation and recommendation[section_id]:
                # Add section header based on section ID
                if section_id == "alerting_activity":
                    recommendation_text += "Alerting Activity / Reason for Review\n"
                elif section_id == "prior_sars":
                    recommendation_text += "Prior SARs\n"
                elif section_id == "scope_of_review":
                    recommendation_text += "Scope of Review\n"
                elif section_id == "investigation_summary":
                    recommendation_text += "Summary of the Investigation (Red Flags, Supporting Evidence, etc.)\n"
                elif section_id == "conclusion":
                    recommendation_text += "Conclusion\n"
                elif section_id == "cta":
                    recommendation_text += "\nC. Escalations/Referrals\n\nCTA\n"
                elif section_id == "retain_close":
                    recommendation_text += "\nD. Retain or Close Customer Relationship(s)\n"
                
                recommendation_text += recommendation[section_id] + "\n\n"
        
        # Create a temporary file for export
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            case_number = case_data.get("case_number", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Write header
            tmp.write(f"SAR Recommendation - Case {case_number}\n".encode('utf-8'))
            tmp.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n".encode('utf-8'))
            
            # Write recommendation
            tmp.write(recommendation_text.encode('utf-8'))
            
            # Add footer
            tmp.write("\n\n===================================================================\n".encode('utf-8'))
            tmp.write("Generated by SAR Narrative Generator".encode('utf-8'))
            
            tmp_path = tmp.name
        
        # Generate filename for download
        filename = f"SAR_Recommendation_{case_number}_{timestamp}.txt"
        
        # Send file for download
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    
    except Exception as e:
        logger.error(f"Error exporting recommendation: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error exporting recommendation: {str(e)}"
        }), 500

if __name__ == '__main__':
    # Check which variables exist in config for host and port
    host = getattr(config, 'API_HOST', getattr(config, 'HOST', '0.0.0.0'))
    port = getattr(config, 'API_PORT', getattr(config, 'PORT', 8081))
    debug = getattr(config, 'API_DEBUG', getattr(config, 'DEBUG', False))
    
    app.run(debug=debug, host=host, port=port)