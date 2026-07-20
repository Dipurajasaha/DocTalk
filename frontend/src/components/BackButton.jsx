import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function BackButton({ onClick, label = "Back", style = {}, className = "" }) {
  const navigate = useNavigate();
  
  const handleBack = (e) => {
    e.preventDefault();
    if (onClick) {
      onClick(e);
    } else {
      navigate(-1);
    }
  };

  return (
    <button 
      onClick={handleBack} 
      className={`neu-flat ${className}`}
      style={{ 
        display: 'inline-flex', 
        alignItems: 'center', 
        gap: '8px', 
        padding: '10px 18px', 
        borderRadius: '50px', 
        border: '1px solid var(--border-subtle, #e2e8f0)',
        background: 'transparent',
        cursor: 'pointer', 
        fontSize: '14px', 
        fontWeight: '600', 
        color: 'var(--text-primary, #334155)',
        transition: 'all 0.2s',
        marginBottom: '16px',
        ...style 
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = 'rgba(0,0,0,0.03)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent';
      }}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: '-1px' }}>
        <line x1="19" y1="12" x2="5" y2="12"></line>
        <polyline points="12 19 5 12 12 5"></polyline>
      </svg>
      {label}
    </button>
  );
}
