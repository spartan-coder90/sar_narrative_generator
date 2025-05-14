import React, { useState, useEffect } from 'react';
import { Form, Spinner, Alert, Card, Table } from 'react-bootstrap';
import { AlertingActivityData } from '../types';

interface AlertingActivityEditorProps {
  sessionId: string;
  alertingActivityData?: AlertingActivityData;
  generatedSummary?: string;
  onChange: (content: string) => void;
  content: string;
}

const AlertingActivityEditor: React.FC<AlertingActivityEditorProps> = ({ 
  sessionId, 
  alertingActivityData,
  generatedSummary,
  onChange,
  content
}) => {
  const [localContent, setLocalContent] = useState(content);
  
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
  
  if (!alertingActivityData) {
    return (
      <Alert variant="info">
        No alerting activity data available. Please regenerate this section.
      </Alert>
    );
  }
  
  const { alertInfo, account } = alertingActivityData;
  
  return (
    <div>
      <Card className="mb-3">
        <Card.Header className="bg-light">
          <h6 className="mb-0">Alert Information</h6>
        </Card.Header>
        <Card.Body className="p-3">
          <Table bordered hover size="sm">
            <tbody>
              <tr>
                <th style={{ width: '30%' }}>Case Number</th>
                <td>{alertInfo.caseNumber}</td>
              </tr>
              <tr>
                <th>Alert ID</th>
                <td>{alertInfo.alertID}</td>
              </tr>
              <tr>
                <th>Alert Month</th>
                <td>{alertInfo.alertingMonths}</td>
              </tr>
              <tr>
                <th>Alerting Account</th>
                <td>{alertInfo.alertingAccounts || account}</td>
              </tr>
              <tr>
                <th>Review Period</th>
                <td>{alertInfo.reviewPeriod}</td>
              </tr>
              <tr>
                <th>Alert Description</th>
                <td>{alertInfo.alertDescription}</td>
              </tr>
              <tr>
                <th>Transactional Activity</th>
                <td>{alertInfo.transactionalActivityDescription}</td>
              </tr>
              <tr>
                <th>Alert Disposition Summary</th>
                <td>{alertInfo.alertDispositionSummary}</td>
              </tr>
            </tbody>
          </Table>
        </Card.Body>
      </Card>
      
      <Form.Group>
        <Form.Label>Edit Alerting Activity / Reason for Review</Form.Label>
        <Form.Control
          as="textarea"
          rows={8}
          value={localContent}
          onChange={handleContentChange}
          className="narrative-editor"
          placeholder="Enter details about the alerting activity and reason for review..."
        />
        <Form.Text className="text-muted">
          Explain what triggered the alert and the reason for review. If needed, regenerate this section.
        </Form.Text>
      </Form.Group>
    </div>
  );
};

export default AlertingActivityEditor;