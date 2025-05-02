#!/usr/bin/env python
"""
Generate SAR Narrative Script

This script processes case documents and transaction data to generate
complete SAR narratives following regulatory guidelines.
"""
import os
import sys
import argparse
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.processors.case_processor import CaseProcessor
from backend.processors.excel_processor import ExcelProcessor
from backend.processors.data_validator import DataValidator
from backend.generators.narrative_generator import NarrativeGenerator
from backend.integrations.llm_client import LLMClient
from backend.utils.logger import get_logger
import backend.config as config

# Import utility functions
try:
    from sar_extraction_utils import (
        extract_case_number, extract_section_text, extract_alert_info,
        extract_subjects, extract_account_info, extract_prior_cases,
        extract_database_searches, extract_narrative_template,
        identify_activity_type, format_currency, format_date
    )
except ImportError:
    print("Warning: Could not import SAR extraction utilities. Using built-in processors.")

logger = get_logger(__name__)

def process_case_document(file_path: str) -> Dict[str, Any]:
    """
    Process case document using the CaseProcessor or extraction utilities
    
    Args:
        file_path: Path to case document file
        
    Returns:
        Dict: Extracted case data
    """
    # Try using the CaseProcessor first
    try:
        processor = CaseProcessor(file_path)
        case_data = processor.process()
        
        if case_data and case_data.get("case_number"):
            logger.info(f"Successfully processed case document with CaseProcessor: {os.path.basename(file_path)}")
            return case_data
    except Exception as e:
        logger.warning(f"Error using CaseProcessor: {str(e)}")
    
    # Fall back to manual extraction with regex patterns
    logger.info("Falling back to manual extraction")
    case_data = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
            
        # Extract case number
        case_data["case_number"] = extract_case_number(text)
        
        # Extract sections of interest
        alerting_details = extract_section_text(text, "alerting_details")
        customer_info = extract_section_text(text, "customer_information")
        account_info_section = extract_section_text(text, "account_information")
        prior_cases_section = extract_section_text(text, "prior_cases")
        database_searches_section = extract_section_text(text, "database_searches")
        
        # Process each section
        case_data["alert_info"] = extract_alert_info(alerting_details)
        case_data["subjects"] = extract_subjects(customer_info)
        case_data["account_info"] = extract_account_info(account_info_section)
        case_data["prior_cases"] = extract_prior_cases(prior_cases_section)
        case_data["database_searches"] = extract_database_searches(database_searches_section)
        
        # Determine review period if not in alert info
        if case_data["alert_info"] and isinstance(case_data["alert_info"], list):
            review_period = case_data["alert_info"][0].get("review_period", {"start": "", "end": ""})
            case_data["review_period"] = review_period
        
        logger.info(f"Successfully extracted data from case document: {os.path.basename(file_path)}")
        return case_data
    except Exception as e:
        logger.error(f"Error extracting data from case document: {str(e)}")
        return {"case_number": "", "alert_info": [], "subjects": [], "account_info": {}, "prior_cases": []}

def process_excel_file(file_path: str) -> Dict[str, Any]:
    """
    Process Excel file using the ExcelProcessor
    
    Args:
        file_path: Path to Excel file
        
    Returns:
        Dict: Extracted Excel data
    """
    try:
        processor = ExcelProcessor(file_path)
        excel_data = processor.process()
        
        logger.info(f"Successfully processed Excel file: {os.path.basename(file_path)}")
        return excel_data
    except Exception as e:
        logger.error(f"Error processing Excel file: {str(e)}")
        return {"activity_summary": {}, "unusual_activity": {"transactions": []}, "transaction_summary": {}}

