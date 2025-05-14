import React, { useState, useEffect } from 'react';
import { Form, Button, Row, Col, ButtonGroup, Card, Table, Badge, Alert, Spinner } from 'react-bootstrap';
import { NarrativeSection, AlertingActivityData } from '../types';
import { 
  NarrativeSections, 
  Recommendation, 
  NARRATIVE_SECTION_IDS, 
  NARRATIVE_SECTION_TITLES 
} from '../types';

interface SectionEditorProps {
  section: NarrativeSection;
  onChange: (content: string) => void;
  
  // Additional props for specialized sections
  sessionId?: string;
  alertingActivityData?: AlertingActivityData;
  priorCases?: any[];
  generatedSummary?: string;
  isLoading?: boolean;
}

const SectionEditor: React.FC<SectionEditorProps> = ({ 
  section, 
  onChange, 
  sessionId,
  alertingActivityData,
  priorCases,
  generatedSummary,
  isLoading
}) => {
  // Initialize content with generated summary if available, otherwise use section content
  const [content, setContent] = useState(
    generatedSummary && !section.content ? generatedSummary : section.content || ''
  );
  
  // For debugging - log when props change
  useEffect(() => {
    console.log(`SectionEditor props update for ${section.id}:`);
    console.log(`- section.content: ${section.content?.substring(0, 30)}...`);
    console.log(`- generatedSummary: ${generatedSummary?.substring(0, 30)}...`);
  }, [section.id, section.content, generatedSummary]);
  
  // Update local content when section changes or when generatedSummary arrives
  useEffect(() => {
    // If we have a generated summary and no content yet, use the generated summary
    if (generatedSummary && !section.content) {
      console.log(`Setting content to generatedSummary for ${section.id}`);
      setContent(generatedSummary);
      // Also call onChange to update parent component
      onChange(generatedSummary);
    } else if (section.content) {
      // If we have section content, use that (user might have edited it)
      console.log(`Setting content to section.content for ${section.id}`);
      setContent(section.content);
    }
  }, [section.id, section.content, generatedSummary, onChange]);
  
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
  
  // Get help text based on section ID
  const getHelpText = (sectionId: string, isRecommendation: boolean): string => {
    if (isRecommendation) {
      // Recommendation section help text...
    } else {
      // Narrative section help text based on new section IDs
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

  const getTemplateText = (sectionId: string) => {
    const templates: Record<string, string> = {
      'suspicious_activity_summary': 'U.S. Bank National Association (USB), is filing this Suspicious Activity Report (SAR) to report [type of activity] totaling $[amount] by [subject name] in [account type] account number [account number]. The suspicious activity was conducted from [start date] through [end date]. The AML indicators were as follows: [risk indicators]. This SAR contains an attached Comma Separated Value (CSV) file that provides additional details of the suspicious transactions being reported in this SAR.',
      'prior_cases': 'Case # [case number]: Alerting account # [account number] reviewed from [start date] to [end date] due to [alerting activity]. SAR ID reported account # [account number] for activity totaling $[amount] conducted from [start date] to [end date]. [SAR summary]',
      'account_subject_info': 'Personal [account type] account [account number] was opened on [date] and [remains open/was closed on [date]]. The account was closed due to [closure reason]. The account closure funds were moved to [destination] on [date] via [method]. The following foreign nationalities and identifications were identified for [subject name]: [nationality], [ID type] # [ID number] issued on [issue date] and expires on [expiration date].',
      'suspicious_activity_analysis': 'The suspicious activity identified in account [account number] was conducted from [start date] to [end date] and consisted of [transaction types and amounts]. The AML risks associated with these transactions are as follows: [risk indicators].',
      'conclusion': 'In conclusion, USB will conduct a follow-up review to monitor for continuing activity. All requests for supporting documentation can be sent to lawenforcementrequestaml@usbank.com referencing AML case number [case number].',
      'alerting_activity': 'Case [case number]: [Account type] and [account number] alerted in [alert month] for [alert description]. Credits totaled [amount] with [transaction types]. Debits totaled [amount] with [transaction types].',
      'prior_sars': 'Prior SARs: [Case number] filed on [filing date] reporting [description]. No prior SARs were identified for the subjects or account.',
    };
    
    return templates[sectionId] || '';
  };
  
  const insertTemplate = () => {
    const templateText = getTemplateText(section.id);
    setContent(templateText);
    onChange(templateText);
  };
  
  // Format currency for display in specialized sections
  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount);
  };
  
  // Use this to log the generated content for debugging
  useEffect(() => {
    if (section.id === 'alerting_activity' || section.id === 'prior_sars') {
      console.log(`${section.id} - generatedSummary: ${generatedSummary?.substring(0, 50)}...`);
    }
  }, [section.id, generatedSummary]);
  
  // Render specialized content based on section type
  const renderSpecializedContent = () => {
    // If loading, show spinner
    if (isLoading) {
      return (
        <div className="text-center py-4">
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading data...</span>
          </Spinner>
          <p className="mt-2">Loading data...</p>
        </div>
      );
    }
    
    // Alerting Activity Editor content
    if (section.id === 'alerting_activity' && alertingActivityData) {
      const { alertInfo, account, creditSummary, debitSummary } = alertingActivityData;
      
      return (
        <Card className="mb-3">
          <Card.Header className="bg-light">
            <h6 className="mb-0">Alerting Activity Summary</h6>
          </Card.Header>
          <Card.Body className="p-3">
            <div className="mb-3">
              <strong>Case Number:</strong> {alertInfo.caseNumber}<br />
              <strong>Alerting Account(s):</strong> {alertInfo.alertingAccounts || account}<br />
              <strong>Alerting Month(s):</strong> {alertInfo.alertingMonths}<br />
              <strong>Alert Description:</strong> {alertInfo.alertDescription}
            </div>
            
            <div className="row mb-3">
              <div className="col-md-6">
                <div className="card">
                  <div className="card-header bg-light text-dark">
                    <h6 className="mb-0">Credit Summary</h6>
                  </div>
                  <div className="card-body">
                    <p><strong>Total Amount:</strong> {formatCurrency(creditSummary.amountTotal)}</p>
                    <p><strong>Transaction Count:</strong> {creditSummary.transactionCount}</p>
                    <p><strong>Date Range:</strong> {creditSummary.minTransactionDate} - {creditSummary.maxTransactionDate}</p>
                    <p><strong>Amount Range:</strong> {formatCurrency(creditSummary.minCreditAmount)} - {formatCurrency(creditSummary.maxCreditAmount)}</p>
                    <p><strong>Highest Percentage Type:</strong> {creditSummary.highestPercentType} ({creditSummary.highestPercentValue}%)</p>
                  </div>
                </div>
              </div>
              <div className="col-md-6">
                <div className="card">
                  <div className="card-header bg-light text-dark">
                    <h6 className="mb-0">Debit Summary</h6>
                  </div>
                  <div className="card-body">
                    <p><strong>Total Amount:</strong> {formatCurrency(debitSummary.amountTotal)}</p>
                    <p><strong>Transaction Count:</strong> {debitSummary.transactionCount}</p>
                    <p><strong>Date Range:</strong> {debitSummary.minTransactionDate} - {debitSummary.maxTransactionDate}</p>
                    <p><strong>Amount Range:</strong> {formatCurrency(debitSummary.minDebitAmount)} - {formatCurrency(debitSummary.maxDebitAmount)}</p>
                    <p><strong>Highest Percentage Type:</strong> {debitSummary.highestPercentType} ({debitSummary.highestPercentValue}%)</p>
                  </div>
                </div>
              </div>
            </div>
          </Card.Body>
        </Card>
      );
    }
    
    // Prior Cases Editor content
    if (section.id === 'prior_sars' && priorCases) {
      if (priorCases.length === 0) {
        return (
          <Alert variant="info" className="mb-3">
            No prior cases or SARs were identified for this account or customer.
          </Alert>
        );
      }
      
      return (
        <Card className="mb-3">
          <Card.Header className="bg-light">
            <h6 className="mb-0">Prior Cases Summary</h6>
          </Card.Header>
          <Card.Body className="p-3">
            {priorCases.map((priorCase, index) => (
              <Card key={index} className="mb-3">
                <Card.Header className="bg-light">
                  <h6 className="mb-0">
                    Case #{priorCase.case_number}
                    {priorCase.case_step && priorCase.case_step.includes("SAR") ? 
                      <Badge bg="primary" className="ms-2">SAR Filed</Badge> : 
                      <Badge bg="secondary" className="ms-2">No SAR</Badge>
                    }
                  </h6>
                </Card.Header>
                <Card.Body>
                  <Table size="sm" bordered>
                    <tbody>
                      <tr>
                        <th style={{ width: '30%' }}>Case Step</th>
                        <td>{priorCase.case_step || 'N/A'}</td>
                      </tr>
                      <tr>
                        <th>Alert IDs</th>
                        <td>{priorCase.alert_ids?.join(', ') || 'None'}</td>
                      </tr>
                      <tr>
                        <th>Alert Months</th>
                        <td>{priorCase.alert_months?.join(', ') || 'None'}</td>
                      </tr>
                      <tr>
                        <th>Alerting Account</th>
                        <td>{priorCase.alerting_account || 'N/A'}</td>
                      </tr>
                      {priorCase.scope_of_review && (
                        <tr>
                          <th>Review Period</th>
                          <td>{priorCase.scope_of_review.start || ''} to {priorCase.scope_of_review.end || ''}</td>
                        </tr>
                      )}
                      {priorCase.sar_details?.form_number && (
                        <>
                          <tr>
                            <th>SAR Form Number</th>
                            <td>{priorCase.sar_details.form_number}</td>
                          </tr>
                          <tr>
                            <th>SAR Filing Date</th>
                            <td>{priorCase.sar_details.filing_date || 'N/A'}</td>
                          </tr>
                          <tr>
                            <th>SAR Amount</th>
                            <td>{formatCurrency(priorCase.sar_details.amount_reported || 0)}</td>
                          </tr>
                          {priorCase.sar_details.filing_date_start && priorCase.sar_details.filing_date_end && (
                            <tr>
                              <th>SAR Date Range</th>
                              <td>{priorCase.sar_details.filing_date_start} to {priorCase.sar_details.filing_date_end}</td>
                            </tr>
                          )}
                        </>
                      )}
                      {priorCase.general_comments && (
                        <tr>
                          <th>CTA / General Comments</th>
                          <td>{priorCase.general_comments}</td>
                        </tr>
                      )}
                    </tbody>
                  </Table>
                </Card.Body>
              </Card>
            ))}
          </Card.Body>
        </Card>
      );
    }
    
    // Default - no specialized content needed
    return null;
  };
  
  return (
    <div>
      {/* Render specialized content based on section type */}
      {renderSpecializedContent()}
      
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
        
        {/* Add debugging info in development only */}
        {process.env.NODE_ENV === 'development' && section.id === 'prior_sars' && (
          <div className="mb-2 p-2 bg-light">
            <strong>Debug - Generated Summary Available:</strong> {generatedSummary ? 'Yes' : 'No'}
            {generatedSummary && (
              <div className="mt-1 small">
                <strong>First 80 chars:</strong> {generatedSummary.substring(0, 80)}...
              </div>
            )}
          </div>
        )}
        
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