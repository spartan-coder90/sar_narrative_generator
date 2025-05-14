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
import logging
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
from backend.generators.narrative_generator import NarrativeGenerator
from backend.utils.json_utils import save_to_json_file, load_from_json_file
from backend.integrations.llm_client import LLMClient
from backend.data.case_repository import get_case, get_full_case, get_available_cases
from backend.utils.section_extractors import extract_prior_cases_summary, generate_prior_cases_prompt

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

# Valid section IDs for narrative
VALID_SECTION_IDS = [
    "introduction", 
    "prior_cases", 
    "account_info", 
    "activity_summary", 
    "conclusion", 
    "subject_info", 
    "transaction_samples"
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
        
        # Since we're not using Excel files anymore, we'll adapt the excel_data structure
        # to work with our transaction data
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
            "recommendation": recommendation,
            "wordControl": excel_data.get("word_control_macro", {})
        }
        
        # Include case and excel data for complete context
        response["case_data"] = case_data
        response["excel_data"] = excel_data
        response["combined_data"] = combined_data
        response["transaction_data"] = transaction_data
        
        # Save a copy of the processed data for later use
        save_to_json_file({
            "case_data": case_data,
            "excel_data": excel_data,
            "combined_data": combined_data,
            "transaction_data": transaction_data,
            "narrative": narrative,
            "sections": sections,
            "recommendation": recommendation
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
    Get detailed alerting activity summary for a session - with improved error handling
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
        
        # Check if transaction data and alerting activity summary exist
        transaction_data = data.get("transaction_data", {})
        case_data = data.get("case_data", {})
        
        # Generate alerting activity summary if not available
        alerting_activity_summary = transaction_data.get("alerting_activity_summary", {})
        if not alerting_activity_summary:
            try:
                transaction_processor = TransactionProcessor(case_data)
                alerting_activity_summary = transaction_processor.calculate_alerting_activity_summary()
                
                # Sanitize data to prevent JSON issues
                alerting_activity_summary = sanitize_for_json(alerting_activity_summary)
                
                # Save it back to the session data
                if "transaction_data" not in data:
                    data["transaction_data"] = {}
                
                data["transaction_data"]["alerting_activity_summary"] = alerting_activity_summary
                save_to_json_file(data, data_path)
            except Exception as e:
                logger.error(f"Error calculating alerting activity summary: {str(e)}", exc_info=True)
                # Create simplified structure on error
                alerting_activity_summary = {
                    "alertInfo": {
                        "caseNumber": case_data.get("case_number", ""),
                        "alertingAccounts": "",
                        "alertingMonths": "",
                        "alertDescription": ""
                    },
                    "account": "",
                    "creditSummary": {"amountTotal": 0},
                    "debitSummary": {"amountTotal": 0}
                }
        
        # Ensure alerting account is populated
        if not alerting_activity_summary.get("alertInfo", {}).get("alertingAccounts"):
            account_info = case_data.get("account_info", {})
            account_type = account_info.get("account_type", "")
            account_number = account_info.get("account_number", "")
            
            if "alertInfo" not in alerting_activity_summary:
                alerting_activity_summary["alertInfo"] = {}
                
            alerting_activity_summary["alertInfo"]["alertingAccounts"] = f"{account_type} {account_number}".strip()
            
            # Save updated data
            if "transaction_data" not in data:
                data["transaction_data"] = {}
            
            data["transaction_data"]["alerting_activity_summary"] = alerting_activity_summary
            save_to_json_file(data, data_path)
        
        # Get LLM template for formatting the alerting activity - simplified version
        llm_template = "Write a summary of the alerting activity based on the information provided."
        
        # Try to get a generated summary from the recommendation data
        generated_summary = ""
        if "recommendation" in data and "alerting_activity" in data["recommendation"]:
            generated_summary = data["recommendation"]["alerting_activity"]
        
        # If no generated summary exists, generate one using LLM
        if not generated_summary:
            try:
                # Initialize LLM client
                llm_client = LLMClient()
                
                # Format the template with actual data - simplified to avoid errors
                alert_info = alerting_activity_summary.get("alertInfo", {})
                credit_summary = alerting_activity_summary.get("creditSummary", {})
                debit_summary = alerting_activity_summary.get("debitSummary", {})
                
                # Create simplified prompt to avoid JSON errors
                formatted_prompt = f"""
                Write a summary about the following alert information:
                
                Case Number: {alert_info.get("caseNumber", "")}
                Alerting Account: {alert_info.get("alertingAccounts", "")}
                Alerting Month: {alert_info.get("alertingMonths", "")}
                Alert Description: {alert_info.get("alertDescription", "")}
                
                Total Credits: ${credit_summary.get("amountTotal", 0):,.2f}
                Total Debits: ${debit_summary.get("amountTotal", 0):,.2f}
                
                Write a summary in 3 paragraphs:
                1. First paragraph about the case number and alerting details
                2. Second paragraph about credit activity
                3. Third paragraph about debit activity
                """
                
                # Generate the summary
                generated_summary = llm_client.generate_content(formatted_prompt, max_tokens=800, temperature=0.2)
                
                # Update recommendation with generated summary
                if "recommendation" not in data:
                    data["recommendation"] = {}
                
                data["recommendation"]["alerting_activity"] = generated_summary
                save_to_json_file(data, data_path)
            except Exception as e:
                logger.error(f"Error generating alerting activity summary: {str(e)}", exc_info=True)
                generated_summary = "Error generating summary. Please try regenerating the section."
        
        # Create the response data - simplified to avoid JSON errors
        response_data = {
            "status": "success",
            "alertingActivitySummary": sanitize_for_json(alerting_activity_summary),
            "llmTemplate": llm_template,
            "generatedSummary": generated_summary
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching alerting activity summary: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Error fetching alerting activity summary: {str(e)}"
        }), 500
        
@app.route('/api/regenerate/<session_id>/<section_id>', methods=['POST'])
def regenerate_section(session_id, section_id):
    """
    Regenerate a specific section
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    # Expand valid section IDs to include recommendation sections
    VALID_SECTION_IDS_EXTENDED = [
        # SAR Narrative sections
        "introduction", "prior_cases", "account_info", "subject_info",
        "activity_summary", "transaction_samples", "conclusion",
        # Recommendation sections
        "alerting_activity", "prior_sars", "scope_of_review", 
        "investigation_summary", "recommendation_conclusion", "cta", "retain_close"
    ]
    
    # Validate section ID
    if section_id not in VALID_SECTION_IDS_EXTENDED:
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
        
        # Regenerate the specified section
        combined_data = data["combined_data"]
        transaction_data = data.get("transaction_data", {})
        
        # Add transaction data to combined data if it's not already there
        if transaction_data:
            combined_data.update({
                "activity_summary": transaction_data.get("activity_summary", {}),
                "transactions": transaction_data.get("transactions", {}),
                "unusual_activity": transaction_data.get("unusual_activity", {}),
                "counterparties": transaction_data.get("counterparties", {}),
                "cta_sample": transaction_data.get("cta_sample", {}),
                "bip_sample": transaction_data.get("bip_sample", {})
            })
        
        # Initialize LLM client
        llm_client = LLMClient()
        
        # Create narrative generator
        narrative_generator = NarrativeGenerator(combined_data, llm_client)
        
        # Determine if it's a narrative section or recommendation section
        recommendation_sections = ["alerting_activity", "prior_sars", "scope_of_review", 
                                  "investigation_summary", "recommendation_conclusion", "cta", "retain_close"]
        
        section_content = ""
        
        if section_id in recommendation_sections:
            # Generate recommendation section
            if section_id == "alerting_activity":
                section_content = narrative_generator.generate_alerting_activity()
            elif section_id == "prior_sars":
                section_content = narrative_generator.generate_prior_sars_summary()
            elif section_id == "scope_of_review":
                section_content = narrative_generator.generate_scope_of_review()
            elif section_id == "investigation_summary":
                section_content = narrative_generator.generate_investigation_summary()
            elif section_id == "recommendation_conclusion":
                section_content = narrative_generator.generate_recommendation_conclusion()
            elif section_id == "cta":
                section_content = narrative_generator.generate_cta_section()
            elif section_id == "retain_close":
                section_content = narrative_generator.generate_retain_close()
            
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
            # Generate narrative section
            if section_id == "introduction":
                section_content = narrative_generator.generate_introduction()
            elif section_id == "prior_cases":
                section_content = narrative_generator.generate_prior_cases()
            elif section_id == "account_info":
                section_content = narrative_generator.generate_account_info()
            elif section_id == "subject_info":
                section_content = narrative_generator.generate_subject_info()
            elif section_id == "activity_summary":
                section_content = narrative_generator.generate_activity_summary()
            elif section_id == "transaction_samples":
                section_content = narrative_generator.generate_transaction_samples()
            elif section_id == "conclusion":
                section_content = narrative_generator.generate_conclusion()
            
            # Update section in data
            data["sections"][section_id]["content"] = section_content
            
            # Rebuild full narrative
            narrative = rebuild_narrative(data["sections"])
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
        narrative = rebuild_narrative(data["sections"])
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
    
    # Define valid recommendation section IDs
    valid_recommendation_sections = [
        "alerting_activity", "prior_sars", "scope_of_review", 
        "investigation_summary", "conclusion", "cta", "retain_close"
    ]
    
    # Validate section ID
    if section_id not in valid_recommendation_sections:
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
        narrative = data["narrative"]
        
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

def split_narrative_into_sections(narrative):
    """
    Split the narrative into editable sections
    
    Args:
        narrative: Full narrative text
        
    Returns:
        dict: Sections with ID, title, and content
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

def rebuild_narrative(sections):
    """
    Rebuild the full narrative from sections
    
    Args:
        sections: Dictionary of narrative sections
        
    Returns:
        str: Complete narrative
    """
    ordered_sections = [
        sections.get("introduction", {}).get("content", ""),
        sections.get("prior_cases", {}).get("content", ""),
        sections.get("account_info", {}).get("content", ""),
        sections.get("subject_info", {}).get("content", ""),
        sections.get("activity_summary", {}).get("content", ""),
        sections.get("transaction_samples", {}).get("content", ""),
        sections.get("conclusion", {}).get("content", "")
    ]
    
    return "\n\n".join([section for section in ordered_sections if section])

        
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
        
        # Get prior cases from session data
        prior_cases = data.get("prior_cases", [])
        
        # If prior cases aren't already extracted, get them
        if not prior_cases:
            # Get case number
            case_number = ""
            if "case_data" in data:
                case_number = data["case_data"].get("case_number", "")
            
            # Get the original, raw case data
            raw_case_data = get_full_case(case_number)
            
            if not raw_case_data:
                return jsonify({
                    "status": "error",
                    "message": "Case data not found"
                }), 404
                
            # Extract prior cases information directly from the raw case data
            prior_cases = extract_prior_cases_summary(raw_case_data)
            
            # Store prior cases in session data
            data["prior_cases"] = prior_cases
            save_to_json_file(data, data_path)
        
        # Generate prompt for LLM
        prompt = generate_prior_cases_prompt(prior_cases)
        
        # Initialize LLM client
        llm_client = LLMClient()
        
        # Generate the new summary
        generated_summary = llm_client.generate_content(prompt, max_tokens=600, temperature=0.2)
        
        # Update recommendation with generated summary
        if "recommendation" not in data:
            data["recommendation"] = {}
        
        data["recommendation"]["prior_sars"] = generated_summary
        save_to_json_file(data, data_path)
        
        # Create the response data
        response_data = {
            "status": "success",
            "priorCases": prior_cases,
            "prompt": prompt,
            "generatedSummary": generated_summary
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error regenerating prior cases summary: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error regenerating prior cases summary: {str(e)}"
        }), 500        


