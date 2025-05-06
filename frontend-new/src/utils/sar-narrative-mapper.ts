// This file implements the data mapping between backend data and SAR narrative sections

import { NarrativeSections } from '../types';

/**
 * Maps backend response data to frontend narrative sections
 * @param response The API response containing case and transaction data
 * @returns Structured narrative sections for UI display
 */
export function mapBackendDataToSections(response: any): NarrativeSections {
  // Create a case info object for reference data
  const caseInfo = {
    caseNumber: response.case_data?.case_number || '',
    accountNumber: response.case_data?.account_info?.account_number || '',
    dateGenerated: new Date().toISOString()
  };

  // Get the primary subject name
  const primarySubject = response.case_data?.subjects?.find((s: any) => s.is_primary)?.name || 
                        (response.case_data?.subjects?.[0]?.name || 'Unknown Subject');

  // Map the backend data to the expected frontend section structure
  const templateSections: NarrativeSections = {
    // B. SAR/No SAR Recommendation
    "alerting_activity": {
      id: "alerting_activity",
      title: "Alerting Activity / Reason for Review",
      content: formatAlertingActivity(response.case_data, response.alert_info)
    },
    "prior_sars": {
      id: "prior_sars",
      title: "Prior SARs",
      content: formatPriorSARs(response.case_data?.prior_cases)
    },
    "scope_of_review": {
      id: "scope_of_review",
      title: "Scope of Review",
      content: formatScopeOfReview(response.case_data?.review_period, response.case_data?.alert_info)
    },
    "investigation_summary": {
      id: "investigation_summary",
      title: "Summary of the Investigation",
      content: formatInvestigationSummary(response.excel_data, response.case_data)
    },
    "recommendation_conclusion": {
      id: "recommendation_conclusion",
      title: "Conclusion",
      content: formatRecommendationConclusion(response)
    },
    
    // C. Escalations/Referrals
    "cta": {
      id: "cta",
      title: "CTA",
      content: formatCTAInfo(response.case_data, response.excel_data)
    },
    
    // D. Retain or Close Customer Relationship(s)
    "retain_close": {
      id: "retain_close",
      title: "Retain or Close Customer Relationship(s)",
      content: formatRetainClose(response.case_data)
    },
    
    // SAR Narrative sections
    "introduction": {
      id: "introduction",
      title: "Introduction",
      content: response.sections?.introduction?.content || formatIntroduction(response)
    },
    "subject_account_info": {
      id: "subject_account_info",
      title: "Subject/Account Information",
      content: response.sections?.account_info?.content || 
               formatSubjectAccountInfo(response.case_data)
    },
    "suspicious_activity": {
      id: "suspicious_activity",
      title: "Suspicious Activity",
      content: response.sections?.activity_summary?.content || 
               formatSuspiciousActivity(response.excel_data, response.case_data)
    },
    "transaction_samples": {
      id: "transaction_samples",
      title: "Suspicious Transaction Samples",
      content: response.sections?.transaction_samples?.content || 
               formatTransactionSamples(response.excel_data)
    },
    "sar_conclusion": {
      id: "sar_conclusion",
      title: "SAR Conclusion",
      content: response.sections?.conclusion?.content || 
               formatSARConclusion(response.case_data, response.excel_data)
    }
  };
  
  return templateSections;
}

/**
 * Formats alerting activity section
 */
function formatAlertingActivity(caseData: any, alertInfo: any): string {
  if (!caseData) return '';
  
  const caseNumber = caseData.case_number || '';
  const accountInfo = caseData.account_info || {};
  const accountNumber = accountInfo.account_number || '';
  const accountType = accountInfo.account_type || '';
  
  // Get alert information
  let alertDescription = '';
  if (Array.isArray(caseData.alert_info) && caseData.alert_info.length > 0) {
    alertDescription = caseData.alert_info[0].description || '';
  } else if (caseData.alert_info?.description) {
    alertDescription = caseData.alert_info.description;
  }
  
  return `Case Number: ${caseNumber}
Account Number: ${accountNumber}
Account Type: ${accountType}

Alert Information:
${alertDescription}

This case was selected for review due to the above alerting activity that indicates potential suspicious behavior requiring further investigation.`;
}

