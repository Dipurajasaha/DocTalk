import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../contexts/SessionContext';
import { authApi } from '../lib/api';
import '../styles/login.css';

// ─── Validation helpers ───────────────────────────────────────────────────────
const BLOOD_GROUPS = ['A+','A-','B+','B-','AB+','AB-','O+','O-'];
const SPECIALIZATIONS = [
  'General Medicine','Cardiology','Neurology','Orthopedics','Dermatology',
  'Pediatrics','Gynecology','Oncology','Ophthalmology','ENT','Psychiatry',
  'Radiology','Anesthesiology','Urology','Endocrinology','Nephrology',
  'Gastroenterology','Pulmonology','Rheumatology','Other',
];
const NEWS_CATEGORIES = ['general','announcement','alert','health-tip','research'];

const isValidUsername = (v) => /^[a-zA-Z0-9_]{4,20}$/.test(v);
const isValidPassword = (v) => v.length >= 8 && /[A-Z]/.test(v) && /[0-9]/.test(v);
const isValidPhone    = (v) => /^[+]?[\d\s\-()]{7,15}$/.test(v.trim());
const isValidEmail    = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());
const isValidRegNo    = (v) => /^[A-Z0-9\-\/]{3,20}$/i.test(v.trim());
const isValidName     = (v) => v.trim().length >= 2 && !/[<>{}]/.test(v);
const isAdultDob      = (dob) => {
  if (!dob) return false;
  const birth = new Date(dob);
  const today = new Date();
  const age = today.getFullYear() - birth.getFullYear() -
    (today < new Date(today.getFullYear(), birth.getMonth(), birth.getDate()) ? 1 : 0);
  return age >= 0 && age <= 120;
};
const isDoctorAge = (dob) => {
  if (!dob) return false;
  const birth = new Date(dob);
  const today = new Date();
  const age = today.getFullYear() - birth.getFullYear() -
    (today < new Date(today.getFullYear(), birth.getMonth(), birth.getDate()) ? 1 : 0);
  return age >= 22 && age <= 80;
};

function FieldError({ msg }) {
  if (!msg) return null;
  return <span style={{ color:'#c62828', fontSize:'11px', marginTop:'3px', display:'block' }}>{msg}</span>;
}

function PasswordStrength({ value }) {
  if (!value) return null;
  const checks = [
    { label: '8+ chars',     ok: value.length >= 8 },
    { label: 'Uppercase',    ok: /[A-Z]/.test(value) },
    { label: 'Number',       ok: /[0-9]/.test(value) },
    { label: 'Special char', ok: /[^a-zA-Z0-9]/.test(value) },
  ];
  const score = checks.filter(c => c.ok).length;
  const color = score <= 1 ? '#ef4444' : score === 2 ? '#f97316' : score === 3 ? '#eab308' : '#22c55e';
  const label = ['Weak','Fair','Good','Strong'][score - 1] || 'Weak';
  return (
    <div style={{ marginTop: '6px' }}>
      <div style={{ display:'flex', gap:'4px', marginBottom:'4px' }}>
        {[1,2,3,4].map(i => (
          <div key={i} style={{ flex:1, height:'3px', borderRadius:'2px', background: i <= score ? color : '#e5e7eb', transition:'background 0.2s' }} />
        ))}
      </div>
      <div style={{ display:'flex', gap:'8px', flexWrap:'wrap' }}>
        {checks.map(c => (
          <span key={c.label} style={{ fontSize:'10px', color: c.ok ? '#22c55e' : '#9ca3af' }}>
            {c.ok ? '✓' : '○'} {c.label}
          </span>
        ))}
        <span style={{ fontSize:'10px', color, fontWeight:'600', marginLeft:'auto' }}>{label}</span>
      </div>
    </div>
  );
}

