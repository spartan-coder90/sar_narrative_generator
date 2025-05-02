# backend/data/case_repository.py
"""
Repository for static case data used in POC
"""
import json
import os
from typing import Dict, List, Any, Optional

CASES = {
    "CC0015823420": {
        "case_number": "CC0015823420",
        "alert_info": [
            {
                "alert_id": "AMLR5881633",
                "alert_month": "201902",
                "description": "Number of Transactions: 2; High Risk Country; Accounts Involved: 4037670331863968; High-Risk Flag:0; Score = 2",
                "review_period": {
                    "start": "02/01/2020",
                    "end": "01/31/2024"
                }
            },
            {
                "alert_id": "IRF_20180124001509SS",
                "alert_month": "201802",
                "description": "ICS transactions occurring in February 2019.",
                "review_period": {
                    "start": "",
                    "end": ""
                }
            }
        ],
        "subjects": [
            {
                "name": "GLENN A BROWDER",
                "is_primary": True,
                "party_key": "00199602848849833",
                "occupation": "Doctor/Dentist",
                "employer": "SUMMIT ORTHOPEDICS",
                "nationality": "US",
                "address": "857 FAIRMOUNT AVE SAINT PAUL MN SAINT PAUL, MINNESOTA, 551053341 UNITED STATES OF AMERICA",
                "account_relationship": "First Co-Owner"
            },
            {
                "name": "MICHAEL R BROWDER",
                "is_primary": False,
                "party_key": "00199934066181087",
                "occupation": "Other (Unemployed)",
                "employer": "",
                "nationality": "US",
                "address": "857 FAIRMOUNT AVE, SAINT PAUL, MN, US, 551053341",
                "account_relationship": "Co-Owner Non-Primary"
            },
            {
                "name": "MICHAEL RHONDA BROWDER",
                "is_primary": False,
                "party_key": "ICS000000099911CO",
                "occupation": "",
                "employer": "",
                "nationality": "",
                "address": "",
                "account_relationship": "Account Signer"
            }
        ],
        "account_info": {
            "account_number": "ICS9999988",
            "account_type": "ICSNPSLV, NPSL Visa",
            "account_title": "BROWDER, GLENN ANDREW",
            "open_date": "09/04/2018",
            "close_date": "",
            "status": "I50 (GOOD ACCOUNT)",
            "related_parties": [
                {"name": "GLENN A BROWDER", "role": "First Co-Owner"},
                {"name": "GLENN ANDREW BROWDER", "role": "Primary"},
                {"name": "MICHAEL R BROWDER", "role": "Co-Owner Non-Primary"},
                {"name": "MICHAEL RHONDA BROWDER", "role": "Account Signer"}
            ],
            "branch": ""
        },
        "accounts": [
            {
                "account_number": "ICS9999988",
                "account_type": "ICSNPSLV, NPSL Visa",
                "account_title": "BROWDER, GLENN ANDREW",
                "open_date": "09/04/2018",
                "close_date": "",
                "status": "I50 (GOOD ACCOUNT)",
                "related_parties": [
                    {"name": "GLENN A BROWDER", "role": "First Co-Owner"},
                    {"name": "GLENN ANDREW BROWDER", "role": "Primary"},
                    {"name": "MICHAEL R BROWDER", "role": "Co-Owner Non-Primary"},
                    {"name": "MICHAEL RHONDA BROWDER", "role": "Account Signer"}
                ],
                "branch": "",
                "credits": {
                    "total_amount": 219.98,
                    "transaction_count": 3,
                    "date_range": {
                        "start": "09/04/2018",
                        "end": "02/11/2019"
                    }
                },
                "debits": {
                    "total_amount": 2419.36,
                    "transaction_count": 13,
                    "date_range": {
                        "start": "09/04/2018",
                        "end": "02/11/2019"
                    }
                }
            },
            {
                "account_number": "0300DDA00000000001047585678",
                "account_type": "DDA85, Platinum Bus MM",
                "account_title": "STEPHEN P MARSHALL CPA",
                "open_date": "11/04/2019",
                "close_date": "",
                "status": "07 (Closed)",
                "related_parties": [
                    {"name": "STEPHEN P MARSHALL CPA", "role": "Authorized Non-Owner"},
                    {"name": "GLENN A BROWDER", "role": "Co-Owner Non-Primary"},
                    {"name": "STEPHEN P MARSHALL CPA", "role": "PRI NON_IND OWNR"}
                ],
                "branch": "MINNEAPOLIS, MINNESOTA, 2797",
                "credits": {
                    "total_amount": 3017.30,
                    "transaction_count": 5,
                    "date_range": {
                        "start": "01/23/2017",
                        "end": "02/06/2018"
                    }
                },
                "debits": {
                    "total_amount": 15.00,
                    "transaction_count": 1,
                    "date_range": {
                        "start": "02/06/2018",
                        "end": "02/06/2018"
                    }
                }
            }
        ],
        "prior_cases": [],
        "database_searches": {
            "kyc": {
                "results": "No WebKYC form links found"
            },
            "adverse_media": {
                "results": "No adverse media found."
            },
            "risk_ratings": [
                {
                    "name": "GLENN A BROWDER",
                    "party_key": "00199602848849833",
                    "sor": "CIS",
                    "rating": "1 Standard"
                },
                {
                    "name": "MICHAEL R BROWDER",
                    "party_key": "00199934066181087",
                    "sor": "CIS",
                    "rating": "1 Standard"
                },
                {
                    "name": "MICHAEL RHONDA BROWDER",
                    "party_key": "ICS000000099911CO",
                    "sor": "ICS",
                    "rating": "N/A N/A"
                }
            ]
        },
        "review_period": {
            "start": "01/01/2017",
            "end": "03/18/2024"
        }
    },
    
    # Second case
    "CC001582389": {
        "case_number": "CC001582389",
        "alert_info": [
            {
                "alert_id": "AMLR5881633",
                "alert_month": "201902",
                "description": "Number of Transactions: 2; High Risk Country; Accounts Involved: 4037670331863968; High-Risk Flag:0; Score = 2",
                "review_period": {
                    "start": "02/01/2020",
                    "end": "01/31/2024"
                }
            },
            {
                "alert_id": "IRF_20180124001509SS",
                "alert_month": "201802",
                "description": "ICS transactions occurring in February 2019.",
                "review_period": {
                    "start": "",
                    "end": ""
                }
            }
        ],
        "subjects": [
            {
                "name": "GLENN A BROWDER",
                "is_primary": True,
                "party_key": "00199602848849833",
                "occupation": "Doctor/Dentist",
                "employer": "SUMMIT ORTHOPEDICS",
                "nationality": "US",
                "address": "857 FAIRMOUNT AVE SAINT PAUL MN SAINT PAUL, MINNESOTA, 551053341 UNITED STATES OF AMERICA",
                "account_relationship": "First Co-Owner"
            },
            {
                "name": "MICHAEL R BROWDER",
                "is_primary": False,
                "party_key": "00199934066181087",
                "occupation": "Other (Unemployed)",
                "employer": "",
                "nationality": "US",
                "address": "857 FAIRMOUNT AVE, SAINT PAUL, MN, US, 551053341",
                "account_relationship": "Co-Owner Non-Primary"
            },
            {
                "name": "MICHAEL RHONDA BROWDER",
                "is_primary": False,
                "party_key": "ICS000000099911CO",
                "occupation": "",
                "employer": "",
                "nationality": "",
                "address": "",
                "account_relationship": "Account Signer"
            }
        ],
        "account_info": {
            "account_number": "ICS9999988",
            "account_type": "ICSNPSLV, NPSL Visa",
            "account_title": "BROWDER, GLENN ANDREW",
            "open_date": "09/04/2018",
            "close_date": "",
            "status": "I50 (GOOD ACCOUNT)",
            "related_parties": [
                {"name": "GLENN A BROWDER", "role": "First Co-Owner"},
                {"name": "GLENN ANDREW BROWDER", "role": "Primary"},
                {"name": "MICHAEL R BROWDER", "role": "Co-Owner Non-Primary"},
                {"name": "MICHAEL RHONDA BROWDER", "role": "Account Signer"}
            ],
            "branch": ""
        },
        "accounts": [
            {
                "account_number": "ICS9999988",
                "account_type": "ICSNPSLV, NPSL Visa",
                "account_title": "BROWDER, GLENN ANDREW",
                "open_date": "09/04/2018",
                "close_date": "",
                "status": "I50 (GOOD ACCOUNT)",
                "related_parties": [
                    {"name": "GLENN A BROWDER", "role": "First Co-Owner"},
                    {"name": "GLENN ANDREW BROWDER", "role": "Primary"},
                    {"name": "MICHAEL R BROWDER", "role": "Co-Owner Non-Primary"},
                    {"name": "MICHAEL RHONDA BROWDER", "role": "Account Signer"}
                ],
                "branch": "",
                "credits": {
                    "total_amount": 219.98,
                    "transaction_count": 3,
                    "date_range": {
                        "start": "09/04/2018",
                        "end": "02/11/2019"
                    }
                },
                "debits": {
                    "total_amount": 2419.36,
                    "transaction_count": 13,
                    "date_range": {
                        "start": "09/04/2018",
                        "end": "02/11/2019"
                    }
                }
            },
            {
                "account_number": "0300DDA00000000001047585678",
                "account_type": "DDA85, Platinum Bus MM",
                "account_title": "STEPHEN P MARSHALL CPA",
                "open_date": "11/04/2019",
                "close_date": "",
                "status": "07 (Closed)",
                "related_parties": [
                    {"name": "STEPHEN P MARSHALL CPA", "role": "Authorized Non-Owner"},
                    {"name": "GLENN A BROWDER", "role": "Co-Owner Non-Primary"},
                    {"name": "STEPHEN P MARSHALL CPA", "role": "PRI NON_IND OWNR"}
                ],
                "branch": "MINNEAPOLIS, MINNESOTA, 2797",
                "credits": {
                    "total_amount": 3017.30,
                    "transaction_count": 5,
                    "date_range": {
                        "start": "01/23/2017",
                        "end": "02/06/2018"
                    }
                },
                "debits": {
                    "total_amount": 15.00,
                    "transaction_count": 1,
                    "date_range": {
                        "start": "02/06/2018",
                        "end": "02/06/2018"
                    }
                }
            }
        ],
        "prior_cases": [],
        "database_searches": {
            "kyc": {
                "results": "No WebKYC form links found"
            },
            "adverse_media": {
                "results": "No adverse media found."
            },
            "risk_ratings": [
                {
                    "name": "GLENN A BROWDER",
                    "party_key": "00199602848849833",
                    "sor": "CIS",
                    "rating": "1 Standard"
                },
                {
                    "name": "MICHAEL R BROWDER",
                    "party_key": "00199934066181087",
                    "sor": "CIS",
                    "rating": "1 Standard"
                },
                {
                    "name": "MICHAEL RHONDA BROWDER",
                    "party_key": "ICS000000099911CO",
                    "sor": "ICS",
                    "rating": "N/A N/A"
                }
            ]
        },
        "review_period": {
            "start": "01/01/2017",
            "end": "03/18/2024"
        }
    }
}

def get_case(case_number: str) -> Optional[Dict[str, Any]]:
    """
    Get case data by case number
    
    Args:
        case_number: Case number to retrieve
        
    Returns:
        Dict: Case data or None if not found
    """
    return CASES.get(case_number)

def get_available_cases() -> List[Dict[str, Any]]:
    """
    Get list of available cases for UI dropdown
    
    Returns:
        List[Dict]: List of case summary objects
    """
    return [
        {
            "case_number": case_number,
            "subjects": [s["name"] for s in case_data["subjects"]],
            "account_number": case_data["account_info"]["account_number"],
            "alert_count": len(case_data["alert_info"])
        }
        for case_number, case_data in CASES.items()
    ]