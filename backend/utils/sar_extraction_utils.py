"""
Utility functions for extracting specific SAR-related information from case documents
"""
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

def extract_case_number(text: str) -> str:
    """
    Extract case number from text using pattern matching
    
    Args:
        text: Text to search
        
    Returns:
        str: Extracted case number or empty string if not found
    """
    # Common case number patterns
    patterns = [
        r"Case\s+Number:?\s*([A-Z0-9-]+)",
        r"Case\s+ID:?\s*([A-Z0-9-]+)",
        r"Case\s+#:?\s*([A-Z0-9-]+)",
        r"Case:?\s*([A-Z0-9-]+)",
        r"CC\d{10}",  # Specific pattern like CC0015823420
        r"AML\d{7}",  # Specific pattern like AML5881633
        r"C\d{8}"     # Specific pattern like C21600043
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1) if '(' in pattern else match.group(0)
    
    return ""

def extract_section_text(text: str, section_name: str) -> str:
    """
    Extract specific section from case document
    
    Args:
        text: Full text of case document
        section_name: Name of section to extract
        
    Returns:
        str: Extracted section text or empty string if not found
    """
    # Common section markers
    section_patterns = {
        "alerting_details": [
            r"(?:Alerting Details|Alert Information)(.*?)(?=\d+\.\s+(?:Prior|Customer|Database))",
            r"\d+\.\s+(?:Alerting Details|Alert Information)(.*?)(?=\d+\.\s+)"
        ],
        "prior_cases": [
            r"(?:Prior Cases|Prior SARs)(.*?)(?=\d+\.\s+(?:Customer|Database))",
            r"\d+\.\s+(?:Prior Cases|Prior SARs)(.*?)(?=\d+\.\s+)"
        ],
        "customer_information": [
            r"(?:Customer Information|Subject Information)(.*?)(?=\d+\.\s+(?:Database|External))",
            r"\d+\.\s+(?:Customer Information|Subject Information)(.*?)(?=\d+\.\s+)"
        ],
        "account_information": [
            r"(?:Account Information)(.*?)(?=\d+\.\s+(?:Recommendations|External))",
            r"\d+\.\s+(?:Account Information)(.*?)(?=\d+\.\s+)"
        ],
        "database_searches": [
            r"(?:Database Searches)(.*?)(?=\d+\.\s+(?:External|Account))",
            r"\d+\.\s+(?:Database Searches)(.*?)(?=\d+\.\s+)"
        ],
        "recommendations": [
            r"(?:Recommendations)(.*?)(?=SAR Narrative|\Z)",
            r"\d+\.\s+(?:Recommendations)(.*?)(?=SAR|\Z)"
        ],
        "sar_narrative": [
            r"(?:SAR Narrative)(.*?)(?=\Z)",
            r"(?:Section 7:?)?(?:\s+)?SAR Narrative(.*?)(?=\Z)"
        ]
    }
    
    if section_name not in section_patterns:
        return ""
    
    for pattern in section_patterns[section_name]:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ""