/**
 * Formats prior SARs section
 */
function formatPriorSARs(priorCases: any[]): string {
  if (!priorCases || priorCases.length === 0) {
    return 'No prior SARs were identified for the subjects or account.';
  }
  
  let priorSARsText = 'The following prior SARs were identified:\n\n';
  
  priorCases.forEach((priorCase, index) => {
    const caseNumber = priorCase.case_number || '';
    const filingDate = priorCase.filing_date || 'Unknown filing date';
    const summary = priorCase.summary || 'No summary available';
    
    priorSARsText += `Prior SAR #${index + 1}: Case Number ${caseNumber}\n`;
    priorSARsText += `Filing Date: ${filingDate}\n`;
    priorSARsText += `Summary: ${summary}\n\n`;
  });
  
  return priorSARsText;
}

/**
 * Formats scope of review section
 */
function formatScopeOfReview(reviewPeriod: any, alertInfo: any): string {
  if (!reviewPeriod) {
    // Try to extract from alert info
    if (Array.isArray(alertInfo) && alertInfo.length > 0 && alertInfo[0].review_period) {
      reviewPeriod = alertInfo[0].review_period;
    } else if (alertInfo?.review_period) {
      reviewPeriod = alertInfo.review_period;
    } else {
      return 'Review period not specified.';
    }
  }
  
  const startDate = reviewPeriod.start || '';
  const endDate = reviewPeriod.end || '';
  
  if (!startDate || !endDate) {
    return 'Review period not fully specified.';
  }
  
  return `This investigation covers the period from ${startDate} through ${endDate}. The review included analysis of account statements, transaction records, customer information, and related documentation to identify potentially suspicious activity.`;
}

/**
 * Formats investigation summary
 */
function formatInvestigationSummary(excelData: any, caseData: any): string {
  if (!excelData || !caseData) return '';
  
  const accountInfo = caseData.account_info || {};
  const accountNumber = accountInfo.account_number || '';
  const subjects = caseData.subjects || [];
  const primarySubject = subjects.find((s: any) => s.is_primary)?.name || 
                        (subjects[0]?.name || 'Unknown Subject');
  
  // Get transaction summary
  const transactionSummary = excelData.transaction_summary || {};
  const totalCredits = formatCurrency(transactionSummary.total_credits || 0);
  const totalDebits = formatCurrency(transactionSummary.total_debits || 0);
  
  // Get activity summary
  const activitySummary = excelData.activity_summary || {};
  const startDate = activitySummary.start_date || '';
  const endDate = activitySummary.end_date || '';
  const totalAmount = formatCurrency(activitySummary.total_amount || 0);
  
  // Try to determine the type of suspicious activity
  let activityType = "suspicious activity";
  let suspiciousIndicators = "";
  
  if (excelData.unusual_activity) {
    const unusualActivity = excelData.unusual_activity;
    
    if (unusualActivity.transactions && unusualActivity.transactions.length > 0) {
      // Check for patterns indicating structuring
      const belowCTRThreshold = unusualActivity.transactions.filter(
        (t: any) => t.amount >= 8000 && t.amount < 10000
      ).length;
      
      if (belowCTRThreshold >= 2) {
        activityType = "structuring";
        suspiciousIndicators = "- Multiple cash transactions just below CTR threshold\n- Pattern of transactions designed to evade reporting requirements";
      } else {
        // Check for high volume wire/ACH activity
        const wireTransactions = unusualActivity.transactions.filter(
          (t: any) => (t.type || "").toLowerCase().includes("wire") || 
                     (t.type || "").toLowerCase().includes("ach")
        ).length;
        
        if (wireTransactions >= 3) {
          activityType = "unusual wire/ACH activity";
          suspiciousIndicators = "- High volume of wire/ACH transactions\n- Transfers to/from high-risk jurisdictions or entities";
        } else {
          // Check for cash activity
          const cashTransactions = unusualActivity.transactions.filter(
            (t: any) => (t.type || "").toLowerCase().includes("cash")
          ).length;
          
          if (cashTransactions >= 3) {
            activityType = "unusual cash activity";
            suspiciousIndicators = "- Large cash deposits without apparent business purpose\n- Cash deposits followed by wire transfers";
          }
        }
      }
    }
  }
  
  if (!suspiciousIndicators) {
    suspiciousIndicators = "- Unusual transaction patterns inconsistent with customer profile\n- Transactions lacking legitimate business purpose";
  }
  
  return `Account ${accountNumber} for ${primarySubject} showed ${activityType} during the period from ${startDate} to ${endDate}.

Transaction Summary:
- Total Credits: ${totalCredits}
- Total Debits: ${totalDebits}
- Total Suspicious Amount: ${totalAmount}

Suspicious Activity Indicators:
${suspiciousIndicators}

This activity appears unusual based on the customer's known profile, business type, and previous transaction history. The pattern of transactions suggests potential money laundering or other illicit financial activity.`;
}

