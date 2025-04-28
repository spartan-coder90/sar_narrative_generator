// src/pages/NotFoundPage.tsx
import React from 'react';
import { Button } from 'react-bootstrap';
import { useNavigate } from 'react-router-dom';

const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();
  
  return (
    <div className="container mt-5 text-center">
      <h1>404 - Page Not Found</h1>
      <p className="lead">The page you are looking for does not exist.</p>
      <Button variant="primary" onClick={() => navigate('/')}>
        Return to Home
      </Button>
    </div>
  );
};

export default NotFoundPage;