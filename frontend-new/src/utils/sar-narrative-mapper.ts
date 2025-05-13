// Updated SAR Narrative Mapper to align with requirements document
import { NarrativeSections, NARRATIVE_SECTION_IDS, NARRATIVE_SECTION_TITLES } from '../types';

/**
 * Maps backend response data to frontend narrative sections based on the updated requirements
 * @param response The API response containing case and transaction data
 * @returns Structured narrative sections for UI display
 */
export function mapBackendDataToSections(response: any): NarrativeSections {
  // Get case data
  const caseData = response.case_data || {};
  const excelData = response.excel_data || {};
  
  // Get Word Control data if available
  const wordControl = excelData.word_control_macro || response.wordControl || {};
  
  // Create a case info object for reference data
  const caseInfo = {
    caseNumber: wordControl.key_values?.["Case Number"] || caseData.case_number || '',
    accountNumber: caseData.account_info?.account_number || '',
    dateGenerated: new Date().toISOString()
  };

  // Get the primary subject name
  const primarySubject = caseData.subjects?.find((s: any) => s.is_primary)?.name || 
                        (caseData.subjects?.[0]?.name || 'Unknown Subject');
  
  // Check for transactions with categories first
  const categoryData = excelData.transactions_summary?.category_summary || {};
  
  // Try to get transaction summary from different sources, preferring new structure
  const transactionSummary = excelData.transactions_summary?.category_summary || 
                             excelData.transaction_summary || {};
  
  // Get activity summary tables if available
  const activitySummaryTables = excelData.activity_summary_tables || {};
  const creditSummary = activitySummaryTables.credit_summary || [];
  const debitSummary = activitySummaryTables.debit_summary || [];
  
  // Get credit totals - try activity tables first, then category summary, then transaction summary
  let totalCredits = 0;
  let totalDebits = 0;
  
  // Try to get totals from credit summary grand total
  const creditGrandTotal = creditSummary.find((row: any) => 
    row["Row Labels"] && typeof row["Row Labels"] === 'string' && 
    row["Row Labels"].toLowerCase().includes('grand total')
  );
  
  if (creditGrandTotal) {
    totalCredits = creditGrandTotal["Total"] || 0;
  } else {
    totalCredits = categoryData.total_credits || transactionSummary.total_credits || 0;
  }
  
  // Try to get totals from debit summary grand total
  const debitGrandTotal = debitSummary.find((row: any) => 
    row["Row Labels"] && typeof row["Row Labels"] === 'string' && 
    row["Row Labels"].toLowerCase().includes('grand total')
  );
  
  if (debitGrandTotal) {
    totalDebits = debitGrandTotal["Total"] || 0;
  } else {
    totalDebits = categoryData.total_debits || transactionSummary.total_debits || 0;
  }
  
  // Format category details if available
  let transactionTypes = '';
  
  if (categoryData.categories && categoryData.categories.length > 0) {
    // Get top credit categories
    const creditCategories = categoryData.categories
      .filter((c: any) => c["Credits ($ Total)"] > 0)
      .sort((a: any, b: any) => b["Credits ($ Total)"] - a["Credits ($ Total)"])
      .slice(0, 3);
      
    if (creditCategories.length > 0) {
      const creditTypes = creditCategories.map((c: any) => 
        `${c["Custom Language Transaction Category"]} (${formatCurrency(c["Credits ($ Total)"])}, ${c["Credits (# Transactions)"]} transactions)`
      ).join(', ');
      
      transactionTypes += `The primary credit transaction types were ${creditTypes}. `;
    }
    
    // Get top debit categories
    const debitCategories = categoryData.categories
      .filter((c: any) => c["Debits ($ Total)"] > 0)
      .sort((a: any, b: any) => b["Debits ($ Total)"] - a["Debits ($ Total)"])
      .slice(0, 3);
      
    if (debitCategories.length > 0) {
      const debitTypes = debitCategories.map((c: any) => 
        `${c["Custom Language Transaction Category"]} (${formatCurrency(c["Debits ($ Total)"])}, ${c["Debits (# Transactions)"]} transactions)`
      ).join(', ');
      
      transactionTypes += `The primary debit transaction types were ${debitTypes}.`;
    }
  } else if (transactionSummary.credit_breakdown && transactionSummary.debit_breakdown) {
    // Fall back to old structure
    const creditBreakdown = transactionSummary.credit_breakdown.slice(0, 3);
    const debitBreakdown = transactionSummary.debit_breakdown.slice(0, 3);
    
    if (creditBreakdown.length > 0) {
      const creditTypes = creditBreakdown.map((item: any) => 
        `${item.type} (${formatCurrency(item.amount)}, ${item.count} transactions)`
      ).join(', ');
      
      transactionTypes += `The primary credit transaction types were ${creditTypes}. `;
    }
    
    if (debitBreakdown.length > 0) {
      const debitTypes = debitBreakdown.map((item: any) => 
        `${item.type} (${formatCurrency(item.amount)}, ${item.count} transactions)`
      ).join(', ');
      
      transactionTypes += `The primary debit transaction types were ${debitTypes}.`;
    }
  }
  
  // Get unusual activity samples
  const unusualActivity = excelData.unusual_activity || {};
  const transactionSamples = unusualActivity.transactions || [];
  
  // Get AML risk indicators
  const amlRisks = "structuring, layering, multi-location activity, rapid movement of funds";
  
  // Get date range from multiple possible sources
  const activitySummary = excelData.activity_summary || {};
  const startDate = wordControl.key_values?.["Start Date"] || activitySummary.start_date || '';
  const endDate = wordControl.key_values?.["End Date"] || activitySummary.end_date || '';
  
  // Create each required section based on requirements document
  return {
    // Section 1 - Suspicious Activity Summary (Introduction, overview, AML indicators)
    [NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_SUMMARY]: {
      id: NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_SUMMARY,
      title: NARRATIVE_SECTION_TITLES[NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_SUMMARY],
      content: `U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report ${transactionTypes} totaling ${formatCurrency(activitySummary.total_amount || 0)} by ${primarySubject} in ${caseData.account_info?.account_type || 'checking/savings'} account number ${caseInfo.accountNumber}. The suspicious activity was conducted from ${startDate} through ${endDate}. The AML indicators were as follows: ${amlRisks}. This SAR contains an attached Comma Separated Value (CSV) file that provides additional details of the suspicious transactions being reported in this SAR.`
    },
    
    // Section 2 - Prior Cases/SARs
    [NARRATIVE_SECTION_IDS.PRIOR_CASES]: {
      id: NARRATIVE_SECTION_IDS.PRIOR_CASES,
      title: NARRATIVE_SECTION_TITLES[NARRATIVE_SECTION_IDS.PRIOR_CASES],
      content: formatPriorCases(caseData.prior_cases || [])
    },
    
    // Section 3 - Account/Subject Information (combined account and subject sections)
    [NARRATIVE_SECTION_IDS.ACCOUNT_SUBJECT_INFO]: {
      id: NARRATIVE_SECTION_IDS.ACCOUNT_SUBJECT_INFO,
      title: NARRATIVE_SECTION_TITLES[NARRATIVE_SECTION_IDS.ACCOUNT_SUBJECT_INFO],
      content: formatAccountSubjectInfo(caseData)
    },
    
    // Section 4 - Suspicious Activity Analysis (previous activity summary + transaction samples)
    [NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_ANALYSIS]: {
      id: NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_ANALYSIS,
      title: NARRATIVE_SECTION_TITLES[NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_ANALYSIS],
      content: `The suspicious activity identified in account ${caseInfo.accountNumber} was conducted from ${startDate} to ${endDate} and consisted of ${transactionTypes}. The AML risks associated with these transactions are as follows: ${amlRisks}.\n\n${formatTransactionSamples(transactionSamples)}`
    },
    
    // Section 5 - Conclusion
    [NARRATIVE_SECTION_IDS.CONCLUSION]: {
      id: NARRATIVE_SECTION_IDS.CONCLUSION,
      title: NARRATIVE_SECTION_TITLES[NARRATIVE_SECTION_IDS.CONCLUSION],
      content: `In conclusion, USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequestaml@usbank.com referencing AML case number ${caseInfo.caseNumber}.`
    }
  };
}

