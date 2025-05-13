import React, { useState, useEffect } from 'react';
import { Form, Button, Row, Col, ButtonGroup } from 'react-bootstrap';
import { NarrativeSection } from '../types';

interface SectionEditorProps {
  section: NarrativeSection;
  onChange: (content: string) => void;
}

const SectionEditor: React.FC<SectionEditorProps> = ({ section, onChange }) => {
  const [content, setContent] = useState(section.content);
  
  // Update content when section changes
  useEffect(() => {
    setContent(section.content);
  }, [section]);
  
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setContent(newContent);
    onChange(newContent);
  };
  
  const insertFormattedText = (format: string) => {
    const textarea = document.getElementById('section-editor') as HTMLTextAreaElement;
    if (!textarea) return;
    
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = content.substring(start, end);
    
    let formattedText = '';
    
    switch (format) {
      case 'dollar':
        // Format as dollar amount
        formattedText = `$${selectedText}`;
        break;
      case 'account':
        // Format as account number
        formattedText = `account number ${selectedText}`;
        break;
      case 'date':
        // Format as date if not already in MM/DD/YYYY format
        if (!/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(selectedText)) {
          const today = new Date();
          formattedText = `${today.getMonth() + 1}/${today.getDate()}/${today.getFullYear()}`;
        } else {
          formattedText = selectedText;
        }
        break;
      case 'name':
        // Format as party name
        formattedText = selectedText;
        break;
      default:
        formattedText = selectedText;
    }
    
    const newContent = content.substring(0, start) + formattedText + content.substring(end);
    setContent(newContent);
    onChange(newContent);
    
    // Set cursor position after the inserted text
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + formattedText.length, start + formattedText.length);
    }, 0);
  };
  
  const getTemplateText = (sectionId: string) => {
    const templates: Record<string, string> = {
      'suspicious_activity_summary': 'U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report [type of activity] totaling $[amount] by [subject name] in [account type] account number [account number]. The suspicious activity was conducted from [start date] through [end date]. The AML indicators were as follows: [risk indicators]. This SAR contains an attached Comma Separated Value (CSV) file that provides additional details of the suspicious transactions being reported in this SAR.',
      'prior_cases': 'Case # [case number]: Alerting account # [account number] reviewed from [start date] to [end date] due to [alerting activity]. SAR ID reported account # [account number] for activity totaling $[amount] conducted from [start date] to [end date]. [SAR summary]',
      'account_subject_info': 'Personal [account type] account [account number] was opened on [date] and [remains open/was closed on [date]]. The account was closed due to [closure reason]. The account closure funds were moved to [destination] on [date] via [method]. The following foreign nationalities and identifications were identified for [subject name]: [nationality], [ID type] # [ID number] issued on [issue date] and expires on [expiration date].',
      'suspicious_activity_analysis': 'The suspicious activity identified in account [account number] was conducted from [start date] to [end date] and consisted of [transaction types and amounts]. The AML risks associated with these transactions are as follows: [risk indicators].',
      'conclusion': 'In conclusion, USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequestaml@usbank.com referencing AML case number [case number].'
    };
    
    return templates[sectionId] || '';
  };
  
  const insertTemplate = () => {
    const templateText = getTemplateText(section.id);
    setContent(templateText);
    onChange(templateText);
  };
  
  return (
    <div>
      <Form.Group>
        <Row className="mb-2">
          <Col>
            <ButtonGroup size="sm">
              <Button variant="outline-secondary" onClick={() => insertFormattedText('dollar')} title="Format as Dollar Amount">
                $
              </Button>
              <Button variant="outline-secondary" onClick={() => insertFormattedText('account')} title="Format as Account Number">
                #
              </Button>
              <Button variant="outline-secondary" onClick={() => insertFormattedText('date')} title="Format as Date">
                📅
              </Button>
              <Button variant="outline-secondary" onClick={() => insertFormattedText('name')} title="Format as Party Name">
                👤
              </Button>
              <Button variant="outline-primary" onClick={insertTemplate} title="Insert Template">
                Template
              </Button>
            </ButtonGroup>
          </Col>
        </Row>
        <Form.Control
          id="section-editor"
          as="textarea"
          rows={10}
          value={content}
          onChange={handleChange}
          className="narrative-editor"
          placeholder={`Enter ${section.title.toLowerCase()} content here...`}
        />
        <Form.Text className="text-muted">
          Edit content while preserving dollar amounts, account numbers, and names. Format key information using the buttons above.
        </Form.Text>
      </Form.Group>
    </div>
  );
};

export default SectionEditor;