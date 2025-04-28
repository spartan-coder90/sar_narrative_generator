import React from 'react';
import { Form } from 'react-bootstrap';
import { NarrativeSection } from '../types';

interface SectionEditorProps {
  section: NarrativeSection;
  onChange: (content: string) => void;
}

const SectionEditor: React.FC<SectionEditorProps> = ({ section, onChange }) => {
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
  };
  
  return (
    <Form.Group>
      <Form.Control
        as="textarea"
        rows={8}
        value={section.content}
        onChange={handleChange}
        className="narrative-editor"
      />
      <Form.Text className="text-muted">
        Edit content while preserving dollar amounts, account numbers, and names.
      </Form.Text>
    </Form.Group>
  );
};

export default SectionEditor;