@app.route('/api/prior-cases/<session_id>', methods=['GET'])
def get_prior_cases_summary(session_id):
    """
    Get prior cases summary for a session - with improved error handling
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
        
        # Get prior cases from session data
        prior_cases = data.get("prior_cases", [])
        
        # If prior cases aren't already extracted, get them
        if not prior_cases:
            # Get case number
            case_number = ""
            if "case_data" in data:
                case_number = data["case_data"].get("case_number", "")
            
            # Get the original, raw case data
            raw_case_data = get_full_case(case_number)
            
            if not raw_case_data:
                return jsonify({
                    "status": "error",
                    "message": "Case data not found"
                }), 404
                
            try:
                # Extract prior cases information directly from the raw case data
                prior_cases = extract_prior_cases_summary(raw_case_data)
                
                # Sanitize data to prevent JSON issues
                prior_cases = sanitize_for_json(prior_cases)
                
                # Store prior cases in session data
                data["prior_cases"] = prior_cases
                save_to_json_file(data, data_path)
            except Exception as e:
                logger.error(f"Error extracting prior cases: {str(e)}", exc_info=True)
                # Return simplified data on error
                prior_cases = []
        
        # Generate prompt for LLM
        try:
            prompt = generate_prior_cases_prompt(prior_cases)
        except Exception as e:
            logger.error(f"Error generating prompt: {str(e)}", exc_info=True)
            prompt = "Error generating prompt for prior cases"
        
        # Try to get a generated summary from the recommendation data
        generated_summary = ""
        if "recommendation" in data and "prior_sars" in data["recommendation"]:
            generated_summary = data["recommendation"]["prior_sars"]
        
        # If no generated summary exists, generate one using LLM
        if not generated_summary:
            try:
                # Initialize LLM client
                llm_client = LLMClient()
                
                # Generate the new summary
                generated_summary = llm_client.generate_content(prompt, max_tokens=600, temperature=0.2)
                
                # Update recommendation with generated summary
                if "recommendation" not in data:
                    data["recommendation"] = {}
                
                data["recommendation"]["prior_sars"] = generated_summary
                save_to_json_file(data, data_path)
            except Exception as e:
                logger.error(f"Error generating prior cases summary with LLM: {str(e)}", exc_info=True)
                generated_summary = "Error generating summary. Please try regenerating the section."
        
        # Simplified response data to avoid JSON errors
        simplified_prior_cases = simplify_prior_cases(prior_cases)
        
        # Create the response data
        response_data = {
            "status": "success",
            "priorCases": simplified_prior_cases,
            "prompt": prompt[:1000] if len(prompt) > 1000 else prompt,  # Truncate long prompts
            "generatedSummary": generated_summary
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching prior cases summary: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": f"Error fetching prior cases summary: {str(e)}"
        }), 500
def sanitize_for_json(data):
    """
    Sanitize data to prevent JSON serialization issues
    """
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, (int, float)):
        return data
    elif data is None:
        return None
    else:
        # Convert everything else to string, truncating if too long
        str_val = str(data)
        if len(str_val) > 10000:  # Truncate very long strings
            return str_val[:10000] + "... [truncated]"
        return str_val

def simplify_prior_cases(prior_cases):
    """
    Create a simplified version of prior cases to avoid JSON issues
    """
    simplified = []
    
    for case in prior_cases:
        simple_case = {
            "case_number": str(case.get("case_number", "")),
            "case_step": str(case.get("case_step", "")),
            "alert_ids": [str(aid) for aid in case.get("alert_ids", [])],
            "alert_months": [str(month) for month in case.get("alert_months", [])],
            "alerting_account": str(case.get("alerting_account", "")),
            "scope_of_review": {
                "start": str(case.get("scope_of_review", {}).get("start", "")),
                "end": str(case.get("scope_of_review", {}).get("end", ""))
            },
            "sar_details": {
                "form_number": str(case.get("sar_details", {}).get("form_number", "")),
                "filing_date": str(case.get("sar_details", {}).get("filing_date", "")),
                "amount_reported": float(case.get("sar_details", {}).get("amount_reported", 0) or 0)
            },
            "general_comments": str(case.get("general_comments", ""))[:1000]  # Truncate long comments
        }
        simplified.append(simple_case)
    
    return simplified

if __name__ == '__main__':
    # Check which variables exist in config for host and port
    host = getattr(config, 'API_HOST', getattr(config, 'HOST', '0.0.0.0'))
    port = getattr(config, 'API_PORT', getattr(config, 'PORT', 8081))
    debug = getattr(config, 'API_DEBUG', getattr(config, 'DEBUG', False))
    
    app.run(debug=debug, host=host, port=port)