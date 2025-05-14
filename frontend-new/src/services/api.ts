// Updated API service with alerting activity endpoint

import axios from 'axios';
import { 
  GenerateResponse, 
  UpdateSectionResponse, 
  RegenerateSectionResponse,
  CaseSummary,
  SectionResponse,
  AlertingActivitySummary
} from '../types';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8081/api';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// API Service
export const ApiService = {
  // Get available cases for dropdown
  getAvailableCases: async (): Promise<{ cases: CaseSummary[] }> => {
    const response = await api.get<{ status: string, cases: CaseSummary[] }>('/cases');
    return response.data;
  },

  // Generate SAR narrative from selected case
  generateNarrativeFromCase: async (caseNumber: string, model: string = 'llama3:8b'): Promise<GenerateResponse> => {
    const response = await api.post<GenerateResponse>('/generate-from-case', {
      case_number: caseNumber,
      model: model
    });
    
    return response.data;
  },
  
  // Get narrative sections for a session
  getSections: async (sessionId: string): Promise<SectionResponse> => {
    try {
      const response = await api.get(`/sections/${sessionId}`);
      
      if (response.data.status === 'success') {
        // Create a properly typed result object
        const result: SectionResponse = {
          status: 'success',
          sections: response.data.sections,
          recommendation: response.data.recommendation || {},
          case_data: response.data.case_data,
          excel_data: response.data.excel_data,
          caseInfo: response.data.caseInfo,
        };
        
        // Add optional properties if they exist
        if (response.data.caseNumber || response.data.case_data?.case_number) {
          result.caseNumber = response.data.caseNumber || response.data.case_data?.case_number;
        }
        
        if (response.data.accountNumber || response.data.case_data?.account_info?.account_number) {
          result.accountNumber = response.data.accountNumber || response.data.case_data?.account_info?.account_number;
        }
        
        result.dateGenerated = response.data.dateGenerated || new Date().toISOString();
        
        return result;
      }
      
      return response.data;
    } catch (error) {
      console.error('Error getting sections:', error);
      throw error;
    }
  },
  
  // Get alerting activity summary
  getAlertingActivitySummary: async (sessionId: string): Promise<AlertingActivitySummary> => {
    try {
      const response = await api.get(`/alerting-activity/${sessionId}`);
      
      if (response.data.status === 'success') {
        return {
          status: 'success',
          alertingActivitySummary: response.data.alertingActivitySummary,
          llmTemplate: response.data.llmTemplate,
          generatedSummary: response.data.generatedSummary
        };
      }
      
      return {
        status: 'error',
        message: response.data.message || 'Unknown error',
        llmTemplate: '',
        generatedSummary: ''
      };
    } catch (error) {
      console.error('Error getting alerting activity summary:', error);
      return {
        status: 'error',
        message: 'Failed to fetch alerting activity summary',
        llmTemplate: '',
        generatedSummary: ''
      };
    }
  },
  
  // Update a specific section of the SAR narrative
  updateSection: async (
    sessionId: string, 
    sectionId: string, 
    content: string
  ): Promise<UpdateSectionResponse> => {
    const response = await api.put<UpdateSectionResponse>(
      `/sections/${sessionId}/${sectionId}`, 
      { content }
    );
    
    return response.data;
  },
  
  // Update a recommendation section
  updateRecommendationSection: async (
    sessionId: string, 
    sectionId: string, 
    content: string
  ): Promise<UpdateSectionResponse> => {
    const response = await api.put<UpdateSectionResponse>(
      `/recommendations/${sessionId}/${sectionId}`, 
      { content }
    );
    
    return response.data;
  },
  
  // Regenerate a specific section (narrative or recommendation)
  regenerateSection: async (
    sessionId: string, 
    sectionId: string
  ): Promise<RegenerateSectionResponse> => {
    const response = await api.post<RegenerateSectionResponse>(
      `/regenerate/${sessionId}/${sectionId}`
    );
    
    return response.data;
  },
  
  // Get export URL
  getExportUrl: (sessionId: string): string => {
    return `${API_BASE_URL}/export/${sessionId}`;
  },

  // Get recommendation export URL
  getRecommendationExportUrl: (sessionId: string): string => {
    return `${API_BASE_URL}/export-recommendation/${sessionId}`;
  },
  // API Service extensions for prior cases
  getPriorCasesSummary: async (sessionId: string): Promise<any> => {
    try {
      const response = await api.get(`/prior-cases/${sessionId}`);
      
      if (response.data.status === 'success') {
        return {
          status: 'success',
          priorCases: response.data.priorCases,
          prompt: response.data.prompt,
          generatedSummary: response.data.generatedSummary
        };
      }
      
      return {
        status: 'error',
        message: response.data.message || 'Unknown error',
        prompt: '',
        generatedSummary: ''
      };
    } catch (error) {
      console.error('Error getting prior cases summary:', error);
      return {
        status: 'error',
        message: 'Failed to fetch prior cases summary',
        prompt: '',
        generatedSummary: ''
      };
    }
},
regeneratePriorCasesSummary: async (sessionId: string): Promise<any> => {
  try {
    const response = await api.post(`/regenerate-prior-cases/${sessionId}`);
    
    if (response.data.status === 'success') {
      return {
        status: 'success',
        priorCases: response.data.priorCases,
        prompt: response.data.prompt,
        generatedSummary: response.data.generatedSummary
      };
    }
    
    return {
      status: 'error',
      message: response.data.message || 'Unknown error',
      prompt: '',
      generatedSummary: ''
    };
  } catch (error) {
    console.error('Error regenerating prior cases summary:', error);
    return {
      status: 'error',
      message: 'Failed to regenerate prior cases summary',
      prompt: '',
      generatedSummary: ''
    };
  }
}
};

export default ApiService;