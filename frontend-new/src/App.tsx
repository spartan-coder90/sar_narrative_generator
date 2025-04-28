import React from 'react';
import { Routes, Route } from 'react-router-dom';
import NavigationBar from './components/NavigationBar';
import HomePage from './pages/HomePage';
import EditPage from './pages/EditPage';
import PreviewPage from './pages/PreviewPage';
import NotFoundPage from './pages/NotFoundPage';
import './App.css';

const App: React.FC = () => {
  return (
    <div className="app-container">
      <NavigationBar />
      <div className="content-container">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/edit/:sessionId" element={<EditPage />} />
          <Route path="/preview/:sessionId" element={<PreviewPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </div>
      <footer className="footer mt-auto py-3 bg-light">
        <div className="container text-center">
          <span className="text-muted"></span>
        </div>
      </footer>
    </div>
  );
};

export default App;