/**
 * Formats recommendation conclusion
 */
function formatRecommendationConclusion(response: any): string {
  const caseData = response.case_data || {};
  const excelData = response.excel_data || {};
  
  const caseNumber = caseData.case_number || '';
  const accountInfo = caseData.account_info || {};
  const accountNumber = accountInfo.account_number || '';
  
  const subjects = caseData.subjects || [];
  const subjectNames = subjects.map((s: any) => s.name).join(', ') || 'Unknown Subject(s)';
  
  // Get activity summary
  const activitySummary = excelData.activity_summary || {};
  const startDate = activitySummary.start_date || '';
  const endDate = activitySummary.end_date || '';
  const totalAmount = formatCurrency(activitySummary.total_amount || 0);
  
  return `Based on the investigation findings, a SAR filing is recommended for case ${caseNumber}. 

The SAR will report ${totalAmount} in suspicious activity conducted through account ${accountNumber} by ${subjectNames} from ${startDate} through ${endDate}.

The activity appears deliberately structured to avoid detection and reporting requirements, and is inconsistent with the stated purpose of the account and the customer's known business activities.`;
}

/**
 * Formats CTA section
 */
function formatCTAInfo(caseData: any, excelData: any): string {
  const subjects = caseData?.subjects || [];
  if (subjects.length === 0) return '';
  
  const primarySubject = subjects.find((s: any) => s.is_primary) || subjects[0] || {};
  const subjectName = primarySubject.name || 'Unknown Subject';
  const occupation = primarySubject.occupation || 'Unknown Occupation';
  const employer = primarySubject.employer || 'Unknown Employer';
  
  // Try to determine business nature based on available data
  let businessNature = "Unknown";
  if (occupation.toLowerCase().includes("doctor") || occupation.toLowerCase().includes("dentist")) {
    businessNature = "Healthcare Professional";
  } else if (occupation.toLowerCase().includes("attorney") || occupation.toLowerCase().includes("lawyer")) {
    businessNature = "Legal Professional";
  }
  
  return `Subject Name: ${subjectName}
Occupation: ${occupation}
Employer: ${employer}
Nature of Business: ${businessNature}

Transaction Patterns:
Based on the transaction analysis, this customer typically engages in standard banking activities including direct deposits, ATM withdrawals, and debit card purchases. The suspicious activity identified represents a significant deviation from established patterns.

The customer has been with the bank since ${caseData.account_info?.open_date || 'Unknown'} and maintains ${caseData.accounts?.length || 1} account(s).

Customer Risk Assessment: Medium-High Risk due to the unusual transaction patterns identified in this investigation.`;
}

/**
 * Formats retain or close section
 */
