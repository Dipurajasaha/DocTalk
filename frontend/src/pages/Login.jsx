import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/login.css';

export default function Login({ setSession }) {
  const [view, setView] = useState('login'); // 'login' or 'register'
  const [category, setCategory] = useState('patient'); // 'patient' or 'doctor'
  const [errorMsg, setErrorMsg] = useState(null);
  const navigate = useNavigate();

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    formData.append('category', category);

    // Call our FastAPI login endpoint (uses bearer token)
    try {
      const username = formData.get('username');
      const password = formData.get('password');
      let url = '/api/auth/patient/login';
      let body = { username, password };
      if (category === 'doctor') {
        url = '/api/auth/doctor/login';
        body = { doctor_id: username, password };
      }

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await response.json();

      // Expected backend TokenResponse: { access_token, token_type, user_id, role }
      if (response.ok && data && data.access_token) {
        const token = data.access_token;
        const sess = { role: data.role || category, user_id: data.user_id || null };
        try { localStorage.setItem('doctalk_token', token); localStorage.setItem('doctalk_session', JSON.stringify(sess)); } catch (e) {}
        if (setSession) setSession({ ...sess, token });
        if (data.role === 'patient' || category === 'patient') navigate('/patient/dashboard'); else navigate('/doctor/dashboard');
      } else {
        setErrorMsg(data.detail || data.error || 'Invalid credentials');
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
      // Backend expects minimal fields for signup
      let url = '/api/auth/patient/signup';
      let body = {};
      if (category === 'patient') {
        body = { username: formData.get('username'), name: formData.get('name'), password: formData.get('password') };
      } else {
        url = '/api/auth/doctor/signup';
        body = { doctor_id: formData.get('username'), name: formData.get('name'), password: formData.get('password') };
      }

      const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await response.json();

      if (response.ok && data && data.access_token) {
        // Auto-login on successful signup
        const token = data.access_token;
        try { localStorage.setItem('doctalk_token', token); localStorage.setItem('doctalk_session', JSON.stringify({ role: data.role })); } catch (e) {}
        if (setSession) setSession({ role: data.role, user_id: data.user_id, token });
        setView('login');
        setErrorMsg(null);
        alert('Registration successful! You are logged in.');
        if (data.role === 'patient') navigate('/patient/dashboard'); else navigate('/doctor/dashboard');
      } else {
        setErrorMsg(data.detail || data.error || 'Registration failed');
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