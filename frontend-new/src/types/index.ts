export interface CaseSummary {
  case_number: string;
  subjects: string[];
  account_number: string;
  alert_count: number;
}

// Case Data Types
export interface Subject {
  name: string;
  is_primary: boolean;
  party_key: string;
  occupation: string;
  employer: string;
  nationality: string;
  address: string;
  account_relationship: string;
}

export interface AccountInfo {
  account_number: string;
  account_type: string;
  account_title: string;
  open_date: string;
  close_date: string;
  status: string;
  related_parties: Array<{name: string, role: string}>;
  branch: string;
}

export interface AlertInfo {
  alert_id: string;
  alert_month: string;
  description: string;
  review_period: {
    start: string;
    end: string;
  };
}

export interface PriorCase {
  case_number: string;
  alert_id: string[];
  alert_month: string[];
  review_period: {
    start: string;
    end: string;
  };
  sar_form_number: string;
  filing_date: string;
  summary: string;
}

export interface CaseData {
  case_number: string;
  alert_info: AlertInfo[] | AlertInfo;
  subjects: Subject[];
  account_info: AccountInfo;
  accounts: AccountInfo[];
  prior_cases: PriorCase[];
  database_searches: any;
  review_period: {
    start: string;
    end: string;
  };
}

// Excel Data Types
export interface TransactionSummary {
  total_credits: number;
  total_debits: number;
  credit_breakdown: Array<{
    type: string;
    amount: number;
    count: number;
  }>;
  debit_breakdown: Array<{
    type: string;
    amount: number;
    count: number;
  }>;
}

export interface ActivitySummary {
  start_date: string;
  end_date: string;
  total_amount: number;
  description: string;
  transaction_types: string[];
}

export interface UnusualActivity {
  transactions: Array<{
    date: string;
    amount: number;
    type: string;
    description: string;
    account?: string;
  }>;
  summary?: {
    total_amount: number;
    date_range: {
      start: string;
      end: string;
    };
  };
}

export interface ExcelData {
  activity_summary: ActivitySummary;
  unusual_activity: UnusualActivity;
  transaction_summary: TransactionSummary;
  account_summaries: any;
  cta_sample: any;
  bip_sample: any;
  inter_account_transfers: any[];
}

// Section Types
export interface NarrativeSection {
  id: string;
  title: string;
  content: string;
}

export interface NarrativeSections {
  [key: string]: NarrativeSection;
}

// Recommendation Types - Update to a more flexible type
export interface Recommendation {
  alerting_activity?: string;
  prior_sars?: string;
  scope_of_review?: string;
  investigation_summary?: string;
  conclusion?: string;
  cta?: string;
  retain_close?: string;
  [key: string]: string | undefined;  // Allow string indexing
}

export interface CaseInfo {
  caseNumber: string;
  accountNumber: string;
  dateGenerated: string;
}

// API Response Types
export interface GenerateResponse {
  status: string;
  sessionId: string;
  caseNumber: string;
  accountNumber: string;
  dateGenerated: string;
  warnings: string[];
  sections: NarrativeSections;
  recommendation: Recommendation | Record<string, string>;
  excelFilename: string;
}

export interface SectionResponse {
  status: string;
  sections?: NarrativeSections;
  recommendation?: Recommendation | Record<string, string>;
  caseInfo?: CaseInfo;
  case_data?: CaseData;
  excel_data?: ExcelData;
  // Add these properties to fix the TypeScript errors
  caseNumber?: string;
  accountNumber?: string;
  dateGenerated?: string;
}

export interface ErrorResponse {
  status: string;
  message: string;
  errors?: string[];
  warnings?: string[];
}

export interface UpdateSectionResponse {
  status: string;
  message: string;
}

export interface RegenerateSectionResponse {
  status: string;
  section: {
    id: string;
    content: string;
    type?: string;
  };
}

// Add types for alerting activity summary

export interface AlertInfo {
  caseNumber: string;
  alertingAccounts: string;
  alertingMonths: string;
  alertDescription: string;
}

export interface CreditSummary {
  percentTotal: number;
  amountTotal: number;
  transactionCount: number;
  minCreditAmount: number;
  maxCreditAmount: number;
  minTransactionDate: string;
  maxTransactionDate: string;
  highestPercentType: string;
  highestPercentValue: number;
}

export interface DebitSummary {
  percentTotal: number;
  amountTotal: number;
  transactionCount: number;
  minDebitAmount: number;
  maxDebitAmount: number;
  minTransactionDate: string;
  maxTransactionDate: string;
  highestPercentType: string;
  highestPercentValue: number;
}

export interface AlertingActivityData {
  alertInfo: AlertInfo;
  account: string;
  creditSummary: CreditSummary;
  debitSummary: DebitSummary;
}

export interface AlertingActivitySummary {
  status: string;
  message?: string;
  alertingActivitySummary?: AlertingActivityData;
  llmTemplate?: string;
  generatedSummary?: string;
}