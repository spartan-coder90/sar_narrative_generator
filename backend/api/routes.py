}), 500

@api_bp.route('/transaction-sample/<session_id>', methods=['POST'])
def add_transaction_sample(session_id):
    """
    Add a transaction sample to the unusual activity
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    data = request.json
    if not data:
        return jsonify({
            "status": "error",
            "message": "Transaction data is required"
        }), 400
    
    required_fields = ['date', 'amount', 'type', 'description', 'account']
    for field in required_fields:
        if field not in data:
            return jsonify({
                "status": "error",
                "message": f"Missing required field: {field}"
            }), 400
    
    data_path = os.path.join(UPLOAD_DIR, session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        with open(data_path, 'r') as f:
            session_data = json.load(f)
        
        combined_data = session_data["combined_data"]
        
        # Initialize unusual_activity if it doesn't exist
        if "unusual_activity" not in combined_data:
            combined_data["unusual_activity"] = {}
        
        if "transactions" not in combined_data["unusual_activity"]:
            combined_data["unusual_activity"]["transactions"] = []
        
        # Add transaction to unusual activity
        combined_data["unusual_activity"]["transactions"].append({
            "date": data["date"],
            "amount": data["amount"],
            "type": data["type"],
            "description": data["description"],
            "account": data["account"]
        })
        
        # Update session data
        session_data["combined_data"] = combined_data
        
        # Regenerate transaction samples section
        narrative_generator = NarrativeGenerator(combined_data)
        transaction_samples = narrative_generator.generate_transaction_samples()
        
        # Update section
        if "transaction_samples" in session_data["sections"]:
            session_data["sections"]["transaction_samples"]["content"] = transaction_samples
        else:
            session_data["sections"]["transaction_samples"] = {
                "id": "transaction_samples",
                "title": "Sample Transactions",
                "content": transaction_samples
            }
        
        # Rebuild narrative
        narrative = rebuild_narrative(session_data["sections"])
        session_data["narrative"] = narrative
        
        with open(data_path, 'w') as f:
            json.dump(session_data, f, default=str)
        
        return jsonify({
            "status": "success",
            "message": "Transaction sample added successfully",
            "updated_section": {
                "id": "transaction_samples",
                "content": transaction_samples
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error adding transaction sample: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error adding transaction sample: {str(e)}"
        }), 500

@api_bp.route('/transaction-samples/<session_id>', methods=['GET'])
def get_transaction_samples(session_id):
    """
    Get transaction samples for the session
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    data_path = os.path.join(UPLOAD_DIR, session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        with open(data_path, 'r') as f:
            session_data = json.load(f)
        
        combined_data = session_data["combined_data"]
        
        # Get transactions
        unusual_activity = combined_data.get("unusual_activity", {})
        transactions = unusual_activity.get("transactions", [])
        
        return jsonify({
            "status": "success",
            "transactions": transactions
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching transaction samples: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error fetching transaction samples: {str(e)}"
        }), 500

@api_bp.route('/export/<session_id>', methods=['GET'])
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
    
    data_path = os.path.join(UPLOAD_DIR, session_id, 'data.json')
    
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
        import tempfile
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

@api_bp.route('/export-recommendation/<session_id>', methods=['GET'])
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
    
    data_path = os.path.join(UPLOAD_DIR, session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        with open(data_path, 'r') as f:
            data = json.load(f)
        case_data = data["case_data"]
        
        # Check if recommendation exists
        if "recommendation" not in data:
            return jsonify({
                "status": "error",
                "message": "Recommendation not found"
            }), 404
        
        recommendation = data["recommendation"]
        
        # Build recommendation text
        recommendation_text = "\n\n".join([
            recommendation.get("alerting_activity", ""),
            recommendation.get("prior_sars", ""),
            recommendation.get("scope_of_review", ""),
            recommendation.get("summary_of_investigation", ""),
            recommendation.get("conclusion", "")
        ])
        
        # Create a temporary file for export
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            case_number = case_data.get("case_number", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Write header
            tmp.write(f"SAR Recommendation - Case {case_number}\n".encode('utf-8'))
            tmp.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n".encode('utf-8'))
            
            # Write recommendation
            tmp.write("====================== SAR RECOMMENDATION ======================\n\n".encode('utf-8'))
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

@api_bp.route('/export-referral/<session_id>/<referral_type>', methods=['GET'])
def export_referral(session_id, referral_type):
    """
    Export a referral document
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    # Check if referral type is valid
    if referral_type not in REFERRAL_TYPES:
        return jsonify({
            "status": "error",
            "message": f"Invalid referral type: {referral_type}"
        }), 400
    
    data_path = os.path.join(UPLOAD_DIR, session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        with open(data_path, 'r') as f:
            data = json.load(f)
        case_data = data["case_data"]
        
        # Get referral documents
        referral_documents = data.get("referral_documents", [])
        
        # Find the specific referral document
        referral_doc = None
        for doc in referral_documents:
            if doc.get("type") == referral_type:
                referral_doc = doc
                break
        
        if not referral_doc:
            # If no saved document, generate one from the template
            referrals = data.get("referrals", {})
            if referral_type in referrals:
                referral_content = referrals[referral_type]
            else:
                # Use template with placeholders
                referral_content = REFERRAL_TYPES[referral_type]["template"]
        else:
            referral_content = referral_doc.get("content", "")
        
        # Create a temporary file for export
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            case_number = case_data.get("case_number", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            referral_name = REFERRAL_TYPES[referral_type]["name"]
            
            # Write header
            tmp.write(f"{referral_name} - Case {case_number}\n".encode('utf-8'))
            tmp.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n".encode('utf-8'))
            
            # Write referral content
            tmp.write(f"====================== {referral_name.upper()} ======================\n\n".encode('utf-8'))
            tmp.write(referral_content.encode('utf-8'))
            
            # Add footer
            tmp.write("\n\n===================================================================\n".encode('utf-8'))
            tmp.write("Generated by SAR Narrative Generator".encode('utf-8'))
            
            tmp_path = tmp.name
        
        # Generate filename for download
        filename = f"{referral_type}_{case_number}_{timestamp}.txt"
        
        # Send file for download
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    
    except Exception as e:
        logger.error(f"Error exporting referral: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error exporting referral: {str(e)}"
        }), 500

@api_bp.route('/export-closure/<session_id>', methods=['GET'])
def export_closure(session_id):
    """
    Export a closure document
    """
    # Validate session ID to prevent directory traversal
    if not re.match(r'^[0-9a-f\-]+$', session_id):
        return jsonify({
            "status": "error",
            "message": "Invalid session ID format"
        }), 400
    
    data_path = os.path.join(UPLOAD_DIR, session_id, 'data.json')
    
    if not os.path.exists(data_path):
        return jsonify({
            "status": "error",
            "message": "Session not found"
        }), 404
    
    try:
        with open(data_path, 'r') as f:
            data = json.load(f)
        case_data = data["case_data"]
        
        # Get closure documents
        closure_documents = data.get("closure_documents", [])
        
        if not closure_documents:
            return jsonify({
                "status": "error",
                "message": "No closure documents found"
            }), 404
        
        # Use the most recent closure document
        closure_doc = closure_documents[-1]
        closure_reason = closure_doc.get("reason", "")
        closure_content = closure_doc.get("content", "")
        
        if not closure_reason in CLOSURE_REASONS:
            closure_reason_text = "Closure Document"
        else:
            closure_reason_text = CLOSURE_REASONS[closure_reason]["name"]
        
        # Create a temporary file for export
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            case_number = case_data.get("case_number", "unknown")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Write header
            tmp.write(f"Closure Document - {closure_reason_text} - Case {case_number}\n".encode('utf-8'))
            tmp.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n".encode('utf-8'))
            
            # Write closure content
            tmp.write("====================== CLOSURE DOCUMENTATION ======================\n\n".encode('utf-8'))
            tmp.write(f"Closure Reason: {closure_reason_text}\n\n".encode('utf-8'))
            tmp.write(closure_content.encode('utf-8'))
            
            # Add footer
            tmp.write("\n\n===================================================================\n".encode('utf-8'))
            tmp.write("Generated by SAR Narrative Generator".encode('utf-8'))
            
            tmp_path = tmp.name
        
        # Generate filename for download
        filename = f"Closure_{case_number}_{timestamp}.txt"
        
        # Send file for download
        return send_file(
            tmp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
    
    except Exception as e:
        logger.error(f"Error exporting closure document: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error exporting closure document: {str(e)}"
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