def process_sar_template(file_path: str) -> Dict[str, str]:
    """
    Process SAR template file
    
    Args:
        file_path: Path to SAR template file
        
    Returns:
        Dict: Extracted template sections
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
            
        template = extract_narrative_template(text)
        
        logger.info(f"Successfully processed SAR template: {os.path.basename(file_path)}")
        return template
    except Exception as e:
        logger.error(f"Error processing SAR template: {str(e)}")
        return {}

def validate_data(case_data: Dict[str, Any], excel_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate extracted data
    
    Args:
        case_data: Extracted case data
        excel_data: Extracted Excel data
        
    Returns:
        Tuple: (is_valid, errors, warnings)
    """
    try:
        validator = DataValidator(case_data, excel_data)
        is_valid, errors, warnings = validator.validate()
        
        logger.info(f"Data validation complete: valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}")
        return is_valid, errors, warnings
    except Exception as e:
        logger.error(f"Error validating data: {str(e)}")
        return False, [f"Error validating data: {str(e)}"], []

def generate_narrative(data: Dict[str, Any], llm_client: Optional[LLMClient] = None) -> str:
    """
    Generate SAR narrative
    
    Args:
        data: Combined and validated data
        llm_client: Optional LLM client for enhanced generation
        
    Returns:
        str: Generated SAR narrative
    """
    try:
        narrative_generator = NarrativeGenerator(data, llm_client)
        narrative = narrative_generator.generate_narrative()
        
        logger.info("Successfully generated SAR narrative")
        return narrative
    except Exception as e:
        logger.error(f"Error generating narrative: {str(e)}")
        
        # Attempt a simplified fallback narrative if generation fails
        try:
            fallback = generate_fallback_narrative(data)
            logger.info("Generated fallback SAR narrative")
            return fallback
        except Exception as fallback_error:
            logger.error(f"Error generating fallback narrative: {str(fallback_error)}")
            return f"Error generating SAR narrative: {str(e)}"

def generate_fallback_narrative(data: Dict[str, Any]) -> str:
    """
    Generate a simplified fallback narrative when primary generation fails
    
    Args:
        data: Combined data
        
    Returns:
        str: Simplified SAR narrative
    """
    # Extract key information
    case_number = data.get("case_number", "Unknown")
    account_info = data.get("account_info", {})
    account_number = account_info.get("account_number", "")
    account_type = account_info.get("account_type", "checking/savings")
    
    # Get subjects
    subjects = data.get("subjects", [])
    subject_names = []
    for subject in subjects:
        subject_names.append(subject.get("name", "unknown subject"))
    
    subject_text = ", ".join(subject_names) if subject_names else "unknown subjects"
    
    # Get activity information
    activity_summary = data.get("activity_summary", {})
    start_date = format_date(activity_summary.get("start_date", ""))
    end_date = format_date(activity_summary.get("end_date", ""))
    
    # Get total amount
    total_amount = activity_summary.get("total_amount", 0)
    if isinstance(total_amount, str):
        try:
            total_amount = float(total_amount.replace("$", "").replace(",", ""))
        except ValueError:
            total_amount = 0
    
    # Determine activity type
    activity_type = "suspicious activity"
    derived_from = "derived from credits and debits"
    
    # Create basic narrative
    introduction = f"U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report {activity_type} totaling {format_currency(total_amount)} {derived_from} by {subject_text} in {account_type} account number {account_number}. The suspicious activity was conducted from {start_date} through {end_date}."
    
    account_section = f"Personal {account_type} account {account_number} was opened on {format_date(account_info.get('open_date', ''))} and remains open."
    
    activity_section = f"The account activity from {start_date} to {end_date} included suspicious transactions totaling {format_currency(total_amount)}."
    
    conclusion = f"In conclusion, USB is reporting {format_currency(total_amount)} in {activity_type} which gave the appearance of suspicious activity and were conducted by {subject_text} in account number {account_number} from {start_date} through {end_date}. USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number {case_number}."
    
    # Combine sections
    narrative = "\n\n".join([introduction, account_section, activity_section, conclusion])
    
    return narrative