def extract_alert_info(text: str) -> List[Dict[str, Any]]:
    """
    Extract alert information from case document text
    
    Args:
        text: Text containing alert information
        
    Returns:
        List[Dict]: List of extracted alerts
    """
    alerts = []
    
    # First try to find alert blocks
    alert_blocks = re.findall(
        r"Alert\s+ID:?\s*([A-Z0-9_-]+)(.*?)(?=Alert\s+ID:|\Z)", 
        text, 
        re.DOTALL | re.IGNORECASE
    )
    
    if not alert_blocks:
        # Try alternate format
        alt_blocks = re.findall(
            r"Alert\s+(?:ID|Identifier):\s*([^\n]+)(?:\n|.)*?(?=Alert\s+(?:ID|Identifier):|Scope of Review|\Z)",
            text,
            re.DOTALL | re.IGNORECASE
        )
        
        if alt_blocks:
            for block in alt_blocks:
                alert_id = block.strip()
                
                # Look for alert month
                month_match = re.search(r"Alert\s+Month:?\s*(\d{6})", text, re.IGNORECASE)
                alert_month = month_match.group(1) if month_match else ""
                
                # Look for review period
                review_match = re.search(
                    r"Review\s+Period:?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})",
                    text,
                    re.IGNORECASE
                )
                
                start_date = ""
                end_date = ""
                if review_match:
                    start_date = review_match.group(1)
                    end_date = review_match.group(2)
                
                # Look for description
                desc_match = re.search(r"Description:?\s*(.+?)(?=\n\n|\Z)", text, re.DOTALL | re.IGNORECASE)
                description = desc_match.group(1).strip() if desc_match else ""
                
                alerts.append({
                    "alert_id": alert_id,
                    "alert_month": alert_month,
                    "description": description,
                    "review_period": {
                        "start": start_date,
                        "end": end_date
                    }
                })
    else:
        for alert_id, block in alert_blocks:
            # Extract alert month
            month_match = re.search(r"Alert\s+Month:?\s*(\d{6})", block, re.IGNORECASE)
            alert_month = month_match.group(1) if month_match else ""
            
            # Extract description
            desc_match = re.search(r"Description:?\s*(.+?)(?=\n\n|\Z)", block, re.DOTALL | re.IGNORECASE)
            description = desc_match.group(1).strip() if desc_match else ""
            
            # Extract review period
            review_match = re.search(
                r"Review\s+Period:?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})",
                block,
                re.IGNORECASE
            )
            
            start_date = ""
            end_date = ""
            if review_match:
                start_date = review_match.group(1)
                end_date = review_match.group(2)
            
            alerts.append({
                "alert_id": alert_id,
                "alert_month": alert_month,
                "description": description,
                "review_period": {
                    "start": start_date,
                    "end": end_date
                }
            })
    
    return alerts

