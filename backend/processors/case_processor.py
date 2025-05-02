"""
Improved case document processor for extracting data from case documents
"""
import re
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from backend.utils.sar_extraction_utils import extract_case_number, extract_subjects
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
            "alert_info": [],  # Changed to list to support multiple alerts
            "subjects": [],
            "account_info": {},
            "accounts": [],  # Added to support multiple accounts
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
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.raw_data = json.load(f)
            elif file_ext in ['.txt', '.doc', '.docx']:
                # Load as text
                with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
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
                r"Case Number\s*[:;]\s*([A-Z0-9]+)",
                r"Case ID:?\s*([A-Z0-9]+)",
                r"Case #:?\s*([A-Z0-9]+)"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, self.raw_data)
                if match:
                    case_number = match.group(1)
                    break
        
        return case_number
    
    def extract_alert_info(self) -> List[Dict[str, Any]]:
        """
        Extract alert information from document, now supporting multiple alerts
        
        Returns:
            List[Dict]: Alert information for each alert found
        """
        alerts = []
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            if "alertInfo" in self.raw_data:
                if isinstance(self.raw_data["alertInfo"], list):
                    # Multiple alerts
                    for alert_data in self.raw_data["alertInfo"]:
                        alert = {
                            "alert_id": alert_data.get("alertId", ""),
                            "alert_month": alert_data.get("alertMonth", ""),
                            "description": alert_data.get("description", ""),
                            "review_period": {
                                "start": alert_data.get("reviewPeriodStart", ""),
                                "end": alert_data.get("reviewPeriodEnd", "")
                            }
                        }
                        alerts.append(alert)
                else:
                    # Single alert
                    alert_data = self.raw_data["alertInfo"]
                    alert = {
                        "alert_id": alert_data.get("alertId", ""),
                        "alert_month": alert_data.get("alertMonth", ""),
                        "description": alert_data.get("description", ""),
                        "review_period": {
                            "start": alert_data.get("reviewPeriodStart", ""),
                            "end": alert_data.get("reviewPeriodEnd", "")
                        }
                    }
                    alerts.append(alert)
        else:
            # Extract from text using regex
            # Find alert sections
            alert_section_pattern = r"(?:Alert ID|Alert Identifier):\s*([A-Z0-9_-]+).*?(?=(?:Alert ID|Alert Identifier):|(?:\d+\.\s+(?:Prior|Customer|Database))|\Z)"
            alert_sections = re.findall(alert_section_pattern, self.raw_data, re.DOTALL)
            
            if not alert_sections:
                # Try a different pattern if no alerts found
                alerting_section = re.search(r"Alerting Details(.*?)(?=\d+\.\s+(?:Prior|Customer|Database)|\Z)", 
                                           self.raw_data, re.DOTALL)
                if alerting_section:
                    alert_text = alerting_section.group(1)
                    # Try to find individual alerts
                    alert_blocks = re.findall(r"(?:Alert ID|Alert Identifier):\s*([A-Z0-9_-]+)(.*?)(?=(?:Alert ID|Alert Identifier):|$)", 
                                            alert_text, re.DOTALL)
                    
                    for alert_id, block in alert_blocks:
                        alert = {
                            "alert_id": alert_id,
                            "alert_month": "",
                            "description": "",
                            "review_period": {
                                "start": "",
                                "end": ""
                            }
                        }
                        
                        # Extract alert month
                        month_match = re.search(r"Alert Month:?\s*(\d{6})", block)
                        if month_match:
                            alert["alert_month"] = month_match.group(1)
                        
                        # Extract description
                        desc_match = re.search(r"Description:?\s*(.+?)(?=\n\n|\Z)", block, re.DOTALL)
                        if desc_match:
                            alert["description"] = desc_match.group(1).strip()
                        
                        # Extract review period
                        review_period_match = re.search(
                            r"Review Period:?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})",
                            block
                        )
                        if review_period_match:
                            alert["review_period"]["start"] = review_period_match.group(1)
                            alert["review_period"]["end"] = review_period_match.group(2)
                        
                        alerts.append(alert)
            else:
                for section in alert_sections:
                    alert_id_match = re.search(r"(?:Alert ID|Alert Identifier):\s*([A-Z0-9_-]+)", section)
                    alert_id = alert_id_match.group(1) if alert_id_match else ""
                    
                    alert = {
                        "alert_id": alert_id,
                        "alert_month": "",
                        "description": "",
                        "review_period": {
                            "start": "",
                            "end": ""
                        }
                    }
                    
                    # Extract alert month
                    month_match = re.search(r"Alert Month:?\s*(\d{6})", section)
                    if month_match:
                        alert["alert_month"] = month_match.group(1)
                    
                    # Extract description
                    desc_match = re.search(r"Description:?\s*(.+?)(?=\n\n|\Z)", section, re.DOTALL)
                    if desc_match:
                        alert["description"] = desc_match.group(1).strip()
                    
                    # Extract review period
                    review_period_match = re.search(
                        r"Review Period:?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})",
                        section
                    )
                    if review_period_match:
                        alert["review_period"]["start"] = review_period_match.group(1)
                        alert["review_period"]["end"] = review_period_match.group(2)
                    
                    alerts.append(alert)
        
        return alerts
    
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
                        "address": subject.get("address", ""),
                        "account_relationship": subject.get("accountRelationship", "")
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
                        "address": subject.get("address", ""),
                        "account_relationship": subject.get("account_relationship", "")
                    })
        else:
            # Extract from text using regex
            # Find customer information section
            customer_section_match = re.search(r"Customer Information(.*?)(?=\d+\.\s+Database|\d+\.\s+External|\Z)", 
                                             self.raw_data, re.DOTALL)
            
            if customer_section_match:
                customer_section = customer_section_match.group(1)
                
                # Find U.S. Bank Customer Information subsection
                usb_customer_section_match = re.search(r"U\.S\. Bank Customer Information(.*?)(?=Non-U\.S\. Bank Customer|\d+\.\s+Database|\Z)", 
                                                     customer_section, re.DOTALL)
                
                if usb_customer_section_match:
                    usb_customer_section = usb_customer_section_match.group(1)
                    
                    # Extract individual subjects - look for patterns like names in all caps
                    # This is a more flexible pattern that will match subject blocks
                    subject_pattern = r"([A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+)(?:.*?)(?=(?:[A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+)|Non-U\.S\. Bank Customer Information|\d+\.\s+Database|\Z)"
                    subject_blocks = re.findall(subject_pattern, usb_customer_section, re.DOTALL)
                    
                    for i, name in enumerate(subject_blocks):
                        # Get the text block for this subject
                        if i < len(subject_blocks) - 1:
                            end_pos = usb_customer_section.find(subject_blocks[i+1], usb_customer_section.find(name))
                            block = usb_customer_section[usb_customer_section.find(name):end_pos]
                        else:
                            block = usb_customer_section[usb_customer_section.find(name):]
                        
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
            
            # If we didn't find any subjects, try a more generic approach
            if not subjects:
                # Look for names and addresses in the entire document
                name_matches = re.findall(r"Customer Name:?\s*([A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+)", self.raw_data)
                address_matches = re.findall(r"Address:?\s*([^\n]+(?:\n[^A-Z\n][^\n]*)*)", self.raw_data)
                
                for i, name in enumerate(name_matches):
                    subject = {
                        "name": name.strip(),
                        "is_primary": False,
                        "party_key": "",
                        "occupation": "",
                        "employer": "",
                        "nationality": "",
                        "address": address_matches[i].strip() if i < len(address_matches) else "",
                        "account_relationship": ""
                    }
                    
                    # Look for related information near this name
                    name_pos = self.raw_data.find(name)
                    context_start = max(0, name_pos - 100)
                    context_end = min(len(self.raw_data), name_pos + 1000)
                    context = self.raw_data[context_start:context_end]
                    
                    # Check if primary
                    if "Primary Party" in context or "Primary" in context:
                        subject["is_primary"] = True
                    
                    # Try to extract other information from context
                    occupation_match = re.search(r"Occupation Description:?\s*([^\n]+)", context)
                    if occupation_match:
                        subject["occupation"] = occupation_match.group(1).strip()
                    
                    employer_match = re.search(r"Employer:?\s*([^\n:]+?)(?:\s*:|\n)", context)
                    if employer_match:
                        subject["employer"] = employer_match.group(1).strip()
                    
                    subjects.append(subject)
        
        return subjects
    
    def extract_accounts(self) -> List[Dict[str, Any]]:
        """
        Extract account information from document, supporting multiple accounts
        
        Returns:
            List[Dict]: Account information for each account found
        """
        accounts = []
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            if "accounts" in self.raw_data:
                for account in self.raw_data["accounts"]:
                    accounts.append({
                        "account_number": account.get("accountNumber", ""),
                        "account_type": account.get("accountType", ""),
                        "account_title": account.get("accountTitle", ""),
                        "open_date": account.get("openDate", ""),
                        "close_date": account.get("closeDate", ""),
                        "status": account.get("status", ""),
                        "related_parties": account.get("relatedParties", []),
                        "branch": account.get("branch", ""),
                        "credits": account.get("credits", {}),
                        "debits": account.get("debits", {})
                    })
        else:
            # Extract from text using regex
            # Find account information section
            account_section_match = re.search(r"Account Information(.*?)(?=\d+\.\s+Recommendations|\Z)", 
                                             self.raw_data, re.DOTALL)
            
            if account_section_match:
                account_section = account_section_match.group(1)
                
                # Find account sections - look for patterns like account numbers or account keys
                account_pattern = r"(?:Account(?:\s+Key)?|Account Number)[:\s]*([A-Z0-9]+).*?(?=(?:Account(?:\s+Key)?|Account Number)[:\s]*[A-Z0-9]+|\d+\.\s+Recommendations|\Z)"
                account_blocks = re.findall(account_pattern, account_section, re.DOTALL)
                
                if not account_blocks:
                    # Try a different pattern
                    account_pattern = r"(?:ICS\d+|0300DDA\d+).*?(?=(?:ICS\d+|0300DDA\d+)|\d+\.\s+Recommendations|\Z)"
                    account_blocks = re.findall(account_pattern, account_section, re.DOTALL)
                
                for block in account_blocks:
                    account = {
                        "account_number": "",
                        "account_type": "",
                        "account_title": "",
                        "open_date": "",
                        "close_date": "",
                        "status": "",
                        "related_parties": [],
                        "branch": "",
                        "credits": {},
                        "debits": {}
                    }
                    
                    # Extract account number/key
                    account_number_match = re.search(r"(?:Account(?:\s+Key)?|Account Number)[:\s]*([A-Z0-9]+)", block)
                    if account_number_match:
                        account["account_number"] = account_number_match.group(1)
                    else:
                        # Try to find any account number-like pattern
                        potential_account_number = re.search(r"(ICS\d+|0300DDA\d+)", block)
                        if potential_account_number:
                            account["account_number"] = potential_account_number.group(1)
                    
                    # Extract account type
                    account_type_match = re.search(r"Account Type[:\s]*([^\n]+)", block)
                    if account_type_match:
                        account["account_type"] = account_type_match.group(1).strip()
                    
                    # Extract account title
                    account_title_match = re.search(r"Account Title[:\s]*([^\n]+)", block)
                    if account_title_match:
                        account["account_title"] = account_title_match.group(1).strip()
                    
                    # Extract open date
                    open_date_match = re.search(r"(?:Open|Opening) Date[:\s&]*([^\n:,]+)", block)
                    if open_date_match:
                        account["open_date"] = open_date_match.group(1).strip()
                    
                    # Extract close date
                    close_date_match = re.search(r"(?:Close|Closing) Date[:\s]*([^\n:,]+)", block)
                    if close_date_match:
                        account["close_date"] = close_date_match.group(1).strip()
                    
                    # Extract status
                    status_match = re.search(r"Status Description[:\s]*([^\n]+)", block)
                    if status_match:
                        account["status"] = status_match.group(1).strip()
                    
                    # Extract related parties
                    related_parties_match = re.search(r"Related parties[^\n]*:[^\n]*\n?([^\n]+(?:\([^)]+\)[,\s]*)+)", block, re.DOTALL)
                    if related_parties_match:
                        parties_text = related_parties_match.group(1)
                        # Identify parties with roles in parentheses
                        party_matches = re.findall(r"([^(,]+)\s*\(([^)]+)\)", parties_text)
                        
                        account["related_parties"] = [
                            {"name": name.strip(), "role": role.strip()}
                            for name, role in party_matches
                        ]
                    
                    # Extract branch
                    branch_match = re.search(r"(?:Branch|Account Holding Branch)[:\s]*([^\n]+)", block)
                    if branch_match:
                        account["branch"] = branch_match.group(1).strip()
                    
                    # Extract credits information
                    credits_section = re.search(r"Credits?:.*?(?=Debits?:|\Z)", block, re.DOTALL)
                    if credits_section:
                        credits_text = credits_section.group(0)
                        
                        # Extract total amount
                        total_amount_match = re.search(r"\$([0-9,.]+)", credits_text)
                        if total_amount_match:
                            try:
                                total_amount = float(total_amount_match.group(1).replace(',', ''))
                                account["credits"]["total_amount"] = total_amount
                            except ValueError:
                                pass
                        
                        # Extract transaction count
                        txn_count_match = re.search(r"(?:Txn[.\s]*C(?:ou)?nt|transactions)[:\s]*(\d+)", credits_text)
                        if txn_count_match:
                            account["credits"]["transaction_count"] = int(txn_count_match.group(1))
                        
                        # Extract date range
                        date_range_match = re.search(r"(?:Earliest|First) Date[:\s]*([^\s]+)[^\n]*(?:Latest|Last) Date[:\s]*([^\s]+)", credits_text)
                        if date_range_match:
                            account["credits"]["date_range"] = {
                                "start": date_range_match.group(1),
                                "end": date_range_match.group(2)
                            }
                    
                    # Extract debits information
                    debits_section = re.search(r"Debits?:.*", block, re.DOTALL)
                    if debits_section:
                        debits_text = debits_section.group(0)
                        
                        # Extract total amount
                        total_amount_match = re.search(r"\$([0-9,.]+)", debits_text)
                        if total_amount_match:
                            try:
                                total_amount = float(total_amount_match.group(1).replace(',', ''))
                                account["debits"]["total_amount"] = total_amount
                            except ValueError:
                                pass
                        
                        # Extract transaction count
                        txn_count_match = re.search(r"(?:Txn[.\s]*C(?:ou)?nt|transactions)[:\s]*(\d+)", debits_text)
                        if txn_count_match:
                            account["debits"]["transaction_count"] = int(txn_count_match.group(1))
                        
                        # Extract date range
                        date_range_match = re.search(r"(?:Earliest|First) Date[:\s]*([^\s]+)[^\n]*(?:Latest|Last) Date[:\s]*([^\s]+)", debits_text)
                        if date_range_match:
                            account["debits"]["date_range"] = {
                                "start": date_range_match.group(1),
                                "end": date_range_match.group(2)
                            }
                    
                    accounts.append(account)
        
        return accounts
    
    def extract_account_info(self) -> Dict[str, Any]:
        """
        Extract primary account information from document
        
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
        
        # Extract all accounts first
        accounts = self.extract_accounts()
        
        # Use the first account as the primary one
        if accounts:
            account_info = accounts[0]
        
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
            prior_cases_section_match = re.search(r"Prior Cases[/\s]?SARs(.*?)(?=\d+\.\s+Customer|\Z)", 
                                                self.raw_data, re.DOTALL)
            
            if prior_cases_section_match:
                prior_cases_section = prior_cases_section_match.group(1)
                
                # Check if there are no prior cases
                if re.search(r"No prior case[s]? or SAR information found", prior_cases_section, re.IGNORECASE):
                    return prior_cases
                
                # Extract individual prior cases - look for case numbers
                case_blocks = re.findall(r"Case Number:?\s*([A-Z0-9]+)(.*?)(?=Case Number:|\Z)", 
                                        prior_cases_section, re.DOTALL)
                
                if not case_blocks:
                    # Try a different pattern
                    case_blocks = re.findall(r"Case Number:?\s*([A-Z0-9]+)", prior_cases_section)
                    if case_blocks:
                        # Simply return the case numbers without details
                        for case_number in case_blocks:
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
                        alert_ids = re.findall(r"Alert ID:?\s*([A-Z0-9\-_]+)", block)
                        prior_case["alert_id"] = alert_ids
                        
                        # Extract alert months
                        alert_months = re.findall(r"Alert Month:?\s*(\d{6})", block)
                        prior_case["alert_month"] = alert_months
                        
# Extract review period
                        review_period_match = re.search(
                            r"(?:Scope of Review|Review Period):?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})",
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
                        summary_match = re.search(r"(?:Summary|SAR summary).*?:?\s*([^\n]+(?:\n[^A-Z\n][^\n]*)*)", block, re.DOTALL)
                        if summary_match:
                            prior_case["summary"] = ' '.join(line.strip() for line in summary_match.group(1).strip().split('\n') if line.strip())
                        
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
            },
            "risk_ratings": []
        }
        
        if isinstance(self.raw_data, dict):
            # Extract from JSON
            if "databaseSearches" in self.raw_data:
                db_searches = self.raw_data["databaseSearches"]
                
                if "kyc" in db_searches:
                    database_searches["kyc"]["results"] = db_searches["kyc"].get("results", "")
                
                if "adverseMedia" in db_searches:
                    database_searches["adverse_media"]["results"] = db_searches["adverseMedia"].get("results", "")
                
                if "riskRatings" in db_searches:
                    database_searches["risk_ratings"] = db_searches["riskRatings"]
            
            # Try alternate keys
            elif "database_searches" in self.raw_data:
                db_searches = self.raw_data["database_searches"]
                
                if "kyc" in db_searches:
                    database_searches["kyc"]["results"] = db_searches["kyc"].get("results", "")
                
                if "adverse_media" in db_searches:
                    database_searches["adverse_media"]["results"] = db_searches["adverse_media"].get("results", "")
                
                if "risk_ratings" in db_searches:
                    database_searches["risk_ratings"] = db_searches["risk_ratings"]
        else:
            # Extract from text using regex
            # Find database searches section
            db_searches_section_match = re.search(r"Database Searches(.*?)(?=\d+\.\s+External|\d+\.\s+Account|\Z)", 
                                               self.raw_data, re.DOTALL)
            
            if db_searches_section_match:
                db_searches_section = db_searches_section_match.group(1)
                
                # Extract KYC results
                kyc_section_match = re.search(r"KYC Database[:\s]*(.*?)(?=Risk Ratings|Adverse Media|\Z)", db_searches_section, re.DOTALL)
                if kyc_section_match:
                    kyc_section = kyc_section_match.group(1)
                    database_searches["kyc"]["results"] = kyc_section.strip()
                
                # Extract adverse media results
                adverse_section_match = re.search(r"Adverse Media.*?(.*?)(?=\d+\.\s+External|Active Subjects|External Databases|\Z)", 
                                               db_searches_section, re.DOTALL)
                if adverse_section_match:
                    adverse_section = adverse_section_match.group(1)
                    
                    # Look for specific results
                    adverse_results_match = re.search(r"No adverse media found", adverse_section)
                    if adverse_results_match:
                        database_searches["adverse_media"]["results"] = adverse_results_match.group(0)
                    else:
                        database_searches["adverse_media"]["results"] = adverse_section.strip()
                
                # Extract risk ratings
                risk_ratings_section_match = re.search(r"Risk Ratings(.*?)(?=Adverse Media|\Z)", db_searches_section, re.DOTALL)
                if risk_ratings_section_match:
                    risk_ratings_section = risk_ratings_section_match.group(1)
                    
                    # Try to extract risk ratings from table-like structure
                    risk_rating_rows = re.findall(r"([A-Z][A-Z\s]+(?:[A-Z]\.?\s)?[A-Z][A-Z]+)\s+([0-9]+)\s+([A-Z]+)\s+([^\n]+)", risk_ratings_section)
                    
                    for name, party_key, sor, rating in risk_rating_rows:
                        database_searches["risk_ratings"].append({
                            "name": name.strip(),
                            "party_key": party_key.strip(),
                            "sor": sor.strip(),
                            "rating": rating.strip()
                        })
        
        return database_searches
    
    def get_main_review_period(self) -> Dict[str, str]:
        """
        Get the main review period from alert info
        
        Returns:
            Dict: Review period start and end dates
        """
        review_period = {
            "start": "",
            "end": ""
        }
        
        # Try to get from alerts
        if self.data["alert_info"]:
            for alert in self.data["alert_info"]:
                if alert["review_period"]["start"] and alert["review_period"]["end"]:
                    review_period = alert["review_period"]
                    break
        
        # Try to get from case review period in text
        if not review_period["start"] or not review_period["end"]:
            if not isinstance(self.raw_data, dict):
                review_period_match = re.search(r"Case review period:?\s*(\d{1,2}/\d{1,2}/\d{2,4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{2,4})", 
                                              self.raw_data)
                if review_period_match:
                    review_period["start"] = review_period_match.group(1)
                    review_period["end"] = review_period_match.group(2)
        
        return review_period
    
    def process(self) -> Dict[str, Any]:
        """
        Process the case document
        
        Returns:
            Dict: All extracted data from case document
        """
        if not self.load_document():
            return self.data
        
        logger.info("Extracting case number...")
        self.data["case_number"] = self.extract_case_number()
        
        logger.info("Extracting alert information...")
        self.data["alert_info"] = self.extract_alert_info()
        
        logger.info("Extracting subjects...")
        self.data["subjects"] = self.extract_subjects()
        
        logger.info("Extracting accounts...")
        self.data["accounts"] = self.extract_accounts()
        if self.data["accounts"]:
            # Use the first account as the primary one
            self.data["account_info"] = self.data["accounts"][0]
        else:
            logger.info("Extracting primary account info...")
            self.data["account_info"] = self.extract_account_info()
        
        logger.info("Extracting prior cases...")
        self.data["prior_cases"] = self.extract_prior_cases()
        
        logger.info("Extracting database searches...")
        self.data["database_searches"] = self.extract_database_searches()
        
        logger.info("Getting main review period...")
        self.data["review_period"] = self.get_main_review_period()
        
        return self.data