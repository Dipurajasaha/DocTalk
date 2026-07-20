import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/home.css';
import { apiClient } from '../lib/apiClient';

// ─── Animated counter hook ────────────────────────────────────────────────────
function useCounter(target, duration = 1800, start = false) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!start) return;
    let startTime = null;
    const step = (timestamp) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(eased * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [target, duration, start]);
  return count;
}

// ─── Intersection Observer hook ───────────────────────────────────────────────
function useInView(threshold = 0.15) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setInView(true); obs.disconnect(); } }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, inView];
}

// ─── Feature card ─────────────────────────────────────────────────────────────
function FeatureCard({ icon, title, desc, delay }) {
  const [ref, inView] = useInView();
  return (
    <div ref={ref} className={`feature-card ${inView ? 'revealed' : ''}`} style={{ animationDelay: `${delay}ms` }}>
      <div className="feature-icon-wrap">{icon}</div>
      <h3>{title}</h3>
      <p>{desc}</p>
    </div>
  );
}

// ─── Stat item ────────────────────────────────────────────────────────────────
function StatItem({ value, suffix, label, startCount }) {
  const count = useCounter(value, 1800, startCount);
  return (
    <div className="stat-item">
      <span className="stat-number">{count.toLocaleString()}{suffix}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

const Home = () => {
  const navigate = useNavigate();
  const [news, setNews] = useState([]);
  const [newsLoading, setNewsLoading] = useState(true);
  const [newsError, setNewsError] = useState(false);
  const [statsRef, statsInView] = useInView(0.3);
  const [stats, setStats] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadNews = async () => {
      try {
        const data = await apiClient.get('/api/public/news', { retries: 1 });
        if (!cancelled) {
          setNews(Array.isArray(data) ? data : []);
          setNewsError(false);
        }
      } catch (_) {
        if (!cancelled) {
          setNews([]);
          setNewsError(true);
        }
      } finally {
        if (!cancelled) setNewsLoading(false);
      }
    };
    loadNews();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const { apiClient } = await import('../lib/apiClient');
        const data = await apiClient.get('/api/public/stats', { retries: 1 });
        setStats(data);
      } catch (_) { setStats(null); }
    };
    loadStats();
  }, []);

  const catConfig = {
    alert: { color: '#ef4444', bg: '#fef2f2', icon: '🚨' },
    announcement: { color: '#3b82f6', bg: '#eff6ff', icon: '📢' },
    'health-tip': { color: '#22c55e', bg: '#f0fdf4', icon: '💡' },
    research: { color: '#8b5cf6', bg: '#f5f3ff', icon: '🔬' },
    general: { color: '#6C5CE7', bg: '#EDE9FE', icon: '📋' },
  };

  return (
    <div className="home-container">

      {/* ══════════════════════════════════ NAVBAR ══════════════════════════════════ */}
      <nav className={`home-navbar ${scrolled ? 'scrolled' : ''}`}>
        <div className="nav-brand">
          <div className="nav-text-logo">DocTalk<span className="logo-sup">AI</span></div>
        </div>
        <ul className="nav-links desktop-only">
          <li><a href="#about">About</a></li>
          <li><a href="#features">Features</a></li>
          <li><a href="#news">News</a></li>
          <li><a href="#team">Team</a></li>
        </ul>
        <div className="nav-actions desktop-only">
          <button onClick={() => navigate('/login')} className="nav-login-btn">Sign In</button>
          <button onClick={() => navigate('/login')} className="nav-cta-btn">Get Started →</button>
        </div>
        <button className="hamburger" onClick={() => setMobileMenuOpen(o => !o)} aria-label="Menu">
          <span></span><span></span><span></span>
        </button>
        {mobileMenuOpen && (
          <div className="mobile-menu">
            <a href="#about" onClick={() => setMobileMenuOpen(false)}>About</a>
            <a href="#features" onClick={() => setMobileMenuOpen(false)}>Features</a>
            <a href="#news" onClick={() => setMobileMenuOpen(false)}>News</a>
            <a href="#team" onClick={() => setMobileMenuOpen(false)}>Team</a>
            <button onClick={() => navigate('/login')} className="nav-cta-btn" style={{ margin: '8px 0 0' }}>Get Started →</button>
          </div>
        )}
      </nav>

      <main className="home-main">

        {/* ══════════════════════════════════ HERO ══════════════════════════════════ */}
        <section className="hero-section">
          <div className="hero-content">
            <div className="hero-badge-pill">
              <span className="badge-dot"></span>
              AI-Powered Healthcare Platform
            </div>
            <h1 className="hero-title">
              The smarter way to<br />
              <span className="hero-title-accent">manage your health</span>
            </h1>
            <p className="hero-subtitle">
              Connect with doctors, access your medical records, and get AI-powered health insights — all in one place. Built for patients, doctors, and hospitals.
            </p>
            <div className="hero-cta-row">
              <button onClick={() => navigate('/login')} className="btn-primary-hero">
                Start for Free
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
              </button>
              <a href="#about" className="btn-ghost-hero">
                Learn more
              </a>
            </div>
            <div className="hero-trust-row">
              <span className="trust-item">✓ Free to use</span>
              <span className="trust-dot">·</span>
              <span className="trust-item">✓ No credit card</span>
              <span className="trust-dot">·</span>
              <span className="trust-item">✓ End-to-end encrypted</span>
            </div>
          </div>

          <div className="hero-visual">
            <div className="hero-card-stack">
              {/* Main card */}
              <div className="hero-main-card">
                <div className="hmc-header">
                  <div className="hmc-avatar">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6C5CE7" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                  </div>
                  <div>
                    <div className="hmc-name">AI Health Assistant</div>
                    <div className="hmc-status"><span className="status-dot"></span> Online</div>
                  </div>
                </div>
                <div className="hmc-msg ai">How can I help you today?</div>
                <div className="hmc-msg user">I've had a headache for 3 days</div>
                <div className="hmc-msg ai typing">
                  <div className="typing-dot"></div><div className="typing-dot"></div><div className="typing-dot"></div>
                </div>
                <div className="hmc-input-row">
                  <span className="hmc-input-fake">Type a message...</span>
                  <button className="hmc-send">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
                  </button>
                </div>
              </div>
              {/* Floating chips */}
              <div className="hero-chip chip-1">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
                Appointment booked
              </div>
              <div className="hero-chip chip-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6C5CE7" strokeWidth="2.5"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                Report analyzed
              </div>
              <div className="hero-chip chip-3">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg>
                Reminder: 3 PM
              </div>
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════ NEWS ══════════════════════════════════ */}
        <section id="news" className="news-section">
          <div className="section-header-center">
            <div className="section-eyebrow">Health News</div>
            <h2 className="section-title">Latest Health News</h2>
            <p className="section-body" style={{ maxWidth: '520px', margin: '0 auto' }}>
              Curated health headlines from around the web, refreshed for you.
            </p>
          </div>

          {newsLoading ? (
            <div className="news-skeleton-grid">
              {[1, 2, 3].map(i => <div key={i} className="news-skeleton-card" />)}
            </div>
          ) : newsError ? (
            <div className="news-empty">
              <div style={{ fontSize: '48px', marginBottom: '12px' }}>⚠️</div>
              <p>Couldn't load health news right now. Make sure the backend server is running.</p>
              <button onClick={() => window.location.reload()} className="btn-primary-hero" style={{ marginTop: '16px' }}>Retry</button>
            </div>
          ) : news.length === 0 ? (
            <div className="news-empty">
              <div style={{ fontSize: '48px', marginBottom: '12px' }}>📰</div>
              <p>No platform updates yet. Check back after the next release.</p>
              <button onClick={() => navigate('/login')} className="btn-primary-hero" style={{ marginTop: '16px' }}>Open the App</button>
            </div>
          ) : (
            <div className="news-grid">
              {news.map((item) => {
                const cfg = catConfig[item.category] || catConfig.general;
                return (
                  <div key={item.id} className="news-card" style={{ borderTopColor: cfg.color }}>
                    <div className="news-card-top">
                      <span className="news-cat-badge" style={{ color: cfg.color, background: cfg.bg }}>
                        {cfg.icon} {item.category}
                      </span>
                      {item.is_global && <span className="news-global-badge">🌍 Global</span>}
                    </div>
                    <h3 className="news-card-title">{item.title}</h3>
                    <p className="news-card-body">
                      {item.content?.length > 110 ? item.content.slice(0, 110) + '…' : item.content}
                    </p>
                    <div className="news-card-footer">
                      <span>{item.hospital_name || 'DocTalk Team'}</span>
                      <span>{new Date(item.published_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* ══════════════════════════════════ STATS ══════════════════════════════════ */}
        <div className="stats-band" ref={statsRef}>
          <StatItem value={stats?.patients || 15000} suffix="+" label="Patients Served" startCount={statsInView} />
          <div className="stats-divider" />
          <StatItem value={stats?.doctors || 850} suffix="+" label="Doctors Registered" startCount={statsInView} />
          <div className="stats-divider" />
          <StatItem value={stats?.admins || 12} suffix="+" label="Admins Registered" startCount={statsInView} />
          <div className="stats-divider" />
          <StatItem value={98} suffix="%" label="Satisfaction Rate" startCount={statsInView} />
        </div>

        {/* ══════════════════════════════════ ABOUT ══════════════════════════════════ */}
        <section id="about" className="about-section">
          <div className="about-left">
            <div className="section-eyebrow">About DocTalk AI</div>
            <h2 className="section-title">Bridging the gap between patients and care</h2>
            <p className="section-body">
              DocTalk AI is a final-year Computer Science engineering project designed to solve real healthcare access problems. We combine large language models, real-time communication, and medical record management into one seamless platform.
            </p>
            <ul className="check-list">
              {['Automated AI pre-screening & triage', 'Secure end-to-end encrypted messaging', 'Centralised medical record storage', 'Smart appointment scheduling', 'Real-time doctor–patient chat', 'Hospital-wide analytics & reporting'].map(item => (
                <li key={item}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6C5CE7" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div className="about-right">
            <div className="about-visual">
              <div className="av-card av-card-top">
                <div className="av-icon-wrap" style={{ background: '#EDE9FE' }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#6C5CE7" strokeWidth="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 10.8 19.79 19.79 0 01.1 2.22 2 2 0 012.08 0h3a2 2 0 012 1.72 12.8 12.8 0 00.7 2.81 2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.8 12.8 0 002.81.7A2 2 0 0122 16.92z" /></svg>
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b' }}>Real-time Consultation</div>
                  <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>WebSocket-powered messaging</div>
                </div>
              </div>
              <div className="av-card av-card-mid">
                <div className="av-icon-wrap" style={{ background: '#f0fdf4' }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b' }}>Data Encrypted</div>
                  <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>All records secured at rest</div>
                </div>
              </div>
              <div className="av-card av-card-bot">
                <div className="av-icon-wrap" style={{ background: '#fff7ed' }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#f97316" strokeWidth="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 00-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0020 4.77 5.07 5.07 0 0019.91 1S18.73.65 16 2.48a13.38 13.38 0 00-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 005 4.77a5.44 5.44 0 00-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 009 18.13V22" /></svg>
                </div>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: '700', color: '#1e293b' }}>Open Source</div>
                  <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>Built with FastAPI + React</div>
                </div>
              </div>
              <div className="av-bg-glow"></div>
            </div>
          </div>
        </section>

        {/* ══════════════════════════════════ FEATURES ══════════════════════════════════ */}
        <section id="features" className="features-section">
          <div className="section-header-center">
            <div className="section-eyebrow">Platform Features</div>
            <h2 className="section-title">Everything you need for digital healthcare</h2>
            <p className="section-body" style={{ maxWidth: '560px', margin: '0 auto' }}>
              A complete suite of tools designed for patients, doctors, and hospital administrators — working together in one unified platform.
            </p>
          </div>
          <div className="features-grid">
            <FeatureCard delay={0} icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>} title="AI Symptom Chat" desc="Describe your symptoms to our AI and get instant preliminary assessments, triage recommendations, and suggested next steps." />
            <FeatureCard delay={80} icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></svg>} title="Smart Scheduling" desc="Browse doctor availability in real time. Book, reschedule, or cancel appointments with just a few clicks, any time." />
            <FeatureCard delay={160} icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>} title="Medical Records Hub" desc="Upload, organise, and share prescriptions, lab reports, and X-rays. All your health documents in one secure place." />
            <FeatureCard delay={240} icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>} title="Med Image Analysis" desc="Upload medical imaging for AI-assisted analysis. Get structured reports highlighting potential areas of concern instantly." />
            <FeatureCard delay={320} icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" /></svg>} title="Doctor Network" desc="Patients can search for verified specialists by specialty, location, or availability and initiate consultations directly." />
            <FeatureCard delay={400} icon={<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>} title="Hospital Analytics" desc="Centralised dashboards for hospital admins with disease surveillance, severity tracking, and exportable datasets." />
          </div>
        </section>

        {/* ══════════════════════════════════ TEAM ══════════════════════════════════ */}
        <section id="team" className="team-section">
          <div className="section-header-center">
            <div className="section-eyebrow">The Team</div>
            <h2 className="section-title">Built by CSE (AIML) students,<br />for real people</h2>
            <p className="section-body" style={{ maxWidth: '480px', margin: '0 auto' }}>
              A five-person final-year capstone team tackling healthcare access through AI.
            </p>
          </div>
          <div className="team-grid">
            {[
              { name: 'Shuvankar Dhara', role: <>Team Lead <br/> Backend & APIs</>, icon: '⚙️', color: '#fef3c7', iconColor: '#d97706' },
              { name: 'Dipu Raja Saha', role: 'AI & ML Integration', icon: '🤖', color: '#dbeafe', iconColor: '#2563eb' },
              { name: 'Sumit Paul', role: 'Workflow & Security', icon: '🔐', color: '#dcfce7', iconColor: '#16a34a' },
              { name: 'Subhobrata Maity', role: 'Frontend & UI/UX', icon: '🎨', color: '#EDE9FE', iconColor: '#6C5CE7' },
              { name: 'Swapnil Chatterjee', role: 'Database Architecture', icon: '🗄️', color: '#fce7f3', iconColor: '#db2777' },
            ].map((dev, i) => (
              <div key={i} className="team-card">
                <div className="team-avatar" style={{ background: dev.color }}>
                  <span style={{ fontSize: '28px' }}>{dev.icon}</span>
                </div>
                <h3>{dev.name}</h3>
                <p className="team-role">{dev.role}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════ CTA ══════════════════════════════════ */}
        <section className="cta-section">
          <div className="cta-inner">
            <div className="cta-glow"></div>
            <h2>Ready to take control of your health?</h2>
            <p>Join thousands of patients and doctors already using DocTalk AI.</p>
            <button onClick={() => navigate('/login')} className="cta-main-btn">
              Get Started for Free
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7" /></svg>
            </button>
            <div className="cta-trust">No credit card required · Free forever plan available</div>
          </div>
        </section>
      </main>

      {/* ══════════════════════════════════ FOOTER ══════════════════════════════════ */}
      <footer className="site-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <div className="nav-text-logo" style={{ color: '#fff', marginBottom: '12px' }}>
              DocTalk<span className="logo-sup" style={{ background: 'linear-gradient(135deg, #a78bfa, #c4b5fd)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>AI</span>
            </div>
            <p className="footer-tagline">AI-powered healthcare for everyone.</p>
            <div className="footer-newsletter">
              <input type="email" placeholder="your@email.com" />
              <button>Subscribe</button>
            </div>
          </div>
          <div className="footer-links-group">
            <div className="footer-col">
              <h4>Platform</h4>
              <a href="#about">About</a>
              <a href="#features">Features</a>
              <a href="#team">Team</a>
            </div>
            <div className="footer-col">
              <h4>For Patients</h4>
              <a href="#">AI Chat</a>
              <a href="#">Find Doctors</a>
              <a href="#">Health Records</a>
            </div>
            <div className="footer-col">
              <h4>For Doctors</h4>
              <a href="#">Provider Portal</a>
              <a href="#">Patient Management</a>
              <a href="#">Scheduling</a>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} DocTalk AI · Academic CSE Project</span>
          <div className="footer-social-row">
            <span>fb</span><span>tw</span><span>in</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Home;