export default function Login() {
  const [view, setView] = useState('login');       // 'login' | 'register' | 'forgot'
  const [category, setCategory] = useState('patient');
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [pwValue, setPwValue] = useState('');
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSent, setForgotSent] = useState(false);
  const navigate = useNavigate();
  const { login } = useSession();

  const setFE = (key, msg) => setFieldErrors(prev => ({ ...prev, [key]: msg }));
  const clearFE = (key) => setFE(key, undefined);

  // ─── Login ───────────────────────────────────────────────────────────────
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    const fd = new FormData(e.target);
    const username = fd.get('username').trim();
    const password = fd.get('password');
    let errs = {};
    if (!username) errs.lu = 'Username is required.';
    if (!password) errs.lp = 'Password is required.';
    if (Object.keys(errs).length) { setFieldErrors(errs); return; }
    setFieldErrors({});
    try {
      let data;
      if (category === 'doctor') {
        data = await authApi.loginDoctor(username, password);
      } else if (category === 'hospital') {
        const { hospitalApi } = await import('../lib/api');
        data = await hospitalApi.login(username, password);
      } else {
        data = await authApi.loginPatient(username, password);
      }
      if (data?.access_token) {
        const token = data.access_token;
        const uid = data.hospital_id || data.user_id || username;
        const sess = { role: data.role || category, user_id: uid };
        try { localStorage.setItem('doctalk_token', token); localStorage.setItem('doctalk_session', JSON.stringify(sess)); } catch (_) {}
        if (login) await login({ token, sessionHint: sess });
        if (category === 'hospital') navigate('/hospital/dashboard');
        else if (data.role === 'patient' || category === 'patient') navigate('/patient/dashboard');
        else navigate('/doctor/dashboard');
      } else {
        setErrorMsg((data && (data.detail || data.error)) || 'Invalid credentials');
      }
    } catch (err) {
      setErrorMsg(err?.message || 'Server connection error. Is the backend running?');
    }
  };

  // ─── Register ────────────────────────────────────────────────────────────
  const validateRegister = (fd, cat) => {
    const errs = {};
    const name     = fd.get('name')?.trim() || '';
    const username = fd.get('username')?.trim() || '';
    const password = fd.get('password') || '';
    const dob      = fd.get('dob') || '';

    if (!isValidName(name))     errs.name = 'Enter a real full name (2+ characters, no special chars).';
    if (!isValidUsername(username)) errs.username = 'Username: 4–20 chars, letters/numbers/underscore only.';
    if (!isValidPassword(password)) errs.password = 'Password must be 8+ chars with at least 1 uppercase and 1 number.';

    if (cat === 'patient') {
      if (!isAdultDob(dob)) errs.dob = 'Enter a valid date of birth.';
      const blood = fd.get('blood_group')?.trim() || '';
      if (!BLOOD_GROUPS.includes(blood)) errs.blood_group = 'Select a valid blood group (e.g. A+, O-, AB+).';
      const mobile = fd.get('mobile')?.trim() || '';
      if (!isValidPhone(mobile)) errs.mobile = 'Enter a valid mobile number.';
      const address = fd.get('address')?.trim() || '';
      if (address.length < 5) errs.address = 'Enter a valid address (5+ characters).';
    }

    if (cat === 'doctor') {
      if (!isDoctorAge(dob)) errs.dob = 'Doctor must be between 22 and 80 years old.';
      const regNo = fd.get('registration_number')?.trim() || '';
      if (!isValidRegNo(regNo)) errs.registration_number = 'Registration number: 3–20 alphanumeric chars.';
      const spec = fd.get('specialization')?.trim() || '';
      if (!spec) errs.specialization = 'Specialization is required.';
      const mobile = fd.get('mobile')?.trim() || '';
      if (mobile && !isValidPhone(mobile)) errs.mobile = 'Enter a valid mobile number.';
      const email = fd.get('email')?.trim() || '';
      if (email && !isValidEmail(email)) errs.email = 'Enter a valid email address.';
    }

    if (cat === 'hospital') {
      const regNo = fd.get('registration_number')?.trim() || '';
      if (regNo && !isValidRegNo(regNo)) errs.registration_number = 'Registration number: 3–20 alphanumeric chars.';
      const phone = fd.get('phone')?.trim() || '';
      if (phone && !isValidPhone(phone)) errs.phone = 'Enter a valid phone number.';
      const email = fd.get('email')?.trim() || '';
      if (email && !isValidEmail(email)) errs.email = 'Enter a valid email address.';
    }

    return errs;
  };

  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    const fd = new FormData(e.target);
    const errs = validateRegister(fd, category);
    if (Object.keys(errs).length) { setFieldErrors(errs); return; }
    setFieldErrors({});

    try {
      const username = fd.get('username').trim();
      const name     = fd.get('name').trim();
      const password = fd.get('password');
      let data;

      if (category === 'hospital') {
        const { hospitalApi } = await import('../lib/api');
        const payload = { hospital_id: username, name, password };
        ['address','city','state','registration_number','phone','email','website'].forEach(k => {
          const v = fd.get(k); if (v) payload[k] = v;
        });
        data = await hospitalApi.signup(payload);
      } else if (category === 'patient') {
        data = await authApi.signupPatient(username, name, password);
      } else {
        data = await authApi.signupDoctor(username, name, password);
      }

      if (data?.access_token) {
        const token = data.access_token;
        try { localStorage.setItem('doctalk_token', token); localStorage.setItem('doctalk_session', JSON.stringify({ role: data.role })); } catch (_) {}
        if (login) await login({ token, sessionHint: { role: data.role, user_id: data.user_id || data.hospital_id } });
        setView('login'); setErrorMsg(null);
        alert('Registration successful! You are logged in.');
        if (category === 'hospital') navigate('/hospital/dashboard');
        else if (data.role === 'patient') navigate('/patient/dashboard');
        else navigate('/doctor/dashboard');
      } else {
        setErrorMsg((data && (data.detail || data.error)) || 'Registration failed');
      }
    } catch (err) {
      setErrorMsg(err?.message || 'Server connection error.');
    }
  };

  // ─── Forgot Password ──────────────────────────────────────────────────────
  const handleForgotSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!isValidEmail(forgotEmail)) { setErrorMsg('Please enter a valid email address.'); return; }
    // In a real app this would call an API endpoint. For now we simulate it.
    try {
      // await authApi.forgotPassword(forgotEmail, category);
      setForgotSent(true);
    } catch (err) {
      setErrorMsg(err?.message || 'Failed to send reset email.');
    }
  };

  // ─── Input helpers ────────────────────────────────────────────────────────
  const F = ({ label, name, type='text', placeholder='', required=false, children, hint }) => (
    <div className="input-field">
      <label>{label}{required && <span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span>}</label>
      {children || (
        <input
          type={type}
          name={name}
          placeholder={placeholder}
          required={required}
          onChange={() => clearFE(name)}
          style={fieldErrors[name] ? { borderColor:'#ef4444' } : {}}
        />
      )}
      {hint && !fieldErrors[name] && <span style={{ fontSize:'11px', color:'#9ca3af', marginTop:'3px', display:'block' }}>{hint}</span>}
      <FieldError msg={fieldErrors[name]} />
    </div>
  );

  return (
    <div className="login-page">
      <div className={`container ${view === 'login' || view === 'forgot' ? 'login-view' : 'register-view'}`}>
        <div className="logo-container">
          <div className="text-logo">DocTalk<span className="logo-sup">AI</span></div>
        </div>

        {errorMsg && (
          <div style={{ width:'100%', maxWidth:'460px', margin:'0 auto 14px' }}>
            <div className="flash-msg error">{errorMsg}</div>
          </div>
        )}
        {successMsg && (
          <div style={{ width:'100%', maxWidth:'460px', margin:'0 auto 14px' }}>
            <div className="flash-msg" style={{ background:'#e8f5e9', border:'1px solid #a5d6a7', color:'#2e7d32' }}>{successMsg}</div>
          </div>
        )}

        {/* ── Forgot Password View ── */}
        {view === 'forgot' && (
          <div className="fade-in">
            <h3 style={{ textAlign:'center', marginBottom:'6px', color:'#2D3748', fontSize:'16px' }}>Reset Password</h3>
            <p style={{ textAlign:'center', fontSize:'13px', color:'#6B6B6B', marginBottom:'20px' }}>
              Enter your registered email. We'll send a reset link.
            </p>
            {forgotSent ? (
              <div style={{ textAlign:'center', padding:'20px' }}>
                <div style={{ fontSize:'40px', marginBottom:'12px' }}>📧</div>
                <p style={{ color:'#2e7d32', fontWeight:'600', marginBottom:'8px' }}>Reset link sent!</p>
                <p style={{ color:'#6B6B6B', fontSize:'13px', marginBottom:'20px' }}>
                  Check your inbox at <strong>{forgotEmail}</strong> for the password reset link.
                </p>
                <button className="action-btn" style={{ width:'100%' }} onClick={() => { setView('login'); setForgotSent(false); setForgotEmail(''); }}>
                  Back to Login
                </button>
              </div>
            ) : (
              <form onSubmit={handleForgotSubmit} className="single-column-form">
                <div className="category-btns" style={{ marginBottom:'16px' }}>
                  {['patient','doctor','hospital'].map(c => (
                    <button key={c} type="button" className={`toggle-tab ${category === c ? 'active' : ''}`} onClick={() => setCategory(c)}>
                      {c.charAt(0).toUpperCase() + c.slice(1)}
                    </button>
                  ))}
                </div>
                <div className="input-field">
                  <label>Email Address<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                  <input
                    type="email"
                    placeholder="Enter your registered email"
                    value={forgotEmail}
                    onChange={e => setForgotEmail(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="action-btn" style={{ width:'100%', marginTop:'10px' }}>
                  Send Reset Link
                </button>
                <button type="button" onClick={() => { setView('login'); setErrorMsg(null); }}
                  style={{ background:'none', border:'none', color:'#8B7EFF', cursor:'pointer', fontSize:'13px', fontWeight:'600', textAlign:'center', marginTop:'4px' }}>
                  ← Back to Login
                </button>
              </form>
            )}
          </div>
        )}

        {/* ── Login / Register View ── */}
        {view !== 'forgot' && (
          <>
            <div className="btn-group">
              <button className={`toggle-tab ${view === 'login' ? 'active' : ''}`} onClick={() => { setView('login'); setErrorMsg(null); setFieldErrors({}); }}>Login</button>
              <button className={`toggle-tab ${view === 'register' ? 'active' : ''}`} onClick={() => { setView('register'); setErrorMsg(null); setFieldErrors({}); }}>Register</button>
            </div>

            <div className="category-btns">
              {['patient','doctor','hospital'].map(c => (
                <button key={c} className={`toggle-tab ${category === c ? 'active' : ''}`} onClick={() => { setCategory(c); setFieldErrors({}); setErrorMsg(null); }}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </button>
              ))}
            </div>

            <div key={view + category} className="fade-in">

              {/* ── Login form ── */}
              {view === 'login' && (
                <div className="single-column-form">
                  <form onSubmit={handleLoginSubmit} className="single-column-form">
                    <div className="input-field">
                      <label>Username<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="text" name="username" placeholder="Enter your username" required
                        onChange={() => clearFE('lu')}
                        style={fieldErrors.lu ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.lu} />
                    </div>
                    <div className="input-field">
                      <label>Password<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="password" name="password" placeholder="Enter your password" required
                        onChange={() => clearFE('lp')}
                        style={fieldErrors.lp ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.lp} />
                    </div>

                    {/* Forgot Password link */}
                    <div style={{ textAlign:'right', marginTop:'-8px' }}>
                      <button type="button"
                        onClick={() => { setView('forgot'); setErrorMsg(null); setFieldErrors({}); }}
                        style={{ background:'none', border:'none', color:'#8B7EFF', cursor:'pointer', fontSize:'12px', fontWeight:'600', padding:'0', textDecoration:'underline' }}>
                        Forgot Password?
                      </button>
                    </div>

                    <button type="submit" className="action-btn" style={{ width:'100%', marginTop:'8px' }}>
                      Login as {category === 'patient' ? 'Patient' : category === 'doctor' ? 'Doctor' : 'Hospital'}
                    </button>
                  </form>
                </div>
              )}

              {/* ── Patient Register ── */}
              {view === 'register' && category === 'patient' && (
                <form onSubmit={handleRegisterSubmit}>
                  <div className="form-grid">
                    <F label="Full Name" name="name" placeholder="e.g. Rahul Kumar" required
                      hint="2+ characters, no special symbols" />
                    <F label="Date of Birth" name="dob" type="date" required />
                    <div className="input-field">
                      <label>Gender<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <select name="gender" required>
                        <option value="">— Select gender —</option>
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                        <option value="Other">Other</option>
                      </select>
                    </div>
                    <div className="input-field">
                      <label>Blood Group<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <select name="blood_group" required onChange={() => clearFE('blood_group')}
                        style={fieldErrors.blood_group ? { borderColor:'#ef4444' } : {}}>
                        <option value="">— Select —</option>
                        {BLOOD_GROUPS.map(b => <option key={b} value={b}>{b}</option>)}
                      </select>
                      <FieldError msg={fieldErrors.blood_group} />
                    </div>
                    <div className="input-field">
                      <label>Mobile Number<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="tel" name="mobile" placeholder="+91 98765 43210" required
                        onChange={() => clearFE('mobile')}
                        style={fieldErrors.mobile ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.mobile} />
                    </div>
                    <F label="Email Address" name="email" type="email" placeholder="you@example.com" hint="Optional" />
                    <div className="input-field full-width">
                      <label>Address<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="text" name="address" placeholder="House/Street, City, State" required
                        onChange={() => clearFE('address')}
                        style={fieldErrors.address ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.address} />
                    </div>
                    <div className="input-field">
                      <label>Username<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="text" name="username" placeholder="4–20 chars, a–z 0–9 _" required
                        onChange={() => clearFE('username')}
                        style={fieldErrors.username ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.username} />
                    </div>
                    <div className="input-field">
                      <label>Password<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="password" name="password" placeholder="Min 8 chars" required
                        onChange={e => { setPwValue(e.target.value); clearFE('password'); }}
                        style={fieldErrors.password ? { borderColor:'#ef4444' } : {}} />
                      <PasswordStrength value={pwValue} />
                      <FieldError msg={fieldErrors.password} />
                    </div>
                    <div className="input-field full-width">
                      <button type="submit" className="action-btn" style={{ width:'100%', marginTop:'10px' }}>Register as Patient</button>
                    </div>
                  </div>
                </form>
              )}

              {/* ── Doctor Register ── */}
              {view === 'register' && category === 'doctor' && (
                <form onSubmit={handleRegisterSubmit}>
                  <div className="form-grid">
                    <F label="Full Name" name="name" placeholder="Dr. Priya Sharma" required hint="Must match official records" />
                    <div className="input-field">
                      <label>Date of Birth<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="date" name="dob" required
                        onChange={() => clearFE('dob')}
                        style={fieldErrors.dob ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.dob} />
                    </div>
                    <div className="input-field">
                      <label>Gender<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <select name="gender" required>
                        <option value="">— Select gender —</option>
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                        <option value="Other">Other</option>
                      </select>
                    </div>
                    <div className="input-field">
                      <label>Specialization<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <select name="specialization" required onChange={() => clearFE('specialization')}
                        style={fieldErrors.specialization ? { borderColor:'#ef4444' } : {}}>
                        <option value="">— Select specialization —</option>
                        {SPECIALIZATIONS.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                      <FieldError msg={fieldErrors.specialization} />
                    </div>
                    <div className="input-field">
                      <label>Medical Registration No.<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="text" name="registration_number" placeholder="e.g. MCI-2024-78901" required
                        onChange={() => clearFE('registration_number')}
                        style={fieldErrors.registration_number ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.registration_number} />
                    </div>
                    <F label="Years of Experience" name="experience" type="number" placeholder="e.g. 5" />
                    <F label="Hospital / Clinic Name" name="hospital_name" placeholder="City Medical Centre" required />
                    <F label="Hospital Location" name="hospital_location" placeholder="City, State" required />
                    <div className="input-field">
                      <label>Mobile Number<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="tel" name="mobile" placeholder="+91 98765 43210" required
                        onChange={() => clearFE('mobile')}
                        style={fieldErrors.mobile ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.mobile} />
                    </div>
                    <div className="input-field">
                      <label>Email Address<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="email" name="email" placeholder="doctor@hospital.com" required
                        onChange={() => clearFE('email')}
                        style={fieldErrors.email ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.email} />
                    </div>
                    <div className="input-field">
                      <label>Username<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="text" name="username" placeholder="4–20 chars, a–z 0–9 _" required
                        onChange={() => clearFE('username')}
                        style={fieldErrors.username ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.username} />
                    </div>
                    <div className="input-field">
                      <label>Password<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="password" name="password" placeholder="Min 8 chars, 1 uppercase, 1 number" required
                        onChange={e => { setPwValue(e.target.value); clearFE('password'); }}
                        style={fieldErrors.password ? { borderColor:'#ef4444' } : {}} />
                      <PasswordStrength value={pwValue} />
                      <FieldError msg={fieldErrors.password} />
                    </div>
                    <div className="input-field full-width">
                      <button type="submit" className="action-btn" style={{ width:'100%', marginTop:'10px' }}>Register as Doctor</button>
                    </div>
                  </div>
                </form>
              )}

              {/* ── Hospital Register ── */}
              {view === 'register' && category === 'hospital' && (
                <form onSubmit={handleRegisterSubmit}>
                  <div className="form-grid">
                    <div className="input-field full-width">
                      <label>Hospital Name<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="text" name="name" placeholder="Full official hospital name" required
                        onChange={() => clearFE('name')}
                        style={fieldErrors.name ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.name} />
                    </div>
                    <div className="input-field">
                      <label>Hospital ID<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="text" name="username" placeholder="Unique login ID (4–20 chars)" required
                        onChange={() => clearFE('username')}
                        style={fieldErrors.username ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.username} />
                    </div>
                    <div className="input-field">
                      <label>Password<span style={{ color:'#ef4444', marginLeft:'2px' }}>*</span></label>
                      <input type="password" name="password" placeholder="Min 8 chars" required
                        onChange={e => { setPwValue(e.target.value); clearFE('password'); }}
                        style={fieldErrors.password ? { borderColor:'#ef4444' } : {}} />
                      <PasswordStrength value={pwValue} />
                      <FieldError msg={fieldErrors.password} />
                    </div>
                    <div className="input-field full-width">
                      <label>Address</label>
                      <input type="text" name="address" placeholder="Building, Street, Area" />
                    </div>
                    <F label="City" name="city" placeholder="e.g. Kolkata" />
                    <F label="State" name="state" placeholder="e.g. West Bengal" />
                    <div className="input-field">
                      <label>Registration Number</label>
                      <input type="text" name="registration_number" placeholder="e.g. WBMC-2024-001"
                        onChange={() => clearFE('registration_number')}
                        style={fieldErrors.registration_number ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.registration_number} />
                    </div>
                    <div className="input-field">
                      <label>Phone</label>
                      <input type="tel" name="phone" placeholder="+91 33 2222 1111"
                        onChange={() => clearFE('phone')}
                        style={fieldErrors.phone ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.phone} />
                    </div>
                    <div className="input-field">
                      <label>Email</label>
                      <input type="email" name="email" placeholder="admin@hospital.com"
                        onChange={() => clearFE('email')}
                        style={fieldErrors.email ? { borderColor:'#ef4444' } : {}} />
                      <FieldError msg={fieldErrors.email} />
                    </div>
                    <F label="Website" name="website" type="url" placeholder="https://hospital.com" />
                    <div className="input-field full-width">
                      <button type="submit" className="action-btn" style={{ width:'100%', marginTop:'10px' }}>Register as Hospital</button>
                    </div>
                  </div>
                </form>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
