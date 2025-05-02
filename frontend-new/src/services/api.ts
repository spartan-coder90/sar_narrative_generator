// Modified frontend-new/src/services/api.ts
import axios from 'axios';
import { 
  GenerateResponse, 
  UpdateSectionResponse, 
  RegenerateSectionResponse,
  CaseSummary
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

  // Generate SAR narrative from selected case and uploaded Excel file
  generateNarrative: async (caseNumber: string, excelFile: File): Promise<GenerateResponse> => {
    const formData = new FormData();
    formData.append('case_number', caseNumber);
    formData.append('excelFile', excelFile);
    
    const response = await api.post<GenerateResponse>('/generate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    return response.data;
  },
  
  // Get narrative sections for a session
  getSections: async (sessionId: string) => {
    const response = await api.get(`/sections/${sessionId}`);
    return response.data;
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
  
    // Generate SAR narrative from selected case and uploaded Excel file
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
  // Get export URL
  getExportUrl: (sessionId: string): string => {
    return `${API_BASE_URL}/export/${sessionId}`;
  }
};


export default ApiService;