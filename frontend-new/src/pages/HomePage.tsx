// Modified frontend-new/src/pages/HomePage.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Button, Alert, Spinner } from 'react-bootstrap';
import axios from 'axios';
import ApiService from '../services/api';
import { ErrorResponse, CaseSummary } from '../types';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedCase, setSelectedCase] = useState<string>('');
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isLoadingCases, setIsLoadingCases] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [availableCases, setAvailableCases] = useState<CaseSummary[]>([]);
  
  // Fetch available cases on component mount
  useEffect(() => {
    const fetchCases = async () => {
      try {
        setIsLoadingCases(true);
        const response = await ApiService.getAvailableCases();
        setAvailableCases(response.cases);
      } catch (err) {
        console.error('Error fetching available cases:', err);
        setError('Failed to load available cases');
      } finally {
        setIsLoadingCases(false);
      }
    };
    
    fetchCases();
  }, []);
  
  const handleCaseChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedCase(e.target.value);
  };
  
  const handleExcelFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setExcelFile(e.target.files[0]);
    }
  };
  
  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    // Reset state
    setError(null);
    setWarnings([]);
    
    // Validate input
    if (!selectedCase) {
      setError('Please select a case');
      return;
    }
    
    if (!excelFile) {
      setError('Excel file is required');
      return;
    }
    
    // Show loading state
    setIsLoading(true);
    
    try {
      // Call API to generate narrative
      const response = await ApiService.generateNarrativeFromCase(selectedCase, excelFile);
      
      // Check if there are warnings
      if (response.warnings && response.warnings.length > 0) {
        setWarnings(response.warnings);
      }
      
      // Redirect to edit page
      navigate(`/edit/${response.sessionId}`);
    } catch (err) {
      console.error('Error generating narrative:', err);
      
      // Handle error response
      if (axios.isAxiosError(err) && err.response?.data) {
        const errorData = err.response.data as ErrorResponse;
        setError(errorData.message || 'An error occurred while processing the files');
        
        if (errorData.warnings) {
          setWarnings(errorData.warnings);
        }
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="container mt-4">
      <div className="row">
        <div className="col-md-8 offset-md-2">
          <h1 className="mb-4">SAR Narrative Generator</h1>
          
          <Card className="shadow-sm">
            <Card.Header className="bg-primary text-white">
              <h4 className="mb-0">Select Case & Upload Transactions</h4>
            </Card.Header>
            <Card.Body>
              <Form onSubmit={handleSubmit}>
                <Form.Group className="mb-3">
                  <Form.Label>Select Case</Form.Label>
                  <Form.Select
                    value={selectedCase}
                    onChange={handleCaseChange}
                    disabled={isLoadingCases}
                  >
                    <option value="">Select a case...</option>
                    // Continuing frontend-new/src/pages/HomePage.tsx
                    {availableCases.map((caseItem) => (
                      <option key={caseItem.case_number} value={caseItem.case_number}>
                        {caseItem.case_number} - {caseItem.subjects.join(', ')}
                      </option>
                    ))}
                  </Form.Select>
                  {isLoadingCases && (
                    <div className="text-center mt-2">
                      <Spinner animation="border" size="sm" />
                      <span className="ms-2">Loading cases...</span>
                    </div>
                  )}
                  <Form.Text className="text-muted">
                    Select a case from the available options.
                  </Form.Text>
                </Form.Group>
                
                <Form.Group className="mb-3">
                  <Form.Label>Transaction Excel File</Form.Label>
                  <Form.Control 
                    type="file" 
                    onChange={handleExcelFileChange}
                    accept=".xlsx,.xls,.csv"
                  />
                  <Form.Text className="text-muted">
                    Upload the Excel file containing transaction data.
                  </Form.Text>
                </Form.Group>
                
                <div className="d-grid">
                  <Button 
                    variant="primary" 
                    type="submit" 
                    disabled={isLoading || !selectedCase || !excelFile}
                  >
                    {isLoading ? (
                      <>
                        <Spinner 
                          as="span" 
                          animation="border" 
                          size="sm" 
                          role="status" 
                          aria-hidden="true" 
                          className="me-2"
                        />
                        Processing...
                      </>
                    ) : (
                      'Generate SAR Narrative'
                    )}
                  </Button>
                </div>
              </Form>
            </Card.Body>
          </Card>
          
          {error && (
            <Alert variant="danger" className="mt-3">
              <Alert.Heading>Error</Alert.Heading>
              <p>{error}</p>
            </Alert>
          )}
          
          {warnings.length > 0 && (
            <Alert variant="warning" className="mt-3">
              <Alert.Heading>Warnings</Alert.Heading>
              <ul className="mb-0">
                {warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </Alert>
          )}
        </div>
      </div>
    </div>
  );
};

export default HomePage;