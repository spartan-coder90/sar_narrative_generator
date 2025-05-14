import React, { useState, useEffect } from 'react';
import { Form, Spinner, Alert, Card, Table, Badge } from 'react-bootstrap';

interface PriorCase {
  case_number: string;
  case_step: string;
  alert_ids: string[];
  alert_months: string[];
  alerting_account: string;
  scope_of_review: {
    start: string;
    end: string;
  };
  sar_details: {
    form_number: string;
    filing_date: string;
    amount_reported: number;
    sar_summary: string;
    filing_date_start?: string;
    filing_date_end?: string;
  };
  general_comments: string;
}

interface PriorCasesEditorProps {
  sessionId: string;
  priorCases?: PriorCase[];
  generatedSummary?: string;
  onChange: (content: string) => void;
  content: string;
}

const PriorCasesEditor: React.FC<PriorCasesEditorProps> = ({ 
  sessionId, 
  priorCases,
  generatedSummary,
  onChange,
  content
}) => {
  const [localContent, setLocalContent] = useState(content);
  const [isLoading, setIsLoading] = useState(false);
  
  // Update local content when content prop changes
  useEffect(() => {
    setLocalContent(content || generatedSummary || '');
  }, [content, generatedSummary]);
  
  // Handle text changes
  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setLocalContent(newContent);
    onChange(newContent);
  };
  
  // Format currency for display
  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount);
  };
  
  if (!priorCases) {
    return (
      <Alert variant="info">
        No prior cases data available. Please regenerate this section.
      </Alert>
    );
  }
  
  if (priorCases.length === 0) {
    return (
      <div>
        <Alert variant="info" className="mb-3">
          No prior cases or SARs were identified for this account or customer.
        </Alert>
        
        <Form.Group>
          <Form.Label>Edit Prior Cases / SAR Summary</Form.Label>
          <Form.Control
            as="textarea"
            rows={4}
            value={localContent}
            onChange={handleContentChange}
            className="narrative-editor"
            placeholder="No prior cases or SARs were identified for the subjects or account."
          />
          <Form.Text className="text-muted">
            Edit the prior cases summary as needed.
          </Form.Text>
        </Form.Group>
      </div>
    );
  }
  
  return (
    <div>
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
                  {priorCase.case_step.includes("SAR") ? 
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
                      <td>{priorCase.case_step}</td>
                    </tr>
                    <tr>
                      <th>Alert IDs</th>
                      <td>{priorCase.alert_ids.join(', ') || 'None'}</td>
                    </tr>
                    <tr>
                      <th>Alert Months</th>
                      <td>{priorCase.alert_months.join(', ') || 'None'}</td>
                    </tr>
                    <tr>
                      <th>Alerting Account</th>
                      <td>{priorCase.alerting_account}</td>
                    </tr>
                    <tr>
                      <th>Review Period</th>
                      <td>{priorCase.scope_of_review.start} to {priorCase.scope_of_review.end}</td>
                    </tr>
                    {priorCase.sar_details.form_number && (
                      <>
                        <tr>
                          <th>SAR Form Number</th>
                          <td>{priorCase.sar_details.form_number}</td>
                        </tr>
                        <tr>
                          <th>SAR Filing Date</th>
                          <td>{priorCase.sar_details.filing_date}</td>
                        </tr>
                        <tr>
                          <th>SAR Amount</th>
                          <td>{formatCurrency(priorCase.sar_details.amount_reported)}</td>
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
      
      <Form.Group>
        <Form.Label>Edit Prior Cases / SAR Summary</Form.Label>
        <Form.Control
          as="textarea"
          rows={8}
          value={localContent}
          onChange={handleContentChange}
          className="narrative-editor"
          placeholder="Enter a summary of prior cases and SARs..."
        />
        <Form.Text className="text-muted">
          Summarize the prior cases and SARs, focusing on case number, alerting account, review period, and SAR details if applicable.
        </Form.Text>
      </Form.Group>
    </div>
  );
};

export default PriorCasesEditor;