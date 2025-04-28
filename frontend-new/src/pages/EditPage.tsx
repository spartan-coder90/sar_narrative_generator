import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, Alert, Spinner, Tabs, Tab, Modal } from 'react-bootstrap';
import { Save, ArrowRepeat, Eye, ArrowLeft } from 'react-bootstrap-icons';
import ApiService from '../services/api';
import SectionEditor from '../components/SectionEditor';
import { NarrativeSections } from '../types';

const EditPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  
  const [sections, setSections] = useState<NarrativeSections>({});
  const [activeTab, setActiveTab] = useState<string>('introduction');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isRegenerating, setIsRegenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  // Modal state
  const [showRegenerateModal, setShowRegenerateModal] = useState<boolean>(false);
  
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
  
  const openRegenerateModal = () => {
    setShowRegenerateModal(true);
  };
  
  const handleRegenerateSection = async () => {
    if (!sessionId || !activeTab) return;
    
    setShowRegenerateModal(false);
    
    try {
      setIsRegenerating(true);
      setError(null);
      
      const response = await ApiService.regenerateSection(sessionId, activeTab);
      
      if (response.status === 'success' && response.section) {
        // Update section content
        setSections(prevSections => ({
          ...prevSections,
          [response.section.id]: {
            ...prevSections[response.section.id],
            content: response.section.content
          }
        }));
        
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
  
  if (isLoading) {
    return (
      <div className="container mt-5 text-center">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
        <p className="mt-2">Loading narrative sections...</p>
      </div>
    );
  }
  
  return (
    <div className="container mt-4">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h1>Edit SAR Narrative</h1>
        <div>
          <Button 
            variant="outline-secondary" 
            className="me-2"
            onClick={() => navigate('/')}
          >
            <ArrowLeft className="me-1" />Back
          </Button>
          <Button 
            variant="primary" 
            onClick={handlePreview}
          >
            <Eye className="me-1" /> Preview & Export
          </Button>
        </div>
      </div>
      
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
      
      <div className="card shadow-sm mb-4">
        <div className="card-header">
          <Tabs
            activeKey={activeTab}
            onSelect={handleTabChange}
            className="mb-0"
          >
            {Object.entries(sections).map(([sectionId, section]) => (
              <Tab 
                key={sectionId} 
                eventKey={sectionId} 
                title={section.title}
              />
            ))}
          </Tabs>
        </div>
        <div className="card-body">
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
                  variant="outline-secondary"
                  onClick={openRegenerateModal}
                  disabled={isRegenerating || isSaving}
                  className="me-2"
                >
                  <ArrowRepeat className="me-1" />
                  {isRegenerating ? 'Regenerating...' : 'Regenerate Section'}
                </Button>
                <Button
                  variant="primary"
                  onClick={handleSaveSection}
                  disabled={isSaving || isRegenerating}
                >
                  <Save className="me-1" />
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Regenerate Confirmation Modal */}
      <Modal
        show={showRegenerateModal}
        onHide={() => setShowRegenerateModal(false)}
        centered
      >
        <Modal.Header closeButton>
          <Modal.Title>Confirm Regeneration</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            Are you sure you want to regenerate this section? Any changes you've
            made will be lost.
          </p>
          <p className="text-muted mb-0">
            Note: Key data such as account numbers, subject names, and transaction
            amounts will be preserved.
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button 
            variant="secondary" 
            onClick={() => setShowRegenerateModal(false)}
          >
            Cancel
          </Button>
          <Button 
            variant="primary" 
            onClick={handleRegenerateSection}
          >
            Regenerate
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default EditPage;