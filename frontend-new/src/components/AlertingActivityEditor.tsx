import React, { useState, useEffect } from 'react';
import { Form, Spinner, Alert, Card } from 'react-bootstrap';
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
  const [isLoading, setIsLoading] = useState(false);
  
  // Update local content when content prop changes
  useEffect(() => {
    setLocalContent(content);
  }, [content]);
  
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
  
  const { alertInfo, account, creditSummary, debitSummary } = alertingActivityData;
  
  return (
    <div>
      <Card className="mb-3">
        <Card.Header className="bg-light">
          <h6 className="mb-0">Alerting Activity Summary</h6>
        </Card.Header>
        <Card.Body className="p-3">
          <div className="mb-3">
            <strong>Case Number:</strong> {alertInfo.caseNumber}<br />
            <strong>Alerting Account(s):</strong> {alertInfo.alertingAccounts}<br />
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