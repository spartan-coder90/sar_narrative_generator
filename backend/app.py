import os
import uuid
import sys
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import tempfile
from datetime import datetime
import logging
from werkzeug.utils import secure_filename

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
            "excelFilename": os.path.basename(excel_path)
        }
        
        # Save a copy of the processed data for later use
        with open(os.path.join(upload_folder, 'data.json'), 'w') as f:
            json.dump({
                "case_data": case_data,
                "excel_data": excel_data,
                "combined_data": combined_data,
                "narrative": narrative,
                "sections": sections
            }, f, default=str)  # Added default=str to handle datetime serialization
        
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
        with open(data_path, 'r') as f:
            data = json.load(f)
        
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
    if not section_id in ["introduction", "prior_cases", "account_info", "activity_summary", "conclusion"]:
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
        with open(data_path, 'r') as f:
            data = json.load(f)
        
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
    if not section_id in ["introduction", "prior_cases", "account_info", "activity_summary", "conclusion"]:
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
        with open(data_path, 'r') as f:
            data = json.load(f)
        
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
        else:
            return jsonify({
                "status": "error",
                "message": "Invalid section ID"
            }), 400
        
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
        with open(data_path, 'r') as f:
            data = json.load(f)
        
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


if __name__ == '__main__':
    # Check which variables exist in config for host and port
    host = getattr(config, 'API_HOST', getattr(config, 'HOST', '0.0.0.0'))
    port = getattr(config, 'API_PORT', getattr(config, 'PORT', 8080))
    debug = getattr(config, 'API_DEBUG', getattr(config, 'DEBUG', False))
    
    # Add missing import
    import re
    
    app.run(debug=debug, host=host, port=port)