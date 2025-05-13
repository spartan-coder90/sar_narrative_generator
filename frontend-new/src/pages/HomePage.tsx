import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Button, Alert, Spinner, Container, Row, Col, Badge } from 'react-bootstrap';
import axios from 'axios';
import ApiService from '../services/api';
import { ErrorResponse, CaseSummary } from '../types';

// Define an interface for case items with display name
interface FormattedCaseSummary extends CaseSummary {
  displayName: string;
}

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedCase, setSelectedCase] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isLoadingCases, setIsLoadingCases] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [availableCases, setAvailableCases] = useState<FormattedCaseSummary[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('llama3-8b');
  const [caseDetails, setCaseDetails] = useState<FormattedCaseSummary | null>(null);

  // Fetch available cases on component mount
  useEffect(() => {
    const fetchCases = async () => {
      try {
        setIsLoadingCases(true);
        const response = await ApiService.getAvailableCases();
        
        // Format case display names to show proper account numbers
        const formattedCases: FormattedCaseSummary[] = response.cases.map(caseItem => ({
          ...caseItem,
          displayName: `${caseItem.case_number} - ${caseItem.subjects.join(', ')}${caseItem.account_number ? ` (${caseItem.account_number})` : ''}`
        }));
        
        setAvailableCases(formattedCases);
      } catch (err) {
        console.error('Error fetching available cases:', err);
        setError('Failed to load available cases');
      } finally {
        setIsLoadingCases(false);
      }
    };
    
    fetchCases();
  }, []);
  
  // Update case details when selection changes
  useEffect(() => {
    if (selectedCase) {
      const selectedCaseDetails = availableCases.find(c => c.case_number === selectedCase);
      if (selectedCaseDetails) {
        setCaseDetails(selectedCaseDetails);
      }
    } else {
      setCaseDetails(null);
    }
  }, [selectedCase, availableCases]);
  
  const handleCaseChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedCase(e.target.value);
    setError(null);
    setWarnings([]);
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
    
    // Show loading state
    setIsLoading(true);
    
    try {
      // Call API to generate narrative from selected case
      const response = await ApiService.generateNarrativeFromCase(selectedCase, selectedModel);
      
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
        setError(errorData.message || 'An error occurred while processing the case');
        
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
              <Form onSubmit={handleSubmit}>
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
                        {caseItem.displayName}
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
                    Select an existing case to generate a SAR narrative.
                  </Form.Text>
                </Form.Group>
                
                {caseDetails && (
                  <div className="mb-3 p-3 border rounded bg-light">
                    <h6>Case Details</h6>
                    <div><strong>Case Number:</strong> {caseDetails.case_number}</div>
                    <div><strong>Subject(s):</strong> {caseDetails.subjects.join(', ')}</div>
                    <div><strong>Account Number:</strong> {caseDetails.account_number || 'N/A'}</div>
                    <div>
                      <strong>Alerts:</strong> {' '}
                      <Badge bg="info">{caseDetails.alert_count} alert{caseDetails.alert_count !== 1 ? 's' : ''}</Badge>
                    </div>
                  </div>
                )}
                
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
                    disabled={isLoading || !selectedCase}
                    className="py-2"
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
                        Processing Case...
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