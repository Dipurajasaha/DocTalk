import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../contexts/SessionContext';
import { hospitalApi } from '../lib/api';
import '../styles/hospital.css';

export default function HospitalDashboard() {
  const { session, logout } = useSession();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('overview');
  const [dashboard, setDashboard] = useState(null);
  const [reports, setReports] = useState([]);
  const [newsList, setNewsList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Report form
  const [showReportForm, setShowReportForm] = useState(false);
  const [reportForm, setReportForm] = useState({
    patient_name: '',
    patient_age: '',
    patient_gender: '',
    disease_name: '',
    symptoms: '',
    new_symptoms: '',
    severity: 'moderate',
    onset_date: '',
    additional_notes: '',
    is_anonymous: false,
  });

  // News form
  const [showNewsForm, setShowNewsForm] = useState(false);
  const [newsForm, setNewsForm] = useState({
    title: '',
    content: '',
    category: 'general',
    is_global: false,
    priority: 0,
  });

  const [submitMsg, setSubmitMsg] = useState(null);

  // ─── Load data ───
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dash, rep, news] = await Promise.all([
        hospitalApi.dashboard(),
        hospitalApi.listReports(1, 100),
        hospitalApi.listNews(),
      ]);
      setDashboard(dash);
      setReports(rep.reports || []);
      setNewsList(news || []);
    } catch (err) {
      setError(err?.message || 'Failed to load hospital data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // ─── Submit symptom report ───
  const handleReportSubmit = async (e) => {
    e.preventDefault();
    setSubmitMsg(null);
    try {
      const symptoms = reportForm.symptoms.split(',').map((s) => s.trim()).filter(Boolean);
      const newSymptoms = reportForm.new_symptoms
        ? reportForm.new_symptoms.split(',').map((s) => s.trim()).filter(Boolean)
        : undefined;

      await hospitalApi.createReport({
        patient_name: reportForm.patient_name || undefined,
        patient_age: reportForm.patient_age ? parseInt(reportForm.patient_age) : undefined,
        patient_gender: reportForm.patient_gender || undefined,
        disease_name: reportForm.disease_name,
        symptoms,
        new_symptoms: newSymptoms?.length ? newSymptoms : undefined,
        severity: reportForm.severity,
        onset_date: reportForm.onset_date || undefined,
        additional_notes: reportForm.additional_notes || undefined,
        is_anonymous: reportForm.is_anonymous,
      });

      setSubmitMsg({ type: 'success', text: 'Symptom report submitted successfully!' });
      setShowReportForm(false);
      setReportForm({
        patient_name: '', patient_age: '', patient_gender: '', disease_name: '',
        symptoms: '', new_symptoms: '', severity: 'moderate', onset_date: '',
        additional_notes: '', is_anonymous: false,
      });
      loadData();
    } catch (err) {
      setSubmitMsg({ type: 'error', text: err?.message || 'Failed to submit report' });
    }
  };

  // ─── Submit news ───
  const handleNewsSubmit = async (e) => {
    e.preventDefault();
    setSubmitMsg(null);
    try {
      await hospitalApi.createNews({
        title: newsForm.title,
        content: newsForm.content,
        category: newsForm.category,
        is_global: newsForm.is_global,
        priority: parseInt(newsForm.priority) || 0,
      });
      setSubmitMsg({ type: 'success', text: 'News published successfully!' });
      setShowNewsForm(false);
      setNewsForm({ title: '', content: '', category: 'general', is_global: false, priority: 0 });
      loadData();
    } catch (err) {
      setSubmitMsg({ type: 'error', text: err?.message || 'Failed to publish news' });
    }
  };

  if (loading && !dashboard) {
    return <div className="hospital-loading"><div className="spinner"></div><p>Loading hospital dashboard...</p></div>;
  }

  if (error && !dashboard) {
    return <div className="hospital-error"><h3>Error</h3><p>{error}</p><button onClick={loadData}>Retry</button></div>;
  }

  const severityColors = { mild: '#10b981', moderate: '#f59e0b', severe: '#ef4444', critical: '#7c3aed' };

  return (
    <div className="hospital-dashboard">
      {/* ─── Header ─── */}
      <header className="hospital-header">
        <div className="hospital-header-left">
          <h1>🏥 Hospital Portal</h1>
          <span className="hospital-name">{dashboard?.hospital_name || session?.user_id}</span>
        </div>
        <div className="hospital-header-right">
          <button className="btn btn-outline" onClick={() => navigate('/')}>Home</button>
          <button className="btn btn-danger" onClick={logout}>Logout</button>
        </div>
      </header>

      {/* ─── Flash messages ─── */}
      {submitMsg && (
        <div className={`flash-msg ${submitMsg.type}`}>
          {submitMsg.text}
          <button className="flash-close" onClick={() => setSubmitMsg(null)}>×</button>
        </div>
      )}

      {/* ─── Tabs ─── */}
      <nav className="hospital-tabs">
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>📊 Overview</button>
        <button className={`tab-btn ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => setActiveTab('reports')}>📋 Symptom Reports</button>
        <button className={`tab-btn ${activeTab === 'submit-report' ? 'active' : ''}`} onClick={() => { setActiveTab('submit-report'); setShowReportForm(true); }}>➕ New Report</button>
        <button className={`tab-btn ${activeTab === 'news' ? 'active' : ''}`} onClick={() => setActiveTab('news')}>📰 News</button>
        <button className={`tab-btn ${activeTab === 'analysis' ? 'active' : ''}`} onClick={() => setActiveTab('analysis')}>📈 Analysis</button>
      </nav>

      {/* ─── Tab Content ─── */}
      <div className="hospital-content">
        {/* OVERVIEW */}
        {activeTab === 'overview' && dashboard && (
          <div className="overview-grid">
            <div className="stat-card">
              <div className="stat-icon">📋</div>
              <div className="stat-value">{dashboard.total_reports}</div>
              <div className="stat-label">Total Reports</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">📰</div>
              <div className="stat-value">{dashboard.total_news}</div>
              <div className="stat-label">News Published</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">🦠</div>
              <div className="stat-value">{dashboard.disease_summary?.length || 0}</div>
              <div className="stat-label">Unique Diseases</div>
            </div>
            <div className="stat-card">
              <div className="stat-icon">🔴</div>
              <div className="stat-value">{dashboard.severity_breakdown?.critical || 0}</div>
              <div className="stat-label">Critical Cases</div>
            </div>

            {/* Severity breakdown */}
            <div className="insight-card severity-card">
              <h3>Severity Breakdown</h3>
              <div className="severity-bars">
                {Object.entries(dashboard.severity_breakdown || {}).map(([key, val]) => (
                  <div key={key} className="severity-row">
                    <span className="severity-label" style={{ color: severityColors[key] || '#6b7280' }}>{key}</span>
                    <div className="severity-bar-track">
                      <div className="severity-bar-fill" style={{
                        width: `${Math.max(5, (val / Math.max(1, Math.max(...Object.values(dashboard.severity_breakdown || { mild: 1 })))) * 100)}%`,
                        background: severityColors[key] || '#6b7280',
                      }}></div>
                    </div>
                    <span className="severity-count">{val}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Disease summary */}
            <div className="insight-card disease-card">
              <h3>Disease Summary</h3>
              <div className="disease-list">
                {(dashboard.disease_summary || []).slice(0, 10).map((item) => (
                  <div key={item.disease} className="disease-row">
                    <span className="disease-name">{item.disease}</span>
                    <span className="disease-count">{item.count} reports</span>
                  </div>
                ))}
                {(dashboard.disease_summary || []).length === 0 && (
                  <p className="empty-msg">No reports yet</p>
                )}
              </div>
            </div>

            {/* Recent reports */}
            <div className="insight-card recent-card">
              <h3>Recent Reports</h3>
              {(dashboard.recent_reports || []).length === 0 ? (
                <p className="empty-msg">No recent reports</p>
              ) : (
                <div className="recent-list">
                  {dashboard.recent_reports.map((r) => (
                    <div key={r.id} className="recent-item">
                      <strong>{r.disease_name}</strong>
                      <span className="severity-badge" style={{ background: severityColors[r.severity] || '#6b7280' }}>
                        {r.severity}
                      </span>
                      <small>{new Date(r.created_at).toLocaleDateString()}</small>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* REPORTS LIST */}
        {activeTab === 'reports' && (
          <div className="reports-list-section">
            <div className="section-header">
              <h2>Symptom Reports ({reports.length})</h2>
              <button className="btn btn-primary" onClick={() => { setShowReportForm(true); setActiveTab('submit-report'); }}>+ New Report</button>
            </div>
            {reports.length === 0 ? (
              <p className="empty-msg">No symptom reports submitted yet.</p>
            ) : (
              <div className="reports-table-wrap">
                <table className="reports-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Disease</th>
                      <th>Symptoms</th>
                      <th>New Symptoms</th>
                      <th>Severity</th>
                      <th>Patient</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((r) => (
                      <tr key={r.id}>
                        <td>{new Date(r.created_at).toLocaleDateString()}</td>
                        <td><strong>{r.disease_name}</strong></td>
                        <td>
                          <div className="symptom-tags">
                            {(r.symptoms || []).map((s, i) => (
                              <span key={i} className="symptom-tag">{s}</span>
                            ))}
                          </div>
                        </td>
                        <td>
                          {(r.new_symptoms || []).length > 0 ? (
                            <div className="symptom-tags">
                              {(r.new_symptoms || []).map((s, i) => (
                                <span key={i} className="symptom-tag new-symptom">🆕 {s}</span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </td>
                        <td>
                          <span className="severity-badge" style={{ background: severityColors[r.severity] || '#6b7280' }}>
                            {r.severity}
                          </span>
                        </td>
                        <td>{r.is_anonymous ? 'Anonymous' : (r.patient_name || 'N/A')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* SUBMIT REPORT FORM */}
        {activeTab === 'submit-report' && showReportForm && (
          <div className="form-section">
            <h2>📋 Submit Symptom Report</h2>
            <form onSubmit={handleReportSubmit} className="hospital-form">
              <div className="form-row">
                <div className="form-group">
                  <label>Disease Name *</label>
                  <input type="text" value={reportForm.disease_name} onChange={(e) => setReportForm({ ...reportForm, disease_name: e.target.value })} placeholder="e.g. COVID-19, Influenza" required />
                </div>
                <div className="form-group">
                  <label>Severity</label>
                  <select value={reportForm.severity} onChange={(e) => setReportForm({ ...reportForm, severity: e.target.value })}>
                    <option value="mild">Mild</option>
                    <option value="moderate">Moderate</option>
                    <option value="severe">Severe</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Symptoms (comma separated) *</label>
                <textarea value={reportForm.symptoms} onChange={(e) => setReportForm({ ...reportForm, symptoms: e.target.value })} placeholder="fever, cough, fatigue" rows={2} required />
              </div>

              <div className="form-group highlight-group">
                <label>🆕 New / Unusual Symptoms (comma separated)</label>
                <textarea value={reportForm.new_symptoms} onChange={(e) => setReportForm({ ...reportForm, new_symptoms: e.target.value })} placeholder="e.g. purple rash, loss of smell (leave empty if none)" rows={2} />
                <small className="form-hint">These will be highlighted as potentially novel symptoms for alerting other hospitals</small>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Patient Name</label>
                  <input type="text" value={reportForm.patient_name} onChange={(e) => setReportForm({ ...reportForm, patient_name: e.target.value })} placeholder="Optional" />
                </div>
                <div className="form-group">
                  <label>Age</label>
                  <input type="number" value={reportForm.patient_age} onChange={(e) => setReportForm({ ...reportForm, patient_age: e.target.value })} placeholder="Optional" min={0} max={150} />
                </div>
                <div className="form-group">
                  <label>Gender</label>
                  <select value={reportForm.patient_gender} onChange={(e) => setReportForm({ ...reportForm, patient_gender: e.target.value })}>
                    <option value="">—</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Onset Date</label>
                  <input type="date" value={reportForm.onset_date} onChange={(e) => setReportForm({ ...reportForm, onset_date: e.target.value })} />
                </div>
                <div className="form-group">
                  <label>Additional Notes</label>
                  <input type="text" value={reportForm.additional_notes} onChange={(e) => setReportForm({ ...reportForm, additional_notes: e.target.value })} placeholder="Optional notes" />
                </div>
              </div>

              <div className="form-group checkbox-group">
                <label>
                  <input type="checkbox" checked={reportForm.is_anonymous} onChange={(e) => setReportForm({ ...reportForm, is_anonymous: e.target.checked })} />
                  Submit anonymously (hide patient details)
                </label>
              </div>

              <div className="form-actions">
                <button type="submit" className="btn btn-primary">Submit Report</button>
                <button type="button" className="btn btn-outline" onClick={() => { setShowReportForm(false); setActiveTab('overview'); }}>Cancel</button>
              </div>
            </form>
          </div>
        )}

        {/* NEWS */}
        {activeTab === 'news' && (
          <div className="news-section">
            <div className="section-header">
              <h2>📰 Hospital News & Announcements</h2>
              <button className="btn btn-primary" onClick={() => setShowNewsForm(true)}>+ Publish News</button>
            </div>

            {showNewsForm && (
              <div className="form-section">
                <h3>Publish News</h3>
                <form onSubmit={handleNewsSubmit} className="hospital-form">
                  <div className="form-group">
                    <label>Title *</label>
                    <input type="text" value={newsForm.title} onChange={(e) => setNewsForm({ ...newsForm, title: e.target.value })} placeholder="News title" required maxLength={200} />
                  </div>
                  <div className="form-group">
                    <label>Content *</label>
                    <textarea value={newsForm.content} onChange={(e) => setNewsForm({ ...newsForm, content: e.target.value })} placeholder="News content" rows={4} required />
                  </div>
                  <div className="form-row">
                    <div className="form-group">
                      <label>Category</label>
                      <select value={newsForm.category} onChange={(e) => setNewsForm({ ...newsForm, category: e.target.value })}>
                        <option value="general">General</option>
                        <option value="outbreak">Outbreak Alert</option>
                        <option value="research">Research</option>
                        <option value="policy">Policy</option>
                        <option value="awareness">Awareness</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Priority</label>
                      <input type="number" value={newsForm.priority} onChange={(e) => setNewsForm({ ...newsForm, priority: e.target.value })} min={0} max={10} />
                    </div>
                  </div>
                  <div className="form-group checkbox-group">
                    <label>
                      <input type="checkbox" checked={newsForm.is_global} onChange={(e) => setNewsForm({ ...newsForm, is_global: e.target.checked })} />
                      Share globally (visible to all hospitals & users)
                    </label>
                  </div>
                  <div className="form-actions">
                    <button type="submit" className="btn btn-primary">Publish</button>
                    <button type="button" className="btn btn-outline" onClick={() => setShowNewsForm(false)}>Cancel</button>
                  </div>
                </form>
              </div>
            )}

            {newsList.length === 0 ? (
              <p className="empty-msg">No news published yet.</p>
            ) : (
              <div className="news-list">
                {newsList.map((n) => (
                  <div key={n.id} className={`news-card ${n.is_global ? 'global' : ''}`}>
                    <div className="news-card-header">
                      <h3>{n.title}</h3>
                      <div className="news-badges">
                        {n.is_global && <span className="badge badge-global">🌍 Global</span>}
                        <span className="badge badge-category">{n.category}</span>
                        {n.priority > 5 && <span className="badge badge-high-priority">🔴 High Priority</span>}
                      </div>
                    </div>
                    <p className="news-content">{n.content}</p>
                    <small className="news-date">{new Date(n.published_at).toLocaleString()}</small>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ANALYSIS */}
        {activeTab === 'analysis' && (
          <div className="analysis-section">
            <h2>📈 Centralized Disease Analysis</h2>
            <p className="analysis-subtitle">Aggregated symptom data from all hospitals — useful for research, outbreak detection, and dataset generation.</p>

            <div className="analysis-grid">
              <div className="analysis-card">
                <h3>Severity Distribution</h3>
                <div className="severity-bars">
                  {Object.entries(dashboard?.severity_breakdown || {}).map(([key, val]) => (
                    <div key={key} className="severity-row">
                      <span className="severity-label" style={{ color: severityColors[key] || '#6b7280' }}>{key}</span>
                      <div className="severity-bar-track">
                        <div className="severity-bar-fill" style={{
                          width: `${Math.max(5, (val / Math.max(1, Math.max(...Object.values(dashboard?.severity_breakdown || { mild: 1 })))) * 100)}%`,
                          background: severityColors[key] || '#6b7280',
                        }}></div>
                      </div>
                      <span className="severity-count">{val}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="analysis-card">
                <h3>Top Diseases</h3>
                <div className="disease-list">
                  {(dashboard?.disease_summary || []).length === 0 ? (
                    <p className="empty-msg">No data yet</p>
                  ) : (
                    (dashboard?.disease_summary || []).map((item, i) => (
                      <div key={i} className="disease-row">
                        <span className="disease-rank">#{i + 1}</span>
                        <span className="disease-name">{item.disease}</span>
                        <span className="disease-count">{item.count}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            <div className="global-data-note">
              <h4>🌐 Global Data Access</h4>
              <p>All symptom reports across hospitals are available via the public API for research, ML training, and epidemiological analysis. Data can be exported and used as a centralized healthcare dataset.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}