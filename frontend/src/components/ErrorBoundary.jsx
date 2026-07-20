
import React from 'react';
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return <div style={{padding:'20px',color:'red',background:'white',zIndex:9999,position:'relative'}}><h1>Runtime Error!</h1><pre>{this.state.error.stack}</pre></div>;
    }
    return this.props.children;
  }
}

