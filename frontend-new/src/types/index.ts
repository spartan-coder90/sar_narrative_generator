// Modified frontend-new/src/types/index.ts
// Add CaseSummary type
export interface CaseSummary {
  case_number: string;
  subjects: string[];
  account_number: string;
  alert_count: number;
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

// API Response Types
export interface GenerateResponse {
  status: string;
  sessionId: string;
  caseNumber: string;
  accountNumber: string;
  dateGenerated: string;
  warnings: string[];
  sections: NarrativeSections;
  excelFilename: string;
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
  };
}