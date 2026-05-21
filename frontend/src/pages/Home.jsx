import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/home.css';

const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="home-container">
      {/* Navbar */}
      <nav className="home-navbar">
        <div className="nav-text-logo">
          DocTalk<span className="logo-sup">AI</span>
        </div>
        <ul className="nav-links">
          <li><a href="#about">About</a></li>
          <li><a href="#services">Services</a></li>
          <li><a href="#developers">Developers</a></li>
        </ul>
        <div className="home-nav-actions">
          <button onClick={() => navigate('/login')} className="home-login-btn">Get Started</button>
        </div>
      </nav>

      <main className="home-main">
        {/* Hero Section */}
        <section className="hero-section">
          <div className="hero-badge">AI-Powered Healthcare Ecosystem</div>
          <h1 className="hero-title">
            Revolutionize your healthcare <br/>journey with <span className="highlight">DocTalk</span> AI
          </h1>
          <p className="hero-subtitle">
            Experience next-generation symptom assessment, seamless doctor consultations, and centralized medical records management. Connect with providers anytime, anywhere.
          </p>
          <div className="hero-actions">
            <button onClick={() => navigate('/login')} className="primary-btn">Join Now</button>
          </div>
          
          <div className="hero-image-spread">
            <div className="img-box img-small gradient-bg-1">
               <span className="info-tag">AI Chat</span>
            </div>
            <div className="img-box img-large gradient-bg-2">
               <span className="info-tag">Diagnosis</span>
            </div>
            <div className="img-box img-medium gradient-bg-3">
               <span className="info-tag">Appointments</span>
            </div>
          </div>
        </section>

        {/* Core Capabilities Section */}
        <section className="stats-section core-features">
          <div className="stat-card feature-card">
            <h2 className="stat-value" style={{fontSize: '1.5rem', marginBottom: '8px', color: '#333'}}>AI Diagnosis</h2>
            <p className="stat-label">Intelligent symptom analysis 24/7</p>
          </div>
          <div className="stat-card feature-card">
            <h2 className="stat-value" style={{fontSize: '1.5rem', marginBottom: '8px', color: '#333'}}>Direct Chat</h2>
            <p className="stat-label">Communicate securely with specialists</p>
          </div>
          <div className="stat-card feature-card">
            <h2 className="stat-value" style={{fontSize: '1.5rem', marginBottom: '8px', color: '#333'}}>Record Hub</h2>
            <p className="stat-label">Manage your medical history safely</p>
          </div>
        </section>

        {/* Goals Section */}
        <section id="about" className="goal-section">
          <div className="goal-content">
            <h2>Bridging the gap between<br/>technology and care</h2>
            <p>
              DocTalk AI aims to democratize healthcare access. By integrating advanced natural language models with a seamless telemedicine platform, we ensure that every patient question is addressed and every consultation is effective.
            </p>
            <ul className="goal-list">
              <li><span className="check-icon"></span> Automated Pre-screening</li>
              <li><span className="check-icon"></span> Encrypted Messaging</li>
              <li><span className="check-icon"></span> Secure Document Uploads</li>
              <li><span className="check-icon"></span> Flexible Scheduling</li>
              <li><span className="check-icon"></span> Real-time notifications</li>
              <li><span className="check-icon"></span> Doctor Dashboard</li>
            </ul>
          </div>
          <div className="goal-image-wrapper">
             <div className="mock-doctor-img gradient-bg-doctor"></div>
          </div>
        </section>

        {/* Developers Section */}
        <section id="developers" className="developers-section">
          <h2>Meet the Developers</h2>
          <p className="section-subtitle">The innovative team behind this capstone healthcare project.</p>
          <div className="dev-grid">
            {[
              { name: 'Developer 1', role: 'Frontend & UI/UX Design' },
              { name: 'Developer 2', role: 'Backend & APIs' },
              { name: 'Developer 3', role: 'AI Model Integration' },
              { name: 'Developer 4', role: 'Database & Security' }
            ].map((dev, idx) => (
              <div key={idx} className="dev-card">
                 <div className="dev-avatar gradient-bg-avatar"></div>
                 <h3>{dev.name}</h3>
                 <p className="dev-role">{dev.role}</p>
                 <div className="dev-socials">
                    <span className="social-icon">in</span>
                    <span className="social-icon">gh</span>
                 </div>
              </div>
            ))}
          </div>
        </section>

        {/* Services Section */}
        <section id="services" className="vision-section">
          <h2>Our Core Services</h2>
          <p className="section-subtitle">Delivering a comprehensive suite of digital healthcare tools<br/>for patients and medical professionals.</p>
          
          <div className="vision-grid services-grid">
            {[
              { num: '01', title: 'Smart Symptom Checker', desc: 'Interact with our AI assistant to get instant preliminary health assessments.' },
              { num: '02', title: 'Specialist Discovery', desc: 'Find and connect with certified medical experts tailored to your needs.' },
              { num: '03', title: 'Instant Messaging', desc: 'Communicate directly with doctors through a secure chat interface.' },
              { num: '04', title: 'File Management', desc: 'Easily upload, store, and share medical reports and prescriptions.' },
              { num: '05', title: 'Appointment Booking', desc: 'Schedule, reschedule, or cancel visits with specific doctors effortlessly.' },
              { num: '06', title: 'Doctor Dashboard', desc: 'Dedicated tools for professionals to manage patient queues and reviews.' },
            ].map((item, idx) => (
              <div key={idx} className="vision-card service-panel">
                 <div className="card-header">
                    <span className="card-num">{item.num}</span>
                 </div>
                 <h3>{item.title}</h3>
                 <p>{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="cta-section">
           <div className="cta-box">
              <h2>Empower your health journey.<br/>Join DocTalk today.</h2>
              <button onClick={() => navigate('/login')} className="cta-btn">Get Started</button>
           </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="dark-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="nav-text-logo" style={{ color: '#fff', marginBottom: '16px' }}>DocTalk<span className="logo-sup" style={{background: 'linear-gradient(135deg, #fff, #a5b4fc)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'}}>AI</span></div>
            <p className="footer-label">Subscribe our newsletter for platform updates</p>
            <div className="newsletter-input">
              <input type="email" placeholder="Email address..." />
              <button className="subs-btn">Subscribe</button>
            </div>
          </div>
          <div className="footer-links">
            <div className="link-column">
              <h4>Platform</h4>
              <a href="#about">About</a>
              <a href="#services">Features</a>
              <a href="#developers">Team</a>
            </div>
            <div className="link-column">
              <h4>For Patients</h4>
              <a href="#">AI Chat</a>
              <a href="#">Find Doctors</a>
              <a href="#">Health Records</a>
            </div>
            <div className="link-column">
              <h4>For Doctors</h4>
              <a href="#">Provider Network</a>
              <a href="#">Patient Management</a>
              <a href="#">Scheduling</a>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} DocTalk AI. Academic HealthCare Project.</p>
          <div className="footer-social">
             <span>fb</span><span>tw</span><span>in</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Home;