def extract_subjects(text: str) -> List[Dict[str, Any]]:
    """
    Extract subject information from case document text
    
    Args:
        text: Text containing subject information
        
    Returns:
        List[Dict]: List of extracted subjects
    """
    subjects = []
    
    # First find U.S. Bank Customer Information section
    usb_customer_section = re.search(
        r"U\.S\.\s+Bank\s+Customer\s+Information(.*?)(?=Non-U\.S\.\s+Bank\s+Customer|\d+\.\s+Database|\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    
    if usb_customer_section:
        section_text = usb_customer_section.group(1)
        
        # Find subject blocks - look for names in ALL CAPS
        subject_blocks = re.findall(
            r"([A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+)(?:.*?)(?=(?:[A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+)|Non-U\.S\.\s+Bank|\d+\.\s+Database|\Z)",
            section_text,
            re.DOTALL
        )
        
        for i, name in enumerate(subject_blocks):
            # Get the text block for this subject
            if i < len(subject_blocks) - 1:
                end_pos = section_text.find(subject_blocks[i+1], section_text.find(name))
                block = section_text[section_text.find(name):end_pos]
            else:
                block = section_text[section_text.find(name):]
            
            # Extract basic information
            subject = {
                "name": name.strip(),
                "is_primary": "Primary Party" in block or "Primary" in block,
                "party_key": "",
                "occupation": "",
                "employer": "",
                "nationality": "",
                "address": "",
                "account_relationship": ""
            }
            
            # Extract party key
            party_key_match = re.search(r"Party Key:?\s*([0-9]+)", block)
            if party_key_match:
                subject["party_key"] = party_key_match.group(1)
            
            # Extract occupation
            occupation_match = re.search(r"Occupation Description:?\s*([^\n]+)", block)
            if occupation_match:
                subject["occupation"] = occupation_match.group(1).strip()
            
            # Extract employer
            employer_match = re.search(r"Employer:?\s*([^\n:]+?)(?:\s*:|\n)", block)
            if employer_match:
                subject["employer"] = employer_match.group(1).strip()
            
            # Extract nationality
            nationality_match = re.search(r"Country of Nationality:?\s*([^\n:]+?)(?:\s*:|\n)", block)
            if nationality_match:
                subject["nationality"] = nationality_match.group(1).strip()
            
            # Extract address
            address_match = re.search(r"Address:?\s*([^\n]+(?:\n[^A-Z\n][^\n]*)*)", block)
            if address_match:
                subject["address"] = ' '.join(line.strip() for line in address_match.group(1).strip().split('\n'))
            
            # Try to find account relationship
            relationship_match = re.search(r"\((.*?(?:Owner|Signer|Primary|Co-Owner|Authorized).*?)\)", block)
            if relationship_match:
                subject["account_relationship"] = relationship_match.group(1).strip()
            
            subjects.append(subject)
    
    # If no subjects found, try a more generic approach
    if not subjects:
        # Look for customer name sections directly
        name_blocks = re.findall(r"Customer Name:?\s*([A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+).*?(?=Customer Name:|\Z)", text, re.DOTALL | re.IGNORECASE)
        
        for name_block in name_blocks:
            name = name_block.strip()
            
            # Find context around the name
            name_pos = text.find(name)
            context_start = max(0, name_pos - 200)
            context_end = min(len(text), name_pos + 1000)
            context = text[context_start:context_end]
            
            subject = {
                "name": name,
                "is_primary": "Primary Party" in context or "Primary" in context,
                "party_key": "",
                "occupation": "",
                "employer": "",
                "nationality": "",
                "address": "",
                "account_relationship": ""
            }
            
            # Extract occupation
            occupation_match = re.search(r"Occupation(?:\s+Description)?:?\s*([^\n]+)", context)
            if occupation_match:
                subject["occupation"] = occupation_match.group(1).strip()
            
            # Extract employer
            employer_match = re.search(r"Employer:?\s*([^\n:]+?)(?:\s*:|\n)", context)
            if employer_match:
                subject["employer"] = employer_match.group(1).strip()
            
            # Extract address
            address_match = re.search(r"Address:?\s*([^\n]+(?:\n[^A-Z\n][^\n]*)*)", context)
            if address_match:
                subject["address"] = ' '.join(line.strip() for line in address_match.group(1).strip().split('\n'))
            
            subjects.append(subject)
    
    return subjects

def extract_account_info(text: str) -> Dict[str, Any]:
    """
    Extract account information from case document text
    
    Args:
        text: Text containing account information
        
    Returns:
        Dict: Extracted account information
    """
    account_info = {
        "account_number": "",
        "account_type": "",
        "account_title": "",
        "open_date": "",
        "close_date": "",
        "status": "",
        "related_parties": [],
        "branch": ""
    }
    
    # Look for account number
    account_number_match = re.search(
        r"Account(?:\s+(?:Number|Key|#))?[:\s]*([A-Z0-9]+)",
        text,
        re.IGNORECASE
    )
    if account_number_match:
        account_info["account_number"] = account_number_match.group(1)
    else:
        # Try to find any account number-like pattern
        alt_account_match = re.search(r"(?:ICS|DDA)\d+", text)
        if alt_account_match:
            account_info["account_number"] = alt_account_match.group(0)
    
    # Look for account type
    account_type_match = re.search(r"Account Type[:\s]*([^\n]+)", text, re.IGNORECASE)
    if account_type_match:
        account_info["account_type"] = account_type_match.group(1).strip()
    
    # Look for account title
    account_title_match = re.search(r"Account Title[:\s]*([^\n]+)", text, re.IGNORECASE)
    if account_title_match:
        account_info["account_title"] = account_title_match.group(1).strip()
    
    # Look for open date
    open_date_match = re.search(r"(?:Open|Opening) Date[:\s&]*([^\n:,]+)", text, re.IGNORECASE)
    if open_date_match:
        account_info["open_date"] = open_date_match.group(1).strip()
    
    # Look for close date
    close_date_match = re.search(r"(?:Close|Closing) Date[:\s]*([^\n:,]+)", text, re.IGNORECASE)
    if close_date_match:
        account_info["close_date"] = close_date_match.group(1).strip()
    
    # Look for status
    status_match = re.search(r"Status(?:\s+Description)?[:\s]*([^\n]+)", text, re.IGNORECASE)
    if status_match:
        account_info["status"] = status_match.group(1).strip()
    
    # Look for related parties
    related_parties_match = re.search(
        r"Related parties[^\n]*:[^\n]*\n?([^\n]+(?:\([^)]+\)[,\s]*)+)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if related_parties_match:
        parties_text = related_parties_match.group(1)
        party_matches = re.findall(r"([^(,]+)\s*\(([^)]+)\)", parties_text)
        
        account_info["related_parties"] = [
            {"name": name.strip(), "role": role.strip()}
            for name, role in party_matches
        ]
    
    # Look for branch
    branch_match = re.search(r"(?:Branch|Account Holding Branch)[:\s]*([^\n]+)", text, re.IGNORECASE)
    if branch_match:
        account_info["branch"] = branch_match.group(1).strip()
    
    return account_info

def extract_prior_cases(text: str) -> List[Dict[str, Any]]:
    """
    Extract prior cases information from case document text
    
    Args:
        text: Text containing prior cases information
        
    Returns:
        List[Dict]: List of extracted prior cases
    """
    prior_cases = []
    
    # Check if there are no prior cases
    if re.search(r"No prior case[s]? or SAR information found", text, re.IGNORECASE):
        return prior_cases
    
    # Find prior cases by case number
    case_blocks = re.findall(
        r"Case Number:?\s*([A-Z0-9]+)(.*?)(?=Case Number:|\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    
    if not case_blocks:
        # Try alternative pattern
        alt_case_matches = re.findall(r"Case Number:?\s*([A-Z0-9]+)", text, re.IGNORECASE)
        if alt_case_matches:
            for case_number in alt_case_matches:
                prior_cases.append({
                    "case_number": case_number,
                    "alert_id": [],
                    "alert_month": [],
                    "review_period": {
                        "start": "",
                        "end": ""
                    },
                    "sar_form_number": "",
                    "filing_date": "",
                    "summary": ""
                })
    else:
        for case_number, block in case_blocks:
            prior_case = {
                "case_number": case_number.strip(),
                "alert_id": [],
                "alert_month": [],
                "review_period": {
                    "start": "",
                    "end": ""
                },
                "sar_form_number": "",
                "filing_date": "",
                "summary": ""
            }
            
            # Extract alert IDs
            alert_ids = re.findall(r"Alert ID:?\s*([A-Z0-9\-_]+)", block, re.IGNORECASE)
            prior_case["alert_id"] = alert_ids
            
            # Extract alert months
            alert_months = re.findall(r"Alert Month:?\s*(\d{6})", block, re.IGNORECASE)
            prior_case["alert_month"] = alert_months
            
            # Extract review period
            review_period_match = re.search(
                r"(?:Scope of Review|Review Period):?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})",
                block,
                re.IGNORECASE
            )
            if review_period_match:
                prior_case["review_period"]["start"] = review_period_match.group(1)
                prior_case["review_period"]["end"] = review_period_match.group(2)
            
            # Extract SAR form number
            sar_form_match = re.search(r"SAR Form Number:?\s*(\d+)", block, re.IGNORECASE)
            if sar_form_match:
                prior_case["sar_form_number"] = sar_form_match.group(1)
            
            # Extract filing date
            filing_date_match = re.search(r"Filing date:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", block, re.IGNORECASE)
            if filing_date_match:
                prior_case["filing_date"] = filing_date_match.group(1)
            
            # Extract summary
            summary_match = re.search(
                r"(?:Summary|SAR summary).*?:?\s*([^\n]+(?:\n[^A-Z\n][^\n]*)*)",
                block,
                re.DOTALL | re.IGNORECASE
            )
            if summary_match:
                prior_case["summary"] = ' '.join(line.strip() for line in summary_match.group(1).strip().split('\n') if line.strip())
            
            prior_cases.append(prior_case)
    
    return prior_cases

def extract_database_searches(text: str) -> Dict[str, Any]:
    """
    Extract database searches information from case document text
    
    Args:
        text: Text containing database searches information
        
    Returns:
        Dict: Extracted database searches information
    """
    database_searches = {
        "kyc": {
            "results": ""
        },
        "adverse_media": {
            "results": ""
        },
        "risk_ratings": []
    }
    
    # Extract KYC results
    kyc_section_match = re.search(
        r"KYC Database[:\s]*(.*?)(?=Risk Ratings|Adverse Media|\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if kyc_section_match:
        database_searches["kyc"]["results"] = kyc_section_match.group(1).strip()
    
    # Extract adverse media results
    adverse_section_match = re.search(
        r"Adverse Media.*?(.*?)(?=\d+\.\s+External|Active Subjects|External Databases|\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if adverse_section_match:
        adverse_section = adverse_section_match.group(1)
        
        # Look for specific results
        adverse_results_match = re.search(r"No adverse media found", adverse_section, re.IGNORECASE)
        if adverse_results_match:
            database_searches["adverse_media"]["results"] = adverse_results_match.group(0)
        else:
            database_searches["adverse_media"]["results"] = adverse_section.strip()
    
    # Extract risk ratings
    risk_ratings_section_match = re.search(
        r"Risk Ratings(.*?)(?=Adverse Media|\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    if risk_ratings_section_match:
        risk_ratings_section = risk_ratings_section_match.group(1)
        
        # Try to extract risk ratings from table-like structure
        risk_rating_rows = re.findall(
            r"([A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+)\s+([0-9]+)\s+([A-Z]+)\s+([^\n]+)",
            risk_ratings_section
        )
        
        for name, party_key, sor, rating in risk_rating_rows:
            database_searches["risk_ratings"].append({
                "name": name.strip(),
                "party_key": party_key.strip(),
                "sor": sor.strip(),
                "rating": rating.strip()
            })
    
    return database_searches

def extract_narrative_template(text: str) -> Dict[str, str]:
    """
    Extract narrative template from SAR Narrative Template document
    
    Args:
        text: Text of SAR Narrative Template document
        
    Returns:
        Dict: Extracted narrative template sections
    """
    template = {
        "introduction": "",
        "prior_cases": "",
        "account_info": "",
        "subject_info": "",
        "activity_summary": "",
        "transaction_samples": "",
        "conclusion": ""
    }
    
    # Look for SAR Narrative section
    sar_narrative_match = re.search(
        r"SAR\s+Narrative(.*?)(?=\Z)",
        text,
        re.DOTALL | re.IGNORECASE
    )
    
    if sar_narrative_match:
        sar_text = sar_narrative_match.group(1)
        
        # Extract introduction template
        intro_match = re.search(
            r"U\.S\.\s+Bank.*?filing this.*?to report(.*?)(?=\*\*Add details|\Z)",
            sar_text,
            re.DOTALL | re.IGNORECASE
        )
        if intro_match:
            template["introduction"] = intro_match.group(0).strip()
        
        # Extract subject/account info template
        subject_match = re.search(
            r"\*\*Add details around Subject/Account Information:\*\*(.*?)(?=\*\*Add details around Suspicious Activity|\Z)",
            sar_text,
            re.DOTALL | re.IGNORECASE
        )
        if subject_match:
            template["subject_info"] = subject_match.group(1).strip()
        
        # Extract suspicious activity template
        activity_match = re.search(
            r"\*\*Add details around Suspicious Activity:\*\*(.*?)(?=\*\*A sample|\Z)",
            sar_text,
            re.DOTALL | re.IGNORECASE
        )
        if activity_match:
            template["activity_summary"] = activity_match.group(1).strip()
        
        # Extract transaction samples template
        samples_match = re.search(
            r"\*\*A sample of the suspicious transactions:\*\*(.*?)(?=In conclusion|\Z)",
            sar_text,
            re.DOTALL | re.IGNORECASE
        )
        if samples_match:
            template["transaction_samples"] = samples_match.group(1).strip()
        
        # Extract conclusion template
        conclusion_match = re.search(
            r"In conclusion,.*?(?=\Z)",
            sar_text,
            re.DOTALL | re.IGNORECASE
        )
        if conclusion_match:
            template["conclusion"] = conclusion_match.group(0).strip()
    
    return template

def extract_keywords_from_text(text: str, keyword_list: List[str]) -> List[str]:
    """
    Extract keywords from text based on provided list
    
    Args:
        text: Text to search for keywords
        keyword_list: List of keywords to look for
        
    Returns:
        List[str]: List of found keywords
    """
    found_keywords = []
    text_lower = text.lower()
    
    for keyword in keyword_list:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    
    return found_keywords

def identify_activity_type(text: str) -> Tuple[str, str]:
    """
    Identify the type of suspicious activity from text
    
    Args:
        text: Text to analyze
        
    Returns:
        Tuple[str, str]: (activity_type, derived_from)
    """
    # Define indicators for each activity type
    activity_indicators = {
        "structuring": ["structure", "ctr", "cash deposit", "multiple deposit", "9000", "below 10000"],
        "money laundering": ["launder", "shell", "funnel", "layering", "money laundering"],
        "wire fraud": ["wire fraud", "wire transfer fraud", "unauthorized wire"],
        "identity theft": ["identity theft", "stolen identity", "id theft"],
        "check fraud": ["check fraud", "check kiting", "counterfeit check"],
        "account takeover": ["account takeover", "unauthorized access"],
        "cash": ["cash", "currency", "monetary instrument"],
        "ACH activity": ["ach", "automated clearing house"],
        "suspicious activity": []  # Default if nothing else matches
    }
    
    derivation_indicators = {
        "credits": ["credit", "deposit", "incoming"],
        "debits": ["debit", "withdrawal", "outgoing"],
        "credits and debits": ["credits and debits", "deposits and withdrawals"]
    }
    
    # Check for activity type indicators
    text_lower = text.lower()
    best_match = None
    best_count = 0
    
    for activity, indicators in activity_indicators.items():
        count = sum(1 for indicator in indicators if indicator in text_lower)
        if count > best_count:
            best_count = count
            best_match = activity
    
    activity_type = best_match or "suspicious activity"
    
    # Check for derived from indicators
    best_match = None
    best_count = 0
    
    for derived, indicators in derivation_indicators.items():
        count = sum(1 for indicator in indicators if indicator in text_lower)
        if count > best_count:
            best_count = count
            best_match = derived
    
    derived_from = best_match or "credits and debits"
    
    return activity_type, derived_from

def format_currency(amount):
    """
    Format amount as currency
    
    Args:
        amount: Amount to format
        
    Returns:
        str: Formatted currency amount
    """
    if not amount:
        return "$0.00"
    
    # Convert string to float if needed
    if isinstance(amount, str):
        # Remove currency symbols and commas
        amount = amount.replace(', ', '').replace(',', '')
        try:
            amount = float(amount)
        except ValueError:
            return "$0.00"
    
    # Format with commas and 2 decimal places
    return "${:,.2f}".format(amount)

def format_date(date_str):
    """
    Format date as MM/DD/YYYY
    
    Args:
        date_str: Date string to format
        
    Returns:
        str: Formatted date string
    """
    if not date_str:
        return ""
    
    # Check if already in correct format
    date_match = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', str(date_str))
    if date_match:
        month, day, year = date_match.groups()
        
        # Ensure 4-digit year
        if len(year) == 2:
            year = f"20{year}" if int(year) < 50 else f"19{year}"
        
        # Format with leading zeros
        return f"{int(month):02d}/{int(day):02d}/{year}"
    
    # Try to parse string as date
    try:
        for fmt in ['%Y-%m-%d', '%m-%d-%Y', '%d-%m-%Y', '%Y/%m/%d']:
            try:
                date_obj = datetime.strptime(date_str, fmt)
                return date_obj.strftime("%m/%d/%Y")
            except ValueError:
                continue
    except:
        pass
    return date_str