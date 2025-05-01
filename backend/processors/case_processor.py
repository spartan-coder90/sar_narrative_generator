"""
Case document processor that uses LLM prompting to extract data from case documents
"""
import re
import json
import os
from typing import Dict, List, Any, Optional
import requests
from datetime import datetime

from backend.utils.logger import get_logger
from backend.integrations.llm_client import LLMClient

logger = get_logger(__name__)

class CaseProcessor:
    """
    Processes case documents to extract relevant data for SAR narratives
    Uses LLM-based extraction for better flexibility and accuracy
    """
    
    def __init__(self, file_path: str):
        """
        Initialize with path to case document file
        
        Args:
            file_path: Path to case document file (any supported format)
        """
        self.file_path = file_path
        self.file_ext = os.path.splitext(self.file_path)[1].lower()
        self.raw_data = None
        self.text_content = ""
        self.llm_client = LLMClient()
        
        # Default structure for extracted data (keeping original structure)
        self.data = {
            "case_number": "",
            "alert_info": {
                "alert_id": "",
                "alert_month": "",
                "description": "",
                "review_period": {
                    "start": "",
                    "end": ""
                }
            },
            "subjects": [],
            "account_info": {
                "account_number": "",
                "account_type": "",
                "account_title": "",
                "open_date": "",
                "close_date": "",
                "status": "",
                "related_parties": [],
                "branch": ""
            },
            "prior_cases": [],
            "database_searches": {
                "kyc": {"results": ""},
                "adverse_media": {"results": ""}
            }
        }
    
    def load_document(self) -> bool:
        """
        Load the case document
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First try as JSON
            if self.file_ext == '.json':
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.raw_data = json.load(f)
                    self.text_content = json.dumps(self.raw_data, indent=2)
            else:
                # For other formats, just read as text
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.text_content = f.read()
                    self.raw_data = self.text_content
                
                # If this fails, try binary mode
                if not self.text_content:
                    with open(self.file_path, 'rb') as f:
                        binary_content = f.read()
                        self.text_content = binary_content.decode('utf-8', errors='ignore')
                        self.raw_data = self.text_content
            
            logger.info(f"Successfully loaded case document: {os.path.basename(self.file_path)}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading case document: {str(e)}")
            return False
    
    def extract_case_number(self) -> str:
        """
        Extract case number from document
        
        Returns:
            str: Case number
        """
        # First try direct extraction if JSON
        if isinstance(self.raw_data, dict):
            for key in ['caseNumber', 'case_number', 'case_id', 'id']:
                if key in self.raw_data:
                    case_number = self.raw_data[key]
                    if case_number:
                        return str(case_number)
        
        # Use LLM-based extraction
        prompt = """
        Extract the case number from the following document. 
        The case number is typically a unique identifier that starts with letters like CC, C, or AML followed by numbers.
        Return only the case number without any explanation or additional text.
        
        Document content:
        {text_content}
        """
        
        # Use a substring of the document to avoid token limits
        text_preview = self.text_content[:5000]  # First 5000 chars should be enough for case number
        
        try:
            case_number = self.llm_client.generate_narrative(
                prompt.format(text_content=text_preview),
                {}
            ).strip()
            
            # Simple validation - remove any extraneous text
            case_number = re.sub(r'^.*?([A-Z]{1,4}\d+).*?$', r'\1', case_number, flags=re.DOTALL)
            
            return case_number
            
        except Exception as e:
            logger.error(f"Error extracting case number: {str(e)}")
            
            # Fallback to basic pattern matching
            patterns = [
                r"Case(?:\s+)?(?:Number|ID|#):?\s*([A-Z0-9\-]+)",
                r"(?:^|\n|\r)(?:CC|C|AML)(\d+)",
                r"(?:^|\n|\r)([A-Z]{1,4}\d{5,})"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text_preview)
                if match:
                    return match.group(1).strip()
            
            return ""
    
    def extract_alert_info(self) -> Dict[str, Any]:
        """
        Extract alert information from document
        
        Returns:
            Dict: Alert information
        """
        # First try direct extraction if JSON
        if isinstance(self.raw_data, dict):
            for key in ['alertInfo', 'alert_info', 'alerting_details', 'alert']:
                if key in self.raw_data and isinstance(self.raw_data[key], dict):
                    alert_data = self.raw_data[key]
                    return self._process_alert_json(alert_data)
        
        # Use LLM-based extraction
        prompt = """
        Extract the following alert information from the document:
        1. Alert ID - typically a unique identifier for the alert
        2. Alert month - typically in format YYYYMM (like 202302)
        3. Alert description - a description of why the alert was triggered
        4. Review period start date - the beginning of the period under review (MM/DD/YYYY format)
        5. Review period end date - the end of the period under review (MM/DD/YYYY format)
        
        Format your response as JSON with the following structure:
        {
            "alert_id": "extracted alert ID",
            "alert_month": "extracted alert month",
            "description": "extracted description",
            "review_period": {
                "start": "start date in MM/DD/YYYY format",
                "end": "end date in MM/DD/YYYY format"
            }
        }
        
        Document content:
        {text_content}
        """
        
        # Use a substring focusing on the beginning of the document where alert info typically appears
        text_preview = self.text_content[:10000]
        
        try:
            alert_info_json = self.llm_client.generate_narrative(
                prompt.format(text_content=text_preview),
                {}
            ).strip()
            
            # Parse the JSON response
            try:
                alert_info = json.loads(alert_info_json)
                return alert_info
            except json.JSONDecodeError:
                # If not valid JSON, try to extract structured information
                return self._extract_alert_info_fallback(alert_info_json)
            
        except Exception as e:
            logger.error(f"Error extracting alert info: {str(e)}")
            
            # Return default structure
            return {
                "alert_id": "",
                "alert_month": "",
                "description": "",
                "review_period": {
                    "start": "",
                    "end": ""
                }
            }
    
    def _process_alert_json(self, alert_data: Dict) -> Dict[str, Any]:
        """Process alert data from JSON"""
        alert_info = {
            "alert_id": "",
            "alert_month": "",
            "description": "",
            "review_period": {
                "start": "",
                "end": ""
            }
        }
        
        # Map field names
        field_mappings = {
            'alert_id': ['alertId', 'alert_id', 'id', 'alert_number'],
            'alert_month': ['alertMonth', 'alert_month', 'month', 'period'],
            'description': ['description', 'desc', 'alert_description', 'summary']
        }
        
        for our_field, possible_fields in field_mappings.items():
            for field in possible_fields:
                if field in alert_data:
                    alert_info[our_field] = alert_data[field]
                    break
        
        # Handle review period specifically
        for period_key in ['reviewPeriod', 'review_period', 'period', 'date_range']:
            if period_key in alert_data and isinstance(alert_data[period_key], dict):
                period_data = alert_data[period_key]
                if 'start' in period_data:
                    alert_info['review_period']['start'] = period_data['start']
                if 'end' in period_data:
                    alert_info['review_period']['end'] = period_data['end']
                break
        
        return alert_info
    
    def _extract_alert_info_fallback(self, text: str) -> Dict[str, Any]:
        """Extract alert info from text using patterns"""
        alert_info = {
            "alert_id": "",
            "alert_month": "",
            "description": "",
            "review_period": {
                "start": "",
                "end": ""
            }
        }
        
        # Extract alert ID
        alert_id_match = re.search(r"alert[_\s]*id[:\s]*([\w\-]+)", text, re.IGNORECASE)
        if alert_id_match:
            alert_info["alert_id"] = alert_id_match.group(1)
        
        # Extract alert month
        alert_month_match = re.search(r"alert[_\s]*month[:\s]*(\d{6})", text, re.IGNORECASE)
        if alert_month_match:
            alert_info["alert_month"] = alert_month_match.group(1)
        
        # Extract description
        desc_match = re.search(r"description[:\s]*(.*?)(?=review|$)", text, re.IGNORECASE | re.DOTALL)
        if desc_match:
            alert_info["description"] = desc_match.group(1).strip()
        
        # Extract review period
        period_match = re.search(r"review[_\s]*period[:\s]*.*?(\d{1,2}/\d{1,2}/\d{2,4}).*?(\d{1,2}/\d{1,2}/\d{2,4})", 
                              text, re.IGNORECASE | re.DOTALL)
        if period_match:
            alert_info["review_period"]["start"] = period_match.group(1)
            alert_info["review_period"]["end"] = period_match.group(2)
        
        return alert_info
    
    def extract_subjects(self) -> List[Dict[str, Any]]:
        """
        Extract subject information from document
        
        Returns:
            List[Dict]: Subject information
        """
        # First try direct extraction if JSON
        if isinstance(self.raw_data, dict):
            for key in ['subjects', 'subject', 'customers', 'customer_information']:
                if key in self.raw_data and isinstance(self.raw_data[key], list):
                    return self._process_subjects_json(self.raw_data[key])
        
        # Use LLM-based extraction
        prompt = """
        Extract information about all subjects (individuals or entities) mentioned in the document.
        For each subject, extract:
        1. Name
        2. Whether they are the primary subject (true/false)
        3. Party key (if available)
        4. Occupation
        5. Employer
        6. Nationality
        7. Address
        8. Account relationship (role in relation to the account)
        
        Format your response as a JSON array with the following structure for each subject:
        [
            {
                "name": "full name",
                "is_primary": true/false,
                "party_key": "party key if available",
                "occupation": "occupation if available",
                "employer": "employer if available",
                "nationality": "nationality if available",
                "address": "address if available",
                "account_relationship": "relationship to account if available"
            },
            {
                // next subject...
            }
        ]
        
        Document content:
        {text_content}
        """
        
        # Look for Customer Information section
        customer_section_match = re.search(r"Customer(?:\s+)?Information(.*?)(?=\n\n\d+\.|\Z)", 
                                      self.text_content, re.DOTALL | re.IGNORECASE)
        
        text_to_analyze = customer_section_match.group(1) if customer_section_match else self.text_content
        
        # Limit to a reasonable size
        text_to_analyze = text_to_analyze[:20000]
        
        try:
            subjects_json = self.llm_client.generate_narrative(
                prompt.format(text_content=text_to_analyze),
                {}
            ).strip()
            
            # Parse the JSON response
            try:
                subjects = json.loads(subjects_json)
                return subjects
            except json.JSONDecodeError:
                logger.error("Failed to parse subjects JSON")
                return []
            
        except Exception as e:
            logger.error(f"Error extracting subjects: {str(e)}")
            return []
    
    def _process_subjects_json(self, subjects_data: List) -> List[Dict[str, Any]]:
        """Process subjects data from JSON"""
        processed_subjects = []
        
        for subject in subjects_data:
            if not isinstance(subject, dict):
                continue
                
            processed_subject = {
                "name": "",
                "is_primary": False,
                "party_key": "",
                "occupation": "",
                "employer": "",
                "nationality": "",
                "address": "",
                "account_relationship": ""
            }
            
            # Map field names
            field_mappings = {
                'name': ['name', 'full_name', 'customer_name', 'subject_name'],
                'is_primary': ['is_primary', 'primary', 'isPrimary', 'primary_party'],
                'party_key': ['party_key', 'partyKey', 'key', 'id'],
                'occupation': ['occupation', 'job', 'profession'],
                'employer': ['employer', 'company', 'business'],
                'nationality': ['nationality', 'country', 'citizenOf', 'country_of_nationality'],
                'address': ['address', 'location', 'residentialAddress'],
                'account_relationship': ['account_relationship', 'accountRelationship', 'relationship', 'role']
            }
            
            for our_field, possible_fields in field_mappings.items():
                for field in possible_fields:
                    if field in subject:
                        if our_field == 'is_primary' and isinstance(subject[field], str):
                            # Convert string to boolean
                            processed_subject[our_field] = subject[field].lower() in ['true', 'yes', 'primary', '1']
                        else:
                            processed_subject[our_field] = subject[field]
                        break
            
            # Only add if we have at least a name
            if processed_subject["name"]:
                processed_subjects.append(processed_subject)
        
        return processed_subjects
    
    def extract_account_info(self) -> Dict[str, Any]:
        """
        Extract account information from document
        
        Returns:
            Dict: Account information
        """
        # First try direct extraction if JSON
        if isinstance(self.raw_data, dict):
            for key in ['accountInfo', 'account_info', 'account', 'accounts']:
                if key in self.raw_data:
                    if isinstance(self.raw_data[key], dict):
                        return self._process_account_json(self.raw_data[key])
                    elif isinstance(self.raw_data[key], list) and len(self.raw_data[key]) > 0:
                        return self._process_account_json(self.raw_data[key][0])
        
        # Use LLM-based extraction
        prompt = """
        Extract account information from the document including:
        1. Account number
        2. Account type (checking, savings, etc.)
        3. Account title/name
        4. Open date (MM/DD/YYYY format)
        5. Close date (MM/DD/YYYY format if closed)
        6. Status (OPEN, CLOSED, etc.)
        7. Related parties (list of individuals associated with account)
        8. Branch name/location
        
        Format your response as JSON with the following structure:
        {
            "account_number": "account number",
            "account_type": "account type",
            "account_title": "account title",
            "open_date": "MM/DD/YYYY",
            "close_date": "MM/DD/YYYY if closed, otherwise empty",
            "status": "account status",
            "related_parties": ["person1", "person2"],
            "branch": "branch name/location"
        }
        
        Document content:
        {text_content}
        """
        
        # Look for Account Information section
        account_section_match = re.search(r"Account(?:\s+)?Information(.*?)(?=\n\n\d+\.|\Z)", 
                                        self.text_content, re.DOTALL | re.IGNORECASE)
        
        text_to_analyze = account_section_match.group(1) if account_section_match else self.text_content
        
        # Limit to a reasonable size
        text_to_analyze = text_to_analyze[:10000]
        
        try:
            account_info_json = self.llm_client.generate_narrative(
                prompt.format(text_content=text_to_analyze),
                {}
            ).strip()
            
            # Parse the JSON response
            try:
                account_info = json.loads(account_info_json)
                
                # Convert related_parties to list if it's a string
                if "related_parties" in account_info and isinstance(account_info["related_parties"], str):
                    account_info["related_parties"] = [p.strip() for p in account_info["related_parties"].split(',')]
                
                return account_info
            except json.JSONDecodeError:
                logger.error("Failed to parse account info JSON")
                return {
                    "account_number": "",
                    "account_type": "",
                    "account_title": "",
                    "open_date": "",
                    "close_date": "",
                    "status": "",
                    "related_parties": [],
                    "branch": ""
                }
            
        except Exception as e:
            logger.error(f"Error extracting account info: {str(e)}")
            return {
                "account_number": "",
                "account_type": "",
                "account_title": "",
                "open_date": "",
                "close_date": "",
                "status": "",
                "related_parties": [],
                "branch": ""
            }
    
    def _process_account_json(self, account_data: Dict) -> Dict[str, Any]:
        """Process account data from JSON"""
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
        
        # Map field names
        field_mappings = {
            'account_number': ['accountNumber', 'account_number', 'number', 'id', 'acct_number'],
            'account_type': ['accountType', 'account_type', 'type'],
            'account_title': ['accountTitle', 'account_title', 'title', 'name'],
            'open_date': ['openDate', 'open_date', 'dateOpened', 'opening_date'],
            'close_date': ['closeDate', 'close_date', 'dateClosed', 'closing_date'],
            'status': ['status', 'accountStatus', 'account_status', 'state'],
            'branch': ['branch', 'branchName', 'branch_name', 'location']
        }
        
        for our_field, possible_fields in field_mappings.items():
            for field in possible_fields:
                if field in account_data:
                    account_info[our_field] = account_data[field]
                    break
        
        # Handle related parties which might be a list or string
        for field in ['relatedParties', 'related_parties', 'parties', 'owners']:
            if field in account_data:
                if isinstance(account_data[field], list):
                    account_info['related_parties'] = account_data[field]
                elif isinstance(account_data[field], str):
                    account_info['related_parties'] = [p.strip() for p in account_data[field].split(',')]
                break
        
        return account_info
    
    def extract_prior_cases(self) -> List[Dict[str, Any]]:
        """
        Extract prior cases information from document
        
        Returns:
            List[Dict]: Prior cases information
        """
        # First try direct extraction if JSON
        if isinstance(self.raw_data, dict):
            for key in ['priorCases', 'prior_cases', 'sars', 'prior_sars']:
                if key in self.raw_data and isinstance(self.raw_data[key], list):
                    return self._process_prior_cases_json(self.raw_data[key])
        
        # Use LLM-based extraction
        prompt = """
        Extract information about prior cases or SARs mentioned in the document.
        For each prior case, extract:
        1. Case number
        2. Alert ID(s) - can be multiple
        3. Alert month(s) - can be multiple
        4. Review period start and end dates
        5. SAR form number (if available)
        6. Filing date (if available)
        7. Summary or description of the case
        
        Format your response as a JSON array:
        [
            {
                "case_number": "case number",
                "alert_id": ["alert id 1", "alert id 2"],
                "alert_month": ["alert month 1", "alert month 2"],
                "review_period": {
                    "start": "MM/DD/YYYY",
                    "end": "MM/DD/YYYY"
                },
                "sar_form_number": "form number if available",
                "filing_date": "MM/DD/YYYY if available",
                "summary": "summary of the case"
            },
            {
                // next prior case...
            }
        ]
        
        If no prior cases are mentioned, return an empty array [].
        
        Document content:
        {text_content}
        """
        
        # Look for Prior Cases section
        prior_cases_section_match = re.search(r"Prior(?:\s+)?Cases(?:/SARs)?(.*?)(?=\n\n\d+\.|\Z)", 
                                          self.text_content, re.DOTALL | re.IGNORECASE)
        
        # If section contains "No prior case", return empty list
        if prior_cases_section_match and "No prior case" in prior_cases_section_match.group(1):
            return []
        
        text_to_analyze = prior_cases_section_match.group(1) if prior_cases_section_match else self.text_content
        
        # Limit to a reasonable size
        text_to_analyze = text_to_analyze[:20000]
        
        try:
            prior_cases_json = self.llm_client.generate_narrative(
                prompt.format(text_content=text_to_analyze),
                {}
            ).strip()
            
            # Parse the JSON response
            try:
                prior_cases = json.loads(prior_cases_json)
                return prior_cases
            except json.JSONDecodeError:
                logger.error("Failed to parse prior cases JSON")
                return []
            
        except Exception as e:
            logger.error(f"Error extracting prior cases: {str(e)}")
            return []
    
    def _process_prior_cases_json(self, prior_cases_data: List) -> List[Dict[str, Any]]:
        """Process prior cases data from JSON"""
        processed_cases = []
        
        for case in prior_cases_data:
            if not isinstance(case, dict):
                continue
                
            processed_case = {
                "case_number": "",
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
            
            # Map field names
            field_mappings = {
                'case_number': ['caseNumber', 'case_number', 'number', 'id', 'case_id'],
                'sar_form_number': ['sarFormNumber', 'sar_form_number', 'form_number', 'sar_number'],
                'filing_date': ['filingDate', 'filing_date', 'date_filed', 'filed_date'],
                'summary': ['summary', 'description', 'details', 'narrative']
            }
            
            for our_field, possible_fields in field_mappings.items():
                for field in possible_fields:
                    if field in case:
                        processed_case[our_field] = case[field]
                        break
            
            # Handle alert IDs which might be a list or single value
            for field in ['alertId', 'alert_id', 'alert_ids', 'alerts']:
                if field in case:
                    if isinstance(case[field], list):
                        processed_case['alert_id'] = case[field]
                    elif isinstance(case[field], str):
                        processed_case['alert_id'] = [case[field]]
                    break
            
            # Handle alert months similarly
            for field in ['alertMonth', 'alert_month', 'alert_months', 'months']:
                if field in case:
                    if isinstance(case[field], list):
                        processed_case['alert_month'] = case[field]
                    elif isinstance(case[field], str):
                        processed_case['alert_month'] = [case[field]]
                    break
            
            # Handle review period
            for period_field in ['reviewPeriod', 'review_period', 'period', 'date_range']:
                if period_field in case and isinstance(case[period_field], dict):
                    for key in ['start', 'beginning', 'from']:
                        if key in case[period_field]:
                            processed_case['review_period']['start'] = case[period_field][key]
                            break
                    
                    for key in ['end', 'ending', 'to']:
                        if key in case[period_field]:
                            processed_case['review_period']['end'] = case[period_field][key]
                            break
                    break
            
            # Only add if we have at least a case number
            if processed_case["case_number"]:
                processed_cases.append(processed_case)
        
        return processed_cases
    
    def extract_database_searches(self) -> Dict[str, Any]:
        """
        Extract database searches information from document
        
        Returns:
            Dict: Database searches information
        """
        # First try direct extraction if JSON
        if isinstance(self.raw_data, dict):
            for key in ['databaseSearches', 'database_searches', 'searches']:
                if key in self.raw_data and isinstance(self.raw_data[key], dict):
                    return self._process_database_searches_json(self.raw_data[key])
        
        # Use LLM-based extraction
        prompt = """
        Extract information about database searches mentioned in the document, particularly:
        1. KYC database results
        2. Adverse media results
        
        Format your response as JSON:
        {
            "kyc": {
                "results": "Extract of KYC database search results"
            },
            "adverse_media": {
                "results": "Extract of adverse media search results"
            }
        }
        
        Document content:
        {text_content}
        """
        
        # Look for Database Searches section
        db_searches_section_match = re.search(r"Database(?:\s+)?Searches(.*?)(?=\n\n\d+\.|\Z)", 
                                          self.text_content, re.DOTALL | re.IGNORECASE)
        
        text_to_analyze = db_searches_section_match.group(1) if db_searches_section_match else self.text_content
        
        # Limit to a reasonable size
        text_to_analyze = text_to_analyze[:10000]
        
        try:
            db_searches_json = self.llm_client.generate_narrative(
                prompt.format(text_content=text_to_analyze),
                {}
            ).strip()
            
            # Parse the JSON response
            try:
                db_searches = json.loads(db_searches_json)
                return db_searches
            except json.JSONDecodeError:
                logger.error("Failed to parse database searches JSON")
                return {
                    "kyc": {"results": ""},
                    "adverse_media": {"results": ""}
                }
            
        except Exception as e:
            logger.error(f"Error extracting database searches: {str(e)}")
            return {
                "kyc": {"results": ""},
                "adverse_media": {"results": ""}
            }
    
    def _process_database_searches_json(self, searches_data: Dict) -> Dict[str, Any]:
        """Process database searches data from JSON"""
        db_searches = {
            "kyc": {"results": ""},
            "adverse_media": {"results": ""}
        }
        
        # Handle KYC results
        for key in ['kyc', 'KYC', 'kycDatabase', 'kyc_database']:
            if key in searches_data:
                if isinstance(searches_data[key], dict) and 'results' in searches_data[key]:
                    db_searches['kyc']['results'] = searches_data[key]['results']
                elif isinstance(searches_data[key], str):
                    db_searches['kyc']['results'] = searches_data[key]
                break
        
        # Handle adverse media results
        for key in ['adverseMedia', 'adverse_media', 'adverse']:
            if key in searches_data:
                if isinstance(searches_data[key], dict) and 'results' in searches_data[key]:
                    db_searches['adverse_media']['results'] = searches_data[key]['results']
                elif isinstance(searches_data[key], str):
                    db_searches['adverse_media']['results'] = searches_data[key]
                break
        
        return db_searches
    
    def process(self) -> Dict[str, Any]:
        """
        Process the case document and extract all relevant information
        
        Returns:
            Dict: All extracted data from case document
        """
        if not self.load_document():
            return self.data
        
        # Extract data from document using LLM prompting
        self.data["case_number"] = self.extract_case_number()
        self.data["alert_info"] = self.extract_alert_info()
        self.data["subjects"] = self.extract_subjects()
        self.data["account_info"] = self.extract_account_info()
        self.data["prior_cases"] = self.extract_prior_cases()
        self.data["database_searches"] = self.extract_database_searches()
        
        return self.data