function formatRetainClose(caseData: any): string {
  const accountInfo = caseData?.account_info || {};
  const accountStatus = accountInfo.status || '';
  
  // Default to retain unless account is already closed
  const isAccountClosed = accountStatus.toLowerCase().includes("closed");
  
  if (isAccountClosed) {
    return `Account Relationship Status: CLOSED

The customer relationship has already been closed as of ${accountInfo.close_date || 'Unknown Date'}.

Closure Reason: ${accountInfo.closure_reason || 'Suspicious Activity'}`;
  } else {
    return `Account Relationship Status: RETAIN

Despite the filing of this SAR, it is recommended to retain the customer relationship at this time while implementing enhanced monitoring for the account.

Justification:
- This appears to be an isolated incident
- Customer has a long-standing relationship with the bank
- The suspicious activity has been properly documented and reported
- Continued monitoring will provide additional insight into any potential future suspicious behavior`;
  }
}

/**
 * Formats SAR narrative introduction
 */
function formatIntroduction(response: any): string {
  const caseData = response.case_data || {};
  const excelData = response.excel_data || {};
  
  // Determine activity type
  let activityType = "suspicious activity";
  const unusualActivity = excelData.unusual_activity || {};
  
  if (unusualActivity.transactions && unusualActivity.transactions.length > 0) {
    // Check for patterns indicating structuring
    const belowCTRThreshold = unusualActivity.transactions.filter(
      (t: any) => t.amount >= 8000 && t.amount < 10000
    ).length;
    
    if (belowCTRThreshold >= 2) {
      activityType = "structuring";
    } else {
      // Check for high volume wire/ACH activity
      const wireTransactions = unusualActivity.transactions.filter(
        (t: any) => (t.type || "").toLowerCase().includes("wire") || 
                   (t.type || "").toLowerCase().includes("ach")
      ).length;
      
      if (wireTransactions >= 3) {
        activityType = "wire transfer activity";
      } else {
        // Check for cash activity
        const cashTransactions = unusualActivity.transactions.filter(
          (t: any) => (t.type || "").toLowerCase().includes("cash")
        ).length;
        
        if (cashTransactions >= 3) {
          activityType = "cash activity";
        }
      }
    }
  }
  
  const accountInfo = caseData.account_info || {};
  const accountNumber = accountInfo.account_number || '';
  const accountType = accountInfo.account_type || 'account';
  
  const subjects = caseData.subjects || [];
  const subjectNames = subjects.map((s: any) => s.name).join(', ') || 'Unknown Subject(s)';
  
  const activitySummary = excelData.activity_summary || {};
  const startDate = activitySummary.start_date || '';
  const endDate = activitySummary.end_date || '';
  const totalAmount = formatCurrency(activitySummary.total_amount || 0);
  
  return `U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report ${activityType} totaling ${totalAmount} derived from credits and debits by ${subjectNames} in ${accountType} account number ${accountNumber}. The suspicious activity was conducted from ${startDate} through ${endDate}.`;
}

/**
 * Formats subject and account information
 */
function formatSubjectAccountInfo(caseData: any): string {
  const subjects = caseData?.subjects || [];
  const accountInfo = caseData?.account_info || {};
  
  let subjectText = '';
  
  // Format subject information
  subjects.forEach((subject: any, index: number) => {
    const name = subject.name || 'Unknown Subject';
    const occupation = subject.occupation || '';
    const employer = subject.employer || '';
    const relationship = subject.account_relationship || '';
    const address = subject.address || '';
    
    subjectText += `${name}`;
    
    if (occupation || employer) {
      subjectText += ` is employed as a ${occupation}${employer ? ` at ${employer}` : ''}. `;
    } else {
      subjectText += `. `;
    }
    
    if (relationship) {
      subjectText += `${name} is listed as ${relationship} on the account. `;
    }
    
    if (address) {
      subjectText += `Address: ${address}. `;
    }
    
    if (index < subjects.length - 1) {
      subjectText += '\n\n';
    }
  });
  
  // Format account information
  const accountNumber = accountInfo.account_number || '';
  const accountType = accountInfo.account_type || '';
  const openDate = accountInfo.open_date || '';
  const closeDate = accountInfo.close_date || '';
  const status = accountInfo.status || '';
  const isOpen = !closeDate || !status.toLowerCase().includes('closed');
  
  let accountText = `\n\nPersonal ${accountType} account ${accountNumber} was opened on ${openDate}`;
  
  if (isOpen) {
    accountText += ' and remains open.';
  } else {
    accountText += ` and was closed on ${closeDate}.`;
  }
  
  return subjectText + accountText;
}

