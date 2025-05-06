// src/services/api.ts
import axios from 'axios';
import { 
  GenerateResponse, 
  UpdateSectionResponse, 
  RegenerateSectionResponse,
  CaseSummary,
  SectionResponse
} from '../types';
import { mapBackendDataToSections } from '../utils/sar-narrative-mapper';

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

  // Generate SAR narrative from selected case and uploaded Excel file
  generateNarrative: async (caseFile: File, excelFile: File): Promise<GenerateResponse> => {
    const formData = new FormData();
    formData.append('caseFile', caseFile);
    formData.append('excelFile', excelFile);
    
    const response = await api.post<GenerateResponse>('/generate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    return response.data;
  },
  
  // Generate SAR narrative from existing case and uploaded Excel file
  generateNarrativeFromCase: async (caseNumber: string, excelFile: File): Promise<GenerateResponse> => {
    const formData = new FormData();
    formData.append('case_number', caseNumber);
    formData.append('excelFile', excelFile);
    
    const response = await api.post<GenerateResponse>('/generate-from-case', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    return response.data;
  },
  
  // Get narrative sections for a session
  getSections: async (sessionId: string): Promise<SectionResponse> => {
    try {
      const response = await api.get(`/sections/${sessionId}`);
      
      // If the response doesn't include properly formatted sections,
      // transform the data to match the expected format
      if (response.data.status === 'success' && response.data.sections) {
        // The response already has sections in the expected format
        return {
          ...response.data,
          caseInfo: {
            caseNumber: response.data.case_data?.case_number || '',
            accountNumber: response.data.case_data?.account_info?.account_number || '',
            dateGenerated: response.data.dateGenerated || new Date().toISOString()
          },
          // Map additional section data if needed
          recommendation: {
            alerting_activity: response.data.sections.introduction?.content || '',
            prior_sars: response.data.sections.prior_cases?.content || '',
            scope_of_review: '',
            summary_of_investigation: response.data.sections.activity_summary?.content || '',
            conclusion: response.data.sections.conclusion?.content || '',
            retain_close: ''
          },
          referrals: {
            CTA: ''
          }
        };
      } else if (response.data.status === 'success') {
        // Transform the data using our mapping utility
        const transformedSections = mapBackendDataToSections(response.data);
        
        return {
          status: 'success',
          sections: transformedSections,
          caseInfo: {
            caseNumber: response.data.case_data?.case_number || '',
            accountNumber: response.data.case_data?.account_info?.account_number || '',
            dateGenerated: response.data.dateGenerated || new Date().toISOString()
          }
        };
      }
      
      return response.data;
    } catch (error) {
      console.error('Error getting sections:', error);
      throw error;
    }
  },
  
  // Update a specific section
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
  
  // Regenerate a specific section
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
  }
};

export default ApiService;