def export_narrative(narrative: str, case_number: str, output_dir: str) -> str:
    """
    Export narrative to a file
    
    Args:
        narrative: Generated SAR narrative
        case_number: Case number
        output_dir: Output directory
        
    Returns:
        str: Path to output file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"SAR_Narrative_{case_number}_{timestamp}.txt"
    output_path = os.path.join(output_dir, filename)
    
    # Write narrative to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"SAR Narrative - Case {case_number}\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("====================== SECTION 7: SAR NARRATIVE ======================\n\n")
        f.write(narrative)
        f.write("\n\n===================================================================\n")
        f.write("Generated by SAR Narrative Generator")
    
    logger.info(f"Exported SAR narrative to: {output_path}")
    return output_path

def print_summary(case_data: Dict[str, Any], excel_data: Dict[str, Any], narrative_stats: Dict[str, Any]) -> None:
    """
    Print summary of processed data and generated narrative
    
    Args:
        case_data: Extracted case data
        excel_data: Extracted Excel data
        narrative_stats: Statistics about the generated narrative
    """
    print("\n" + "=" * 80)
    print("SAR NARRATIVE GENERATION SUMMARY")
    print("=" * 80)
    
    print(f"\nCASE INFORMATION:")
    print(f"  Case Number: {case_data.get('case_number', 'Unknown')}")
    print(f"  Subjects: {len(case_data.get('subjects', []))}")
    print(f"  Prior Cases: {len(case_data.get('prior_cases', []))}")
    
    print(f"\nACCOUNT INFORMATION:")
    account_info = case_data.get("account_info", {})
    print(f"  Account Number: {account_info.get('account_number', 'Unknown')}")
    print(f"  Account Type: {account_info.get('account_type', 'Unknown')}")
    print(f"  Status: {account_info.get('status', 'Unknown')}")
    
    print(f"\nACTIVITY INFORMATION:")
    activity_summary = excel_data.get("activity_summary", {})
    print(f"  Total Amount: {format_currency(activity_summary.get('total_amount', 0))}")
    print(f"  Date Range: {format_date(activity_summary.get('start_date', ''))} to {format_date(activity_summary.get('end_date', ''))}")
    
    print(f"\nNARRATIVE STATISTICS:")
    print(f"  Total Length: {narrative_stats.get('length', 0)} characters")
    print(f"  Sections: {narrative_stats.get('sections', 0)}")
    print(f"  Output File: {narrative_stats.get('output_file', 'Not exported')}")
    
    print("\n" + "=" * 80)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Generate SAR Narrative')
    parser.add_argument('--case', required=True, help='Path to case document file')
    parser.add_argument('--excel', required=True, help='Path to Excel transaction file')
    parser.add_argument('--template', help='Path to SAR narrative template file')
    parser.add_argument('--output', default='output', help='Output directory')
    parser.add_argument('--use-llm', action='store_true', help='Use LLM for enhanced generation')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Process case document
    print(f"Processing case document: {args.case}")
    case_data = process_case_document(args.case)
    
    # Process Excel file
    print(f"Processing Excel file: {args.excel}")
    excel_data = process_excel_file(args.excel)
    
    # Process template if provided
    template = {}
    if args.template:
        print(f"Processing SAR template: {args.template}")
        template = process_sar_template(args.template)
    
    # Validate data
    print("Validating data...")
    is_valid, errors, warnings = validate_data(case_data, excel_data)
    
    if errors:
        print("\nValidation Errors:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("\nValidation Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    # Proceed only if valid or if there are just warnings
    if not is_valid and errors:
        print("\nCannot generate narrative due to validation errors.")
        return
    
    # Combine data
    combined_data = DataValidator(case_data, excel_data).fill_missing_data()
    
    # Add template information if available
    if template:
        combined_data["template"] = template
    
    # Initialize LLM client if requested
    llm_client = None
    if args.use_llm:
        print("Initializing LLM client for enhanced generation...")
        llm_client = LLMClient()
    
    # Generate narrative
    print("Generating SAR narrative...")
    narrative = generate_narrative(combined_data, llm_client)
    
    # Calculate narrative statistics
    narrative_stats = {
        "length": len(narrative),
        "sections": narrative.count("\n\n") + 1
    }
    
    # Export narrative
    output_file = export_narrative(narrative, case_data.get("case_number", "unknown"), args.output)
    narrative_stats["output_file"] = output_file
    
    # Print summary
    print_summary(case_data, excel_data, narrative_stats)
    
    print(f"\nSAR narrative generated successfully!")
    print(f"Output file: {output_file}")

if __name__ == "__main__":
    main()