"""
API routes for SAR Narrative Generator
"""
from flask import Blueprint, request, jsonify, current_app
import os
from werkzeug.utils import secure_filename
import uuid
import json
from typing import Dict, List, Any

from ..processors.excel_processor import ExcelProcessor
from ..processors.case_processor import CaseProcessor
from ..processors.data_validator import DataValidator
from ..generators.narrative_generator import NarrativeGenerator
from ..integrations.llm_client import LLMClient
from ..config import UPLOAD_DIR
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Create Blueprint
api_bp = Blueprint('api', __name__)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "version": "1.0.0"
    }), 200

@api_bp.route('/generate', methods=['POST'])
def generate_narrative():
    """
    Generate SAR narrative from Excel and case document
    
    Requires:
    - case_file: Case document file (JSON or text)
    - excel_file: Transaction Excel file
    - use_llm: (optional) Whether to use LLM for enhanced generation
    
    Returns:
    - narrative: Generated SAR narrative
    - warnings: Any warnings during processing
    - errors: Any errors during processing
    """
    # Check if files were uploaded
    if 'caseFile' not in request.files or 'excelFile' not in request.files:
        return jsonify({
            "status": "error",
            "message": "Both caseFile and excelFile are required"
        }), 400
    
    case_file = request.files['caseFile']
    excel_file = request.files['excelFile']
    
    # Check if files are empty
    if case_file.filename == '' or excel_file.filename == '':
        return jsonify({
            "status": "error",
            "message": "Empty file names"
        }), 400
    
    # Create a unique directory for this upload
    upload_id = str(uuid.uuid4())
    upload_dir = os.path.join(UPLOAD_DIR, upload_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save uploaded files
    case_filename = secure_filename(case_file.filename)
    excel_filename = secure_filename(excel_file.filename)
    
    case_filepath = os.path.join(upload_dir, case_filename)
    excel_filepath = os.path.join(upload_dir, excel_filename)
    
    case_file.save(case_filepath)
    excel_file.save(excel_filepath)
    
    logger.info(f"Files saved to {upload_dir}")
    
    try:
        # Process case document
        case_processor = CaseProcessor(case_filepath)
        case_data = case_processor.process()
        
        # Process Excel file
        excel_processor = ExcelProcessor(excel_filepath)
        excel_data = excel_processor.process()
        
        # Validate data
        validator = DataValidator(case_data, excel_data)
        is_valid, errors, warnings = validator.validate()
        
        if not is_valid and errors:
            return jsonify({
                "status": "error",
                "message": "Validation failed",
                "errors": errors
            }), 400
        
        # Fill missing data
        combined_data = validator.fill_missing_data()
        
        # Generate narrative
        use_llm = request.form.get('use_llm', 'false').lower() == 'true'
        
        if use_llm:
            # Initialize LLM client
            llm_client = LLMClient()
            narrative_generator = NarrativeGenerator(combined_data, llm_client)
            narrative = narrative_generator.generate_with_llm()
        else:
            narrative_generator = NarrativeGenerator(combined_data)
            narrative = narrative_generator.generate_narrative()
        
        return jsonify({
            "status": "success",
            "narrative": narrative,
            "warnings": warnings,
            "case_data": case_data,
            "excel_data": excel_data
        }), 200
    
    except Exception as e:
        logger.error(f"Error generating narrative: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error generating narrative: {str(e)}"
        }), 500
    finally:
        # Clean up temporary files
        try:
            import shutil
            shutil.rmtree(upload_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")

@api_bp.route('/templates', methods=['GET'])
def get_templates():
    """Get available narrative templates"""
    from ..config import TEMPLATES, ACTIVITY_TYPES
    
    return jsonify({
        "status": "success",
        "templates": TEMPLATES,
        "activity_types": ACTIVITY_TYPES
    }), 200