/**
 * Format prior cases section
 */
function formatPriorCases(priorCases: any[]): string {
  if (!priorCases || priorCases.length === 0) {
    return 'No prior SARs were identified for the subjects or account.';
  }
  
  let priorSARsText = '';
  
  priorCases.forEach((priorCase, index) => {
    const caseNumber = priorCase.case_number || '';
    const filingDate = priorCase.filing_date || 'Unknown filing date';
    const summary = priorCase.summary || 'No summary available';
    const alertIds = priorCase.alert_id || [];
    const reviewPeriod = priorCase.review_period || {};
    
    priorSARsText += `Case # ${caseNumber}: Alerting account # reviewed from ${reviewPeriod.start || ''} to ${reviewPeriod.end || ''} due to ${alertIds.join(', ')}.\n`;
    priorSARsText += `SAR filed on ${filingDate}: ${summary}\n\n`;
  });
  
  return priorSARsText;
}

/**
 * Format account and subject information section
 */
function formatAccountSubjectInfo(caseData: any): string {
  const accountInfo = caseData.account_info || {};
  const subjects = caseData.subjects || [];
  
  let accountText = `Personal ${accountInfo.account_type || 'checking/savings'} account ${accountInfo.account_number || ''} was opened on ${accountInfo.open_date || ''} and `;
  
  if (accountInfo.close_date) {
    accountText += `was closed on ${accountInfo.close_date}. `;
    accountText += `The account was closed due to ${accountInfo.closure_reason || '[INVESTIGATOR TO INSERT CLOSURE REASON]'}. `;
    accountText += `The account closure funds were moved to [INVESTIGATOR TO INSERT DESTINATION] on [INVESTIGATOR TO INSERT DATE] via [INVESTIGATOR TO INSERT METHOD].`;
  } else {
    accountText += `remains open.`;
  }
  
  let subjectText = '\n\n';
  
  subjects.forEach((subject: any) => {
    subjectText += `${subject.name || 'Unknown subject'} is employed as a ${subject.occupation || ''} at ${subject.employer || ''}. `;
    
    if (subject.account_relationship) {
      subjectText += `${subject.name} is listed as ${subject.account_relationship} on the account. `;
    }
    
    // Add foreign nationality information if available
    if (subject.nationality && subject.nationality !== 'US' && subject.nationality !== 'USA') {
      subjectText += `\n\nThe following foreign nationalities and identifications were identified for ${subject.name}: ${subject.nationality}, `;
      subjectText += `[INVESTIGATOR TO INSERT ID TYPE] # [INVESTIGATOR TO INSERT ID NUMBER] issued on [ISSUE DATE] and expires on [EXPIRATION DATE].`;
    }
    
    subjectText += '\n\n';
  });
  
  return accountText + subjectText;
}

/**
 * Format transaction samples section
 */
function formatTransactionSamples(transactions: any[]): string {
  if (!transactions || transactions.length === 0) {
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