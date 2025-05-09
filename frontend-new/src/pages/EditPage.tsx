import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Alert, Spinner, Card, Row, Col, Container, Badge } from 'react-bootstrap';
import { Save, Eye, ArrowLeft, CheckCircle } from 'react-bootstrap-icons';
import ApiService from '../services/api';
import SectionEditor from '../components/SectionEditor';
import { NarrativeSections } from '../types';

const EditPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  const [sections, setSections] = useState<NarrativeSections>({});
  const [activeTab, setActiveTab] = useState<string>('alerting_activity');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [caseInfo, setCaseInfo] = useState<any>({});
  
// In EditPage.tsx - update the useEffect hook
useEffect(() => {
  const fetchSections = async () => {
    if (!sessionId) return;
    
    try {
      setIsLoading(true);
      const response = await ApiService.getSections(sessionId);
      
      // Add console logging to see the response structure
      console.log("API Response:", response);
      
      if (response.status === 'success') {
        // Create template sections
        const templateSections: NarrativeSections = {
          // Your existing template sections code...
          // (Keep this part unchanged)
        };
        
        setSections(templateSections);
        
        // Extract case information from various possible sources
        const extractedCaseInfo = {
          caseNumber: 'N/A',
          accountNumber: 'N/A',
          dateGenerated: new Date().toISOString()
        };
        
        // Try from caseInfo object first
        if (response.caseInfo) {
          if (response.caseInfo.caseNumber) {
            extractedCaseInfo.caseNumber = response.caseInfo.caseNumber;
          }
          if (response.caseInfo.accountNumber) {
            extractedCaseInfo.accountNumber = response.caseInfo.accountNumber;
          }
          if (response.caseInfo.dateGenerated) {
            extractedCaseInfo.dateGenerated = response.caseInfo.dateGenerated;
          }
        }
        
        // Try from case_data - this is likely where your data is
        if (response.case_data) {
          if (response.case_data.case_number) {
            extractedCaseInfo.caseNumber = response.case_data.case_number;
          }
          if (response.case_data.account_info?.account_number) {
            extractedCaseInfo.accountNumber = response.case_data.account_info.account_number;
          }
        }
        
        // Add a type check before accessing direct properties
        if ('caseNumber' in response && response.caseNumber) {
          extractedCaseInfo.caseNumber = response.caseNumber;
        }
        if ('accountNumber' in response && response.accountNumber) {
          extractedCaseInfo.accountNumber = response.accountNumber;
        }
        
        console.log("Setting case info:", extractedCaseInfo);
        setCaseInfo(extractedCaseInfo);
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
  
  const handleTabChange = (key: string | null) => {
    if (key) {
      setActiveTab(key);
    }
  };
  
  const handleContentChange = (sectionId: string, content: string) => {
    setSections(prevSections => ({
      ...prevSections,
      [sectionId]: {
        ...prevSections[sectionId],
        content
      }
    }));
  };
  
  const handleSaveSection = async () => {
    if (!sessionId || !activeTab) return;
    
    try {
      setIsSaving(true);
      setError(null);
      
      const currentSection = sections[activeTab];
      if (!currentSection) {
        throw new Error('Section not found');
      }
      
      const response = await ApiService.updateSection(
        sessionId,
        activeTab,
        currentSection.content
      );
      
      if (response.status === 'success') {
        setSuccessMessage('Section saved successfully');
        
        // Auto-hide success message after 3 seconds
        setTimeout(() => {
          setSuccessMessage(null);
        }, 3000);
      } else {
        setError('Failed to save section');
      }
    } catch (err) {
      console.error('Error saving section:', err);
      setError('An error occurred while saving the section');
    } finally {
      setIsSaving(false);
    }
  };
  
  const handlePreview = () => {
    if (sessionId) {
      navigate(`/preview/${sessionId}`);
    }
  };

  const checkCompleteness = () => {
    // Check if all sections have content
    const incomplete = Object.entries(sections).filter(([id, section]) => !section.content.trim());
    return incomplete.length === 0;
  };
  
  if (isLoading) {
    return (
      <Container className="mt-5 text-center">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <p className="mt-2">Loading narrative sections...</p>
      </Container>
    );
  }
  
  return (
    <Container fluid className="mt-4">
      <Row>
        <Col md={3}>
          <Card className="shadow-sm mb-4">
            <Card.Header className="bg-primary text-white">
              <h5 className="mb-0">Case Information</h5>
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
              <div className="mb-3">
                <strong>Status:</strong> {checkCompleteness() ? 
                  <Badge bg="success">Complete <CheckCircle className="ms-1" /></Badge> : 
                  <Badge bg="warning">Incomplete</Badge>
                }
              </div>
              <div className="d-grid gap-2">
                <Button 
                  variant="outline-secondary"
                  onClick={() => navigate('/')}
                >
                  <ArrowLeft className="me-1" />Back to Home
                </Button>
                <Button 
                  variant="primary" 
                  onClick={handlePreview}
                >
                  <Eye className="me-1" /> Preview & Export
                </Button>
              </div>
            </Card.Body>
          </Card>

          <Card className="shadow-sm mb-4">
            <Card.Header className="bg-secondary text-white">
              <h5 className="mb-0">Sections</h5>
            </Card.Header>
            <Card.Body className="p-0">
              <div className="list-group list-group-flush">
                <div className="list-group-item bg-light fw-bold">7. Recommendations</div>
                <div className="list-group-item bg-light ps-4">B. SAR/No SAR Recommendation</div>
                {["alerting_activity", "prior_sars", "scope_of_review", "investigation_summary", "recommendation_conclusion"].map(sectionId => (
                  <Button
                    key={sectionId}
                    variant="link"
                    className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-5 ${activeTab === sectionId ? 'active' : ''}`}
                    onClick={() => handleTabChange(sectionId)}
                  >
                    {sections[sectionId]?.title}
                    {!sections[sectionId]?.content.trim() && <Badge bg="warning" pill>Empty</Badge>}
                  </Button>
                ))}
                
                <div className="list-group-item bg-light ps-4">C. Escalations/Referrals</div>
                <Button
                  key="cta"
                  variant="link"
                  className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-5 ${activeTab === "cta" ? 'active' : ''}`}
                  onClick={() => handleTabChange("cta")}
                >
                  CTA
                  {!sections["cta"]?.content.trim() && <Badge bg="warning" pill>Empty</Badge>}
                </Button>
                
                <div className="list-group-item bg-light ps-4">D. Retain or Close Customer Relationship(s)</div>
                <Button
                  key="retain_close"
                  variant="link"
                  className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-5 ${activeTab === "retain_close" ? 'active' : ''}`}
                  onClick={() => handleTabChange("retain_close")}
                >
                  Retain or Close
                  {!sections["retain_close"]?.content.trim() && <Badge bg="warning" pill>Empty</Badge>}
                </Button>
                
                <div className="list-group-item bg-light fw-bold">SAR Narrative</div>
                {["introduction", "subject_account_info", "suspicious_activity", "transaction_samples", "sar_conclusion"].map(sectionId => (
                  <Button
                    key={sectionId}
                    variant="link"
                    className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-4 ${activeTab === sectionId ? 'active' : ''}`}
                    onClick={() => handleTabChange(sectionId)}
                  >
                    {sections[sectionId]?.title}
                    {!sections[sectionId]?.content.trim() && <Badge bg="warning" pill>Empty</Badge>}
                  </Button>
                ))}
              </div>
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={9}>
          <Card className="shadow-sm mb-4">
            <Card.Header className="bg-primary text-white d-flex justify-content-between align-items-center">
              <h4 className="mb-0">Edit SAR Documentation</h4>
              <div>
                <Button 
                  variant="light" 
                  onClick={handlePreview}
                  className="me-2"
                >
                  <Eye className="me-1" /> Preview
                </Button>
              </div>
            </Card.Header>
            <Card.Body>
              {error && (
                <Alert variant="danger" onClose={() => setError(null)} dismissible>
                  {error}
                </Alert>
              )}
              
              {successMessage && (
                <Alert variant="success" onClose={() => setSuccessMessage(null)} dismissible>
                  {successMessage}
                </Alert>
              )}
              
              <div className="mb-4">
                <h5>{sections[activeTab]?.title || 'Section'}</h5>
                <p className="text-muted">
                  {getHelpText(activeTab)}
                </p>
              </div>
              
              {Object.entries(sections).map(([sectionId, section]) => (
                <div 
                  key={sectionId}
                  className={sectionId === activeTab ? '' : 'd-none'}
                >
                  <SectionEditor 
                    section={section}
                    onChange={(content) => handleContentChange(sectionId, content)}
                  />
                  
                  <div className="d-flex justify-content-end mt-3">
                    <Button
                      variant="primary"
                      onClick={handleSaveSection}
                      disabled={isSaving}
                    >
                      <Save className="me-1" />
                      {isSaving ? 'Saving...' : 'Save Changes'}
                    </Button>
                  </div>
                </div>
              ))}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

// Helper function to provide context-sensitive help text for each section
function getHelpText(sectionId: string): string {
  const helpTexts: Record<string, string> = {
    // B. SAR/No SAR Recommendation
    'alerting_activity': 'Enter alerting activity information including case number, account types, and alerting reason.',
    'prior_sars': 'Enter any prior SAR information related to this case.',
    'scope_of_review': 'Enter the review period for this case.',
    'investigation_summary': 'Document red flags, supporting evidence, and investigation details. Investigator input required.',
    'recommendation_conclusion': 'Summary of SAR recommendation including unusual activity types, accounts, subjects, amount, and date range.',
    
    // C. Escalations/Referrals
    'cta': 'Enter Customer Transaction Assessment information including customer details, business nature, transaction sources, and relationships.',
    
    // D. Retain or Close Customer Relationship(s)
    'retain_close': 'Indicate whether to retain or close customer relationships. For closure, include F-coded customers, high-risk typology, and closure justification.',
    
    // SAR Narrative
    'introduction': 'The introduction should provide a summary of the suspicious activity being reported, including the type of activity, total amount, customer name, account information, and date range.',
    'subject_account_info': 'Provide details about the subject and their account(s), including relationships and identifying information.',
    'suspicious_activity': 'Describe the suspicious activity patterns, transaction details, and AML risk indicators.',
    'transaction_samples': 'Include representative examples of suspicious transactions to illustrate the patterns being reported.',
    'sar_conclusion': 'Summarize the report including total amount, activity type, customer information, account details, and date range. Include standard information for document requests with AML case number.'
  };
  
  return helpTexts[sectionId] || 'Edit this section of the SAR documentation.';
}

export default EditPage;