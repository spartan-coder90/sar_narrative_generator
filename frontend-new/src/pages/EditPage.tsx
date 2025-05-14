import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Alert, Spinner, Card, Row, Col, Container, Badge } from 'react-bootstrap';
import { Save, Eye, ArrowLeft, CheckCircle, ArrowClockwise } from 'react-bootstrap-icons';
import ApiService from '../services/api';
import SectionEditor from '../components/SectionEditor';
import AlertingActivityEditor from '../components/AlertingActivityEditor';
import PriorCasesEditor from '../components/PriorCasesEditor';
import { 
  NarrativeSections, 
  Recommendation, 
  AlertingActivityData, 
  NARRATIVE_SECTION_IDS, 
  NARRATIVE_SECTION_TITLES 
} from '../types';

const EditPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  const [sections, setSections] = useState<NarrativeSections>({});
  const [recommendation, setRecommendation] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState<string>(NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_SUMMARY);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [caseInfo, setCaseInfo] = useState<any>({});
  const [activeSection, setActiveSection] = useState<{id: string, content: string, title: string, isRecommendation: boolean} | null>(null);
  const [alertingActivityData, setAlertingActivityData] = useState<AlertingActivityData | undefined>(undefined);
  const [alertingActivityTemplate, setAlertingActivityTemplate] = useState<string>('');
  const [generatedAlertSummary, setGeneratedAlertSummary] = useState<string>('');
  const [isLoadingAlertActivity, setIsLoadingAlertActivity] = useState<boolean>(false);
  const [priorCasesData, setPriorCasesData] = useState<any[]>([]);
  const [isLoadingPriorCases, setIsLoadingPriorCases] = useState<boolean>(false);
  // Add a new state for generated prior cases summary
  const [generatedPriorCasesSummary, setGeneratedPriorCasesSummary] = useState<string>('');

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
            // Fix for account number display - prioritize correct source
            let accountNumber = "";
            
            // First try to get account number from Case Information's Relevant Accounts
            const relevantAccounts = getRelevantAccountsFromCaseData(response.case_data);
            if (relevantAccounts && relevantAccounts.length > 0) {
              accountNumber = relevantAccounts[0];
            } 
            // If not found, use account_info
            else if (response.case_data.account_info?.account_number) {
              accountNumber = response.case_data.account_info.account_number;
            }
            
            const extractedInfo = {
              caseNumber: response.case_data.case_number || '',
              accountNumber: accountNumber,
              dateGenerated: new Date().toISOString()
            };
            setCaseInfo(extractedInfo);
          }
          
          // Set first section as active by default
          if (response.sections && Object.keys(response.sections).length > 0) {
            // Use the first required section as default
            const firstSectionId = NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_SUMMARY;
            if (response.sections[firstSectionId]) {
              setActiveTab(firstSectionId);
              setActiveSection({
                id: firstSectionId,
                content: response.sections[firstSectionId].content,
                title: response.sections[firstSectionId].title,
                isRecommendation: false
              });
            } else {
              // Fallback to the first available section
              const firstAvailableId = Object.keys(response.sections)[0];
              setActiveTab(firstAvailableId);
              setActiveSection({
                id: firstAvailableId,
                content: response.sections[firstAvailableId].content,
                title: response.sections[firstAvailableId].title,
                isRecommendation: false
              });
            }
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
          
          // Fetch alerting activity data after sections are loaded
          fetchAlertingActivityData();
          fetchPriorCasesData();
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
  
  // NEW FUNCTION: Initialize LLM-generated content in state
  // This function ensures that LLM-generated content is properly populated 
  // in the recommendation state and active section when it becomes available
  const initializeLLMContent = () => {
    console.log("Initializing LLM content in state...");
    console.log(`Alert summary available: ${!!generatedAlertSummary} (${generatedAlertSummary?.length || 0} chars)`);
    console.log(`Prior cases summary available: ${!!generatedPriorCasesSummary} (${generatedPriorCasesSummary?.length || 0} chars)`);
    
    // Check if alerting activity has content to initialize
    if (generatedAlertSummary && generatedAlertSummary.trim() !== '') {
      // If recommendation doesn't have this content yet, or it's empty
      if (!recommendation.alerting_activity || recommendation.alerting_activity.trim() === '') {
        console.log("Updating alerting_activity with generated content in state");
        
        // Update recommendation state
        setRecommendation(prev => ({
          ...prev,
          alerting_activity: generatedAlertSummary
        }));
        
        // If this is the current active section, also update the active section content
        if (activeSection && activeSection.id === 'alerting_activity') {
          console.log("Updating activeSection content with generated alert summary");
          setActiveSection(prev => prev ? {
            ...prev,
            content: generatedAlertSummary
          } : null);
        }
      }
    }
    
    // Check if prior cases summary has content to initialize
    if (generatedPriorCasesSummary && generatedPriorCasesSummary.trim() !== '') {
      // If recommendation doesn't have this content yet, or it's empty
      if (!recommendation.prior_sars || recommendation.prior_sars.trim() === '') {
        console.log("Updating prior_sars with generated content in state");
        
        // Update recommendation state
        setRecommendation(prev => ({
          ...prev,
          prior_sars: generatedPriorCasesSummary
        }));
        
        // If this is the current active section, also update the active section content
        if (activeSection && activeSection.id === 'prior_sars') {
          console.log("Updating activeSection content with generated prior cases summary");
          setActiveSection(prev => prev ? {
            ...prev,
            content: generatedPriorCasesSummary
          } : null);
        }
      }
    }
  };
  
  // NEW EFFECT: Run initialization once LLM content is loaded
  // This effect ensures that when the content is fetched from APIs,
  // it's properly set in the recommendation state and active section
  useEffect(() => {
    // Only run initialization when:
    // 1. Alerting activity has finished loading (whether successful or not)
    // 2. Prior cases have finished loading (whether successful or not)
    // 3. We're not currently loading the overall page 
    if (!isLoadingAlertActivity && !isLoadingPriorCases && !isLoading) {
      initializeLLMContent();
    }
  }, [
    isLoadingAlertActivity, 
    isLoadingPriorCases, 
    isLoading,
    generatedAlertSummary, 
    generatedPriorCasesSummary
  ]);
  
  const fetchAlertingActivityData = async () => {
    if (!sessionId) return;
    
    try {
      setIsLoadingAlertActivity(true);
      console.log("Fetching alerting activity data...");
      
      const response = await ApiService.getAlertingActivitySummary(sessionId);
      
      if (response.status === 'success') {
        console.log("Successfully fetched alerting activity data");
        setAlertingActivityData(response.alertingActivitySummary);
        setAlertingActivityTemplate(response.llmTemplate || '');
        
        // Store the generated summary in state for initialization
        if (response.generatedSummary) {
          console.log(`Received generated alert summary (${response.generatedSummary.length} chars)`);
          setGeneratedAlertSummary(response.generatedSummary);
        } else {
          console.warn("No generated summary found in alerting activity response");
        }
      } else {
        console.warn('Failed to load alerting activity data:', response.message);
      }
    } catch (err) {
      console.error('Error fetching alerting activity data:', err);
    } finally {
      setIsLoadingAlertActivity(false);
    }
  };
  
  const fetchPriorCasesData = async () => {
    if (!sessionId) return;
    
    try {
      setIsLoadingPriorCases(true);
      console.log("Fetching prior cases data...");
      
      const response = await ApiService.getPriorCasesSummary(sessionId);
      
      if (response.status === 'success') {
        console.log("Successfully fetched prior cases data");
        setPriorCasesData(response.priorCases || []);
        
        // Store the generated summary in state for initialization
        if (response.generatedSummary) {
          console.log(`Received generated prior cases summary (${response.generatedSummary.length} chars)`);
          setGeneratedPriorCasesSummary(response.generatedSummary);
        } else {
          console.warn("No generated summary found in prior cases response");
        }
      } else {
        console.warn('Failed to load prior cases data:', response.message);
      }
    } catch (err) {
      console.error('Error fetching prior cases data:', err);
    } finally {
      setIsLoadingPriorCases(false);
    }
  };
  
  // Helper function to extract Relevant Accounts from case_data
  const getRelevantAccountsFromCaseData = (caseData: any): string[] => {
    if (!caseData || !caseData.full_data) return [];
    
    for (const section of caseData.full_data) {
      if (section.section === "Case Information" && section["Relevant Accounts"]) {
        return section["Relevant Accounts"];
      }
    }
    
    return [];
  };
  
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
      "prior_sars": "Prior SARs/SAR Summary",
      "scope_of_review": "Scope of Review",
      "investigation_summary": "Summary of Investigation",
      "conclusion": "Conclusion",
      "cta": "CTA",
      "bip": "BIP",
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
      
      // Log the content being saved for debugging
      console.log(`Saving section ${sectionId}, content length: ${content.length}`);
      
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
          
          // If the regenerated section is alerting_activity, refresh the data
          if (sectionId === 'alerting_activity') {
            fetchAlertingActivityData();
          }
          
          // If the regenerated section is prior_sars, refresh prior cases data
          if (sectionId === 'prior_sars') {
            fetchPriorCasesData();
          }
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
        "bip": "Detail any BIP details and questions.",
        "retain_close": "Indicate whether customer relationships should be retained or closed."
      };
      
      return recommendationHelpText[sectionId] || "";
    } else {
      // Help text for narrative sections based on new requirements
      const narrativeHelpText: Record<string, string> = {
        [NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_SUMMARY]: "Summary of unusual activity including transaction types, totals, dates, and AML indicators.",
        [NARRATIVE_SECTION_IDS.PRIOR_CASES]: "Summarize any relevant prior cases or SARs including case/SAR numbers, review periods, and filing details.",
        [NARRATIVE_SECTION_IDS.ACCOUNT_SUBJECT_INFO]: "Summary of account details and account holders. Include foreign nationalities and IDs if applicable.",
        [NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_ANALYSIS]: "Detailed analysis of unusual activity identified in transaction data including AML risk indicators.",
        [NARRATIVE_SECTION_IDS.CONCLUSION]: "Conclusion statement with contact information for supporting documentation."
      };
      
      return narrativeHelpText[sectionId] || "";
    }
  };
  
  // Render appropriate editor based on section type
  const renderSectionEditor = () => {
    if (!activeSection) return null;
    
    // Add debug information when in development
    if (process.env.NODE_ENV === 'development') {
      const relevantContent = 
        activeSection.id === 'alerting_activity' ? generatedAlertSummary : 
        activeSection.id === 'prior_sars' ? generatedPriorCasesSummary : '';
        
      if (relevantContent) {
        console.log(`${activeSection.id} - Generated content available (${relevantContent.length} chars)`);
        console.log(`${activeSection.id} - Current active section content (${activeSection.content.length} chars)`);
      }
    }
    
    // If this is the alerting activity section, use the special editor
    if (activeSection.isRecommendation && activeSection.id === 'alerting_activity') {
      return (
        <AlertingActivityEditor 
          sessionId={sessionId || ''}
          alertingActivityData={alertingActivityData}
          generatedSummary={generatedAlertSummary}
          onChange={handleContentChange}
          content={activeSection.content}
        />
      );
    }
    
    if (activeSection.isRecommendation && activeSection.id === 'prior_sars') {
      return (
        <PriorCasesEditor 
          sessionId={sessionId || ''}
          priorCases={priorCasesData}
          generatedSummary={generatedPriorCasesSummary}
          onChange={handleContentChange}
          content={activeSection.content}
        />
      );
    }
    
    // Otherwise use the standard section editor
    return (
      <SectionEditor 
        section={{
          id: activeSection.id,
          title: activeSection.title,
          content: activeSection.content
        }}
        onChange={handleContentChange}
      />
    );
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
                <Button
                  key="bip"
                  variant="link"
                  className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-5 ${activeTab === "bip" ? 'active' : ''}`}
                  onClick={() => handleTabChange("bip")}
                >
                  BIP
                  {!recommendation["bip"] || recommendation["bip"].trim() === '' ? 
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
                {/* Display SAR Narrative Sections in the required order */}
                {[
                  NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_SUMMARY,
                  NARRATIVE_SECTION_IDS.PRIOR_CASES,
                  NARRATIVE_SECTION_IDS.ACCOUNT_SUBJECT_INFO,
                  NARRATIVE_SECTION_IDS.SUSPICIOUS_ACTIVITY_ANALYSIS,
                  NARRATIVE_SECTION_IDS.CONCLUSION
                ].map(sectionId => (
                  sections[sectionId] && (
                    <Button
                      key={sectionId}
                      variant="link"
                      className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-4 ${activeTab === sectionId ? 'active' : ''}`}
                      onClick={() => handleTabChange(sectionId)}
                    >
                      {sections[sectionId].title}
                      {!sections[sectionId].content.trim() ? <Badge bg="warning" pill>Empty</Badge> : null}
                    </Button>
                  )
                ))}
                
                {/* Show any other sections that might exist */}
                {Object.entries(sections)
                  .filter(([id]) => !Object.values(NARRATIVE_SECTION_IDS).includes(id))
                  .map(([sectionId, section]) => (
                    <Button
                      key={sectionId}
                      variant="link"
                      className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ps-4 ${activeTab === sectionId ? 'active' : ''}`}
                      onClick={() => handleTabChange(sectionId)}
                    >
                      {section.title}
                      {!section.content.trim() ? <Badge bg="warning" pill>Empty</Badge> : null}
                    </Button>
                  ))
                }
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
              
              {isLoadingAlertActivity && activeSection?.id === 'alerting_activity' ? (
                <div className="text-center py-4">
                  <Spinner animation="border" role="status">
                    <span className="visually-hidden">Loading alerting activity data...</span>
                  </Spinner>
                  <p className="mt-2">Loading alerting activity data...</p>
                </div>
              ) : (
                activeSection && renderSectionEditor()
              )}
              
              <div className="d-flex justify-content-end mt-3">
                <Button
                  variant="primary"
                  onClick={handleSaveSection}
                  disabled={isSaving || !activeSection}
                >
                  <Save className="me-1" />
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default EditPage;