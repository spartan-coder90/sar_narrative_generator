import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Button, Alert, Spinner } from 'react-bootstrap';
import axios from 'axios';  // Add this import
import ApiService from '../services/api';
import { ErrorResponse } from '../types';

// Rest of the file remains the same...

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [caseFile, setCaseFile] = useState<File | null>(null);
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  
  const handleCaseFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setCaseFile(e.target.files[0]);
    }
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
    
    // Validate files
    if (!caseFile || !excelFile) {
      setError('Both case file and Excel file are required');
      return;
    }
    
    // Show loading state
    setIsLoading(true);
    
    try {
      // Call API to generate narrative
      const response = await ApiService.generateNarrative(caseFile, excelFile);
      
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
              <h4 className="mb-0">Upload Files</h4>
            </Card.Header>
            <Card.Body>
              <Form onSubmit={handleSubmit}>
                <Form.Group className="mb-3">
                  <Form.Label>Case Document</Form.Label>
                  <Form.Control 
                    type="file" 
                    onChange={handleCaseFileChange}
                    accept=".json,.txt,.doc,.docx"
                  />
                  <Form.Text className="text-muted">
                    Upload the case document containing subject and account information.
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
                    disabled={isLoading || !caseFile || !excelFile}
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