import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Button, Alert, Spinner, Container, Row, Col, Tab, Tabs } from 'react-bootstrap';
import axios from 'axios';
import ApiService from '../services/api';
import { ErrorResponse, CaseSummary } from '../types';

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedCase, setSelectedCase] = useState<string>('');
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const [caseFile, setCaseFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isLoadingCases, setIsLoadingCases] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [availableCases, setAvailableCases] = useState<CaseSummary[]>([]);
  const [activeTab, setActiveTab] = useState<string>('static-case');
  const [selectedModel, setSelectedModel] = useState<string>('llama3-8b');


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

  const handleCaseFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setCaseFile(e.target.files[0]);
    }
  };
  
  const handleSubmitStaticCase = async (e: React.FormEvent<HTMLFormElement>) => {
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

  const handleSubmitUploadCase = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    // Reset state
    setError(null);
    setWarnings([]);
    
    // Validate input
    if (!caseFile) {
      setError('Case file is required');
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
    <Container className="mt-4">
      <Row>
        <Col md={8} className="mx-auto">
          <h1 className="mb-4 text-center">AML SAR Narrative Generator</h1>
          
          <Card className="shadow-sm mb-4">
            <Card.Header className="bg-primary text-white">
              <h4 className="mb-0">Generate SAR Narrative</h4>
            </Card.Header>
            <Card.Body>
              <Tabs 
                activeKey={activeTab} 
                onSelect={(k) => k && setActiveTab(k)}
                className="mb-4"
                justify
              >
                <Tab eventKey="static-case" title="Existing Case">
                  <Form onSubmit={handleSubmitStaticCase}>
                    <Form.Group className="mb-3">
                      <Form.Label>Select Case</Form.Label>
                      <Form.Select
                        value={selectedCase}
                        onChange={handleCaseChange}
                        disabled={isLoadingCases}
                      >
                        <option value="">Select a case...</option>
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
                        Select existing case.
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
                        Upload the Excel file containing transaction data for analysis.
                      </Form.Text>
                    </Form.Group>
                    
                    <Form.Group className="mb-3">
                      <Form.Label>LLM Model</Form.Label>
                      <Form.Select
                        value={selectedModel}
                        onChange={(e) => setSelectedModel(e.target.value)}
                      >
                        <option value="llama3-8b">Llama 3:8B</option>
                        <option value="gpt-3.5-turbo">GPT 3.5 Turbo</option>
                        <option value="gpt-4">GPT 4</option>
                      </Form.Select>
                      <Form.Text className="text-muted">
                        Select the language model to use for generating narrative sections.
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
                          'Generate Narrative'
                        )}
                      </Button>
                    </div>
                  </Form>
                </Tab>
                <Tab eventKey="upload-case" title="Upload Case">
                  <Form onSubmit={handleSubmitUploadCase}>
                    <Form.Group className="mb-3">
                      <Form.Label>Case Document</Form.Label>
                      <Form.Control 
                        type="file" 
                        onChange={handleCaseFileChange}
                        accept=".txt,.doc,.docx,.json"
                      />
                      <Form.Text className="text-muted">
                        Upload the case document file (TXT, DOC, DOCX, or JSON format).
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
                        Upload the Excel file containing transaction data for analysis.
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
                </Tab>
              </Tabs>
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

          <div className="text-center mt-4">
            <p className="text-muted">
              This tool generates SAR narratives based on case data and transaction information according to U.S. Bank AML compliance requirements.
            </p>
          </div>
        </Col>
      </Row>
    </Container>
  );
};

export default HomePage;