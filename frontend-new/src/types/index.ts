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
    caseFilename: string;
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
  
  // Form Data
  export interface FileUploadFormData {
    caseFile: File | null;
    excelFile: File | null;
  }