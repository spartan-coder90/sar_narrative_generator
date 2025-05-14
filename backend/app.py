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
from werkzeug.utils import secure_filename
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
    extract_prior_cases_summary, generate_prior_cases_prompt,
    extract_scope_of_review, generate_scope_of_review_prompt
)

# Set up logging
logger = get_logger(__name__)

# Initialize app
app = Flask(__name__)

# Configure Flask app directly with variables from config
app.config['UPLOAD_FOLDER'] = config.UPLOAD_DIR  # Using UPLOAD_DIR from config
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload
app.config['SECRET_KEY'] = os.urandom(24)  # Generate a random secret key

# Check if API_DEBUG exists, otherwise default to False
if hasattr(config, 'API_DEBUG'):
    app.config['DEBUG'] = config.API_DEBUG
else:
    app.config['DEBUG'] = False

CORS(app)  # Enable CORS for all routes

# Create required directories
os.makedirs(config.UPLOAD_DIR, exist_ok=True)  # Using UPLOAD_DIR

# Valid section IDs for narrative - updated to match new section format
VALID_SECTION_IDS = list(SECTION_IDS.values())

# Valid recommendation section IDs
VALID_RECOMMENDATION_SECTIONS = [
    "alerting_activity", "prior_sars", "scope_of_review", 
    "investigation_summary", "conclusion", "cta", "retain_close"
]

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "version": "1.0.0"
    }), 200

@app.route('/api/cases', methods=['GET'])
def get_available_case_list():
    """Get list of available cases for UI dropdown"""
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
    Process selected case to generate SAR narrative
    
    Requires:
    - case_number: Case number to use from static repository
    - model: (optional) LLM model to use for generation
    
    Returns:
    - sessionId: Session ID for future requests
    - sections: Generated SAR narrative sections
    - warning: Any warnings during processing
    """
    # Get case_number from request
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
        
        # Create excel_data structure from transaction data
        excel_data = {
            "activity_summary": transaction_data.get("activity_summary", {}),
            "unusual_activity": transaction_data.get("unusual_activity", {}),
            "transaction_summary": {
                "total_credits": transaction_data.get("activity_summary", {}).get("totals", {}).get("credits", {}).get("total_amount", 0),
                "total_debits": transaction_data.get("activity_summary", {}).get("totals", {}).get("debits", {}).get("total_amount", 0),
                "credit_breakdown": [],
                "debit_breakdown": []
            },
            "account_summaries": transaction_data.get("activity_summary", {}).get("accounts", {}),
            "cta_sample": transaction_data.get("cta_sample", {}),
            "bip_sample": transaction_data.get("bip_sample", {}),
            "inter_account_transfers": []
        }
        
        # Create credit and debit breakdowns from activity summary
        for account_num, account_data in transaction_data.get("activity_summary", {}).get("accounts", {}).items():
            # Credit breakdown
            for txn_type, txn_data in account_data.get("credits", {}).get("by_type", {}).items():
                excel_data["transaction_summary"]["credit_breakdown"].append({
                    "type": txn_type,
                    "amount": txn_data.get("amount", 0),
                    "count": txn_data.get("count", 0)
                })
            
            # Debit breakdown
            for txn_type, txn_data in account_data.get("debits", {}).get("by_type", {}).items():
                excel_data["transaction_summary"]["debit_breakdown"].append({
                    "type": txn_type,
                    "amount": txn_data.get("amount", 0),
                    "count": txn_data.get("count", 0)
                })
        
        # Validate data
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
    Get narrative sections for a session with corrected account number handling
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
        
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        data = load_from_json_file(data_path)
        
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
    Extract the correct account number from case data
    
    Args:
        case_data: The case data dictionary
        
    Returns:
        str: The correct account number
    """
    account_number = ""
    
    # First priority: Get from Relevant Accounts in Case Information section
    if case_data.get("full_data"):
        for section in case_data["full_data"]:
            if section.get("section") == "Case Information" and section.get("Relevant Accounts"):
                if section["Relevant Accounts"] and len(section["Relevant Accounts"]) > 0:
                    account_number = section["Relevant Accounts"][0]
                    logger.debug(f"Using account number {account_number} from Relevant Accounts")
                    break
    
    # Second priority: Get from case_data.account_info.account_number
    if not account_number and case_data.get("account_info") and case_data["account_info"].get("account_number"):
        account_number = case_data["account_info"]["account_number"]
        logger.debug(f"Using account number {account_number} from account_info")
    
    # Third priority: Try to find from accounts array
    if not account_number and case_data.get("accounts") and len(case_data["accounts"]) > 0:
        account = case_data["accounts"][0]
        if account.get("account_number"):
            account_number = account["account_number"]
            logger.debug(f"Using account number {account_number} from accounts array")
    
    # If still no account number found, log a warning
    if not account_number:
        logger.warning(f"No account number found for case {case_data.get('case_number', 'unknown')}")
        account_number = "Unknown"
    
    return account_number

@app.route('/api/alerting-activity/<session_id>', methods=['GET'])
def get_alerting_activity(session_id):
    """
    Get detailed alerting activity summary for a session - directly from case data alerts
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        # If file is empty, return empty result
        if os.path.getsize(data_path) == 0:
            logger.warning(f"Empty data file found: {data_path}")
            return jsonify({
                "status": "error",
                "message": "Empty data file",
                "alertingActivitySummary": {
                    "alertInfo": {"caseNumber": "", "alertDescription": ""}
                },
                "generatedSummary": ""
            }), 200
            
        # Read and parse data
        try:
            data = load_from_json_file(data_path)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in file {data_path}: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Invalid JSON in data file: {str(e)}",
                "alertingActivitySummary": {
                    "alertInfo": {"caseNumber": "", "alertDescription": ""}
                },
                "generatedSummary": ""
            }), 200
            
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
    Regenerate a specific section using NarrativeGenerator directly
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    # Validate section ID
    if section_id not in VALID_SECTION_IDS and section_id not in VALID_RECOMMENDATION_SECTIONS:
        return jsonify({
            "status": "error",
            "message": "Invalid section ID"
        }), 400
    
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        data = load_from_json_file(data_path)
        
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
    Update a specific section of the SAR narrative
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    # Validate section ID
    if section_id not in VALID_SECTION_IDS:
        return jsonify({
            "status": "error",
            "message": "Invalid section ID"
        }), 400
    
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    content = request.json.get('content')
    if not content:
        return jsonify({
            "status": "error",
            "message": "Content is required"
        }), 400
    
    try:
        data = load_from_json_file(data_path)
        
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
    Update a specific recommendation section
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    # Validate section ID
    if section_id not in VALID_RECOMMENDATION_SECTIONS:
        return jsonify({
            "status": "error",
            "message": "Invalid recommendation section ID"
        }), 400
    
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    content = request.json.get('content')
    if not content:
        return jsonify({
            "status": "error",
            "message": "Content is required"
        }), 400
    
    try:
        data = load_from_json_file(data_path)
        
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
    Get prior cases summary for a session
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        data = load_from_json_file(data_path)
        
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
    Regenerate prior cases summary for a session
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        data = load_from_json_file(data_path)
        
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
    Export the final SAR narrative
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        data = load_from_json_file(data_path)
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
    Export the SAR recommendation
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    data_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        data = load_from_json_file(data_path)
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