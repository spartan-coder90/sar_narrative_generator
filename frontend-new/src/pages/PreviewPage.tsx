import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Alert, Spinner, Card, Row, Col, Container, ListGroup, Badge } from 'react-bootstrap';
import { Download, PencilSquare, Printer, ArrowLeft, FileText } from 'react-bootstrap-icons';
import ApiService from '../services/api';
import { NarrativeSections } from '../types';

const PreviewPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  const [sections, setSections] = useState<NarrativeSections>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [caseInfo, setCaseInfo] = useState<any>({});
  
  useEffect(() => {
    const fetchSections = async () => {
      if (!sessionId) return;
      
      try {
        setIsLoading(true);
        const response = await ApiService.getSections(sessionId);
        
        if (response.status === 'success' && response.sections) {
          setSections(response.sections);
          
          // Extract case info if available
          if (response.caseInfo) {
            setCaseInfo(response.caseInfo);
          }
        } else {
          setError('Failed to load narrative sections');
        }
      } catch (err) {
        console.error('Error fetching sections:', err);
        setError('An error occurred while loading the narrative sections');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchSections();
  }, [sessionId]);
  
  const handleExport = () => {
    if (!sessionId) return;
    
    // Create a temporary anchor and trigger a download
    const link = document.createElement('a');
    link.href = ApiService.getExportUrl(sessionId);
    link.target = '_blank';
    link.download = `SAR_Narrative_${caseInfo.caseNumber || sessionId}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  
  const handlePrint = () => {
    window.print();
  };
  
  const buildFullNarrative = () => {
    const orderedSectionIds = [
      'introduction',
      'prior_cases',
      'account_info',
      'subject_info',
      'activity_summary',
      'transaction_samples',
      'conclusion'
    ];
    
    return orderedSectionIds
      .map(id => sections[id]?.content || '')
      .filter(content => content)
      .join('\n\n');
  };
  
  if (isLoading) {
    return (
      <Container className="mt-5 text-center">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <p className="mt-2">Loading preview...</p>
      </Container>
    );
  }
  
  return (
    <Container fluid className="mt-4">
      <Row>
        <Col md={3}>
          <Card className="shadow-sm mb-4">
            <Card.Header className="bg-primary text-white">
              <h5 className="mb-0">SAR Information</h5>
            </Card.Header>
            <Card.Body>
              <div className="mb-3">
                <strong>Case Number:</strong> {caseInfo.caseNumber || 'N/A'}
              </div>
              <div className="mb-3">
                <strong>Account Number:</strong> {caseInfo.accountNumber || 'N/A'}
              </div>
              <div className="mb-3">
                <strong>Date Generated:</strong> {caseInfo.dateGenerated ? new Date(caseInfo.dateGenerated).toLocaleDateString() : 'N/A'}
              </div>
              <div className="d-grid gap-2">
                <Button 
                  variant="outline-secondary" 
                  onClick={() => navigate(`/edit/${sessionId}`)}
                >
                  <PencilSquare className="me-1" /> Back to Edit
                </Button>
                <Button 
                  variant="primary" 
                  onClick={handleExport}
                >
                  <Download className="me-1" /> Export Document
                </Button>
                <Button 
                  variant="outline-primary" 
                  onClick={handlePrint}
                >
                  <Printer className="me-1" /> Print Document
                </Button>
              </div>
            </Card.Body>
          </Card>
          
          <Card className="shadow-sm mb-4">
            <Card.Header className="bg-secondary text-white">
              <h5 className="mb-0">Sections</h5>
            </Card.Header>
            <ListGroup variant="flush">
              {Object.entries(sections).map(([id, section]) => (
                <ListGroup.Item key={id} className="d-flex justify-content-between align-items-center">
                  {section.title}
                  {section.content ? (
                    <Badge bg="success" pill>Complete</Badge>
                  ) : (
                    <Badge bg="danger" pill>Missing</Badge>
                  )}
                </ListGroup.Item>
              ))}
            </ListGroup>
          </Card>
        </Col>
        
        <Col md={9}>
          <Card className="shadow-sm">
            <Card.Header className="bg-primary text-white d-flex justify-content-between align-items-center">
              <h4 className="mb-0">Section 7: SAR Narrative</h4>
              <div>
                <Button 
                  variant="light" 
                  onClick={handleExport}
                  className="me-2"
                >
                  <Download className="me-1" /> Export
                </Button>
                <Button 
                  variant="outline-light" 
                  onClick={handlePrint}
                >
                  <Printer className="me-1" /> Print
                </Button>
              </div>
            </Card.Header>
            <Card.Body>
              {error && (
                <Alert variant="danger" onClose={() => setError(null)} dismissible>
                  {error}
                </Alert>
              )}
              
              <div className="narrative-preview">
                {buildFullNarrative().split('\n\n').map((paragraph, index) => (
                  <div key={index} className="mb-4">
                    <p>{paragraph}</p>
                  </div>
                ))}
              </div>
            </Card.Body>
          </Card>
          
          <div className="d-flex justify-content-between mt-4">
            <Button 
              variant="outline-secondary" 
              onClick={() => navigate('/')}
            >
              <ArrowLeft className="me-1" /> Home
            </Button>
            <div>
              <Button 
                variant="outline-primary" 
                className="me-2"
                onClick={() => navigate(`/edit/${sessionId}`)}
              >
                <PencilSquare className="me-1" /> Edit Narrative
              </Button>
              <Button 
                variant="success" 
                onClick={handleExport}
              >
                <FileText className="me-1" /> Export Narrative
              </Button>
            </div>
          </div>
        </Col>
      </Row>
    </Container>
  );
};

export default PreviewPage;