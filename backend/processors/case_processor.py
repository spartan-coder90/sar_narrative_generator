"""
Case document processor for extracting data from case documents
"""
import re
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

from backend.utils.logger import get_logger

logger = get_logger(__name__)

class CaseProcessor:
    """Processes case documents to extract relevant data for SAR narratives"""
    
    def __init__(self, file_path: str):
        """
        Initialize with path to case document file
        
        Args:
            file_path: Path to case document file (JSON or text format)
        """
        self.file_path = file_path
        self.raw_data = None
        self.data = {
            "case_number": "",
            "alert_info": {},
            "subjects": [],
            "account_info": {},
            "prior_cases": [],
            "database_searches": {}
        }
    
    def load_document(self) -> bool:
        """
        Load the case document
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            file_ext = os.path.splitext(self.file_path)[1].lower()
            
            if file_ext == '.json':
                # Load as JSON
                with open(self.file_path, 'r') as f:
                    self.raw_data = json.load(f)
            elif file_ext in ['.txt', '.doc', '.docx']:
                # Load as text
                with open(self.file_path, 'r') as f:
                    self.raw_data = f.read()
            else:
                logger.error(f"Unsupported file format: {file_ext}")
                return False
            
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
        case_number = ""
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            case_number = self.raw_data.get("caseNumber", "")
            if not case_number:
                # Try alternate keys
                case_number = self.raw_data.get("case_number", "")
                if not case_number and "case" in self.raw_data:
                    case_number = self.raw_data["case"].get("number", "")
        else:
            # Extract from text using regex
            patterns = [
                r"Case Number:?\s*([A-Z0-9]+)",
                r"Case ID:?\s*([A-Z0-9]+)",
                r"Case #:?\s*([A-Z0-9]+)"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, self.raw_data)
                if match:
                    case_number = match.group(1)
                    break
        
        return case_number
    
    def extract_alert_info(self) -> Dict[str, Any]:
        """
        Extract alert information from document
        
        Returns:
            Dict: Alert information
        """
        alert_info = {
            "alert_id": "",
            "alert_month": "",
            "description": "",
            "review_period": {
                "start": "",
                "end": ""
            }
        }
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            if "alertInfo" in self.raw_data:
                alert_data = self.raw_data["alertInfo"]
                alert_info["alert_id"] = alert_data.get("alertId", "")
                alert_info["alert_month"] = alert_data.get("alertMonth", "")
                alert_info["description"] = alert_data.get("description", "")
                
                if "reviewPeriod" in alert_data:
                    alert_info["review_period"]["start"] = alert_data["reviewPeriod"].get("start", "")
                    alert_info["review_period"]["end"] = alert_data["reviewPeriod"].get("end", "")
            
            # Try alternate keys
            elif "alerting_details" in self.raw_data:
                alert_data = self.raw_data["alerting_details"]
                alert_info["alert_id"] = alert_data.get("alert_id", "")
                alert_info["alert_month"] = alert_data.get("alert_month", "")
                alert_info["description"] = alert_data.get("description", "")
                
                if "review_period" in alert_data:
                    alert_info["review_period"]["start"] = alert_data["review_period"].get("start", "")
                    alert_info["review_period"]["end"] = alert_data["review_period"].get("end", "")
        else:
            # Extract from text using regex
            # Alert ID
            alert_id_match = re.search(r"Alert ID:?\s*([A-Z0-9\-]+)", self.raw_data)
            if alert_id_match:
                alert_info["alert_id"] = alert_id_match.group(1)
            
            # Alert Month
            alert_month_match = re.search(r"Alert Month:?\s*(\d{6})", self.raw_data)
            if alert_month_match:
                alert_info["alert_month"] = alert_month_match.group(1)
            
            # Description
            desc_match = re.search(r"Description:?\s*(.+?)(?=\n\n|\Z)", self.raw_data, re.DOTALL)
            if desc_match:
                alert_info["description"] = desc_match.group(1).strip()
            
            # Review Period
            review_period_match = re.search(
                r"Review Period:?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*(\d{1,2}/\d{1,2}/\d{2,4})",
                self.raw_data
            )
            if review_period_match:
                alert_info["review_period"]["start"] = review_period_match.group(1)
                alert_info["review_period"]["end"] = review_period_match.group(2)
        
        return alert_info
    
    def extract_subjects(self) -> List[Dict[str, Any]]:
        """
        Extract subject information from document
        
        Returns:
            List[Dict]: Subject information
        """
        subjects = []
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            if "subjects" in self.raw_data:
                for subject in self.raw_data["subjects"]:
                    subjects.append({
                        "name": subject.get("name", ""),
                        "is_primary": subject.get("isPrimary", False),
                        "party_key": subject.get("partyKey", ""),
                        "occupation": subject.get("occupation", ""),
                        "employer": subject.get("employer", ""),
                        "nationality": subject.get("nationality", ""),
                        "address": subject.get("address", "")
                    })
            
            # Try alternate keys
            elif "customer_information" in self.raw_data:
                for subject in self.raw_data["customer_information"]:
                    subjects.append({
                        "name": subject.get("name", ""),
                        "is_primary": subject.get("is_primary", False),
                        "party_key": subject.get("party_key", ""),
                        "occupation": subject.get("occupation", ""),
                        "employer": subject.get("employer", ""),
                        "nationality": subject.get("nationality", ""),
                        "address": subject.get("address", "")
                    })
        else:
            # Extract from text using regex
            # Find customer information section
            customer_section_match = re.search(r"Customer Information(.+?)(?=\n\n\d+\.|\Z)", self.raw_data, re.DOTALL)
            
            if customer_section_match:
                customer_section = customer_section_match.group(1)
                
                # Extract individual subjects
                subject_blocks = re.findall(r"([A-Z\s]+(?:GOMEZ-CUENCA|THEESFIELD).*?)(?=\n\n[A-Z\s]+(?:GOMEZ-CUENCA|THEESFIELD)|\n\nNon-U\.S\.|\Z)", 
                                           customer_section, re.DOTALL)
                
                for block in subject_blocks:
                    subject = {
                        "name": "",
                        "is_primary": False,
                        "party_key": "",
                        "occupation": "",
                        "employer": "",
                        "nationality": "",
                        "address": ""
                    }
                    
                    # Extract name
                    name_match = re.search(r"^([A-Z\s]+(?:GOMEZ-CUENCA|THEESFIELD))", block)
                    if name_match:
                        subject["name"] = name_match.group(1).strip()
                    
                    # Check if primary
                    if "Primary Party" in block:
                        subject["is_primary"] = True
                    
                    # Extract party key
                    party_key_match = re.search(r"Party Key\s*(\d+)", block)
                    if party_key_match:
                        subject["party_key"] = party_key_match.group(1)
                    
                    # Extract occupation
                    occupation_match = re.search(r"Occupation\s*([^:]+?)(?:\s*:|$)", block)
                    if occupation_match:
                        subject["occupation"] = occupation_match.group(1).strip()
                    
                    # Extract employer
                    employer_match = re.search(r"Employer\s*([^:]+?)(?:\s*:|$)", block)
                    if employer_match:
                        subject["employer"] = employer_match.group(1).strip()
                    
                    # Extract nationality
                    nationality_match = re.search(r"Country of Nationality\s*([^:]+?)(?:\s*:|$)", block)
                    if nationality_match:
                        subject["nationality"] = nationality_match.group(1).strip()
                    
                    # Extract address
                    address_match = re.search(r"Address:?\s*([^\n]+)", block)
                    if address_match:
                        subject["address"] = address_match.group(1).strip()
                    
                    subjects.append(subject)
        
        return subjects
    
    def extract_account_info(self) -> Dict[str, Any]:
        """
        Extract account information from document
        
        Returns:
            Dict: Account information
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
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            if "accountInfo" in self.raw_data:
                account_data = self.raw_data["accountInfo"]
                account_info["account_number"] = account_data.get("accountNumber", "")
                account_info["account_type"] = account_data.get("accountType", "")
                account_info["account_title"] = account_data.get("accountTitle", "")
                account_info["open_date"] = account_data.get("openDate", "")
                account_info["close_date"] = account_data.get("closeDate", "")
                account_info["status"] = account_data.get("status", "")
                account_info["related_parties"] = account_data.get("relatedParties", [])
                account_info["branch"] = account_data.get("branch", "")
            
            # Try alternate keys
            elif "account_information" in self.raw_data:
                account_data = self.raw_data["account_information"]
                account_info["account_number"] = account_data.get("account_number", "")
                account_info["account_type"] = account_data.get("account_type", "")
                account_info["account_title"] = account_data.get("account_title", "")
                account_info["open_date"] = account_data.get("open_date", "")
                account_info["close_date"] = account_data.get("close_date", "")
                account_info["status"] = account_data.get("status", "")
                account_info["related_parties"] = account_data.get("related_parties", [])
                account_info["branch"] = account_data.get("branch", "")
        else:
            # Extract from text using regex
            # Find account information section
            account_section_match = re.search(r"Account Information(.+?)(?=\n\n\d+\.|\Z)", self.raw_data, re.DOTALL)
            
            if account_section_match:
                account_section = account_section_match.group(1)
                
                # Extract account number
                account_number_match = re.search(r"Account Number:?\s*(\d+)", account_section)
                if account_number_match:
                    account_info["account_number"] = account_number_match.group(1)
                
                # Extract account type
                account_type_match = re.search(r"Account Type:?\s*([^\n]+)", account_section)
                if account_type_match:
                    account_info["account_type"] = account_type_match.group(1).strip()
                
                # Extract account title
                account_title_match = re.search(r"Account Title:?\s*([^\n]+)", account_section)
                if account_title_match:
                    account_info["account_title"] = account_title_match.group(1).strip()
                
                # Extract open date
                open_date_match = re.search(r"(?:Open|Opening) Date:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", account_section)
                if open_date_match:
                    account_info["open_date"] = open_date_match.group(1)
                
                # Extract close date
                close_date_match = re.search(r"(?:Close|Closing) Date:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", account_section)
                if close_date_match:
                    account_info["close_date"] = close_date_match.group(1)
                    account_info["status"] = "CLOSED"
                else:
                    account_info["status"] = "OPEN"
                
                # Extract related parties
                related_parties_match = re.search(r"Related parties [^\n]+:\s*([^\n]+)", account_section)
                if related_parties_match:
                    parties = related_parties_match.group(1).strip()
                    account_info["related_parties"] = [p.strip() for p in parties.split(',')]
                
                # Extract branch
                branch_match = re.search(r"Branch:?\s*([^\n]+)", account_section)
                if branch_match:
                    account_info["branch"] = branch_match.group(1).strip()
        
        return account_info
    
    def extract_prior_cases(self) -> List[Dict[str, Any]]:
        """
        Extract prior cases information from document
        
        Returns:
            List[Dict]: Prior cases information
        """
        prior_cases = []
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            if "priorCases" in self.raw_data:
                for case in self.raw_data["priorCases"]:
                    prior_cases.append({
                        "case_number": case.get("caseNumber", ""),
                        "alert_id": case.get("alertId", []),
                        "alert_month": case.get("alertMonth", []),
                        "review_period": {
                            "start": case.get("reviewPeriodStart", ""),
                            "end": case.get("reviewPeriodEnd", "")
                        },
                        "sar_form_number": case.get("sarFormNumber", ""),
                        "filing_date": case.get("filingDate", ""),
                        "summary": case.get("summary", "")
                    })
            
            # Try alternate keys
            elif "prior_cases" in self.raw_data:
                for case in self.raw_data["prior_cases"]:
                    prior_cases.append({
                        "case_number": case.get("case_number", ""),
                        "alert_id": case.get("alert_id", []),
                        "alert_month": case.get("alert_month", []),
                        "review_period": {
                            "start": case.get("review_period_start", ""),
                            "end": case.get("review_period_end", "")
                        },
                        "sar_form_number": case.get("sar_form_number", ""),
                        "filing_date": case.get("filing_date", ""),
                        "summary": case.get("summary", "")
                    })
        else:
            # Extract from text using regex
            # Find prior cases section
            prior_cases_section_match = re.search(r"Prior Cases/SARs(.+?)(?=\n\n\d+\.|\Z)", self.raw_data, re.DOTALL)
            
            if prior_cases_section_match:
                prior_cases_section = prior_cases_section_match.group(1)
                
                # Extract individual prior cases
                case_blocks = re.findall(r"Case Number:?\s*([A-Z0-9]+)(.+?)(?=Case Number:|\Z)", 
                                        prior_cases_section, re.DOTALL)
                
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
                    alert_ids = re.findall(r"Alert ID:?\s*([A-Z0-9\-]+)", block)
                    prior_case["alert_id"] = alert_ids
                    
                    # Extract alert months
                    alert_months = re.findall(r"Alert Month:?\s*(\d{6})", block)
                    prior_case["alert_month"] = alert_months
                    
                    # Extract review period
                    review_period_match = re.search(
                        r"(?:Scope of Review|Review Period):?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*(\d{1,2}/\d{1,2}/\d{2,4})",
                        block
                    )
                    if review_period_match:
                        prior_case["review_period"]["start"] = review_period_match.group(1)
                        prior_case["review_period"]["end"] = review_period_match.group(2)
                    
                    # Extract SAR form number
                    sar_form_match = re.search(r"SAR Form Number:?\s*(\d+)", block)
                    if sar_form_match:
                        prior_case["sar_form_number"] = sar_form_match.group(1)
                    
                    # Extract filing date
                    filing_date_match = re.search(r"Filing date:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", block)
                    if filing_date_match:
                        prior_case["filing_date"] = filing_date_match.group(1)
                    
                    # Extract summary
                    summary_match = re.search(r"Summary of [^\n]+:\s*([^\n]+)", block)
                    if summary_match:
                        prior_case["summary"] = summary_match.group(1).strip()
                    
                    prior_cases.append(prior_case)
        
        return prior_cases
    
    def extract_database_searches(self) -> Dict[str, Any]:
        """
        Extract database searches information from document
        
        Returns:
            Dict: Database searches information
        """
        database_searches = {
            "kyc": {
                "results": ""
            },
            "adverse_media": {
                "results": ""
            }
        }
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            if "databaseSearches" in self.raw_data:
                db_searches = self.raw_data["databaseSearches"]
                
                if "kyc" in db_searches:
                    database_searches["kyc"]["results"] = db_searches["kyc"].get("results", "")
                
                if "adverseMedia" in db_searches:
                    database_searches["adverse_media"]["results"] = db_searches["adverseMedia"].get("results", "")
            
            # Try alternate keys
            elif "database_searches" in self.raw_data:
                db_searches = self.raw_data["database_searches"]
                
                if "kyc" in db_searches:
                    database_searches["kyc"]["results"] = db_searches["kyc"].get("results", "")
                
                if "adverse_media" in db_searches:
                    database_searches["adverse_media"]["results"] = db_searches["adverse_media"].get("results", "")
        else:
            # Extract from text using regex
            # Find database searches section
            db_searches_section_match = re.search(r"Database Searches(.+?)(?=\n\n\d+\.|\Z)", self.raw_data, re.DOTALL)
            
            if db_searches_section_match:
                db_searches_section = db_searches_section_match.group(1)
                
                # Extract KYC results
                kyc_match = re.search(r"KYC Database:(.+?)(?=Adverse Media|\Z)", db_searches_section, re.DOTALL)
                if kyc_match:
                    kyc_section = kyc_match.group(1)
                    
                    # Look for specific results
                    kyc_results_match = re.search(r"No (?:WebKYC form links|matching [Hh]ogan profiles) found", kyc_section)
                    if kyc_results_match:
                        database_searches["kyc"]["results"] = kyc_results_match.group(0)
                
                # Extract adverse media results
                adverse_match = re.search(r"Adverse Media(.+?)(?=\n\n|Risk Ratings|\Z)", db_searches_section, re.DOTALL)
                if adverse_match:
                    adverse_section = adverse_match.group(1)
                    
                    # Look for specific results
                    adverse_results_match = re.search(r"No adverse media found", adverse_section)
                    if adverse_results_match:
                        database_searches["adverse_media"]["results"] = adverse_results_match.group(0)
        
        return database_searches
    
    def process(self) -> Dict[str, Any]:
        """
        Process the case document
        
        Returns:
            Dict: All extracted data from case document
        """
        if not self.load_document():
            return self.data
        
        self.data["case_number"] = self.extract_case_number()
        self.data["alert_info"] = self.extract_alert_info()
        self.data["subjects"] = self.extract_subjects()
        self.data["account_info"] = self.extract_account_info()
        self.data["prior_cases"] = self.extract_prior_cases()
        self.data["database_searches"] = self.extract_database_searches()
        
        return self.data
