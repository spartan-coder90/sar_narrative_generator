import os
import uuid
import sys
import re  # Added import at top of file
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
from backend.processors.excel_processor import ExcelProcessor
from backend.processors.case_processor import CaseProcessor
from backend.processors.data_validator import DataValidator
from backend.generators.narrative_generator import NarrativeGenerator
from backend.utils.json_utils import save_to_json_file, load_from_json_file


# Set up logging
logger = get_logger(__name__)

#constants 
VALID_SECTION_IDS = [
    "introduction", 
    "prior_cases", 
    "account_info", 
    "activity_summary", 
    "conclusion", 
    "subject_info", 
    "transaction_samples"
]

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


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "version": "1.0.0"
    }), 200

@app.route('/api/generate', methods=['POST'])
def generate_narrative():
    """
    Process uploaded files and generate SAR narrative
    """
    # Check if files were uploaded
    if 'caseFile' not in request.files or 'excelFile' not in request.files:
        return jsonify({
            "status": "error",
            "message": "Both case file and Excel file are required"
        }), 400
    
    case_file = request.files['caseFile']
    excel_file = request.files['excelFile']
    
    if case_file.filename == '' or excel_file.filename == '':
        return jsonify({
            "status": "error",
            "message": "Empty file names"
        }), 400
    
    # Create a unique session folder for this request
    session_id = str(uuid.uuid4())
    upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    os.makedirs(upload_folder, exist_ok=True)
    
    # Save uploaded files
    case_path = os.path.join(upload_folder, secure_filename(case_file.filename))
    excel_path = os.path.join(upload_folder, secure_filename(excel_file.filename))
    
    case_file.save(case_path)
    excel_file.save(excel_path)
    
    try:
        # Process case document
        logger.info(f"Processing case file: {os.path.basename(case_path)}")
        case_processor = CaseProcessor(case_path)
        case_data = case_processor.process()
        
        # Process Excel file
        logger.info(f"Processing Excel file: {os.path.basename(excel_path)}")
        excel_processor = ExcelProcessor(excel_path)
        excel_data = excel_processor.process()
        
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
        
        # Generate narrative
        try:
            narrative_generator = NarrativeGenerator(combined_data)
            narrative = narrative_generator.generate_narrative()
        except Exception as e:
            logger.error(f"Error generating narrative: {str(e)}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"Error in narrative generation: {str(e)}"
            }), 500
        
        # Split narrative into sections
        sections = split_narrative_into_sections(narrative)
        
        # Create response with session ID for future reference
        response = {
            "status": "success",
            "sessionId": session_id,
            "caseNumber": case_data.get("case_number", ""),
            "accountNumber": case_data.get("account_info", {}).get("account_number", ""),
            "dateGenerated": datetime.now().isoformat(),
            "warnings": warnings,
            "sections": sections,
            "caseFilename": os.path.basename(case_path),
            "excelFilename": os.path.basename(excel_path),
            # Add Word Control Macro data if available
            "wordControl": excel_data.get("word_control_macro", {})
        }
        
        # Include case and excel data for complete context
        response["case_data"] = case_data
        response["excel_data"] = excel_data
        response["combined_data"] = combined_data
        
        # Save a copy of the processed data for later use
        save_to_json_file({
            "case_data": case_data,
            "excel_data": excel_data,
            "combined_data": combined_data,
            "narrative": narrative,
            "sections": sections,
            "wordControl": excel_data.get("word_control_macro", {})
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
    Get narrative sections for a session
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
        
        return jsonify({
            "status": "success",
            "sections": data["sections"]
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching sections: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error fetching sections: {str(e)}"
        }), 500


@app.route('/api/sections/<session_id>/<section_id>', methods=['PUT'])
def update_section(session_id, section_id):
    """
    Update a specific section
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
        if section_id in data["sections"]:
            data["sections"][section_id]["content"] = content
            
            # Rebuild full narrative
            narrative = rebuild_narrative(data["sections"])
            data["narrative"] = narrative
            
            # Save updated data
            with open(data_path, 'w') as f:
                json.dump(data, f, default=str)  # Added default=str to handle datetime serialization
            
            return jsonify({
                "status": "success",
                "message": "Section updated successfully"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Section not found"
            }), 404
    
    except Exception as e:
        logger.error(f"Error updating section: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error updating section: {str(e)}"
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
    
    try:
        data = load_from_json_file(data_path)

        
        # Regenerate the specified section
        combined_data = data["combined_data"]
        narrative_generator = NarrativeGenerator(combined_data)
        
        # Generate section based on ID
        section_content = ""
        if section_id == "introduction":
            section_content = narrative_generator.generate_introduction()
        elif section_id == "prior_cases":
            section_content = narrative_generator.generate_prior_cases()
        elif section_id == "account_info":
            section_content = narrative_generator.generate_account_info()
        elif section_id == "activity_summary":
            section_content = narrative_generator.generate_activity_summary()
        elif section_id == "conclusion":
            section_content = narrative_generator.generate_conclusion()
        elif section_id == "subject_info":
            section_content = narrative_generator.generate_subject_info()
        elif section_id == "transaction_samples":
            section_content = narrative_generator.generate_transaction_samples()
        
        # Update section in data
        data["sections"][section_id]["content"] = section_content
        
        # Rebuild full narrative
        narrative = rebuild_narrative(data["sections"])
        data["narrative"] = narrative
        
        # Save updated data
        with open(data_path, 'w') as f:
            json.dump(data, f, default=str)  # Added default=str to handle datetime serialization
        
        return jsonify({
            "status": "success",
            "section": {
                "id": section_id,
                "content": section_content
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error regenerating section: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error regenerating section: {str(e)}"
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
            "activity_summary": {"id": "activity_summary", "title": "Activity Summary", "content": ""},
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
        "activity_summary": {
            "id": "activity_summary",
            "title": "Activity Summary",
            "content": paragraphs[3] if len(paragraphs) > 3 else ""
        },
        "conclusion": {
            "id": "conclusion",
            "title": "Conclusion",
            "content": paragraphs[4] if len(paragraphs) > 4 else ""
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
        sections.get("activity_summary", {}).get("content", ""),
        sections.get("conclusion", {}).get("content", "")
    ]
    
    return "\n\n".join([section for section in ordered_sections if section])

@app.route('/api/cases', methods=['GET'])
def get_available_case_list():
    """Get list of available cases for UI dropdown"""
    try:
        from backend.data.case_repository import get_available_cases
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
    Process selected case and uploaded Excel file to generate SAR narrative
    
    Requires:
    - case_number: Case number to use from static repository
    - excelFile: Transaction Excel file
    
    Returns:
    - narrative: Generated SAR narrative
    - warnings: Any warnings during processing
    - errors: Any errors during processing
    """
    # Check if case_number was provided
    case_number = request.form.get('case_number')
    if not case_number:
        return jsonify({
            "status": "error",
            "message": "Case number is required"
        }), 400
    
    # Check if Excel file was uploaded
    if 'excelFile' not in request.files:
        return jsonify({
            "status": "error",
            "message": "Excel file is required"
        }), 400
    
    excel_file = request.files['excelFile']
    
    # Check if file is empty
    if excel_file.filename == '':
        return jsonify({
            "status": "error",
            "message": "Empty Excel file name"
        }), 400
    
    # Retrieve static case data
    try:
        from backend.data.case_repository import get_case, get_full_case
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
    
    # Save uploaded Excel file
    excel_filename = secure_filename(excel_file.filename)
    excel_path = os.path.join(upload_folder, excel_filename)
    excel_file.save(excel_path)
    
    try:
        # Process Excel file
        logger.info(f"Processing Excel file: {os.path.basename(excel_path)}")
        excel_processor = ExcelProcessor(excel_path)
        excel_data = excel_processor.process()
        
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
        
        # Generate narrative
        try:
            narrative_generator = NarrativeGenerator(combined_data)
            narrative = narrative_generator.generate_narrative()
        except Exception as e:
            logger.error(f"Error generating narrative: {str(e)}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"Error in narrative generation: {str(e)}"
            }), 500
        
        # Split narrative into sections
        sections = split_narrative_into_sections(narrative)
        
        # Create response with session ID for future reference
        response = {
            "status": "success",
            "sessionId": session_id,
            "caseNumber": case_data.get("case_number", ""),
            "accountNumber": case_data.get("account_info", {}).get("account_number", ""),
            "dateGenerated": datetime.now().isoformat(),
            "warnings": warnings,
            "sections": sections,
            "excelFilename": os.path.basename(excel_path),
            "wordControl": excel_data.get("word_control_macro", {}),
            "fullCaseData": case_data.get("full_data", None)
        }
        
        # Include full data for context
        response["case_data"] = case_data
        response["excel_data"] = excel_data
        response["combined_data"] = combined_data
        
        # Save a copy of the processed data for later use
        save_to_json_file({
            "case_data": case_data,
            "excel_data": excel_data,
            "combined_data": combined_data,
            "narrative": narrative,
            "sections": sections,
            "wordControl": excel_data.get("word_control_macro", {})
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

if __name__ == '__main__':
    # Check which variables exist in config for host and port
    host = getattr(config, 'API_HOST', getattr(config, 'HOST', '0.0.0.0'))
    port = getattr(config, 'API_PORT', getattr(config, 'PORT', 8081))
    debug = getattr(config, 'API_DEBUG', getattr(config, 'DEBUG', False))
    
    # Add missing import
    import re
    
    app.run(debug=debug, host=host, port=port)