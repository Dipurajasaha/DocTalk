import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/login.css';

export default function Login() {
  const [view, setView] = useState('login'); // 'login' or 'register'
  const [category, setCategory] = useState('patient'); // 'patient' or 'doctor'
  const [errorMsg, setErrorMsg] = useState(null);
  const navigate = useNavigate();

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    formData.append('category', category);

    // Call our FastAPI login endpoint
    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        // Instead of JSON, we can just send the FormData exactly as HTML did:
        body: formData, 
        credentials: 'include' // THIS SAVES THE SESSION COOKIE!
      });
      const data = await response.json();
      
      if (data.success) {
        if (category === 'patient') {
          navigate('/patient/dashboard');
        } else {
          navigate('/doctor/dashboard');
        }
      } else {
        setErrorMsg(data.error || 'Invalid credentials');
      }
    } catch (err) {
      setErrorMsg('Server connection error. Is the FastAPI backend running?');
    }
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    formData.append('category', category);

    try {
      const response = await fetch('/api/register', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      
      if (data.success) {
        setView('login');
        setErrorMsg(null);
        alert('Registration successful! Please login.');
      } else {
        setErrorMsg(data.error || 'Registration failed');
      }
    } catch (err) {
      setErrorMsg('Server connection error.');
    }
  };

  return (
    <div className="login-page">
      <div className={`container ${view === 'login' ? 'login-view' : 'register-view'}`}>
        <div className="logo-container">
          <div className="text-logo">
            DocTalk<span className="logo-sup">AI</span>
          </div>
        </div>
      
      {errorMsg && (
        <div style={{ width: '100%', maxWidth: '460px', margin: '0 auto 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div className="flash-msg error">{errorMsg}</div>
        </div>
      )}

      <div className="btn-group">
        <button className={`toggle-tab ${view === 'login' ? 'active' : ''}`} onClick={() => setView('login')}>Login</button>
        <button className={`toggle-tab ${view === 'register' ? 'active' : ''}`} onClick={() => setView('register')}>Register</button>
      </div>

      <div className="category-btns">
        <button className={`toggle-tab ${category === 'patient' ? 'active' : ''}`} onClick={() => setCategory('patient')}>Patient</button>
        <button className={`toggle-tab ${category === 'doctor' ? 'active' : ''}`} onClick={() => setCategory('doctor')}>Doctor</button>
      </div>

      <div key={view + category} className="fade-in">
        {view === 'login' && (
          <div className="single-column-form">
            <form onSubmit={handleLoginSubmit} className="single-column-form">
              <div className="input-field">
                <label>User Name</label>
                <input type="text" name="username" placeholder="Enter username" required />
              </div>
              <div className="input-field">
                <label>Password</label>
                <input type="password" name="password" placeholder="Enter password" required />
              </div>
              <button type="submit" className="action-btn" style={{ width: '100%', marginTop: '10px' }}>
                Login as {category === 'patient' ? 'Patient' : 'Doctor'}
              </button>
            </form>
          </div>
        )}

        {view === 'register' && category === 'patient' && (
          <form onSubmit={handleRegisterSubmit}>
            <div className="form-grid">
              <div className="input-field full-width">
                <label>Name</label>
                <input type="text" name="name" placeholder="Full name" required />
              </div>
              <div className="input-field">
                <label>Date of Birth</label>
                <input type="date" name="dob" required />
              </div>
              <div className="input-field">
                <label>Gender</label>
                <select name="gender" required>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div className="input-field">
                <label>Blood Group</label>
                <input type="text" name="blood_group" placeholder="e.g. A+" required />
              </div>
              <div className="input-field">
                <label>Mobile Number</label>
                <input type="tel" name="mobile" placeholder="Enter mobile number" required />
              </div>
              <div className="input-field full-width">
                <label>Address</label>
                <input type="text" name="address" placeholder="Address" required />
              </div>
              <div className="input-field">
                <label>User Name</label>
                <input type="text" name="username" placeholder="Choose username" required />
              </div>
              <div className="input-field">
                <label>Password</label>
                <input type="password" name="password" placeholder="Choose password" required />
              </div>
              <div className="input-field full-width">
                <button type="submit" className="action-btn" style={{ width: '100%', marginTop: '10px' }}>Register as Patient</button>
              </div>
            </div>
          </form>
        )}

        {view === 'register' && category === 'doctor' && (
          <form onSubmit={handleRegisterSubmit}>
            <div className="form-grid">
              <div className="input-field full-width">
                <label>Name</label>
                <input type="text" name="name" placeholder="Full name" required />
              </div>
              <div className="input-field">
                <label>Date of Birth</label>
                <input type="date" name="dob" required />
              </div>
              <div className="input-field">
                <label>Gender</label>
                <select name="gender" required>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div className="input-field">
                <label>Registration Number</label>
                <input type="text" name="registration_number" placeholder="Enter registration number" required />
              </div>
              <div className="input-field">
                <label>Hospital Name</label>
                <input type="text" name="hospital_name" placeholder="Enter hospital name" required />
              </div>
              <div className="input-field full-width">
                <label>Hospital Location</label>
                <input type="text" name="hospital_location" placeholder="Enter hospital location" required />
              </div>
              <div className="input-field full-width">
                <label>Specialization</label>
                <input type="text" name="specialization" placeholder="Enter specialization" required />
              </div>
              <div className="input-field">
                <label>User Name</label>
                <input type="text" name="username" placeholder="Choose username" required />
              </div>
              <div className="input-field">
                <label>Password</label>
                <input type="password" name="password" placeholder="Choose password" required />
              </div>
              <div className="input-field full-width">
                <button type="submit" className="action-btn" style={{ width: '100%', marginTop: '10px' }}>Register as Doctor</button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
    </div>
  );
}