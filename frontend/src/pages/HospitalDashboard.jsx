import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSession } from '../contexts/SessionContext';
import { hospitalApi } from '../lib/api';
import '../styles/hospital.css';

// ─── tiny helpers ─────────────────────────────────────────────────────────────
const sev = { mild:'#22c55e', moderate:'#f59e0b', severe:'#ef4444', critical:'#7c3aed' };
const sevBg = { mild:'#f0fdf4', moderate:'#fffbeb', severe:'#fef2f2', critical:'#faf5ff' };
const catCfg = {
  general:      { color:'#6C5CE7', bg:'#EDE9FE', icon:'📋' },
  outbreak:     { color:'#ef4444', bg:'#fef2f2', icon:'🚨' },
  research:     { color:'#8b5cf6', bg:'#f5f3ff', icon:'🔬' },
  policy:       { color:'#3b82f6', bg:'#eff6ff', icon:'📜' },
  awareness:    { color:'#22c55e', bg:'#f0fdf4', icon:'💡' },
  announcement: { color:'#f97316', bg:'#fff7ed', icon:'📢' },
};
const fmt = (d) => new Date(d).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'});
const fmtTime = (d) => new Date(d).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'});

function SevBadge({ level }) {
  return (
    <span style={{ padding:'3px 10px', borderRadius:'50px', fontSize:'11px', fontWeight:'700',
      background: sevBg[level]||'#f1f5f9', color: sev[level]||'#64748B', textTransform:'uppercase', letterSpacing:'0.4px' }}>
      {level}
    </span>
  );
}

function EmptyState({ icon, title, sub, action, onAction }) {
  return (
    <div className="h-empty">
      <div style={{ fontSize:'48px', marginBottom:'12px' }}>{icon}</div>
      <div style={{ fontWeight:'700', color:'#1e293b', marginBottom:'6px' }}>{title}</div>
      <div style={{ color:'#94a3b8', fontSize:'13px', marginBottom: action?'16px':0 }}>{sub}</div>
      {action && <button className="h-btn-primary" onClick={onAction}>{action}</button>}
    </div>
  );
}

