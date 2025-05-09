import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Alert, Spinner, Card, Row, Col, Container, Badge } from 'react-bootstrap';
import { Save, Eye, ArrowLeft, CheckCircle, ArrowClockwise } from 'react-bootstrap-icons';
import ApiService from '../services/api';
import SectionEditor from '../components/SectionEditor';
import { NarrativeSections, Recommendation } from '../types';

const EditPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  const [sections, setSections] = useState<NarrativeSections>({});
  const [recommendation, setRecommendation] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<string>('introduction');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [caseInfo, setCaseInfo] = useState<any>({});
  const [activeSection, setActiveSection] = useState<{id: string, content: string, title: string, isRecommendation: boolean} | null>(null);
  
  useEffect(() => {
    const fetchSections = async () => {
      if (!sessionId) return;
      
      try {
        setIsLoading(true);
        const response = await ApiService.getSections(sessionId);
        
        if (response.status === 'success') {
          // Set narrative sections
          if (response.sections) {
            setSections(response.sections);
          }
          
          // Set recommendation sections
          if (response.recommendation) {
            setRecommendation(response.recommendation as Record<string, string>);
          }
          
          // Extract case information
          if (response.caseInfo) {
            setCaseInfo(response.caseInfo);
          } else if (response.case_data) {
            const extractedInfo = {
              caseNumber: response.case_data.case_number || '',
              accountNumber: response.case_data.account_info?.account_number || '',
              dateGenerated: new Date().toISOString()
            };
            setCaseInfo(extractedInfo);
          }
          
          // Set first section as active by default
          if (response.sections && Object.keys(response.sections).length > 0) {
            const firstSectionId = Object.keys(response.sections)[0];
            setActiveTab(firstSectionId);
            setActiveSection({
              id: firstSectionId,
              content: response.sections[firstSectionId].content,
              title: response.sections[firstSectionId].title,
              isRecommendation: false
            });
          } else if (response.recommendation && Object.keys(response.recommendation).length > 0) {
            const firstRecSectionId = Object.keys(response.recommendation)[0];
            setActiveTab(firstRecSectionId);
            setActiveSection({
              id: firstRecSectionId,
              content: (response.recommendation as Record<string, string>)[firstRecSectionId],
              title: getRecommendationSectionTitle(firstRecSectionId),
              isRecommendation: true
            });
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
  
  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    
    // Determine if this is a narrative section or recommendation section
    if (sections[tabId]) {
      // Narrative section
      setActiveSection({
        id: tabId,
        content: sections[tabId].content,
        title: sections[tabId].title,
        isRecommendation: false
      });
    } else if (recommendation[tabId]) {
      // Recommendation section
      setActiveSection({
        id: tabId,
        content: recommendation[tabId],
        title: getRecommendationSectionTitle(tabId),
        isRecommendation: true
      });
    }
  };
  
  const getRecommendationSectionTitle = (sectionId: string): string => {
    const sectionTitles: {[key: string]: string} = {
      "alerting_activity": "Alerting Activity / Reason for Review",
      "prior_sars": "Prior SARs",
      "scope_of_review": "Scope of Review",
      "investigation_summary": "Summary of the Investigation",
      "conclusion": "Recommendation Conclusion",
      "cta": "CTA",
      "retain_close": "Retain or Close Customer Relationship(s)"
    };
    
    return sectionTitles[sectionId] || `Section: ${sectionId}`;
  };
  
  const handleContentChange = (content: string) => {
    if (!activeSection) return;
    
    if (activeSection.isRecommendation) {
      // Update recommendation section
      setRecommendation(prev => ({
        ...prev,
        [activeSection.id]: content
      }));
    } else {
      // Update narrative section
      setSections(prev => ({
        ...prev,
        [activeSection.id]: {
          ...prev[activeSection.id],
          content
        }
      }));
    }
    
    // Update active section
    setActiveSection(prev => prev ? { ...prev, content } : null);
  };
  
  const handleSaveSection = async () => {
    if (!sessionId || !activeSection) return;
    
    try {
      setIsSaving(true);
      setError(null);
      
      const sectionId = activeSection.id;
      const content = activeSection.content;
      const isRecommendation = activeSection.isRecommendation;
      
      // Determine the API endpoint and data format based on section type
      let response;
      if (isRecommendation) {
        // Save recommendation section
        response = await ApiService.updateRecommendationSection(
          sessionId,
          sectionId,
          content
        );
      } else {
        // Save narrative section
        response = await ApiService.updateSection(
          sessionId,
          sectionId,
          content
        );
      }
      
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
  
  const handleRegenerateSection = async () => {
    if (!sessionId || !activeSection) return;
    
    try {
      setIsRegenerating(true);
      setError(null);
      
      const sectionId = activeSection.id;
      
      const response = await ApiService.regenerateSection(
        sessionId,
        sectionId
      );
      
      if (response.status === 'success' && response.section) {
        // Update the section with regenerated content
        const newContent = response.section.content;
        const isRecommendation = response.section.type === 'recommendation';
        
        if (isRecommendation) {
          // Update recommendation section
          setRecommendation(prev => ({
            ...prev,
            [sectionId]: newContent
          }));
        } else {
          // Update narrative section
          setSections(prev => ({
            ...prev,
            [sectionId]: {
              ...prev[sectionId],
              content: newContent
            }
          }));
        }
        
        // Update active section
        setActiveSection(prev => prev ? { ...prev, content: newContent } : null);
        
        setSuccessMessage('Section regenerated successfully');
        
        // Auto-hide success message after 3 seconds
        setTimeout(() => {
          setSuccessMessage(null);
        }, 3000);
      } else {
        setError('Failed to regenerate section');
      }
    } catch (err) {
      console.error('Error regenerating section:', err);
      setError('An error occurred while regenerating the section');
    } finally {
      setIsRegenerating(false);
    }
  };
  
  const handlePreview = () => {
    if (sessionId) {
      navigate(`/preview/${sessionId}`);
    }
  };

  const checkCompleteness = () => {
    // Check if all sections have content
    const narrativeComplete = Object.values(sections).every(
      section => section.content.trim() !== ''
    );
    
    // Check if all recommendation sections have content
    const recommendationComplete = Object.keys(recommendation).every(
      key => recommendation[key] && recommendation[key].trim() !== ''
    );
    
    return narrativeComplete && recommendationComplete;
  };

  // This function provides help text for each section
  const getHelpText = (sectionId: string, isRecommendation: boolean): string => {
    if (isRecommendation) {
      // Help text for recommendation sections
      const recommendationHelpText: Record<string, string> = {
        "alerting_activity": "Summarize what triggered the alert and why the case was selected for review.",
        "prior_sars": "List any prior SARs filed on this subject or account.",
        "scope_of_review": "Specify the date range that was reviewed for this case.",
        "investigation_summary": "Describe the investigation findings, red flags, and supporting evidence.",
        "conclusion": "Provide the final recommendation with specific activity details.",
        "cta": "Detail any Customer Transaction Assessment details and questions.",
        "retain_close": "Indicate whether customer relationships should be retained or closed."
      };
      
      return recommendationHelpText[sectionId] || "";
    } else {
      // Help text for narrative sections
      const narrativeHelpText: Record<string, string> = {
        "introduction": "Introduce the SAR filing with activity type, amount, subject name, account details, and date range.",
        "prior_cases": "Include information about any prior SARs filed on this account or subject.",
        "account_info": "Provide details about the account including type, open date, and status.",
        "subject_info": "Include information about the subject including occupation and relationship to the account.",
        "activity_summary": "Summarize the suspicious activity including transaction patterns and AML risks.",
        "transaction_samples": "Provide specific examples of suspicious transactions with dates and amounts.",
        "conclusion": "Summarize the SAR filing with total amounts, date ranges, and reference number."
      };
      
      return narrativeHelpText[sectionId] || "";
    }
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
                {["alerting_activity", "prior_sars", "scope_of_review", "investigation_summary", "conclusion"].map(sectionId => (
                  <Button
                    key={sectionId}
                    variant="link"
                    className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-5 ${activeTab === sectionId ? 'active' : ''}`}
                    onClick={() => handleTabChange(sectionId)}
                  >
                    {getRecommendationSectionTitle(sectionId)}
                    {!recommendation[sectionId] || recommendation[sectionId].trim() === '' ? 
                      <Badge bg="warning" pill>Empty</Badge> : null
                    }
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
                  {!recommendation["cta"] || recommendation["cta"].trim() === '' ? 
                    <Badge bg="warning" pill>Empty</Badge> : null
                  }
                </Button>
                
                <div className="list-group-item bg-light ps-4">D. Retain or Close Customer Relationship(s)</div>
                <Button
                  key="retain_close"
                  variant="link"
                  className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-5 ${activeTab === "retain_close" ? 'active' : ''}`}
                  onClick={() => handleTabChange("retain_close")}
                >
                  Retain or Close
                  {!recommendation["retain_close"] || recommendation["retain_close"].trim() === '' ? 
                    <Badge bg="warning" pill>Empty</Badge> : null
                  }
                </Button>
                
                <div className="list-group-item bg-light fw-bold">SAR Narrative</div>
                {Object.entries(sections).map(([sectionId, section]) => (
                  <Button
                    key={sectionId}
                    variant="link"
                    className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-4 ${activeTab === sectionId ? 'active' : ''}`}
                    onClick={() => handleTabChange(sectionId)}
                  >
                    {section.title}
                    {!section.content.trim() ? <Badge bg="warning" pill>Empty</Badge> : null}
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
                  onClick={handleRegenerateSection}
                  className="me-2"
                  disabled={isRegenerating || !activeSection}
                >
                  <ArrowClockwise className="me-1" /> 
                  {isRegenerating ? 'Regenerating...' : 'Regenerate'}
                </Button>
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
              
              {activeSection && (
                <div className="mb-4">
                  <h5>{activeSection.title}</h5>
                  <p className="text-muted">
                    {getHelpText(activeSection.id, activeSection.isRecommendation)}
                  </p>
                </div>
              )}
              
              {activeSection && (
                <div>
                  <SectionEditor 
                    section={{
                      id: activeSection.id,
                      title: activeSection.title,
                      content: activeSection.content
                    }}
                    onChange={handleContentChange}
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
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default EditPage;