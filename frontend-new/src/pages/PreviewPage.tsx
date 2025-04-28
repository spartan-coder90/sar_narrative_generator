import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Alert, Spinner, Card } from 'react-bootstrap';
import { Download, PencilSquare } from 'react-bootstrap-icons';
import ApiService from '../services/api';
import { NarrativeSections } from '../types';

const PreviewPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  const [sections, setSections] = useState<NarrativeSections>({});
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    const fetchSections = async () => {
      if (!sessionId) return;
      
      try {
        setIsLoading(true);
        const response = await ApiService.getSections(sessionId);
        
        if (response.status === 'success' && response.sections) {
          setSections(response.sections);
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
    link.download = `SAR_Narrative_${sessionId}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  
  const buildFullNarrative = () => {
    const orderedSectionIds = [
      'introduction',
      'prior_cases',
      'account_info',
      'activity_summary',
      'conclusion'
    ];
    
    return orderedSectionIds
      .map(id => sections[id]?.content || '')
      .filter(content => content)
      .join('\n\n');
  };
  
  if (isLoading) {
    return (
      <div className="container mt-5 text-center">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <p className="mt-2">Loading preview...</p>
      </div>
    );
  }
  
  return (
    <div className="container mt-4">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1>Preview SAR Narrative</h1>
        <div>
          <Button 
            variant="outline-secondary" 
            className="me-2"
            onClick={() => navigate(`/edit/${sessionId}`)}
          >
            <PencilSquare className="me-1" /> Back to Edit
          </Button>
          <Button 
            variant="success" 
            onClick={handleExport}
          >
            <Download className="me-1" /> Export Document
          </Button>
        </div>
      </div>
      
      {error && (
        <Alert variant="danger" onClose={() => setError(null)} dismissible>
          {error}
        </Alert>
      )}
      
      <Card className="shadow-sm">
        <Card.Header className="bg-primary text-white">
          <h4 className="mb-0">Section 7: SAR Narrative</h4>
        </Card.Header>
        <Card.Body>
          <div className="narrative-preview">
            {buildFullNarrative().split('\n\n').map((paragraph, index) => (
              <p key={index}>{paragraph}</p>
            ))}
          </div>
        </Card.Body>
      </Card>
      
      <div className="d-flex justify-content-center mt-4">
        <Button 
          variant="outline-secondary" 
          className="me-2"
          onClick={() => navigate(`/edit/${sessionId}`)}
        >
          <PencilSquare className="me-1" /> Back to Edit
        </Button>
        <Button 
          variant="success" 
          onClick={handleExport}
        >
          <Download className="me-1" /> Export Document
        </Button>
      </div>
    </div>
  );
};

export default PreviewPage;