// ─── Donut SVG chart ──────────────────────────────────────────────────────────
function Donut({ data, size=120 }) {
  const total = data.reduce((s,d)=>s+d.v,0)||1;
  let cum=0;
  const cx=size/2, cy=size/2, r=size*0.38, inner=size*0.22;
  const slices = data.map((d,i)=>{
    const pct=d.v/total, sa=cum*2*Math.PI-Math.PI/2;
    cum+=pct;
    const ea=cum*2*Math.PI-Math.PI/2;
    const x1=cx+r*Math.cos(sa), y1=cy+r*Math.sin(sa);
    const x2=cx+r*Math.cos(ea), y2=cy+r*Math.sin(ea);
    return {...d, path:`M${cx} ${cy} L${x1} ${y1} A${r} ${r} 0 ${pct>0.5?1:0} 1 ${x2} ${y2}Z`, pct};
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {slices.map((s,i)=><path key={i} d={s.path} fill={s.color} opacity={0.9}/>)}
      <circle cx={cx} cy={cy} r={inner} fill="#fff"/>
      <text x={cx} y={cy-3} textAnchor="middle" fontSize={size*0.12} fontWeight="800" fill="#0f172a">{total}</text>
      <text x={cx} y={cy+size*0.1} textAnchor="middle" fontSize={size*0.08} fill="#94a3b8">total</text>
    </svg>
  );
}

// ─── Modal wrapper ────────────────────────────────────────────────────────────
function Modal({ open, onClose, title, children, width=520 }) {
  useEffect(()=>{
    if(open) document.body.style.overflow='hidden';
    else document.body.style.overflow='';
    return ()=>{document.body.style.overflow='';};
  },[open]);
  if(!open) return null;
  return (
    <div className="h-modal-backdrop" onClick={onClose}>
      <div className="h-modal" style={{maxWidth:width}} onClick={e=>e.stopPropagation()}>
        <div className="h-modal-header">
          <span className="h-modal-title">{title}</span>
          <button className="h-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="h-modal-body">{children}</div>
      </div>
    </div>
  );
}

// ─── Form field helper ────────────────────────────────────────────────────────
function FF({ label, required, children, hint }) {
  return (
    <div className="h-ff">
      <label className="h-ff-label">{label}{required&&<span style={{color:'#ef4444',marginLeft:'2px'}}>*</span>}</label>
      {children}
      {hint && <span className="h-ff-hint">{hint}</span>}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function HospitalDashboard() {
  const { session, logout } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState('overview');
  const [dashboard, setDashboard] = useState(null);
  const [reports, setReports] = useState([]);
  const [newsList, setNewsList] = useState([]);
  const [patients, setPatients] = useState([]);
  const [detailedAnalysis, setDetailedAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  // modals
  const [reportModal, setReportModal] = useState(false);
  const [newsModal, setNewsModal]     = useState(false);
  const [patientModal, setPatientModal] = useState(false);
  const [patientDetailModal, setPatientDetailModal] = useState(false);

  // report form
  const blankReport = { patient_name:'', patient_age:'', patient_gender:'', patient_username:'', disease_name:'', symptoms:'', new_symptoms:'', severity:'moderate', status:'admitted', onset_date:'', additional_notes:'', is_anonymous:false };
  const [rForm, setRForm] = useState(blankReport);
  const [rSubmitting, setRSubmitting] = useState(false);

  // news form
  const blankNews = { title:'', content:'', category:'general', is_global:false, priority:0 };
  const [nForm, setNForm] = useState(blankNews);
  const [nSubmitting, setNSubmitting] = useState(false);

  // patient form
  const blankPatient = { username:'', name:'', password:'Password123', email:'', mobile:'', gender:'', blood_group:'', address:'' };
  const [pForm, setPForm] = useState(blankPatient);
  const [pSubmitting, setPSubmitting] = useState(false);

  // patient detail
  const [patientDetail, setPatientDetail] = useState(null);
  const [patientDetailLoading, setPatientDetailLoading] = useState(false);

  // reports filter/search
  const [reportSearch, setReportSearch] = useState('');
  const [reportSevFilter, setReportSevFilter] = useState('all');
  const [expandedReport, setExpandedReport] = useState(null);

  const showToast = (msg, type='success') => {
    setToast({ msg, type });
    setTimeout(()=>setToast(null), 3500);
  };

  const loadData = useCallback(async()=>{
    setLoading(true); setError(null);
    try {
      const [dash, rep, news] = await Promise.all([
        hospitalApi.dashboard(),
        hospitalApi.listReports(1,100),
        hospitalApi.listNews(),
      ]);
      setDashboard(dash);
      setReports(rep.reports||[]);
      setNewsList(news||[]);
      setPatients(dash.patients||[]);
      if (dash.detailed_analysis) {
        setDetailedAnalysis(dash.detailed_analysis);
      }
    } catch(err) {
      setError(err?.message||'Failed to load dashboard');
    } finally { setLoading(false); }
  },[]);

  useEffect(()=>{ loadData(); },[loadData]);

  // Load detailed analysis separately when analysis tab opens
  const loadDetailedAnalysis = useCallback(async()=>{
    setAnalysisLoading(true);
    try {
      const analysis = await hospitalApi.getDetailedAnalysis();
      setDetailedAnalysis(analysis);
    } catch(err) {
      // Fallback to dashboard data
      if (dashboard?.detailed_analysis) {
        setDetailedAnalysis(dashboard.detailed_analysis);
      }
    } finally { setAnalysisLoading(false); }
  },[dashboard]);

  useEffect(()=>{
    if (tab === 'analysis') {
      loadDetailedAnalysis();
    }
  },[tab, loadDetailedAnalysis]);

  const handleReportSubmit = async(e)=>{
    e.preventDefault(); setRSubmitting(true);
    try {
      await hospitalApi.createReport({
        ...rForm,
        patient_age: rForm.patient_age ? parseInt(rForm.patient_age) : undefined,
        symptoms: rForm.symptoms.split(',').map(s=>s.trim()).filter(Boolean),
        new_symptoms: rForm.new_symptoms ? rForm.new_symptoms.split(',').map(s=>s.trim()).filter(Boolean) : undefined,
        patient_username: rForm.patient_username || undefined,
        patient_name: rForm.patient_username ? rForm.patient_username : (rForm.patient_name||undefined),
        patient_gender: rForm.patient_gender||undefined,
        onset_date: rForm.onset_date||undefined,
        additional_notes: rForm.additional_notes||undefined,
      });
      showToast('Report submitted successfully!');
      setReportModal(false); setRForm(blankReport); loadData();
    } catch(err) { showToast(err?.message||'Failed to submit report','error'); }
    finally { setRSubmitting(false); }
  };

  const handleNewsSubmit = async(e)=>{
    e.preventDefault(); setNSubmitting(true);
    try {
      await hospitalApi.createNews({ ...nForm, priority: parseInt(nForm.priority)||0 });
      showToast('News published!');
      setNewsModal(false); setNForm(blankNews); loadData();
    } catch(err) { showToast(err?.message||'Failed to publish news','error'); }
    finally { setNSubmitting(false); }
  };

  const handlePatientSubmit = async(e)=>{
    e.preventDefault(); setPSubmitting(true);
    try {
      const payload = { ...pForm };
      Object.keys(payload).forEach(k => { if (!payload[k]) delete payload[k]; });
      await hospitalApi.registerPatient(payload);
      showToast('Patient registered successfully!');
      setPatientModal(false); setPForm(blankPatient); loadData();
    } catch(err) { showToast(err?.message||'Failed to register patient','error'); }
    finally { setPSubmitting(false); }
  };

  const handleViewPatient = async (username) => {
    setPatientDetailLoading(true);
    setPatientDetailModal(true);
    try {
      const history = await hospitalApi.getPatientMedicalHistory(username);
      const patientReports = await hospitalApi.getPatientReports(username);
      setPatientDetail({
        ...history,
        reports: patientReports.reports || [],
      });
    } catch (err) {
      showToast(err?.message || 'Failed to load patient details', 'error');
      setPatientDetailModal(false);
    } finally { setPatientDetailLoading(false); }
  };

  const handleLogout = async()=>{
    try { await logout(); } catch(_) {
      try { localStorage.removeItem('doctalk_token'); localStorage.removeItem('doctalk_session'); } catch(_){}
    }
    navigate('/login');
  };

  // ── derived stats ─────────────────────────────────────────────────────────
  const hour = new Date().getHours();
  const hospitalName = dashboard?.hospital_name || session?.user_id || 'Hospital';
  const initials = hospitalName.split(' ').slice(0,2).map(w=>w[0]?.toUpperCase()||'').join('');
  const sevBreakdown  = dashboard?.severity_breakdown || {};
  const diseaseSummary = dashboard?.disease_summary || [];
  const recentReports  = dashboard?.recent_reports   || [];
  const totalReports   = Object.values(sevBreakdown).reduce((a,b)=>a+b,0);
  const criticalCount  = (sevBreakdown.critical||0)+(sevBreakdown.severe||0);
  const totalBeds      = dashboard?.total_beds;
  const availableBeds  = dashboard?.available_beds;
  const occupiedBeds   = totalBeds != null ? Math.max(0, totalBeds - (availableBeds ?? 0)) : null;
  const hospitalSpecialties = dashboard?.specialties || [];

  // filtered reports
  const filteredReports = reports.filter(r=>{
    const matchSearch = !reportSearch ||
      r.disease_name?.toLowerCase().includes(reportSearch.toLowerCase()) ||
      (r.patient_name||'').toLowerCase().includes(reportSearch.toLowerCase());
    const matchSev = reportSevFilter==='all' || r.severity===reportSevFilter;
    return matchSearch && matchSev;
  });

  // Settings state
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const blankSpecialty = { name: '', doctors: 0 };
  const [specialties, setSpecialties] = useState([]);
  const blankSettings = {
    total_beds: '',
    available_beds: '',
    name: '',
    phone: '',
    email: '',
    address: '',
    city: '',
    state: '',
    website: '',
  };
  const [settingsForm, setSettingsForm] = useState(blankSettings);

  const loadProfile = useCallback(async () => {
    setProfileLoading(true);
    try {
      const p = await hospitalApi.getProfile();
      setProfile(p);
      setSettingsForm({
        total_beds: p.total_beds ?? '',
        available_beds: p.available_beds ?? '',
        name: p.name ?? '',
        phone: p.phone ?? '',
        email: p.email ?? '',
        address: p.address ?? '',
        city: p.city ?? '',
        state: p.state ?? '',
        website: p.website ?? '',
      });
      setSpecialties(p.specialties && p.specialties.length > 0 ? p.specialties.map(s => ({...s})) : [{ name: '', doctors: 1 }]);
    } catch (err) {
      // ignore
    } finally { setProfileLoading(false); }
  }, []);

  useEffect(() => {
    if (tab === 'settings') loadProfile();
  }, [tab, loadProfile]);

  const handleSettingsSave = async () => {
    setProfileSaving(true);
    try {
      const totalBeds = settingsForm.total_beds !== '' ? parseInt(settingsForm.total_beds, 10) : undefined;
      const availableBeds = settingsForm.available_beds !== '' ? parseInt(settingsForm.available_beds, 10) : undefined;
      if (totalBeds != null && availableBeds != null && availableBeds > totalBeds) {
        showToast('Available beds cannot exceed total beds', 'error');
        return;
      }

      const payload = {
        total_beds: totalBeds,
        available_beds: availableBeds,
        specialties: specialties.filter(s => s.name.trim()),
        name: settingsForm.name?.trim() || undefined,
        phone: settingsForm.phone?.trim() || undefined,
        email: settingsForm.email?.trim() || undefined,
        address: settingsForm.address?.trim() || undefined,
        city: settingsForm.city?.trim() || undefined,
        state: settingsForm.state?.trim() || undefined,
        website: settingsForm.website?.trim() || undefined,
      };
      const updated = await hospitalApi.updateProfile(payload);
      setProfile(updated);
      setDashboard((prev) => prev ? {
        ...prev,
        hospital_name: updated.name || prev.hospital_name,
        total_beds: updated.total_beds,
        available_beds: updated.available_beds,
        specialties: updated.specialties || [],
      } : prev);
      showToast('Hospital settings saved successfully!');
    } catch (err) {
      showToast(err?.message || 'Failed to save settings', 'error');
    } finally { setProfileSaving(false); }
  };

  const addSpecialty = () => {
    setSpecialties(prev => [...prev, { name: '', doctors: 1 }]);
  };

  const removeSpecialty = (idx) => {
    setSpecialties(prev => prev.filter((_, i) => i !== idx));
  };

  const updateSpecialty = (idx, field, value) => {
    setSpecialties(prev => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s));
  };

  // ── nav items ─────────────────────────────────────────────────────────────
  const navItems = [
    { id:'overview',  icon:'🏠', label:'Overview'         },
    { id:'reports',   icon:'📋', label:'Symptom Reports'  },
    { id:'news',      icon:'📰', label:'News & Updates'   },
    { id:'patients',  icon:'👤', label:'Patients'         },
    { id:'analysis',  icon:'📊', label:'Disease Analysis' },
    { id:'settings',  icon:'⚙️', label:'Settings'         },
  ];

  // ── loading / error screens ───────────────────────────────────────────────
  if(loading && !dashboard) return (
    <div className="h-splash">
      <div className="h-spinner"/>
      <p>Loading your dashboard…</p>
    </div>
  );
  if(error && !dashboard) return (
    <div className="h-splash">
      <div style={{fontSize:'40px',marginBottom:'12px'}}>⚠️</div>
      <p style={{color:'#ef4444',fontWeight:'600'}}>{error}</p>
      <button className="h-btn-primary" onClick={loadData}>Retry</button>
    </div>
  );

  return (
    <div className="h-wrapper">

      {/* ══════════════════════ TOPBAR ══════════════════════ */}
      <header className="h-topbar">
        <div className="h-topbar-logo">DocTalk<span className="h-logo-sup">AI</span></div>
        <div className="h-topbar-center">
          {navItems.map(n=>(
            <button key={n.id} className={`h-topnav-btn ${tab===n.id?'active':''}`} onClick={()=>setTab(n.id)}>
              <span>{n.icon}</span> {n.label}
            </button>
          ))}
        </div>
        <div className="h-topbar-right">
          <div className="h-topbar-avatar">{initials}</div>
          <span className="h-topbar-name">{hospitalName}</span>
          <button className="h-logout-btn" onClick={handleLogout}>Sign out</button>
        </div>
      </header>

      {/* ══════════════════════ BODY ══════════════════════ */}
      <div className="h-body">

        {/* ── Sidebar ── */}
        <aside className="h-sidebar">
          <div className="h-sidebar-avatar">{initials}</div>
          <div className="h-sidebar-name">{hospitalName}</div>
          <div className="h-sidebar-id">ID: {session?.user_id || '—'}</div>
          <div className="h-sidebar-divider"/>
          <nav className="h-sidenav">
            {navItems.map(n=>(
              <button key={n.id} className={`h-sidenav-btn ${tab===n.id?'active':''}`} onClick={()=>setTab(n.id)}>
                <span className="h-sidenav-icon">{n.icon}</span>
                <span>{n.label}</span>
              </button>
            ))}
          </nav>
          <div className="h-sidebar-divider"/>
          <div className="h-sidebar-stats">
            <div className="h-sidebar-stat">
              <span className="h-ss-val">{totalReports}</span>
              <span className="h-ss-lab">Reports</span>
            </div>
            <div className="h-sidebar-stat">
              <span className="h-ss-val" style={{color: criticalCount>0?'#ef4444':'#22c55e'}}>{criticalCount}</span>
              <span className="h-ss-lab">Critical</span>
            </div>
            <div className="h-sidebar-stat">
              <span className="h-ss-val">{newsList.length}</span>
              <span className="h-ss-lab">News</span>
            </div>
          </div>
          <div style={{flex:1}}/>
          <button className="h-sidebar-logout" onClick={handleLogout}>Sign out</button>
        </aside>

        {/* ── Main panel ── */}
        <main className="h-main">

          {/* ─── Toast ─── */}
          {toast && (
            <div className={`h-toast ${toast.type}`}>
              {toast.type==='success' ? '✓' : '✕'} {toast.msg}
              <button onClick={()=>setToast(null)} style={{background:'none',border:'none',cursor:'pointer',color:'inherit',marginLeft:'8px',fontSize:'16px'}}>×</button>
            </div>
          )}

          {/* ══════════════ OVERVIEW ══════════════ */}
          {tab==='overview' && (
            <div className="h-tab-content">
              <div className="h-welcome-banner" style={{ display:'flex', justifyContent:'space-between', alignItems:'center', background:'#fff', padding:'16px 20px', borderRadius:'12px', border:'1px solid #e2e8f0', marginBottom:'20px' }}>
                <div>
                  <div className="h-greeting-sub" style={{ display:'flex', alignItems:'center', gap:'8px' }}>
                    📅 {new Date().toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}
                    {criticalCount>0 && <span className="h-alert-pill">🚨 {criticalCount} critical case{criticalCount!==1?'s':''} need attention</span>}
                  </div>
                </div>
                <div className="h-welcome-actions">
                  <button className="h-btn-primary" onClick={()=>setReportModal(true)}>+ New Report</button>
                  <button className="h-btn-secondary" onClick={()=>setNewsModal(true)}>📰 Publish News</button>
                </div>
              </div>

              <div className="h-kpi-row">
                {[
                  { icon:'📋', val: dashboard?.total_reports||0, label:'Total Reports',   color:'#6C5CE7', bg:'#EDE9FE' },
                  { icon:'🦠', val: diseaseSummary.length,        label:'Unique Diseases', color:'#ef4444', bg:'#fef2f2' },
                  { icon:'🚨', val: criticalCount,                label:'Severe/Critical', color:'#f97316', bg:'#fff7ed' },
                  { icon:'📰', val: dashboard?.total_news||0,     label:'News Published',  color:'#22c55e', bg:'#f0fdf4' },
                ].map(k=>(
                  <div key={k.label} className="h-kpi-card">
                    <div className="h-kpi-icon" style={{background:k.bg,color:k.color}}>{k.icon}</div>
                    <div className="h-kpi-val" style={{color:k.color}}>{k.val}</div>
                    <div className="h-kpi-label">{k.label}</div>
                  </div>
                ))}
              </div>

              {(totalBeds != null || hospitalSpecialties.length > 0) && (
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(280px,1fr))',gap:'16px',marginBottom:'20px'}}>
                  {totalBeds != null && (
                    <div className="h-card">
                      <div className="h-card-header">
                        <span className="h-card-title">🛏️ Bed Capacity</span>
                        <button className="h-card-link" onClick={()=>setTab('settings')}>Edit →</button>
                      </div>
                      <div style={{display:'flex',gap:'20px',alignItems:'center',padding:'8px 0'}}>
                        <div>
                          <div style={{fontSize:'28px',fontWeight:'800',color:'#6C5CE7'}}>{availableBeds ?? '—'}</div>
                          <div style={{fontSize:'12px',color:'#64748B'}}>Available beds</div>
                        </div>
                        <div style={{width:'1px',height:'48px',background:'#e2e8f0'}}/>
                        <div>
                          <div style={{fontSize:'28px',fontWeight:'800',color:'#0f172a'}}>{totalBeds}</div>
                          <div style={{fontSize:'12px',color:'#64748B'}}>Total capacity</div>
                        </div>
                        <div style={{width:'1px',height:'48px',background:'#e2e8f0'}}/>
                        <div>
                          <div style={{fontSize:'28px',fontWeight:'800',color: occupiedBeds > totalBeds * 0.85 ? '#ef4444' : '#22c55e'}}>
                            {occupiedBeds}
                          </div>
                          <div style={{fontSize:'12px',color:'#64748B'}}>Occupied</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {hospitalSpecialties.length > 0 && (
                    <div className="h-card">
                      <div className="h-card-header">
                        <span className="h-card-title">🔬 Specialties</span>
                        <button className="h-card-link" onClick={()=>setTab('settings')}>Edit →</button>
                      </div>
                      <div style={{display:'flex',flexDirection:'column',gap:'8px',padding:'4px 0'}}>
                        {hospitalSpecialties.slice(0, 6).map((s, idx) => (
                          <div key={`${s.name}-${idx}`} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 10px',background:'#f8fafc',borderRadius:'8px'}}>
                            <span style={{fontSize:'13px',fontWeight:'600',color:'#0f172a'}}>{s.name}</span>
                            <span style={{fontSize:'12px',fontWeight:'700',color:'#6C5CE7'}}>{s.doctors ?? 0} doctor{(s.doctors ?? 0) !== 1 ? 's' : ''}</span>
                          </div>
                        ))}
                        {hospitalSpecialties.length > 6 && (
                          <span style={{fontSize:'12px',color:'#94a3b8'}}>+{hospitalSpecialties.length - 6} more specialties</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="h-overview-grid">
                <div className="h-card">
                  <div className="h-card-header"><span className="h-card-title">Severity Breakdown</span></div>
                  {Object.keys(sevBreakdown).length===0
                    ? <EmptyState icon="📊" title="No data yet" sub="Submit a symptom report to see charts." />
                    : (
                      <div style={{display:'flex',alignItems:'center',gap:'20px',padding:'8px 0'}}>
                        <Donut size={110} data={Object.entries(sevBreakdown).map(([k,v])=>({label:k,v,color:sev[k]||'#94a3b8'}))} />
                        <div style={{flex:1}}>
                          {Object.entries(sevBreakdown).map(([k,v])=>{
                            const pct=Math.round(v/Math.max(totalReports,1)*100);
                            return (
                              <div key={k} style={{marginBottom:'6px'}}>
                                <div style={{display:'flex',justifyContent:'space-between',marginBottom:'3px'}}>
                                  <span style={{fontSize:'12px',fontWeight:'600',color:sev[k],textTransform:'capitalize'}}>{k}</span>
                                  <span style={{fontSize:'12px',fontWeight:'700',color:'#1e293b'}}>{v} <span style={{color:'#94a3b8',fontWeight:'400'}}>({pct}%)</span></span>
                                </div>
                                <div style={{height:'6px',background:'#f1f5f9',borderRadius:'99px',overflow:'hidden'}}>
                                  <div style={{width:`${Math.max(3,pct)}%`,height:'100%',background:sev[k],borderRadius:'99px',transition:'width 0.7s ease'}}/>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )
                  }
                </div>

                <div className="h-card">
                  <div className="h-card-header"><span className="h-card-title">Top Diseases</span></div>
                  {diseaseSummary.length===0
                    ? <EmptyState icon="🦠" title="No diseases recorded" sub="Reports will populate this chart." />
                    : diseaseSummary.slice(0,6).map((d,i)=>{
                        const colors=['#6C5CE7','#ef4444','#f97316','#22c55e','#3b82f6','#8b5cf6'];
                        const pct=Math.round(d.count/Math.max(totalReports,1)*100);
                        return (
                          <div key={i} style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px'}}>
                            <span style={{fontSize:'11px',fontWeight:'700',color:'#94a3b8',width:'18px',textAlign:'right'}}>#{i+1}</span>
                            <span style={{fontSize:'12px',fontWeight:'600',color:'#1e293b',minWidth:'100px',maxWidth:'130px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{d.disease}</span>
                            <div style={{flex:1,height:'8px',background:'#f1f5f9',borderRadius:'99px',overflow:'hidden'}}>
                              <div style={{width:`${Math.max(3,pct)}%`,height:'100%',background:colors[i%6],borderRadius:'99px',transition:'width 0.7s ease'}}/>
                            </div>
                            <span style={{fontSize:'12px',fontWeight:'700',color:colors[i%6],width:'24px',textAlign:'right'}}>{d.count}</span>
                          </div>
                        );
                      })
                  }
                </div>

                <div className="h-card h-card-wide">
                  <div className="h-card-header">
                    <span className="h-card-title">Recent Activity</span>
                    {recentReports.length>0&&<button className="h-card-link" onClick={()=>setTab('reports')}>View all →</button>}
                  </div>
                  {recentReports.length===0
                    ? <EmptyState icon="🕐" title="No activity yet" sub="Your submitted reports will appear here." action="Submit First Report" onAction={()=>setReportModal(true)}/>
                    : (
                      <div className="h-activity-feed">
                        {recentReports.map(r=>(
                          <div key={r.id} className="h-activity-item">
                            <div className="h-activity-dot" style={{background:sev[r.severity]||'#6C5CE7'}}/>
                            <div className="h-activity-body">
                              <div style={{display:'flex',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                                <span style={{fontSize:'13px',fontWeight:'700',color:'#0f172a'}}>{r.disease_name}</span>
                                <SevBadge level={r.severity}/>
                              </div>
                              <div style={{display:'flex',gap:'12px',marginTop:'4px',flexWrap:'wrap'}}>
                                {r.patient_name&&!r.is_anonymous&&<span style={{fontSize:'12px',color:'#64748B'}}>👤 {r.patient_name}</span>}
                                <span style={{fontSize:'12px',color:'#94a3b8'}}>{fmt(r.created_at)} at {fmtTime(r.created_at)}</span>
                              </div>
                              {r.symptoms?.length>0&&(
                                <div style={{display:'flex',gap:'4px',marginTop:'6px',flexWrap:'wrap'}}>
                                  {r.symptoms.slice(0,4).map((s,j)=>(
                                    <span key={j} style={{padding:'2px 8px',borderRadius:'6px',background:'#EDE9FE',color:'#6C5CE7',fontSize:'11px',fontWeight:'500'}}>{s}</span>
                                  ))}
                                  {r.symptoms.length>4&&<span style={{fontSize:'11px',color:'#94a3b8',alignSelf:'center'}}>+{r.symptoms.length-4} more</span>}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )
                  }
                </div>

                <div className="h-card">
                  <div className="h-card-header">
                    <span className="h-card-title">Latest News</span>
                    {newsList.length>0&&<button className="h-card-link" onClick={()=>setTab('news')}>View all →</button>}
                  </div>
                  {newsList.length===0
                    ? <EmptyState icon="📰" title="Nothing published yet" sub="Share updates with your network." action="Publish News" onAction={()=>setNewsModal(true)}/>
                    : newsList.slice(0,3).map(n=>{
                        const cfg=catCfg[n.category]||catCfg.general;
                        return (
                          <div key={n.id} style={{padding:'10px 0',borderBottom:'1px solid #f1f5f9'}}>
                            <div style={{display:'flex',alignItems:'center',gap:'6px',marginBottom:'4px'}}>
                              <span style={{fontSize:'12px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:cfg.bg,color:cfg.color}}>{cfg.icon} {n.category}</span>
                              {n.is_global&&<span style={{fontSize:'11px',color:'#f97316',background:'#fff7ed',padding:'2px 6px',borderRadius:'50px',fontWeight:'700'}}>🌍 Global</span>}
                            </div>
                            <div style={{fontSize:'13px',fontWeight:'700',color:'#0f172a',marginBottom:'2px'}}>{n.title}</div>
                            <div style={{fontSize:'12px',color:'#94a3b8'}}>{fmt(n.published_at)}</div>
                          </div>
                        );
                      })
                  }
                </div>
              </div>
            </div>
          )}

          {/* ══════════════ REPORTS ══════════════ */}
          {tab==='reports' && (
            <div className="h-tab-content">
              <div className="h-section-bar">
                <div>
                  <h2 className="h-section-title">Symptom Reports</h2>
                  <p className="h-section-sub">{reports.length} total report{reports.length!==1?'s':''} submitted</p>
                </div>
                <button className="h-btn-primary" onClick={()=>setReportModal(true)}>+ New Report</button>
              </div>
              <div className="h-filters-row">
                <div className="h-search-wrap">
                  <svg className="h-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                  <input className="h-search-input" placeholder="Search by disease or patient…" value={reportSearch} onChange={e=>setReportSearch(e.target.value)} />
                </div>
                <div className="h-filter-tabs">
                  {['all','mild','moderate','severe','critical'].map(f=>(
                    <button key={f} className={`h-filter-tab ${reportSevFilter===f?'active':''}`}
                      style={reportSevFilter===f&&f!=='all'?{background:sev[f],color:'#fff',border:`1px solid ${sev[f]}`}:{}}
                      onClick={()=>setReportSevFilter(f)}>
                      {f==='all'?'All':f.charAt(0).toUpperCase()+f.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
              {filteredReports.length===0
                ? <EmptyState icon="📋" title="No reports found" sub={reportSearch||reportSevFilter!=='all'?"Try adjusting your filters.":"No symptom reports submitted yet."} action="Submit First Report" onAction={()=>setReportModal(true)}/>
                : (
                  <div className="h-table-wrap">
                    <table className="h-table">
                      <thead>
                        <tr>
                          <th>Disease</th>
                          <th>Severity</th>
                          <th>Status</th>
                          <th>Symptoms</th>
                          <th>Patient</th>
                          <th>Date</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredReports.map(r=>(
                          <React.Fragment key={r.id}>
                            <tr className={expandedReport===r.id?'h-tr-expanded':''}>
                              <td><span className="h-td-primary">{r.disease_name}</span></td>
                              <td><SevBadge level={r.severity}/></td>
                              <td>
                                <select value={r.status || 'admitted'}
                                  onChange={async (e) => {
                                    try {
                                      await hospitalApi.updateReportStatus(r.id, e.target.value);
                                      showToast('Status updated successfully!');
                                      loadData();
                                    } catch (err) { showToast(err?.message||'Failed to update status','error'); }
                                  }}
                                  style={{ padding:'4px 8px', borderRadius:'6px', border:'1px solid #d1d5db', fontSize:'12px', background:'#fff', fontWeight:'600', color: r.status === 'deceased' ? '#ef4444' : r.status === 'discharged' ? '#22c55e' : '#3b82f6', cursor:'pointer' }}>
                                  <option value="admitted">Admitted</option>
                                  <option value="discharged">Discharged</option>
                                  <option value="deceased">Deceased</option>
                                </select>
                              </td>
                              <td>
                                <div style={{display:'flex',gap:'4px',flexWrap:'wrap'}}>
                                  {(r.symptoms||[]).slice(0,3).map((s,i)=>(
                                    <span key={i} style={{padding:'2px 7px',borderRadius:'5px',background:'#EDE9FE',color:'#6C5CE7',fontSize:'11px'}}>{s}</span>
                                  ))}
                                  {(r.symptoms||[]).length>3&&<span style={{fontSize:'11px',color:'#94a3b8'}}>+{r.symptoms.length-3}</span>}
                                </div>
                              </td>
                              <td style={{color:'#64748B',fontSize:'13px'}}>
                                {r.is_anonymous?<span style={{color:'#94a3b8',fontStyle:'italic'}}>Anonymous</span>:(r.patient_name||<span style={{color:'#94a3b8'}}>—</span>)}
                              </td>
                              <td style={{color:'#94a3b8',fontSize:'12px',whiteSpace:'nowrap'}}>{fmt(r.created_at)}</td>
                              <td><button className="h-expand-btn" onClick={()=>setExpandedReport(expandedReport===r.id?null:r.id)}>{expandedReport===r.id?'▲':'▼'}</button></td>
                            </tr>
                            {expandedReport===r.id&&(
                              <tr className="h-tr-detail">
                                <td colSpan={7}>
                                  <div className="h-report-detail">
                                    <div className="h-rd-col">
                                      <span className="h-rd-label">All Symptoms</span>
                                      <div style={{display:'flex',gap:'4px',flexWrap:'wrap',marginTop:'4px'}}>
                                        {(r.symptoms||[]).map((s,i)=><span key={i} style={{padding:'3px 8px',borderRadius:'6px',background:'#EDE9FE',color:'#6C5CE7',fontSize:'12px'}}>{s}</span>)}
                                      </div>
                                    </div>
                                    {(r.new_symptoms||[]).length>0&&(
                                      <div className="h-rd-col">
                                        <span className="h-rd-label">⚠️ Novel Symptoms</span>
                                        <div style={{display:'flex',gap:'4px',flexWrap:'wrap',marginTop:'4px'}}>
                                          {r.new_symptoms.map((s,i)=><span key={i} style={{padding:'3px 8px',borderRadius:'6px',background:'#fef3c7',color:'#92400e',fontSize:'12px',fontWeight:'600'}}>{s}</span>)}
                                        </div>
                                      </div>
                                    )}
                                    {r.patient_age&&<div className="h-rd-col"><span className="h-rd-label">Age</span><span className="h-rd-val">{r.patient_age} yrs</span></div>}
                                    {r.patient_gender&&<div className="h-rd-col"><span className="h-rd-label">Gender</span><span className="h-rd-val" style={{textTransform:'capitalize'}}>{r.patient_gender}</span></div>}
                                    {r.onset_date&&<div className="h-rd-col"><span className="h-rd-label">Onset</span><span className="h-rd-val">{fmt(r.onset_date)}</span></div>}
                                    {r.additional_notes&&<div className="h-rd-col" style={{gridColumn:'span 2'}}><span className="h-rd-label">Notes</span><span className="h-rd-val">{r.additional_notes}</span></div>}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )
              }
            </div>
          )}

          {/* ══════════════ NEWS ══════════════ */}
          {tab==='news' && (
            <div className="h-tab-content">
              <div className="h-section-bar">
                <div><h2 className="h-section-title">News & Announcements</h2><p className="h-section-sub">Broadcast health updates to your network</p></div>
                <button className="h-btn-primary" onClick={()=>setNewsModal(true)}>+ Publish Update</button>
              </div>
              {newsList.length===0
                ? <EmptyState icon="📰" title="Nothing published yet" sub="Share outbreak alerts, research findings, or general announcements." action="Publish First Update" onAction={()=>setNewsModal(true)}/>
                : (
                  <div className="h-news-grid">
                    {newsList.map(n=>{
                      const cfg=catCfg[n.category]||catCfg.general;
                      return (
                        <div key={n.id} className="h-news-card" style={{borderTopColor:cfg.color}}>
                          <div className="h-news-card-top">
                            <span className="h-news-cat" style={{color:cfg.color,background:cfg.bg}}>{cfg.icon} {n.category}</span>
                            {n.is_global&&<span className="h-global-badge">🌍 Global</span>}
                            {n.priority>5&&<span className="h-priority-badge">🔴 High Priority</span>}
                          </div>
                          <h3 className="h-news-title">{n.title}</h3>
                          <p className="h-news-body">{n.content}</p>
                          <div className="h-news-footer"><span>{fmt(n.published_at)} · {fmtTime(n.published_at)}</span></div>
                        </div>
                      );
                    })}
                  </div>
                )
              }
            </div>
          )}

          {/* ══════════════ PATIENTS ══════════════ */}
          {tab==='patients' && (
            <div className="h-tab-content">
              <div className="h-section-bar">
                <div>
                  <h2 className="h-section-title">Patient Directory</h2>
                  <p className="h-section-sub">{patients.length} patient{patients.length!==1?'s':''} registered</p>
                </div>
                <button className="h-btn-primary" onClick={()=>setPatientModal(true)}>+ Register Patient</button>
              </div>
              <div className="excel-sheet-container" style={{ background:'#fff', border:'1px solid #d1d5db', borderRadius:'8px', overflow:'hidden', boxShadow:'0 1px 3px rgba(0,0,0,0.1)' }}>
                <div style={{ background: '#f3f4f6', borderBottom: '1px solid #d1d5db', padding: '6px 12px', fontSize: '12px', fontWeight: '600', color: '#4b5563', display:'flex', gap:'10px' }}>
                  <span>📁 Patient_Database</span>
                </div>
                <div className="h-table-wrap" style={{ margin:0, overflowX:'auto' }}>
                  <table className="h-table excel-table" style={{ borderCollapse:'collapse', width:'100%', fontSize:'13px' }}>
                    <thead>
                      <tr style={{ background:'#f9fafb' }}>
                        <th style={{ border:'1px solid #e5e7eb', padding:'8px 12px', textAlign:'left', background:'#f3f4f6', color:'#374151', width:'30px' }}>#</th>
                        <th style={{ border:'1px solid #e5e7eb', padding:'8px 12px', textAlign:'left', color:'#374151', fontWeight:'600' }}>Patient ID</th>
                        <th style={{ border:'1px solid #e5e7eb', padding:'8px 12px', textAlign:'left', color:'#374151', fontWeight:'600' }}>Name</th>
                        <th style={{ border:'1px solid #e5e7eb', padding:'8px 12px', textAlign:'left', color:'#374151', fontWeight:'600' }}>Gender</th>
                        <th style={{ border:'1px solid #e5e7eb', padding:'8px 12px', textAlign:'left', color:'#374151', fontWeight:'600' }}>Blood Group</th>
                        <th style={{ border:'1px solid #e5e7eb', padding:'8px 12px', textAlign:'left', color:'#374151', fontWeight:'600' }}>Reports</th>
                        <th style={{ border:'1px solid #e5e7eb', padding:'8px 12px', textAlign:'left', color:'#374151', fontWeight:'600' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {patients.length===0 ? (
                        <tr><td colSpan={7} style={{ textAlign:'center', padding:'40px', color:'#9ca3af', fontStyle:'italic' }}>No patients registered yet. Click "+ Register Patient" to start.</td></tr>
                      ) : (
                        patients.map((p, idx)=>(
                          <tr key={p.username} style={{ background: idx%2===0?'#ffffff':'#fcfdfe', borderBottom:'1px solid #e5e7eb' }}>
                            <td style={{ border:'1px solid #e5e7eb', padding:'8px 12px', background:'#f3f4f6', color:'#9ca3af', fontWeight:'600', textAlign:'center' }}>{idx+1}</td>
                            <td style={{ border:'1px solid #e5e7eb', padding:'8px 12px', fontWeight:'700', color:'#111827' }}>{p.username}</td>
                            <td style={{ border:'1px solid #e5e7eb', padding:'8px 12px', color:'#374151' }}>{p.name}</td>
                            <td style={{ border:'1px solid #e5e7eb', padding:'8px 12px', color:'#4b5563', textTransform:'capitalize' }}>{p.gender || '—'}</td>
                            <td style={{ border:'1px solid #e5e7eb', padding:'8px 12px', color:'#4b5563', fontWeight:'600' }}>{p.blood_group || '—'}</td>
                            <td style={{ border:'1px solid #e5e7eb', padding:'8px 12px', textAlign:'center' }}>
                              <span style={{ fontWeight:'800', fontSize:'15px', color: p.report_count > 0 ? '#6C5CE7' : '#9ca3af' }}>{p.report_count || 0}</span>
                            </td>
                            <td style={{ border:'1px solid #e5e7eb', padding:'8px 12px' }}>
                              <button className="h-btn-secondary" style={{ padding:'4px 10px', fontSize:'11px' }} onClick={() => handleViewPatient(p.username)}>
                                📋 View History
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* ══════════════ SETTINGS ══════════════ */}
          {tab==='settings' && (
            <div className="h-tab-content">
              <div className="h-section-bar">
                <div>
                  <h2 className="h-section-title">Hospital Settings</h2>
                  <p className="h-section-sub">Manage hospital capacity, specialties, and contact information</p>
                </div>
                <button className="h-btn-primary" onClick={handleSettingsSave} disabled={profileSaving}>
                  {profileSaving ? 'Saving…' : '💾 Save Settings'}
                </button>
              </div>

              {profileLoading ? (
                <div className="h-splash" style={{padding:'40px'}}>
                  <div className="h-spinner"/><p>Loading settings…</p>
                </div>
              ) : (
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                  {/* Bed Capacity */}
                  <div className="h-card">
                    <div className="h-card-header"><span className="h-card-title">🛏️ Bed Capacity</span></div>
                    <div style={{padding:'8px 0'}}>
                      <div className="h-form-grid-2">
                        <FF label="Total Beds" hint="Total bed capacity of your hospital">
                          <input className="h-input" type="number" min={0} placeholder="e.g. 250" value={settingsForm.total_beds} onChange={e=>setSettingsForm(p=>({...p,total_beds:e.target.value}))}/>
                        </FF>
                        <FF label="Available Beds" hint="Currently available (unoccupied)">
                          <input className="h-input" type="number" min={0} placeholder="e.g. 45" value={settingsForm.available_beds} onChange={e=>setSettingsForm(p=>({...p,available_beds:e.target.value}))}/>
                        </FF>
                      </div>
                      {settingsForm.total_beds && (
                        <div style={{marginTop:'12px',padding:'10px',background:'#f8fafc',borderRadius:'8px',fontSize:'13px'}}>
                          <span style={{fontWeight:'600',color:'#0f172a'}}>Occupancy: </span>
                          <span style={{fontWeight:'700',color:'#6C5CE7'}}>
                            {parseInt(settingsForm.total_beds) - parseInt(settingsForm.available_beds||0)} / {settingsForm.total_beds} beds filled
                          </span>
                          <span style={{fontSize:'11px',color:'#94a3b8',marginLeft:'8px'}}>
                            ({Math.round(((parseInt(settingsForm.total_beds)-parseInt(settingsForm.available_beds||0))/parseInt(settingsForm.total_beds))*100)}%)
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Specialties */}
                  <div className="h-card">
                    <div className="h-card-header">
                      <span className="h-card-title">🔬 Specialties & Specialists</span>
                      <button className="h-card-link" onClick={addSpecialty}>+ Add</button>
                    </div>
                    <div style={{padding:'4px 0'}}>
                      {specialties.map((s, idx) => (
                        <div key={idx} style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'8px',padding:'8px',background:'#f8fafc',borderRadius:'8px',border:'1px solid #e2e8f0'}}>
                          <div style={{flex:1}}>
                            <input className="h-input" style={{fontSize:'13px',padding:'8px 10px'}} placeholder="Specialty name (e.g. Cardiology)" value={s.name} onChange={e=>updateSpecialty(idx, 'name', e.target.value)}/>
                          </div>
                          <div style={{width:'100px'}}>
                            <input className="h-input" style={{fontSize:'13px',padding:'8px 10px',textAlign:'center'}} type="number" min={0} placeholder="Doctors" value={s.doctors} onChange={e=>updateSpecialty(idx, 'doctors', parseInt(e.target.value)||0)}/>
                          </div>
                          <button style={{background:'none',border:'none',color:'#ef4444',cursor:'pointer',fontSize:'18px',padding:'4px'}} onClick={()=>removeSpecialty(idx)}>✕</button>
                        </div>
                      ))}
                      {specialties.length === 0 && (
                        <div style={{textAlign:'center',padding:'16px',color:'#94a3b8',fontSize:'13px'}}>
                          No specialties configured yet.
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Contact Information */}
                  <div className="h-card" style={{gridColumn:'span 2'}}>
                    <div className="h-card-header"><span className="h-card-title">📞 Contact Information</span></div>
                    <div className="h-form-grid-3" style={{padding:'8px 0'}}>
                      <FF label="Hospital Name">
                        <input className="h-input" placeholder="Full hospital name" value={settingsForm.name} onChange={e=>setSettingsForm(p=>({...p,name:e.target.value}))}/>
                      </FF>
                      <FF label="Phone">
                        <input className="h-input" placeholder="+91 XXXXXXXXXX" value={settingsForm.phone} onChange={e=>setSettingsForm(p=>({...p,phone:e.target.value}))}/>
                      </FF>
                      <FF label="Email">
                        <input className="h-input" type="email" placeholder="admin@hospital.com" value={settingsForm.email} onChange={e=>setSettingsForm(p=>({...p,email:e.target.value}))}/>
                      </FF>
                      <FF label="Address">
                        <input className="h-input" placeholder="Street address" value={settingsForm.address} onChange={e=>setSettingsForm(p=>({...p,address:e.target.value}))}/>
                      </FF>
                      <FF label="City">
                        <input className="h-input" placeholder="City" value={settingsForm.city} onChange={e=>setSettingsForm(p=>({...p,city:e.target.value}))}/>
                      </FF>
                      <FF label="State">
                        <input className="h-input" placeholder="State" value={settingsForm.state} onChange={e=>setSettingsForm(p=>({...p,state:e.target.value}))}/>
                      </FF>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ══════════════ ANALYSIS ══════════════ */}
          {tab==='analysis' && (()=>{
            const da = detailedAnalysis;
            const barPalette = ['#6C5CE7','#ef4444','#f97316','#22c55e','#3b82f6','#8b5cf6','#ec4899','#06b6d4'];

            if (analysisLoading && !da) return (
              <div className="h-tab-content">
                <div className="h-splash" style={{padding:'40px'}}>
                  <div className="h-spinner"/><p>Loading disease analysis…</p>
                </div>
              </div>
            );

            return (
              <div className="h-tab-content">
                <div className="h-section-bar">
                  <div>
                    <h2 className="h-section-title">Disease Analysis & Insights</h2>
                    <p className="h-section-sub">Centralised epidemiological data — for research, outbreak detection & surveillance</p>
                  </div>
                  <div style={{display:'flex',gap:'8px'}}>
                    <button className="h-btn-secondary" onClick={()=>{
                      const hdr='Disease,Total,Admitted,Discharged,Deaths,Mortality_Rate,Recovery_Rate,Avg_Age,Avg_Severity\n';
                      const rows=(da?.disease_breakdown||diseaseSummary).map(d=>
                        `${d.disease},${d.total||d.count},${d.admitted||0},${d.discharged||0},${d.deaths||0},${d.mortality_rate||0}%,${d.recovery_rate||0}%,${d.avg_age||'N/A'},${d.avg_severity_score||'N/A'}`
                      ).join('\n');
                      const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([hdr+rows],{type:'text/csv'}));
                      a.download='doctalk_dataset.csv'; a.click();
                    }}>⬇ Export CSV</button>
                  </div>
                </div>

                {/* Overall stats cards */}
                <div className="h-kpi-row" style={{ display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap:'12px', marginBottom:'20px' }}>
                  {[
                    { icon:'📋', val: da?.total_reports || totalReports, label:'Total Cases', color:'#6C5CE7', bg:'#EDE9FE' },
                    { icon:'🏥', val: da?.total_admitted || dashboard?.admitted_count || 0, label:'Admitted', color:'#3b82f6', bg:'#eff6ff' },
                    { icon:'✅', val: da?.total_discharged || dashboard?.discharged_count || 0, label:'Recovered', color:'#22c55e', bg:'#f0fdf4' },
                    { icon:'💀', val: da?.total_deaths || dashboard?.death_count || 0, label:'Deaths', color:'#ef4444', bg:'#fef2f2' },
                    { icon:'📈', val: da ? da.overall_mortality_rate + '%' : '—', label:'Mortality Rate', color:'#f97316', bg:'#fff7ed' },
                    { icon:'📈', val: da ? da.overall_recovery_rate + '%' : '—', label:'Recovery Rate', color:'#22c55e', bg:'#f0fdf4' },
                  ].map(k=>(
                    <div key={k.label} className="h-kpi-card" style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', padding:'12px', background:'#fff', borderRadius:'12px', border:'1px solid #e2e8f0' }}>
                      <div className="h-kpi-icon" style={{background:k.bg,color:k.color,fontSize:'20px',padding:'8px',borderRadius:'50%',marginBottom:'6px', width:'40px',height:'40px',display:'flex',alignItems:'center',justifyContent:'center'}}>{k.icon}</div>
                      <div className="h-kpi-val" style={{color:k.color,fontSize:'20px',fontWeight:'800'}}>{k.val}</div>
                      <div className="h-kpi-label" style={{fontSize:'10px',fontWeight:'600',color:'#64748B',marginTop:'2px',textAlign:'center'}}>{k.label}</div>
                    </div>
                  ))}
                </div>

                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px',marginBottom:'16px'}}>
                  {/* Severity chart */}
                  <div className="h-card">
                    <div className="h-card-header"><span className="h-card-title">Severity Distribution</span></div>
                    {Object.keys(sevBreakdown).length===0
                      ? <EmptyState icon="📊" title="No data" sub="Submit reports to see this chart." />
                      : (
                        <div style={{display:'flex',alignItems:'center',gap:'24px'}}>
                          <Donut size={120} data={Object.entries(sevBreakdown).map(([k,v])=>({label:k,v,color:sev[k]||'#94a3b8'}))} />
                          <div style={{flex:1}}>
                            {Object.entries(sevBreakdown).map(([k,v])=>{
                              const pct=Math.round(v/Math.max(totalReports,1)*100);
                              return (
                                <div key={k} style={{marginBottom:'8px'}}>
                                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
                                    <span style={{fontSize:'12px',fontWeight:'600',color:sev[k],textTransform:'capitalize'}}>{k}</span>
                                    <span style={{fontSize:'12px',fontWeight:'700',color:'#1e293b'}}>{v} <span style={{color:'#94a3b8',fontWeight:'400'}}>({pct}%)</span></span>
                                  </div>
                                  <div style={{height:'8px',background:'#f1f5f9',borderRadius:'99px',overflow:'hidden'}}>
                                    <div style={{width:`${Math.max(3,pct)}%`,height:'100%',background:sev[k],borderRadius:'99px',transition:'width 0.7s ease'}}/>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )
                    }
                  </div>

                  {/* Most deadly diseases */}
                  <div className="h-card">
                    <div className="h-card-header"><span className="h-card-title" style={{color:'#ef4444'}}>☠️ Most Deadly Diseases</span></div>
                    {!da?.most_deadly_diseases?.length
                      ? <EmptyState icon="💀" title="No mortality data" sub="Diseases with recorded deaths will appear here." />
                      : (
                        <div style={{display:'flex',flexDirection:'column',gap:'10px'}}>
                          {da.most_deadly_diseases.map((d,i)=>{
                            const maxM = Math.max(...da.most_deadly_diseases.map(x=>x.mortality_rate),1);
                            const pct = Math.round(d.mortality_rate/maxM*100);
                            return (
                              <div key={i} style={{display:'flex',alignItems:'center',gap:'8px'}}>
                                <span style={{fontSize:'11px',fontWeight:'700',color:'#94a3b8',width:'20px',textAlign:'right'}}>#{i+1}</span>
                                <span style={{fontSize:'12px',fontWeight:'600',color:'#1e293b',minWidth:'100px',maxWidth:'140px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{d.disease}</span>
                                <div style={{flex:1,height:'10px',background:'#fef2f2',borderRadius:'99px',overflow:'hidden'}}>
                                  <div style={{width:`${Math.max(3,pct)}%`,height:'100%',background:'#ef4444',borderRadius:'99px'}}/>
                                </div>
                                <span style={{fontSize:'12px',fontWeight:'700',color:'#ef4444',minWidth:'50px',textAlign:'right'}}>{d.mortality_rate}%</span>
                              </div>
                            );
                          })}
                        </div>
                      )
                    }
                  </div>
                </div>

                {/* Disease breakdown table */}
                <div className="h-card">
                  <div className="h-card-header">
                    <span className="h-card-title">Full Disease Dataset</span>
                    <span style={{fontSize:'12px',color:'#94a3b8'}}>{da?.disease_count || diseaseSummary.length} diseases · {da?.total_reports || totalReports} reports</span>
                  </div>
                  {(da?.disease_breakdown||[]).length===0 && diseaseSummary.length===0
                    ? <EmptyState icon="📄" title="No data available" sub="Submitted reports will populate this table." />
                    : (
                      <div className="h-table-wrap">
                        <table className="h-table">
                          <thead>
                            <tr>
                              <th>#</th>
                              <th>Disease</th>
                              <th>Total</th>
                              <th>Admitted</th>
                              <th>Discharged</th>
                              <th>Deaths</th>
                              <th>Mortality %</th>
                              <th>Recovery %</th>
                              <th>Avg Age</th>
                              <th>Severity Score</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(da?.disease_breakdown||[]).length > 0
                              ? da.disease_breakdown.map((d,i)=>(
                                  <tr key={i}>
                                    <td style={{color:'#94a3b8',fontWeight:'600'}}>{i+1}</td>
                                    <td><span className="h-td-primary">{d.disease}</span></td>
                                    <td><span style={{fontWeight:'800',color:barPalette[i%8]}}>{d.total}</span></td>
                                    <td>{d.admitted}</td>
                                    <td style={{color:'#22c55e',fontWeight:'600'}}>{d.discharged}</td>
                                    <td style={{color:'#ef4444',fontWeight:'600'}}>{d.deaths}</td>
                                    <td style={{fontWeight:'700',color:d.mortality_rate>20?'#ef4444':'#64748B'}}>{d.mortality_rate}%</td>
                                    <td style={{color:'#22c55e',fontWeight:'600'}}>{d.recovery_rate}%</td>
                                    <td>{d.avg_age || '—'}</td>
                                    <td>{d.avg_severity_score || '—'}</td>
                                  </tr>
                                ))
                              : diseaseSummary.map((d,i)=>{
                                  const pct=Math.round(d.count/Math.max(totalReports,1)*100);
                                  return (
                                    <tr key={i}>
                                      <td style={{color:'#94a3b8',fontWeight:'600'}}>{i+1}</td>
                                      <td><span className="h-td-primary">{d.disease}</span></td>
                                      <td><span style={{fontWeight:'800',color:barPalette[i%8]}}>{d.count}</span></td>
                                      <td colSpan={7} style={{color:'#94a3b8',fontSize:'12px'}}>{pct}% of all reports</td>
                                    </tr>
                                  );
                                })
                            }
                          </tbody>
                        </table>
                      </div>
                    )
                  }
                </div>

                <div className="h-global-note">
                  <div style={{fontSize:'24px',marginBottom:'8px'}}>📡</div>
                  <div style={{fontWeight:'700',color:'#6C5CE7',marginBottom:'4px'}}>Global Data Access</div>
                  <div style={{fontSize:'13px',color:'#5b21b6',lineHeight:'1.6'}}>
                    All symptom reports and patient data contribute to the centralised research dataset. This data supports outbreak detection, epidemiological modelling, and machine learning research. The analysis includes mortality rates, recovery rates, and demographic breakdowns for each disease.
                  </div>
                </div>
              </div>
            );
          })()}

        </main>
      </div>

      {/* ══════════════ REPORT MODAL ══════════════ */}
      <Modal open={reportModal} onClose={()=>setReportModal(false)} title="Submit Symptom Report" width={680}>
        <form onSubmit={handleReportSubmit} className="h-modal-form">
          <div className="h-form-grid-2">
            <FF label="Disease / Condition" required>
              <input className="h-input" placeholder="e.g. COVID-19, Dengue Fever" value={rForm.disease_name} onChange={e=>setRForm(p=>({...p,disease_name:e.target.value}))} required/>
            </FF>
            <FF label="Severity">
              <select className="h-input" value={rForm.severity} onChange={e=>setRForm(p=>({...p,severity:e.target.value}))}>
                <option value="mild">Mild</option>
                <option value="moderate">Moderate</option>
                <option value="severe">Severe</option>
                <option value="critical">Critical</option>
              </select>
            </FF>
          </div>

          {/* Link to registered patient (optional) */}
          <FF label="Link to Registered Patient (optional)" hint="If this patient is already registered, select their username to link the report to their medical history">
            <div style={{display:'flex',gap:'8px',alignItems:'center'}}>
              <select className="h-input" value={rForm.patient_username} onChange={e=>{
                const sel = e.target.value;
                setRForm(p=>({...p, patient_username: sel, patient_name: sel || p.patient_name}));
              }} style={{flex:1}}>
                <option value="">— Not a registered patient —</option>
                {patients.map(p=>(
                  <option key={p.username} value={p.username}>{p.username} - {p.name}</option>
                ))}
              </select>
            </div>
          </FF>

          {/* Show manual patient fields only when NOT linking to registered patient */}
          {!rForm.patient_username && (
            <div className="h-form-grid-3">
              <FF label="Patient Name">
                <input className="h-input" placeholder="Optional" value={rForm.patient_name} onChange={e=>setRForm(p=>({...p,patient_name:e.target.value}))}/>
              </FF>
              <FF label="Age">
                <input className="h-input" type="number" placeholder="yrs" min={0} max={150} value={rForm.patient_age} onChange={e=>setRForm(p=>({...p,patient_age:e.target.value}))}/>
              </FF>
              <FF label="Gender">
                <select className="h-input" value={rForm.patient_gender} onChange={e=>setRForm(p=>({...p,patient_gender:e.target.value}))}>
                  <option value="">—</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                </select>
              </FF>
            </div>
          )}

          <FF label="Symptoms" required hint="Separate with commas: fever, cough, fatigue">
            <textarea className="h-input" rows={2} placeholder="fever, headache, body ache…" value={rForm.symptoms} onChange={e=>setRForm(p=>({...p,symptoms:e.target.value}))} required/>
          </FF>

          <FF label="Novel / Unusual Symptoms" hint="New or emerging symptoms not typically seen — flagged for network-wide alert">
            <textarea className="h-input" rows={2} placeholder="Leave blank if none (e.g. purple rash, loss of taste)" value={rForm.new_symptoms} onChange={e=>setRForm(p=>({...p,new_symptoms:e.target.value}))}/>
          </FF>

          <div className="h-form-grid-2">
            <FF label="Onset Date">
              <input className="h-input" type="date" value={rForm.onset_date} onChange={e=>setRForm(p=>({...p,onset_date:e.target.value}))}/>
            </FF>
            <FF label="Additional Notes">
              <input className="h-input" placeholder="Optional clinical notes" value={rForm.additional_notes} onChange={e=>setRForm(p=>({...p,additional_notes:e.target.value}))}/>
            </FF>
          </div>

          <div className="h-modal-actions">
            <button type="button" className="h-btn-ghost" onClick={()=>{setReportModal(false); setRForm(blankReport);}}>Cancel</button>
            <button type="submit" className="h-btn-primary" disabled={rSubmitting}>
              {rSubmitting ? 'Submitting…' : 'Submit Report'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ══════════════ PATIENT REGISTRATION MODAL ══════════════ */}
      <Modal open={patientModal} onClose={()=>setPatientModal(false)} title="Register New Patient" width={580}>
        <form onSubmit={handlePatientSubmit} className="h-modal-form">
          <FF label="Username" required hint="At least 4 characters — this will be the patient's login ID">
            <input className="h-input" placeholder="Patient login ID" value={pForm.username} onChange={e=>setPForm(p=>({...p,username:e.target.value}))} required minLength={4}/>
          </FF>
          <FF label="Full Name" required hint="At least 2 characters">
            <input className="h-input" placeholder="Patient's full name" value={pForm.name} onChange={e=>setPForm(p=>({...p,name:e.target.value}))} required minLength={2}/>
          </FF>
          <div className="h-form-grid-2">
            <FF label="Email"><input className="h-input" type="email" placeholder="patient@example.com" value={pForm.email} onChange={e=>setPForm(p=>({...p,email:e.target.value}))}/></FF>
            <FF label="Mobile"><input className="h-input" placeholder="+91 98765 43210" value={pForm.mobile} onChange={e=>setPForm(p=>({...p,mobile:e.target.value}))}/></FF>
          </div>
          <div className="h-form-grid-2">
            <FF label="Gender">
              <select className="h-input" value={pForm.gender} onChange={e=>setPForm(p=>({...p,gender:e.target.value}))}>
                <option value="">—</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </FF>
            <FF label="Blood Group">
              <select className="h-input" value={pForm.blood_group} onChange={e=>setPForm(p=>({...p,blood_group:e.target.value}))}>
                <option value="">—</option>
                <option value="A+">A+</option>
                <option value="A-">A-</option>
                <option value="B+">B+</option>
                <option value="B-">B-</option>
                <option value="AB+">AB+</option>
                <option value="AB-">AB-</option>
                <option value="O+">O+</option>
                <option value="O-">O-</option>
              </select>
            </FF>
          </div>
          <FF label="Address"><input className="h-input" placeholder="Patient's address" value={pForm.address} onChange={e=>setPForm(p=>({...p,address:e.target.value}))}/></FF>
          <div className="h-modal-actions">
            <button type="button" className="h-btn-ghost" onClick={()=>setPatientModal(false)}>Cancel</button>
            <button type="submit" className="h-btn-primary" disabled={pSubmitting}>
              {pSubmitting ? 'Registering…' : 'Register Patient'}
            </button>
          </div>
        </form>
      </Modal>

      {/* ══════════════ PATIENT DETAIL MODAL ══════════════ */}
      <Modal open={patientDetailModal} onClose={()=>{setPatientDetailModal(false); setPatientDetail(null);}} title="Patient Medical History" width={700}>
        {patientDetailLoading ? (
          <div style={{textAlign:'center',padding:'40px'}}>
            <div className="h-spinner"/><p style={{marginTop:'12px',color:'#64748B'}}>Loading patient history…</p>
          </div>
        ) : patientDetail ? (
          <div>
            {/* Patient info */}
            <div style={{display:'flex',alignItems:'center',gap:'12px',marginBottom:'16px',padding:'12px',background:'#f8fafc',borderRadius:'8px'}}>
              <div style={{width:'48px',height:'48px',borderRadius:'50%',background:'#6C5CE7',color:'#fff',display:'flex',alignItems:'center',justifyContent:'center',fontWeight:'700',fontSize:'18px'}}>
                {(patientDetail.patient?.name||'?')[0]?.toUpperCase()}
              </div>
              <div>
                <div style={{fontWeight:'700',color:'#0f172a'}}>{patientDetail.patient?.name}</div>
                <div style={{fontSize:'12px',color:'#64748B'}}>@{patientDetail.patient?.username} · {patientDetail.patient?.gender||'—'} · {patientDetail.patient?.blood_group||'—'}</div>
              </div>
              <div style={{marginLeft:'auto',textAlign:'right'}}>
                <div style={{fontWeight:'700',fontSize:'18px',color:'#6C5CE7'}}>{patientDetail.total_reports}</div>
                <div style={{fontSize:'11px',color:'#94a3b8'}}>Reports</div>
              </div>
            </div>

            {/* Symptom reports linked to this patient */}
            <h4 style={{color:'#0f172a',marginBottom:'8px',fontSize:'14px'}}>📋 Symptom Reports</h4>
            {(patientDetail.reports||[]).length === 0 ? (
              <div style={{textAlign:'center',padding:'20px',color:'#94a3b8',fontSize:'13px'}}>No symptom reports linked to this patient yet.</div>
            ) : (
              <div style={{maxHeight:'250px',overflowY:'auto',marginBottom:'12px'}}>
                <table className="h-table" style={{fontSize:'12px'}}>
                  <thead>
                    <tr>
                      <th>Disease</th>
                      <th>Severity</th>
                      <th>Status</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {patientDetail.reports.map((r,i)=>(
                      <tr key={r.id||i}>
                        <td><span style={{fontWeight:'600'}}>{r.disease_name}</span></td>
                        <td><SevBadge level={r.severity}/></td>
                        <td style={{color: r.status==='deceased'?'#ef4444':r.status==='discharged'?'#22c55e':'#3b82f6',fontWeight:'600'}}>{r.status}</td>
                        <td style={{color:'#94a3b8'}}>{fmt(r.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Medical history records */}
            <h4 style={{color:'#0f172a',marginBottom:'8px',fontSize:'14px'}}>📜 Medical History</h4>
            {(patientDetail.medical_history||[]).length === 0 ? (
              <div style={{textAlign:'center',padding:'20px',color:'#94a3b8',fontSize:'13px'}}>No additional medical history records.</div>
            ) : (
              <div style={{maxHeight:'200px',overflowY:'auto'}}>
                {patientDetail.medical_history.map((h,i)=>(
                  <div key={h.id||i} style={{padding:'8px 12px',borderLeft:'3px solid #6C5CE7',background:'#f8fafc',marginBottom:'6px',borderRadius:'0 6px 6px 0'}}>
                    <div style={{fontWeight:'600',fontSize:'13px',color:'#0f172a'}}>{h.title}</div>
                    <div style={{fontSize:'11px',color:'#64748B'}}>{h.history_type} · {h.record_date ? fmt(h.record_date) : '—'}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </Modal>

      {/* ══════════════ NEWS MODAL ══════════════ */}
      <Modal open={newsModal} onClose={()=>setNewsModal(false)} title="Publish News Update" width={560}>
        <form onSubmit={handleNewsSubmit} className="h-modal-form">
          <FF label="Headline" required>
            <input className="h-input" placeholder="Short, clear headline" value={nForm.title} onChange={e=>setNForm(p=>({...p,title:e.target.value}))} required maxLength={200}/>
          </FF>
          <FF label="Content" required>
            <textarea className="h-input" rows={4} placeholder="Full details of the announcement…" value={nForm.content} onChange={e=>setNForm(p=>({...p,content:e.target.value}))} required/>
          </FF>
          <div className="h-form-grid-2">
            <FF label="Category">
              <select className="h-input" value={nForm.category} onChange={e=>setNForm(p=>({...p,category:e.target.value}))}>
                <option value="general">General</option>
                <option value="outbreak">Outbreak Alert</option>
                <option value="research">Research</option>
                <option value="policy">Policy</option>
                <option value="awareness">Awareness</option>
                <option value="announcement">Announcement</option>
              </select>
            </FF>
            <FF label="Priority (0–10)" hint="5+ will be flagged as high priority">
              <input className="h-input" type="number" min={0} max={10} value={nForm.priority} onChange={e=>setNForm(p=>({...p,priority:e.target.value}))}/>
            </FF>
          </div>
          <label className="h-checkbox-row">
            <input type="checkbox" checked={nForm.is_global} onChange={e=>setNForm(p=>({...p,is_global:e.target.checked}))}/>
            <span>Share globally — visible to all hospitals and patients on the network</span>
          </label>
          <div className="h-modal-actions">
            <button type="button" className="h-btn-ghost" onClick={()=>setNewsModal(false)}>Cancel</button>
            <button type="submit" className="h-btn-primary" disabled={nSubmitting}>
              {nSubmitting ? 'Publishing…' : 'Publish Update'}
            </button>
          </div>
        </form>
      </Modal>

    </div>
  );
}