/**
 * Formats suspicious activity section
 */
function formatSuspiciousActivity(excelData: any, caseData: any): string {
  const accountInfo = caseData?.account_info || {};
  const accountNumber = accountInfo.account_number || '';
  
  const activitySummary = excelData?.activity_summary || {};
  const startDate = activitySummary.start_date || '';
  const endDate = activitySummary.end_date || '';
  
  const transactionSummary = excelData?.transaction_summary || {};
  const totalCredits = formatCurrency(transactionSummary.total_credits || 0);
  const totalDebits = formatCurrency(transactionSummary.total_debits || 0);
  
  // Get transaction patterns
  let transactionPatterns = '';
  const creditBreakdown = transactionSummary.credit_breakdown || [];
  const debitBreakdown = transactionSummary.debit_breakdown || [];
  
  if (creditBreakdown.length > 0) {
    transactionPatterns += 'The primary credit transaction types were ';
    transactionPatterns += creditBreakdown.slice(0, 3).map((item: any) => 
      `${item.type} (${formatCurrency(item.amount)}, ${item.count} transactions)`
    ).join(', ') + '. ';
  }
  
  if (debitBreakdown.length > 0) {
    transactionPatterns += 'The primary debit transaction types were ';
    transactionPatterns += debitBreakdown.slice(0, 3).map((item: any) => 
      `${item.type} (${formatCurrency(item.amount)}, ${item.count} transactions)`
    ).join(', ') + '.';
  }
  
  // Determine suspicious indicators
  let suspiciousIndicators = '';
  const unusualActivity = excelData?.unusual_activity || {};
  const transactions = unusualActivity.transactions || [];
  
  // Identify common suspicious patterns
  const belowCTRThreshold = transactions.filter(
    (t: any) => t.amount >= 8000 && t.amount < 10000
  ).length;
  
  const wireTransactions = transactions.filter(
    (t: any) => (t.type || "").toLowerCase().includes("wire") || 
               (t.type || "").toLowerCase().includes("ach")
  ).length;
  
  const cashTransactions = transactions.filter(
    (t: any) => (t.type || "").toLowerCase().includes("cash")
  ).length;
  
  if (belowCTRThreshold >= 2) {
    suspiciousIndicators += '- Multiple cash transactions just below CTR threshold\n';
    suspiciousIndicators += '- Pattern of transactions designed to evade reporting requirements\n';
    suspiciousIndicators += '- Structured transactions to avoid detection\n';
  }
  
  if (wireTransactions >= 3) {
    suspiciousIndicators += '- High volume of wire/ACH transactions\n';
    suspiciousIndicators += '- Transfers to/from high-risk jurisdictions or entities\n';
    suspiciousIndicators += '- Rapid movement of funds through the account\n';
  }
  
  if (cashTransactions >= 3) {
    suspiciousIndicators += '- Large cash deposits without apparent business purpose\n';
    suspiciousIndicators += '- Cash deposits followed by immediate withdrawals\n';
    suspiciousIndicators += '- No legitimate business reason for cash activity volume\n';
  }
  
  if (!suspiciousIndicators) {
    suspiciousIndicators += '- Unusual transaction patterns inconsistent with customer profile\n';
    suspiciousIndicators += '- Transactions lacking legitimate business purpose\n';
    suspiciousIndicators += '- Activity inconsistent with stated account purpose\n';
  }
  
  return `The account activity for ${accountNumber} from ${startDate} to ${endDate} included total credits of ${totalCredits} and total debits of ${totalDebits}.

${transactionPatterns}

The AML risks associated with these transactions are as follows:
${suspiciousIndicators}

This activity appears unusual based on the customer's known profile, business type, and previous transaction history.`;
}

/**
 * Formats transaction samples section
 */
function formatTransactionSamples(excelData: any): string {
  const unusualActivity = excelData?.unusual_activity || {};
  const transactions = unusualActivity.transactions || [];
  
  if (transactions.length === 0) {
    return 'No suspicious transaction samples available.';
  }
  
  let samplesText = 'A sample of the suspicious transactions includes:';
  
  // Get up to 5 transactions to showcase
  const sampleCount = Math.min(5, transactions.length);
  
  for (let i = 0; i < sampleCount; i++) {
    const txn = transactions[i];
    const date = txn.date || '';
    const amount = formatCurrency(txn.amount || 0);
    const txnType = txn.type || '';
    const desc = txn.description || '';
    
    samplesText += ` ${date}: ${amount}`;
    if (txnType) {
      samplesText += ` (${txnType})`;
    }
    if (desc) {
      samplesText += ` - ${desc}`;
    }
    
    if (i < sampleCount - 1) {
      samplesText += ';';
    } else {
      samplesText += '.';
    }
  }
  
  return samplesText;
}

/**
 * Formats SAR conclusion section
 */
function formatSARConclusion(caseData: any, excelData: any): string {
  const caseNumber = caseData?.case_number || '';
  const accountInfo = caseData?.account_info || {};
  const accountNumber = accountInfo.account_number || '';
  
  const subjects = caseData?.subjects || [];
  const subjectNames = subjects.map((s: any) => s.name).join(', ') || 'Unknown Subject(s)';
  
  const activitySummary = excelData?.activity_summary || {};
  const startDate = activitySummary.start_date || '';
  const endDate = activitySummary.end_date || '';
  const totalAmount = formatCurrency(activitySummary.total_amount || 0);
  
  // Determine activity type
  let activityType = "suspicious activity";
  const unusualActivity = excelData?.unusual_activity || {};
  const transactions = unusualActivity.transactions || [];
  
  if (transactions.length > 0) {
    // Check for patterns indicating structuring
    const belowCTRThreshold = transactions.filter(
      (t: any) => t.amount >= 8000 && t.amount < 10000
    ).length;
    
    if (belowCTRThreshold >= 2) {
      activityType = "structuring";
    } else {
      // Check for high volume wire/ACH activity
      const wireTransactions = transactions.filter(
        (t: any) => (t.type || "").toLowerCase().includes("wire") || 
                   (t.type || "").toLowerCase().includes("ach")
      ).length;
      
      if (wireTransactions >= 3) {
        activityType = "wire transfer activity";
      } else {
        // Check for cash activity
        const cashTransactions = transactions.filter(
          (t: any) => (t.type || "").toLowerCase().includes("cash")
        ).length;
        
        if (cashTransactions >= 3) {
          activityType = "cash activity";
        }
      }
    }
  }
  
  return `In conclusion, USB is reporting ${totalAmount} in ${activityType} which gave the appearance of suspicious activity and were conducted by ${subjectNames} in account number ${accountNumber} from ${startDate} through ${endDate}. USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequests@usbank.com referencing AML case number ${caseNumber}.`;
}

/**
 * Formats currency values to standardized format
 */
function formatCurrency(amount: number | string): string {
  if (typeof amount === 'string') {
    // Remove currency symbols and commas
    amount = amount.replace(/[$,]/g, '');
    try {
      amount = parseFloat(amount);
    } catch (error) {
      return '$0.00';
    }
  }
  
  // Format with commas and 2 decimal places
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount);
}