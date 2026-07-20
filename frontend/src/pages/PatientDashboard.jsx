import { useState, useEffect, useRef } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useNotifications, useAssetCache } from '../contexts';
import { useLocation, useNavigate } from 'react-router-dom';
import { authApi, patientApi, paymentApi, prescriptionApi, buildAssetDownloadUrl } from '../lib/api';
import { buildAiChatWebSocketUrl, createRealTimeClient } from '../lib/realTimeClient';
import '../styles/patient.css';
import XrayAnalyzerPanel from '../components/XrayAnalyzerPanel';
import MarkdownMessage from '../components/chat/MarkdownMessage';
import FileViewer from '../components/FileViewer';
import AiProcessingCard from '../components/AiProcessingCard';
import StructuredReply from '../components/StructuredReply';
import RazorpayCheckout from '../components/RazorpayCheckout';
import PatientOverview from '../components/PatientOverview';
import PatientAppointmentsPanel from './patient_panels/PatientAppointmentsPanel';
import PatientDocumentsPanel from './patient_panels/PatientDocumentsPanel';
import PatientDocChatPanel from './patient_panels/PatientDocChatPanel';
import PatientHistoryPanel from './patient_panels/PatientHistoryPanel';
import PatientProfilePanel from './patient_panels/PatientProfilePanel';
import PatientExplainPanel from './patient_panels/PatientExplainPanel';
import ErrorBoundary from '../components/ErrorBoundary';

const GENERAL_UPLOADS_FOLDER_PATH = '/my_documents/general_uploads/';
const LEGACY_UNCLASSIFIED_FOLDER_PATH = '/my_documents/unclassified/';

const isJsonLike = (text) => {
  if (!text) return false;
  const trimmed = text.trim();
  if (trimmed.startsWith('```json')) return true;
  if (trimmed.startsWith('{')) return true;
  if (trimmed.startsWith('[')) return true;
  return false;
};

const tryParseJson = (text) => {
  if (!text) return null;
  const trimmed = text.trim();
  const stripped = trimmed.startsWith('```')
    ? trimmed.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
    : trimmed;
  try {
    const parsed = JSON.parse(stripped);
    if (parsed && typeof parsed === 'object') return parsed;
    return null;
  } catch {
    return null;
  }
};

const getCleanAnalysisText = (analysis) => {
  if (!analysis) return '';
  const trimmed = analysis.trim();
  if (isJsonLike(trimmed)) {
    const parsed = tryParseJson(trimmed);
    if (parsed) {
      return parsed.analysis || parsed.findings || parsed.summary || parsed.description || JSON.stringify(parsed, null, 2);
    }

    const getValFor = (key) => {
      const regex = new RegExp(`"${key}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)`, 'i');
      const match = trimmed.match(regex);
      if (match && match[1]) {
        let val = match[1];
        val = val.replace(/\\"/g, '"').replace(/\\n/g, '\n').trim();
        if (val.endsWith('"')) {
          val = val.slice(0, -1);
        }
        return val;
      }
      return '';
    };

    const extractedAnalysis = getValFor('analysis');
    if (extractedAnalysis) return extractedAnalysis;
    const extractedFindings = getValFor('findings');
    if (extractedFindings) return extractedFindings;
    const extractedSummary = getValFor('summary');
    if (extractedSummary) return extractedSummary;
  }
  return analysis;
};

const normalizeAbsoluteFolderPath = (value) => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  const lower = raw.toLowerCase();
  if (lower.includes('uploads\\medical_images') || lower.includes('uploads/medical_images')) return '/my_documents/medical_images/';
  if (lower.includes('uploads\\reports') || lower.includes('uploads/reports')) return '/my_documents/reports/';
  if (lower.includes('uploads\\prescriptions') || lower.includes('uploads/prescriptions')) return '/my_documents/prescriptions/';
  if (lower.includes('uploads\\unclassified') || lower.includes('uploads/unclassified')) return LEGACY_UNCLASSIFIED_FOLDER_PATH;
  return raw;
};

const normalizeFolderPath = (value) => {
  const raw = normalizeAbsoluteFolderPath(value);
  if (!raw) return '';
  if (raw === LEGACY_UNCLASSIFIED_FOLDER_PATH) return GENERAL_UPLOADS_FOLDER_PATH;
  return raw.endsWith('/') ? raw : `${raw}/`;
};

const getFolderDisplayName = (value) => {
  const normalized = normalizeFolderPath(value);
  if (normalized === GENERAL_UPLOADS_FOLDER_PATH) return 'General Uploads';
  const segments = normalized.split('/').filter(Boolean);
  return segments[segments.length - 1] || 'Folder';
};

const getAvatarFallback = (name = 'Patient') => {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#8B7EFF"/>
          <stop offset="100%" stop-color="#6C5CE7"/>
        </linearGradient>
      </defs>
      <rect width="160" height="160" rx="32" fill="url(#bg)"/>
      <circle cx="80" cy="62" r="28" fill="rgba(255,255,255,0.9)"/>
      <path d="M34 138c8-22 25-34 46-34s38 12 46 34" fill="rgba(255,255,255,0.9)"/>
    </svg>
  `.trim();
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
};

export default function PatientDashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(null);
  const { markExpired, logout } = useSession();
  const [messages, setMessages] = useState([]);
  const [inputMsg, setInputMsg] = useState('');
  const [language, setLanguage] = useState('en');
  const [aiSessions, setAiSessions] = useState([]);
  const [activeAiSessionId, setActiveAiSessionId] = useState('');
  const VALID_PANELS = ['overview', 'explain', 'documents', 'xray', 'appointments', 'docchat', 'history', 'profile'];

  const [activePanel, setActivePanel] = useState(() => {
    try {
      const panel = new URLSearchParams(window.location.search).get('panel');
      return VALID_PANELS.includes(panel) ? panel : 'overview';
    } catch (e) {
      return 'overview';
    }
  });

  const [chatHistoryCollapsed, setChatHistoryCollapsed] = useState(false);
  const [chatSearchQuery, setChatSearchQuery] = useState('');
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isRightDrawerOpen, setIsRightDrawerOpen] = useState(false);
  const [chatToDelete, setChatToDelete] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [langDropdownOpen, setLangDropdownOpen] = useState(false);

  const setActivePanelFromNav = (panel) => {
    const nextPanel = VALID_PANELS.includes(panel) ? panel : 'explain';
    setActivePanel(nextPanel);
    setChatHistoryCollapsed(nextPanel !== 'explain');
    navigate(`/patient/dashboard?panel=${encodeURIComponent(nextPanel)}`);
  };

  useEffect(() => {
    setChatHistoryCollapsed(activePanel !== 'explain');
  }, [activePanel]);

  useEffect(() => {
    try {
      const panel = new URLSearchParams(location.search).get('panel');
      const nextPanel = VALID_PANELS.includes(panel) ? panel : 'explain';
      setActivePanel((current) => (current === nextPanel ? current : nextPanel));
    } catch (e) {}
  }, [location.search]);

  const [isUploadingProfile, setIsUploadingProfile] = useState(false);
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const [processingState, setProcessingState] = useState(null);
  const { addNotification } = useNotifications();
  const { getAsset, setAsset, removeAsset } = useAssetCache();

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setIsUploadingProfile(true);
    const formData = new FormData(e.target);
    try {
      const token = localStorage.getItem('doctalk_token');
      const res = await fetch('/api/update_patient_profile', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
        credentials: 'include'
      });
      const data = await res.json();
      if (data.success) {
        setUser(prev => ({ ...prev, name: data.display_name, display_name: data.display_name, profile_pic: data.profile_pic }));
        try { addNotification({ type: 'success', message: 'Profile updated successfully' }); } catch (e) {}
      } else {
        try { addNotification({ type: 'error', message: 'Failed to update profile: ' + (data.error || 'unknown') }); } catch (e) {}
      }
    } catch (err) {
      console.error(err);
      try { addNotification({ type: 'error', message: 'Error updating profile' }); } catch (e) {}
    } finally {
      setIsUploadingProfile(false);
    }
  };

  const chatEndRef = useRef(null);
  const isCreatingChatRef = useRef(false);
  const docChatEndRef = useRef(null);
  const docAutoScrollRef = useRef(false);
  const [docInputFocused, setDocInputFocused] = useState(false);
  const docChatRealtimeRef = useRef(null);
  const docChatSnapshotRef = useRef({ consultationId: null, fingerprint: '' });

  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [medicalHistory, setMedicalHistory] = useState([]);
  const [appointmentDraft, setAppointmentDraft] = useState({
    doctor_id: '',
    reason: 'General consultation',
    note: '',
  });
  const [bookingMode, setBookingMode] = useState('direct');
  const [availableSlots, setAvailableSlots] = useState([]);
  const [selectedSlotId, setSelectedSlotId] = useState('');
  const [slotLoading, setSlotLoading] = useState(false);
  const [bookingInProgress, setBookingInProgress] = useState(false);
  // ── Razorpay payment state ───────────────────────────────────────────────
  const [pendingOrder, setPendingOrder] = useState(null);  // active Razorpay order
  const [paymentProcessing, setPaymentProcessing] = useState(false);

  const [activeDocChat, setActiveDocChat] = useState(null);
  const [consultations, setConsultations] = useState([]);
  const [docMessagePage, setDocMessagePage] = useState(1);
  const [docMessages, setDocMessages] = useState([]);
  const [docAttachmentFile, setDocAttachmentFile] = useState(null);
  const [docSending, setDocSending] = useState(false);
  const [activeConsultationId, setActiveConsultationId] = useState(null);
  const [docChatDisabled, setDocChatDisabled] = useState(false);
  const [docMsgInput, setDocMsgInput] = useState('');
  const [assets, setAssets] = useState({ folders: [], files: [] });
  const [currentFolder, setCurrentFolder] = useState(null);
  const [uploadQueue, setUploadQueue] = useState([]);
  const [previewFile, setPreviewFile] = useState(null);
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  const [uploadedFiles, setUploadedFiles] = useState([]);
  const explainUploadInputRef = useRef(null);

  const [analysisCurrentFolder, setAnalysisCurrentFolder] = useState(null);
  const [selectedDocForAnalysis, setSelectedDocForAnalysis] = useState(null);
  const [analysisMode, setAnalysisMode] = useState('upload');

  // ─── Medical Profile State (comprehensive) ───────────────────────────────
  const loadMed = (key, def) => { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : def; } catch { return def; } };
  const saveMed = (key, val) => { try { localStorage.setItem(key, JSON.stringify(val)); } catch (_) {} };

  const [medTab, setMedTab] = useState('overview');
  const [historyLoading, setHistoryLoading] = useState(false);

  const saveHistoryToApi = async (record) => {
    try {
      const current = await patientApi.getCurrentHistory();
      const currentRecord = current?.record;
      if (currentRecord?.id) {
        await patientApi.updateHistoryRecord(currentRecord.id, record);
      } else {
        await patientApi.createHistoryRecord(record);
      }
    } catch (e) {
      console.error('Failed to save history to API', e);
    }
  };

  const loadHistoryFromApi = async () => {
    setHistoryLoading(true);
    try {
      const data = await patientApi.getCurrentHistory();
      const record = data?.record || null;
      if (record) {
        const v = {
          height: record.weight || '',
          weight: record.weight || '',
          blood_group: record.bloodGroup || '',
          bmi: record.bmi || '',
          blood_pressure: record.bloodPressure || '',
          heart_rate: record.heartRate || '',
          blood_sugar_fasting: record.bloodSugarFasting || '',
          blood_sugar_pp: record.bloodSugarPP || '',
          spo2: record.spo2 || '',
          temperature: record.temperature || '',
        };
        setVitals(v);
        saveMed('dtalk_vitals', v);
        setConditions(Array.isArray(record.conditions) ? record.conditions : []);
        saveMed('dtalk_conditions', Array.isArray(record.conditions) ? record.conditions : []);
        setMedications(Array.isArray(record.medications) ? record.medications : []);
        saveMed('dtalk_medications', Array.isArray(record.medications) ? record.medications : []);
        setAllergies(Array.isArray(record.allergies) ? record.allergies : []);
        saveMed('dtalk_allergies', Array.isArray(record.allergies) ? record.allergies : []);
      }
    } catch (e) {
      console.error('Failed loading history from API', e);
    } finally {
      setHistoryLoading(false);
    }
  };

  // ── Patient Dashboard view state ──────────────────────────────────────────
  const [healthView, setHealthView] = useState('dashboard'); // 'dashboard' | 'record'
  const [prescriptionsList, setPrescriptionsList] = useState([]);
  const [prescriptionsLoading, setPrescriptionsLoading] = useState(false);

  const loadPrescriptions = async () => {
    setPrescriptionsLoading(true);
    try {
      const list = await prescriptionApi.listMine();
      setPrescriptionsList(Array.isArray(list) ? list : []);
    } catch (e) {
      console.error('Failed loading prescriptions', e);
      setPrescriptionsList([]);
    } finally {
      setPrescriptionsLoading(false);
    }
  };
  const latestRx = [...prescriptionsList]
    .sort((a, b) => new Date(b.issuedAt || 0) - new Date(a.issuedAt || 0))[0] || null;

  // Vitals
  const [vitals, setVitals] = useState(() => loadMed('dtalk_vitals', {
    height: '', weight: '', blood_group: '', bmi: '',
    blood_pressure: '', heart_rate: '', blood_sugar_fasting: '',
    blood_sugar_pp: '', spo2: '', temperature: '',
  }));
  const [editingVitals, setEditingVitals] = useState(false);
  const [vitalsForm, setVitalsForm] = useState(vitals);
  const saveVitals = (v) => { setVitals(v); saveMed('dtalk_vitals', v); saveHistoryToApi({ ...v, recordDate: new Date().toISOString() }); };
  const bmiCalc = (h, w) => {
    const hm = parseFloat(h) / 100; const wk = parseFloat(w);
    if (!hm || !wk) return '';
    return (wk / (hm * hm)).toFixed(1);
  };

  // Conditions
  const [conditions, setConditions] = useState(() => loadMed('dtalk_conditions', []));
  const [condForm, setCondForm] = useState({ condition:'', icd_code:'', diagnosed_date:'', doctor_name:'', hospital:'', status:'active', severity:'moderate', is_hereditary:false, notes:'' });
  const [showCondForm, setShowCondForm] = useState(false);
  const [editCondId, setEditCondId] = useState(null);
  const [condFilter, setCondFilter] = useState('all');
  const saveConditions = (r) => { setConditions(r); saveMed('dtalk_conditions', r); saveHistoryToApi({ conditions: r, recordDate: new Date().toISOString() }); };
  const submitCondition = (e) => {
    e.preventDefault();
    const entry = { ...condForm, id: editCondId || Date.now().toString(), updated_at: new Date().toISOString(), created_at: editCondId ? (conditions.find(c=>c.id===editCondId)?.created_at||new Date().toISOString()) : new Date().toISOString() };
    saveConditions(editCondId ? conditions.map(c=>c.id===editCondId?entry:c) : [entry,...conditions]);
    setCondForm({ condition:'', icd_code:'', diagnosed_date:'', doctor_name:'', hospital:'', status:'active', severity:'moderate', is_hereditary:false, notes:'' });
    setShowCondForm(false); setEditCondId(null);
  };

  // Medications
  const [medications, setMedications] = useState(() => loadMed('dtalk_medications', []));
  const [medForm, setMedForm] = useState({ name:'', dosage:'', frequency:'', route:'oral', prescribed_by:'', prescribed_date:'', start_date:'', end_date:'', reason:'', is_ongoing:true, side_effects:'', notes:'' });
  const [showMedForm, setShowMedForm] = useState(false);
  const [editMedId, setEditMedId] = useState(null);
  const saveMedications = (r) => { setMedications(r); saveMed('dtalk_medications', r); saveHistoryToApi({ medications: r, recordDate: new Date().toISOString() }); };
  const submitMedication = (e) => {
    e.preventDefault();
    const entry = { ...medForm, id: editMedId || Date.now().toString(), created_at: editMedId ? (medications.find(m=>m.id===editMedId)?.created_at||new Date().toISOString()) : new Date().toISOString() };
    saveMedications(editMedId ? medications.map(m=>m.id===editMedId?entry:m) : [entry,...medications]);
    setMedForm({ name:'', dosage:'', frequency:'', route:'oral', prescribed_by:'', prescribed_date:'', start_date:'', end_date:'', reason:'', is_ongoing:true, side_effects:'', notes:'' });
    setShowMedForm(false); setEditMedId(null);
  };

  // Allergies
  const [allergies, setAllergies] = useState(() => loadMed('dtalk_allergies', []));
  const [allergyForm, setAllergyForm] = useState({ allergen:'', type:'drug', reaction:'', severity:'moderate', onset_date:'', notes:'' });
  const [showAllergyForm, setShowAllergyForm] = useState(false);
  const [editAllergyId, setEditAllergyId] = useState(null);
  const saveAllergies = (r) => { setAllergies(r); saveMed('dtalk_allergies', r); saveHistoryToApi({ allergies: r, recordDate: new Date().toISOString() }); };
  const submitAllergy = (e) => {
    e.preventDefault();
    const entry = { ...allergyForm, id: editAllergyId || Date.now().toString(), created_at: editAllergyId ? (allergies.find(a=>a.id===editAllergyId)?.created_at||new Date().toISOString()) : new Date().toISOString() };
    saveAllergies(editAllergyId ? allergies.map(a=>a.id===editAllergyId?entry:a) : [entry,...allergies]);
    setAllergyForm({ allergen:'', type:'drug', reaction:'', severity:'moderate', onset_date:'', notes:'' });
    setShowAllergyForm(false); setEditAllergyId(null);
  };

  // Surgeries
  const [surgeries, setSurgeries] = useState(() => loadMed('dtalk_surgeries', []));
  const [surgForm, setSurgForm] = useState({ procedure:'', date:'', surgeon:'', hospital:'', anesthesia:'general', outcome:'successful', complications:'', notes:'' });
  const [showSurgForm, setShowSurgForm] = useState(false);
  const [editSurgId, setEditSurgId] = useState(null);
  const saveSurgeries = (r) => { setSurgeries(r); saveMed('dtalk_surgeries', r); saveHistoryToApi({ conditions: [...(loadMed('dtalk_conditions', [])), ...r.map(s => ({ condition: s.procedure, status: 'resolved', ...s }))], recordDate: new Date().toISOString() }); };
  const submitSurgery = (e) => {
    e.preventDefault();
    const entry = { ...surgForm, id: editSurgId || Date.now().toString(), created_at: editSurgId ? (surgeries.find(s=>s.id===editSurgId)?.created_at||new Date().toISOString()) : new Date().toISOString() };
    saveSurgeries(editSurgId ? surgeries.map(s=>s.id===editSurgId?entry:s) : [entry,...surgeries]);
    setSurgForm({ procedure:'', date:'', surgeon:'', hospital:'', anesthesia:'general', outcome:'successful', complications:'', notes:'' });
    setShowSurgForm(false); setEditSurgId(null);
  };

  // Family History
  const [familyHistory, setFamilyHistory] = useState(() => loadMed('dtalk_family_hx', []));
  const [famForm, setFamForm] = useState({ relation:'', condition:'', age_of_onset:'', deceased:false, notes:'' });
  const [showFamForm, setShowFamForm] = useState(false);
  const [editFamId, setEditFamId] = useState(null);
  const saveFamilyHistory = (r) => { setFamilyHistory(r); saveMed('dtalk_family_hx', r); };
  const submitFamily = (e) => {
    e.preventDefault();
    const entry = { ...famForm, id: editFamId || Date.now().toString() };
    saveFamilyHistory(editFamId ? familyHistory.map(f=>f.id===editFamId?entry:f) : [entry,...familyHistory]);
    setFamForm({ relation:'', condition:'', age_of_onset:'', deceased:false, notes:'' });
    setShowFamForm(false); setEditFamId(null);
  };

  // Immunizations
  const [immunizations, setImmunizations] = useState(() => loadMed('dtalk_immunizations', []));
  const [immuForm, setImmuForm] = useState({ vaccine:'', date_given:'', dose:'', administered_by:'', next_due:'', notes:'' });
  const [showImmuForm, setShowImmuForm] = useState(false);
  const [editImmuId, setEditImmuId] = useState(null);
  const saveImmunizations = (r) => { setImmunizations(r); saveMed('dtalk_immunizations', r); };
  const submitImmunization = (e) => {
    e.preventDefault();
    const entry = { ...immuForm, id: editImmuId || Date.now().toString() };
    saveImmunizations(editImmuId ? immunizations.map(i=>i.id===editImmuId?entry:i) : [entry,...immunizations]);
    setImmuForm({ vaccine:'', date_given:'', dose:'', administered_by:'', next_due:'', notes:'' });
    setShowImmuForm(false); setEditImmuId(null);
  };

  // Lifestyle
  const [lifestyle, setLifestyle] = useState(() => loadMed('dtalk_lifestyle', {
    smoking: 'never', smoking_packs_per_day: '', smoking_years: '',
    alcohol: 'never', alcohol_units_per_week: '',
    tobacco_chewing: false,
    exercise: 'sedentary', exercise_days_per_week: '',
    diet: 'mixed', sleep_hours: '',
    occupation: '', stress_level: 'moderate',
    recreational_drugs: false, notes: '',
  }));
  const [editingLifestyle, setEditingLifestyle] = useState(false);
  const [lifestyleForm, setLifestyleForm] = useState(lifestyle);
  const saveLifestyle = (v) => { setLifestyle(v); saveMed('dtalk_lifestyle', v); };

  // 1. Fetch User Session on Mount
  useEffect(() => {
    const token = localStorage.getItem('doctalk_token');
    if (!token) {
      navigate('/login');
      return;
    }
    authApi.me(token)
      .then(data => {
        if (!data) {
          console.error('Session fetch returned empty/malformed payload');
          try { markExpired(); } catch (e) {}
          navigate('/login');
          return;
        }
        setUser(data);
      })
      .catch((err) => {
        console.error('Session fetch failed:', err);
        try { markExpired(); } catch (e) {}
        navigate('/login');
      });
  }, [navigate]);

  const loadAssets = (options = {}) => {
    const normalizeAssets = (items, assetKind) => (Array.isArray(items) ? items : []).map((item) => ({
      ...item,
      id: item.id,
      asset_kind: String(item.asset_category || item.assetCategory || assetKind || 'unclassified').toLowerCase(),
      name: item.file_name || item.fileName || item.original_name || item.originalName || item.name || 'Document',
      folder: normalizeFolderPath(item.folder_path || item.folderPath || item.folder || ''),
      folder_label: getFolderDisplayName(item.folder_path || item.folderPath || item.folder || ''),
      mime_type: item.file_type || item.fileType || item.mime_type || item.mimeType || '',
      download_url: item.download_url || buildAssetDownloadUrl(item.id),
      uploaded_at: item.created_at || item.createdAt || item.uploaded_at || '',
    }));

    const cacheKey = 'assets_files';
    const cached = !options.forceRefresh && getAsset && getAsset(cacheKey);
    if (cached) {
      setAssets(cached);
      return;
    }

    patientApi.listAssets()
      .then((items) => {
        const files = normalizeAssets(items, 'unclassified');
        const folders = Array.from(new Map(files.map((file) => {
          const folderPath = file.folder || '';
          return [folderPath, { path: folderPath, label: file.folder_label || getFolderDisplayName(folderPath), locked: folderPath === GENERAL_UPLOADS_FOLDER_PATH }];
        })).values());
        const assetsObj = { folders, files };
        setAssets(assetsObj);
        try { setAsset && setAsset(cacheKey, assetsObj); } catch (e) {}
      })
      .catch(e => console.error(e));
  };


  useEffect(() => {
    if(activePanel === 'documents') {
      loadAssets();
      setCurrentFolder(null);
    }
    if (activePanel === 'overview') {
      loadAppointments();
      loadMedicalHistory();
    }
    if(activePanel === 'explain') {
      loadAssets();
      setAnalysisCurrentFolder(null);
    }
    if (activePanel === 'appointments') {
      loadAppointments();
      loadDoctors();
    }
    if (activePanel === 'docchat') {
      loadConsultations();
      loadDoctors();
    }
    if (activePanel === 'history') {
      loadAppointments();
      loadPrescriptions();
      loadHistoryFromApi();
    }
  }, [activePanel]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll for assets that are still processing so UI updates automatically
  useEffect(() => {
    let intervalId;
    const hasProcessing = assets?.files?.some(f => f.processing_status === 'PENDING' || f.processing_status === 'PROCESSING' || f.processing_status === 'UPLOADED');
    if ((activePanel === 'documents' || activePanel === 'explain') && hasProcessing) {
      intervalId = setInterval(() => {
        loadAssets({ forceRefresh: true });
      }, 3000);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [assets, activePanel]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleUploadAssetV2 = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;

    const maxSize = 15 * 1024 * 1024;
    const allowedTypes = ['application/pdf', 'image/png', 'image/jpg', 'image/jpeg', 'image/webp', 'image/gif'];
    if (file.size > maxSize) { try { addNotification({ type: 'error', message: 'File too large. Max 15MB allowed.' }); } catch (e) {} e.target.value = null; return; }
    if (!allowedTypes.includes(file.type) && !file.name.toLowerCase().endsWith('.pdf')) { try { addNotification({ type: 'error', message: 'Unsupported file type. Use PDF or images.' }); } catch (e) {} e.target.value = null; return; }

    const uploadId = 'u-' + Date.now();
    setUploadQueue(prev => [...prev, { id: uploadId, name: file.name, progress: 0, status: 'uploading' }]);
    patientApi.uploadAsset(file)
      .then((data) => {
        if (data && (data.success || data.id)) {
          setUploadQueue(prev => prev.map(u => u.id === uploadId ? { ...u, progress: 100, status: 'done' } : u));
          try { addNotification({ type: 'success', message: 'File uploaded successfully' }); } catch (e) {}
          try { removeAsset && removeAsset('assets_files'); } catch (e) {}
          loadAssets({ forceRefresh: true });
          window.setTimeout(() => {
            setUploadQueue(prev => prev.filter((item) => item.id !== uploadId));
          }, 5000);
        } else {
          setUploadQueue(prev => prev.map(u => u.id === uploadId ? { ...u, status: 'error' } : u));
          try { addNotification({ type: 'error', message: 'Upload failed' }); } catch (e) {}
          window.setTimeout(() => {
            setUploadQueue(prev => prev.filter((item) => item.id !== uploadId));
          }, 5000);
        }
      })
      .catch((err) => {
        console.error('Upload error', err);
        setUploadQueue(prev => prev.map(u => u.id === uploadId ? { ...u, status: 'error' } : u));
        try { addNotification({ type: 'error', message: 'Upload failed: ' + (err?.message || 'unknown') }); } catch (e) {}
        window.setTimeout(() => {
          setUploadQueue(prev => prev.filter((item) => item.id !== uploadId));
        }, 5000);
      });
    if (e.target) e.target.value = null;
  };

  const handleDeleteAssetV2 = (file) => {
    if (!window.confirm("Are you sure you want to delete this file?")) return;
    patientApi.deleteAsset(file.id)
    .then(data => {
      if (data && (data.success || data.message)) {
        try { addNotification({ type: 'success', message: 'File deleted successfully' }); } catch (e) {}
        try { removeAsset && removeAsset('assets_files'); } catch (e) {}
        loadAssets({ forceRefresh: true });
      } else {
        try { addNotification({ type: 'error', message: 'Delete failed: ' + (data && (data.error || data.detail) || 'unknown') }); } catch (e) {}
      }
    }).catch(err => { console.error('Delete error', err); try { addNotification({ type: 'error', message: 'Delete failed: ' + (err?.message || 'unknown') }); } catch (e) {} });
  };

  const getAssetFilenameParts = (file) => {
    const fullName = String(file?.name || file?.original_name || '');
    const lastDot = fullName.lastIndexOf('.');
    if (lastDot > 0) {
      return { baseName: fullName.slice(0, lastDot), extension: fullName.slice(lastDot) };
    }
    return { baseName: fullName, extension: '' };
  };

  const handleRenameAsset = (file) => {
    setRenameTarget(file);
    setRenameValue(getAssetFilenameParts(file).baseName);
  };

  const submitRenameAsset = async () => {
    const target = renameTarget;
    const newName = renameValue.trim();
    if (!target || !newName) return;
    try {
      const { extension } = getAssetFilenameParts(target);
      const sanitizedName = extension && newName.toLowerCase().endsWith(extension.toLowerCase())
        ? newName.slice(0, -extension.length).trim()
        : newName;
      const data = await patientApi.renameAsset(target.id, sanitizedName);
      if (data && (data.id || data.original_name || data.originalName)) {
        try { addNotification({ type: 'success', message: 'File renamed successfully' }); } catch (e) {}
        try { removeAsset && removeAsset('assets_files'); } catch (e) {}
        loadAssets({ forceRefresh: true });
        setRenameTarget(null);
        setRenameValue('');
      } else {
        try { addNotification({ type: 'error', message: 'Renaming failed: ' + (data && (data.error || data.detail) || 'unknown') }); } catch (e) {}
      }
    } catch (err) {
      console.error('Rename error', err);
      try { addNotification({ type: 'error', message: 'Renaming failed: ' + (err?.message || 'unknown') }); } catch (e) {}
    }
  };

  const loadAppointments = async () => {
    try {
      const data = await patientApi.listAppointments();
      if (Array.isArray(data)) setAppointments(data || []);
      else if (data && data.success) setAppointments(data.appointments || []);
    } catch (e) { console.error('Failed loading appointments', e); }
  };

  const loadMedicalHistory = async () => {
    try {
      const data = await patientApi.getMedicalHistory();
      if (data && data.success && Array.isArray(data.entries)) {
        setMedicalHistory(data.entries);
      }
    } catch (e) { console.error('Failed loading medical history', e); }
  };

  const loadDoctors = () => {
    patientApi.listDoctors()
      .then(data => {
        if(Array.isArray(data)) {
          setDoctors(data || []);
        } else if (data.success) {
          setDoctors(data.doctors || []);
        }
      }).catch(e => {
        console.error('Failed loading doctors', e);
        setDoctors([]);
      });
  };

  function normalizeChatMessage(item) {
    return {
      id: item?.id,
      senderId: item?.sender_id || item?.senderId || item?.sender || '',
      sender: item?.sender_role || item?.senderRole || item?.sender || '',
      text: item?.message ?? item?.text ?? '',
      timestamp: item?.timestamp || item?.created_at || item?.createdAt || null,
    };
  }

  const isOutgoingChatMessage = (message) => {
    const senderId = String(message?.senderId || '').trim().toLowerCase();
    const sender = String(message?.sender || '').trim().toLowerCase();

    if (senderId === 'doctalk-ai') {
      return false;
    }

    if (sender === 'user') {
      return true;
    }

    if (sender === 'patient' && senderId !== 'doctalk-ai') {
      return true;
    }

    return false;
  };

  const normalizeChatMessages = (data) => {
    const items = Array.isArray(data) ? data : (data?.items || []);
    return items.map(normalizeChatMessage);
  };

  const getChatMessageKey = (message, index = 0) => {
    if (message?.id) return `id:${String(message.id)}`;
    return `fallback:${String(message?.sender || '')}:${String(message?.timestamp || '')}:${String(message?.text || '')}:${index}`;
  };

  const mergeChronologicalMessages = (currentMessages, incomingMessages) => {
    const current = Array.isArray(currentMessages) ? currentMessages : [];
    const incoming = Array.isArray(incomingMessages) ? incomingMessages : [];
    const merged = [];
    const seen = new Set();

    const append = (message, index) => {
      const key = getChatMessageKey(message, index);
      if (seen.has(key)) return;
      seen.add(key);
      merged.push(message);
    };

    current.forEach(append);
    incoming.forEach(append);

    if (merged.length === current.length && merged.every((message, index) => message === current[index])) {
      return current;
    }

    return merged;
  };

  const loadConsultations = async () => {
    try {
      const data = await patientApi.listConsultations();
      setConsultations(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed loading consultations', e);
      setConsultations([]);
    }
  };

  const loadChatHistory = async () => {
    try {
      const sessionId = activeAiSessionId;
      const data = await patientApi.getAiChatHistory(sessionId);
      const items = Array.isArray(data?.messages) ? data.messages : [];
      const backendMessages = items.map((item) => {
        const rawText = item?.message || item?.content || item?.text || '';
        let structured = null;
        if (rawText) {
          try {
            const parsed = JSON.parse(rawText);
            if (parsed && typeof parsed === 'object' && (parsed.summary || parsed.medicines || parsed.key_points || parsed.title)) {
              structured = parsed;
            }
          } catch {
            structured = null;
          }
        }
        return {
          senderId: item?.sender_id || item?.senderId || (String(item?.role || '').toLowerCase() === 'assistant' ? 'doctalk-ai' : 'user'),
          sender: String(item?.role || '').toLowerCase() === 'assistant' ? 'model' : 'user',
          text: rawText,
          structured,
          id: item?.id || `${item?.timestamp || Date.now()}-${Math.random().toString(16).slice(2)}`,
          timestamp: item?.timestamp || item?.created_at || item?.createdAt || null,
        };
      });
      setMessages(prev => {
        const backendIds = new Set(backendMessages.map(m => m.id));
        const localMessages = prev.filter(m => !backendIds.has(m.id));
        return [...backendMessages, ...localMessages];
      });
    } catch (e) {
      console.error(e);
    }
  };

  const loadAiSessions = async () => {
    if (isCreatingChatRef.current) return;
    try {
      const sessions = await patientApi.listAiSessions();
      const list = Array.isArray(sessions) ? sessions : [];
      
      setAiSessions((prev) => {
        const tempSessions = prev.filter(s => String(s.id).startsWith('temp-'));
        const combined = [...tempSessions, ...list];
        
        if (combined.length === 0) {
          setTimeout(() => {
            patientApi.createAiSession('New Chat').then(session => {
              setAiSessions(p => {
                if (p.find(x => x.id === session.id)) return p;
                return [session, ...p];
              });
              setActiveAiSessionId(session.id);
            }).catch(e => {
              console.error('Failed to auto-create session', e);
            });
          }, 0);
        }
        
        return combined;
      });
      setActiveAiSessionId((prev) => {
        if (prev && list.some((s) => s.id === prev)) {
          return prev;
        }
        return list[0]?.id || '';
      });
    } catch (e) {
      console.error('Failed loading AI sessions', e);
    }
  };

  const handleNewChat = () => {
    isCreatingChatRef.current = true;
    const tempId = `temp-${Date.now()}`;
    const tempSession = {
      id: tempId,
      title: 'New Chat',
      is_default: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
    
    setAiSessions((prev) => [tempSession, ...prev]);
    setActiveAiSessionId(tempId);
    setMessages([]);
    setActivePanelFromNav('explain');

    patientApi.createAiSession('').then((session) => {
      setAiSessions((prev) => prev.map((s) => s.id === tempId ? session : s));
      setActiveAiSessionId((prev) => prev === tempId ? session.id : prev);
    }).catch((e) => {
      console.error('Failed to create chat', e);
      try { addNotification({ type: 'error', message: 'Could not start a new chat.' }); } catch (_) {}
      setAiSessions((prev) => prev.filter((s) => s.id !== tempId));
      setActiveAiSessionId((prev) => {
        if (prev === tempId) {
           return aiSessions[0]?.id || '';
        }
        return prev;
      });
    }).finally(() => {
      isCreatingChatRef.current = false;
    });
  };

  const handleSelectSession = (e) => {
    const id = e.target.value;
    if (!id) return;
    setActiveAiSessionId(id);
    setMessages([]);
  };

  const handleDeleteSession = (id) => {
    if (!id) return;
    if (aiSessions.length <= 1) {
      try { addNotification({ type: 'error', message: 'You must have at least one chat.' }); } catch (_) {}
      return;
    }
    setChatToDelete(id);
  };

  const confirmDeleteChat = () => {
    if (!chatToDelete) return;
    const id = chatToDelete;
    setChatToDelete(null);
    
    // Optimistic UI update
    const sessionToRestore = aiSessions.find(s => s.id === id);
    setAiSessions(prev => prev.filter(s => s.id !== id));
    if (activeAiSessionId === id) {
       setMessages([]);
       setActiveAiSessionId(aiSessions.find(s => s.id !== id)?.id || '');
    }

    patientApi.deleteAiSession(id).then(() => {
       loadAiSessions();
    }).catch(e => {
       console.error('Failed to delete chat', e);
       try { addNotification({ type: 'error', message: 'Could not delete this chat.' }); } catch (_) {}
       if (sessionToRestore) {
           setAiSessions(prev => [...prev, sessionToRestore]);
       }
    });
  };

  useEffect(() => {
    if (!appointmentDraft.doctor_id && doctors.length > 0) {
      setAppointmentDraft(prev => prev.doctor_id ? prev : { ...prev, doctor_id: String(doctors[0].doctor_id || doctors[0].id || '') });
    }
  }, [doctors, appointmentDraft.doctor_id]);

  useEffect(() => {
    const doctorId = String(appointmentDraft.doctor_id || '').trim();
    if (!doctorId) {
      setAvailableSlots([]);
      setSelectedSlotId('');
      return;
    }

    let cancelled = false;
    const loadSlots = async () => {
      setSlotLoading(true);
      try {
        const slots = await patientApi.getAvailableSlots(doctorId);
        if (!cancelled) {
          setAvailableSlots(Array.isArray(slots) ? slots : []);
          setSelectedSlotId((current) => {
            if (current && Array.isArray(slots) && slots.some((slot) => String(slot.id) === String(current))) {
              return current;
            }
            return '';
          });
        }
      } catch (e) {
        if (!cancelled) {
          setAvailableSlots([]);
          setSelectedSlotId('');
        }
      } finally {
        if (!cancelled) setSlotLoading(false);
      }
    };

    loadSlots();
    return () => {
      cancelled = true;
    };
  }, [appointmentDraft.doctor_id]);

  const resolveConsultationForDoctor = (doctorId) => {
    const matchId = String(doctorId || '');
    return consultations.find((item) => String(item.doctor_id || item.doctorId || '') === matchId) || null;
  };

  const resolveAppointmentForDoctor = (doctorId) => {
    const matchId = String(doctorId || '');
    const candidates = appointments.filter((item) => String(item.doctor_id || item.doctorId || '') === matchId);
    return candidates.sort((a, b) => new Date(b.created_at || b.createdAt || 0) - new Date(a.created_at || a.createdAt || 0))[0] || null;
  };

  const getDoctorChatStatus = (doctorId) => {
    const matchId = String(doctorId || '');
    const scheduledAppointments = appointments
      .filter((item) => String(item.doctor_id || item.doctorId || '') === matchId)
      .filter((item) => item.status === 'scheduled' && item.scheduled_time);

    if (scheduledAppointments.length === 0) {
      return { label: 'No Active Consultation', color: '#94A3B8' };
    }

    const now = Date.now();
    const liveAppointment = scheduledAppointments.find((item) => {
      const scheduledAt = new Date(item.scheduled_time).getTime();
      return now >= scheduledAt - 15 * 60 * 1000 && now <= scheduledAt + 30 * 60 * 1000;
    });

    if (liveAppointment) {
      return { label: 'In Consultation', color: '#22C55E' };
    }

    return { label: 'Available for Consultation', color: '#0EA5E9' };
  };

  const ensureConsultationForDoctor = async (doctorId) => {
    const existing = resolveConsultationForDoctor(doctorId);
    if (existing?.id) return existing.id;

    const appointment = resolveAppointmentForDoctor(doctorId);
    if (!appointment?.id) return null;

    const created = await patientApi.createConsultation(appointment.id);
    const consultationId = created?.id || created?.consultation_id || created?.consultationId || null;
    if (consultationId) {
      setConsultations(prev => {
        const next = prev.filter(item => String(item.id || '') !== String(consultationId));
        return [...next, { id: consultationId, appointment_id: appointment.id, doctor_id: String(doctorId), patient_id: String(user?.user_id || '') }];
      });
    }
    return consultationId;
  };

  const loadDocChat = async (consultationId, page = 1) => {
    try {
      if (!consultationId) {
        setDocMessages([]);
        setActiveConsultationId(null);
        return;
      }
      docAutoScrollRef.current = true;
      const data = await patientApi.getConsultationMessages(consultationId, page, 20);
      const items = normalizeChatMessages(data).filter((message) => String(message.senderId || '').toLowerCase() !== 'doctalk-ai');
      setDocMessages((currentMessages) => page === 1
        ? mergeChronologicalMessages(currentMessages, items)
        : mergeChronologicalMessages(items, currentMessages));
      setActiveConsultationId(consultationId);
      setDocMessagePage(page);
      setDocChatDisabled(false);
      docChatSnapshotRef.current = {
        consultationId,
        fingerprint: items.map((message, index) => getChatMessageKey(message, index)).join('|'),
      };
    } catch (e) { console.error('loadDocChat failed', e); }
  };

  useEffect(() => {
    if (activePanel !== 'docchat' || !activeDocChat) {
      docChatRealtimeRef.current?.stop();
      docChatRealtimeRef.current = null;
      docChatSnapshotRef.current = { consultationId: null, fingerprint: '' };
      return;
    }

    let cancelled = false;

    const bootstrapDocChat = async () => {
      const consultationId = await ensureConsultationForDoctor(activeDocChat);
      if (cancelled) return;

      if (!consultationId) {
        docChatRealtimeRef.current?.stop();
        docChatRealtimeRef.current = null;
        docChatSnapshotRef.current = { consultationId: null, fingerprint: '' };
        setActiveConsultationId(null);
        setDocMessages([]);
        return;
      }

      const client = createRealTimeClient({
        url: `/api/chat/consultations/${encodeURIComponent(consultationId)}/messages`,
        mode: 'auto',
        pollInterval: 5000,
        pollRequest: () => patientApi.getConsultationMessages(consultationId, 1, 20),
        getSnapshotKey: (payload) => normalizeChatMessages(payload)
          .filter((message) => String(message.senderId || '').toLowerCase() !== 'doctalk-ai')
          .map((message, index) => getChatMessageKey(message, index)).join('|'),
        onMessage: (payload) => {
          if (cancelled) return;
          if (String(payload?.type || '').toLowerCase() === 'history' && Array.isArray(payload?.messages)) {
            const latestMessages = normalizeChatMessages({ items: payload.messages }).filter((message) => String(message.senderId || '').toLowerCase() !== 'doctalk-ai');
            docChatSnapshotRef.current = {
              consultationId,
              fingerprint: latestMessages.map((message, index) => getChatMessageKey(message, index)).join('|'),
            };
            setDocMessages(latestMessages);
            setActiveConsultationId(consultationId);
            setDocMessagePage(1);
            setDocChatDisabled(false);
            docAutoScrollRef.current = true;
            return;
          }
          const latestMessages = normalizeChatMessages(payload).filter((message) => String(message.senderId || '').toLowerCase() !== 'doctalk-ai');
          docChatSnapshotRef.current = {
            consultationId,
            fingerprint: latestMessages.map((message, index) => getChatMessageKey(message, index)).join('|'),
          };
          setDocMessages((currentMessages) => mergeChronologicalMessages(currentMessages, latestMessages));
          setActiveConsultationId(consultationId);
          setDocMessagePage(1);
          setDocChatDisabled(false);
          docAutoScrollRef.current = true;
        },
        onError: (error) => {
          if (!cancelled) {
            console.error('Patient chat realtime error:', error);
          }
        },
      });

      docChatRealtimeRef.current?.stop();
      docChatRealtimeRef.current = client;

      await loadDocChat(consultationId, 1);
      if (!cancelled && docChatRealtimeRef.current === client) {
        client.start();
      }
    };

    bootstrapDocChat();

    return () => {
      cancelled = true;
      docChatRealtimeRef.current?.stop();
      docChatRealtimeRef.current = null;
    };
  }, [activePanel, activeDocChat, consultations, appointments]);

  const handleDocChatSubmit = async(e) => {
    e.preventDefault();
    const consultationId = activeConsultationId || await ensureConsultationForDoctor(activeDocChat);
    if(!docMsgInput.trim() || !consultationId) return;
    setDocSending(true);
    try {
      const messageText = docMsgInput;
      await patientApi.postConsultationMessage(consultationId, messageText);
      await loadDocChat(consultationId, docMessagePage);
      setDocMsgInput('');
      setDocAttachmentFile(null);
      docAutoScrollRef.current = true;
    } catch(e) {
      console.error('postDocChat failed', e);
      try { addNotification({ type: 'error', message: 'Failed to send message' }); } catch (e) {}
    } finally {
      setDocSending(false);
    }
  };

  const handleDocAttachChange = (e) => {
    const f = e.target.files && e.target.files[0];
    setDocAttachmentFile(f || null);
    if (e.target) e.target.value = null;
  };

  const handleLoadOlderDocMessages = async () => {
    try {
      if (!activeConsultationId) return;
      const nextPage = docMessagePage + 1;
      const data = await patientApi.getConsultationMessages(activeConsultationId, nextPage, 20);
      const items = normalizeChatMessages(data).filter((message) => String(message.senderId || '').toLowerCase() !== 'doctalk-ai');
      if (items.length > 0) {
        setDocMessages(prev => mergeChronologicalMessages(items, prev));
        setDocMessagePage(nextPage);
      }
    } catch (err) { console.error('load older messages failed', err); }
  };

  useEffect(() => {
    if (docAutoScrollRef.current) {
      docChatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      docAutoScrollRef.current = false;
    }
  }, [docMessages]);

  const handleSelectDoctorForAppointment = (docId) => {
    setActivePanelFromNav('appointments');
    setAppointmentDraft(prev => ({ ...prev, doctor_id: String(docId) }));
    setSelectedSlotId('');
  };

  const refreshAvailableSlotsForDoctor = async (doctorId) => {
    const nextDoctorId = String(doctorId || '').trim();
    if (!nextDoctorId) {
      setAvailableSlots([]);
      setSelectedSlotId('');
      return [];
    }

    setSlotLoading(true);
    try {
      const slots = await patientApi.getAvailableSlots(nextDoctorId);
      const nextSlots = Array.isArray(slots) ? slots : [];
      setAvailableSlots(nextSlots);
      setSelectedSlotId((current) => {
        if (current && nextSlots.some((slot) => String(slot.id) === String(current))) {
          return current;
        }
        return '';
      });
      return nextSlots;
    } catch (e) {
      setAvailableSlots([]);
      setSelectedSlotId('');
      return [];
    } finally {
      setSlotLoading(false);
    }
  };

  // ── Razorpay payment handlers ─────────────────────────────────────────────

  /** Step 1: Patient submits form → create Razorpay order (provisional appointment) */
  const handleInitiatePayment = async (e) => {
    e.preventDefault();
    if (bookingInProgress || paymentProcessing) return;

    const doctorId = String(appointmentDraft.doctor_id || '').trim();
    const reason = String(appointmentDraft.reason || '').trim();

    if (!doctorId || !reason) {
      try { addNotification({ type: 'error', message: 'Choose a doctor and add a reason before booking.' }); } catch (e) {}
      return;
    }
    if (bookingMode === 'direct' && !String(selectedSlotId || '').trim()) {
      try { addNotification({ type: 'error', message: 'Choose an available slot before booking.' }); } catch (e) {}
      return;
    }

    setBookingInProgress(true);
    try {
      const order = await paymentApi.createOrder(
        bookingMode,
        doctorId,
        bookingMode === 'direct' ? selectedSlotId : null,
        reason,
        appointmentDraft.note?.trim() || null,
      );
      if (order?.order_id) {
        setPendingOrder(order);
      } else {
        throw new Error(order?.detail || order?.error || 'Order creation failed');
      }
    } catch (err) {
      console.error('create order failed', err);
      if (err?.status === 409) {
        await refreshAvailableSlotsForDoctor(doctorId);
        try { addNotification({ type: 'error', message: 'That slot was just booked. Please choose another.' }); } catch (e) {}
      } else {
        try { addNotification({ type: 'error', message: 'Payment initiation failed: ' + (err?.message || 'server error') }); } catch (e) {}
      }
    } finally {
      setBookingInProgress(false);
    }
  };

  /** Step 2: Razorpay checkout succeeded → verify HMAC on backend */
  const handlePaymentSuccess = async ({ razorpay_order_id, razorpay_payment_id, razorpay_signature, appointment_id }) => {
    setPaymentProcessing(true);
    try {
      const result = await paymentApi.verifyPayment(
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature,
        appointment_id,
      );
      if (result?.success) {
        const isDirectBooking = result.status === 'CONFIRMED';
        try {
          addNotification({
            type: 'success',
            message: isDirectBooking
              ? '✅ Payment successful! Your appointment is confirmed.'
              : '✅ Payment successful! Appointment request sent — the doctor will confirm the time.',
          });
        } catch (e) {}
        setPendingOrder(null);
        setAppointmentDraft(prev => ({ ...prev, reason: 'General consultation', note: '' }));
        await refreshAvailableSlotsForDoctor(appointmentDraft.doctor_id);
        loadAppointments();
      } else {
        try { addNotification({ type: 'error', message: 'Payment verification failed. Please contact support.' }); } catch (e) {}
      }
    } catch (err) {
      console.error('verify payment failed', err);
      try { addNotification({ type: 'error', message: 'Payment verification error: ' + (err?.message || 'server error') }); } catch (e) {}
    } finally {
      setPaymentProcessing(false);
    }
  };

  /** Step 2b: Razorpay checkout failed or was dismissed */
  const handlePaymentFailure = (err) => {
    setPendingOrder(null);
    setPaymentProcessing(false);
    try { addNotification({ type: 'error', message: 'Payment failed: ' + (err?.message || 'unknown error') }); } catch (e) {}
    // Refresh slots in case the slot hold was released by the backend
    if (appointmentDraft.doctor_id) {
      refreshAvailableSlotsForDoctor(appointmentDraft.doctor_id);
    }
    loadAppointments();
  };

  const handlePaymentDismiss = () => {
    setPendingOrder(null);
    setPaymentProcessing(false);
    try { addNotification({ type: 'info', message: 'Payment cancelled. Your appointment request was not confirmed.' }); } catch (e) {}
    if (appointmentDraft.doctor_id) {
      refreshAvailableSlotsForDoctor(appointmentDraft.doctor_id);
    }
    loadAppointments();
  };

  useEffect(() => {
    const handleAiPaymentClick = (e) => {
      const payloadString = e.detail;
      try {
        const orderInfo = JSON.parse(payloadString);
        console.debug('[WS] Received payment order via link click', orderInfo);
        setPendingOrder(orderInfo);
      } catch (err) {
        console.error('Failed to parse payment order from ai-payment-click', err);
      }
    };
    window.addEventListener('ai-payment-click', handleAiPaymentClick);
    return () => window.removeEventListener('ai-payment-click', handleAiPaymentClick);
  }, []);

  /** "Pay Now" button for existing PAYMENT_PENDING appointments */
  const handlePayNow = async (appt) => {
    if (paymentProcessing) return;
    setPaymentProcessing(true);
    try {
      const order = await paymentApi.retryOrder(appt.id);
      if (order?.order_id) {
        setPendingOrder(order);
      } else {
        throw new Error('Could not recreate payment order');
      }
    } catch (err) {
      setPaymentProcessing(false);
      try { addNotification({ type: 'error', message: 'Could not initiate payment: ' + (err?.message || 'server error') }); } catch (e) {}
    }
  };

  useEffect(() => {
    if (!user || activePanel !== 'explain') return;
    loadAiSessions();
  }, [user, activePanel]);

  useEffect(() => {
    if (!user || activePanel !== 'explain' || !activeAiSessionId) return;
    if (activeAiSessionId.toString().startsWith('temp-')) return;
    loadChatHistory();
  }, [user, activePanel, activeAiSessionId]);

  const handleCancelAppointment = async (appointmentId) => {
    if (!window.confirm('Cancel this appointment?')) return;

    try {
      const data = await patientApi.cancelAppointment(appointmentId);
      if (data && (data.success || data.message)) {
        loadAppointments();
      } else {
        try { addNotification({ type: 'error', message: 'Error cancelling appointment: ' + (data && (data.error || data.detail) || 'unknown') }); } catch (e) {}
      }
    } catch (err) {
      console.error('cancel appointment failed', err);
      try { addNotification({ type: 'error', message: 'Error cancelling appointment: ' + (err?.message || 'server error') }); } catch (e) {}
    }
  };

  const renderSlotLabel = (slot) => {
    try {
      const start = new Date(slot.startTime);
      const end = new Date(slot.endTime);
      return `${start.toLocaleDateString()} • ${start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - ${end.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    } catch (e) {
      return 'Available slot';
    }
  };

  useEffect(() => { if (messages.length > 0) { setTimeout(() => { if (chatEndRef.current) { const container = chatEndRef.current.parentElement; container.scrollTo({ top: container.scrollHeight, behavior: "smooth" }); } }, 150); } }, [messages, activeAiSessionId]);

  const handleChatSubmit = async (e, textOverride = null) => {
    if (e) e.preventDefault();
    const textToSend = textOverride !== null ? textOverride : inputMsg;
    if (!textToSend.trim()) return;

    const newMsg = { sender: 'user', text: textToSend, id: Date.now() };
    setMessages(prev => [...prev, newMsg]);
    setInputMsg('');
    const textarea = document.getElementById('chat-input-textarea');
    if (textarea) textarea.style.height = 'auto';
    setIsAiProcessing(true);
    setProcessingState(null);

    // Abort controller for cleanup on unmount
    const abortController = new AbortController();
    let isMounted = true;

    try {
      const token = localStorage.getItem('doctalk_token');
      if (!token) {
        throw new Error('Missing session token');
      }

      const wsUrl = buildAiChatWebSocketUrl({ role: 'patient', token, aiSessionId: activeAiSessionId });
      const socket = new WebSocket(wsUrl);
      let finalText = '';
      let completed = false;
      let settleTimeout = null;

      const cleanup = () => {
        if (settleTimeout) clearTimeout(settleTimeout);
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          try { socket.close(); } catch (e) {}
        }
      };

      abortController.signal.addEventListener('abort', () => {
        cleanup();
        if (!completed) {
          completed = true;
          isMounted = false;
        }
      });

        await new Promise((resolve, reject) => {
          const INACTIVITY_TIMEOUT_MS = 60000;
        let inactivityTimeout = null;

        const clearInactivityTimeout = () => {
          if (inactivityTimeout) {
            clearTimeout(inactivityTimeout);
            inactivityTimeout = null;
          }
        };

        const resetInactivityTimeout = () => {
          clearInactivityTimeout();
          inactivityTimeout = setTimeout(() => {
            try { socket.close(); } catch (e) {}
            rejectOnce(new Error('Assistant response timed out due to inactivity'));
          }, INACTIVITY_TIMEOUT_MS);
        };

        const resolveOnce = () => {
          if (completed) return;
          completed = true;
          clearInactivityTimeout();
          resolve();
        };

        const rejectOnce = (error) => {
          if (completed) return;
          completed = true;
          clearInactivityTimeout();
          reject(error);
        };

        socket.onopen = () => {
          resetInactivityTimeout();
          socket.send(JSON.stringify({ message: textToSend, language }));
        };

        socket.onmessage = (event) => {
          let payload = null;
          try {
            payload = JSON.parse(event.data);
          } catch (parseError) {
            payload = { type: 'token', content: String(event.data || '') };
          }

          resetInactivityTimeout();

          const eventType = String(payload?.type || payload?.status || '').toLowerCase();
          const chunkText = String(payload?.content || payload?.text || payload?.chunk || '');

          if (eventType === 'history') {
            return;
          }

          if (eventType === 'status') {
            if (isMounted) setProcessingState(String(payload?.node || ''));
            return;
          }

          if ((eventType === 'token' || eventType === 'message') && chunkText) {
            finalText += chunkText;
            if (isMounted) {
              setMessages(prev => {
                const filtered = prev.filter(m => m.id !== 'loading');
                const existingIndex = filtered.findIndex(m => m.id === 'assistant-stream');
                const nextMessage = { sender: 'model', text: finalText, id: 'assistant-stream' };
                if (existingIndex >= 0) {
                  const clone = [...filtered];
                  clone[existingIndex] = nextMessage;
                  return clone;
                }
                return [...filtered, nextMessage];
              });
            }
          }

          if (eventType === 'final' || eventType === 'done' || eventType === 'end' || payload?.isFinal === true) {
            if (isMounted) {
              setIsAiProcessing(false);
              setProcessingState(null);
              const textReply = String(chunkText || finalText || '').trim() || "I'm sorry, I was unable to generate a response. Please try again.";
              setMessages(prev => {
                const filtered = prev.filter(m => m.id !== 'loading' && m.id !== 'assistant-stream');
                return [...filtered, { sender: 'model', text: textReply, id: Date.now() }];
              });
              
              if (payload?.payment_order) {
                console.debug('[WS] Received payment order', payload.payment_order);
                setPendingOrder(payload.payment_order);
              }
            }
            try { socket.close(); } catch (e) {}
            resolveOnce();
            return;
          }

          if (eventType === 'error') {
            if (isMounted) {
              setIsAiProcessing(false);
              setProcessingState(null);
            }
            try { socket.close(); } catch (e) {}
            rejectOnce(new Error(chunkText || 'Assistant stream failed'));
          }
        };

        socket.onerror = () => {
          rejectOnce(new Error('Assistant websocket connection failed'));
        };

        socket.onclose = () => {
          if (completed) {
            return;
          }
          if (finalText) {
            if (isMounted) {
              setMessages(prev => {
                const filtered = prev.filter(m => m.id !== 'loading' && m.id !== 'assistant-stream');
                return [...filtered, { sender: 'model', text: finalText, id: Date.now() }];
              });
            }
            resolveOnce();
            return;
          }
          rejectOnce(new Error('Assistant websocket closed unexpectedly'));
        };
      });
    } catch (err) {
      if (isMounted) {
        const errText = String(err?.message || '');
        const shouldShowFallback = /timed out|closed unexpectedly/i.test(errText);
        setMessages(prev => {
          const filtered = prev.filter(m => m.id !== 'loading' && m.id !== 'assistant-stream');
          if (shouldShowFallback) {
            return [...filtered, { sender: 'model', text: 'I am sorry, the connection timed out. Please try again.', id: Date.now() }];
          }
          return filtered;
        });
        setIsAiProcessing(false);
        setProcessingState(null);
        try { addNotification({ type: 'error', message: "Failed to send message: " + err.message }); } catch (e) {}
      }
    } finally {
      isMounted = false;
    }
  };

  const handleAddExplainFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploadedFiles(prev => [...prev, {
      id: Math.random(),
      file: file,
      name: file.name,
      type: file.type
    }]);

    // Persisting the file has been removed for temporary quick analysis uploads.

    if (explainUploadInputRef.current) {
      explainUploadInputRef.current.value = '';
    }
  };

  const handleRemoveExplainFile = (id) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== id));
  };

  const handleExplainUpload = async (e) => {
    e.preventDefault();

    if (uploadedFiles.length === 0) {
      try { addNotification({ type: 'error', message: 'Please select at least one file to analyze.' }); } catch (e) {}
      return;
    }

    setIsAiProcessing(true);
    setProcessingState('Analyzing files... Please wait.');

    try {
      for (const fileObj of uploadedFiles) {
        const formData = new FormData();

        if (fileObj.type === 'application/pdf' || fileObj.name.toLowerCase().endsWith('.pdf')) {
          formData.append('report', fileObj.file);
        } else {
          formData.append('medical_image', fileObj.file);
        }

        formData.append('language', language);
        if (activeAiSessionId) {
          formData.append('ai_session_id', activeAiSessionId);
        }

        const token = localStorage.getItem('doctalk_token');
        const response = await fetch('/api/explain_report', {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: 'include',
          body: formData
        });
        const data = await response.json();

        setIsAiProcessing(false);
        setProcessingState(null);
        setMessages(prev => {
          const filtered = prev.filter(m => m.id !== 'loading');
          if (data.success) {
            const reply = data.reply;
            if (typeof reply === 'object' && reply) {
              return [...filtered, { sender: 'model', structured: reply }];
            }
            return [...filtered, { sender: 'model', text: String(reply) }];
          }
        return [...filtered, { sender: 'model', text: 'Error analyzing ' + fileObj.name + ': ' + (data.error || data.detail || data.message || 'Unknown error') }];
        });
      }

      setUploadedFiles([]);
    } catch (err) {
      setIsAiProcessing(false);
      setProcessingState(null);
      setMessages(prev => prev.filter(m => m.id !== 'loading'));
      try { addNotification({ type: 'error', message: 'Analysis failed: ' + err.message }); } catch (e) {}
    }
  };

  const handleAnalyzeSelected = async () => {
    if (!selectedDocForAnalysis) {
      try { addNotification({ type: 'error', message: 'Please select a document to analyze.' }); } catch (e) {}
      return;
    }

    setIsAiProcessing(true);
    setProcessingState('Analyzing selected document... Please wait.');

    try {
      const formData = new FormData();
      formData.append('file_id', selectedDocForAnalysis);
      formData.append('language', language);
      if (activeAiSessionId) {
        formData.append('ai_session_id', activeAiSessionId);
      }

      const token = localStorage.getItem('doctalk_token');
      const response = await fetch('/api/analyze_document', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
        body: formData
      });
      const data = await response.json();

      setIsAiProcessing(false);
      setProcessingState(null);
      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== 'loading');
        if (data.success) {
          const reply = data.reply;
          if (reply && typeof reply === 'object') return [...filtered, { sender: 'model', structured: reply }];
          return [...filtered, { sender: 'model', text: String(reply) }];
        }
        return [...filtered, { sender: 'model', text: 'Error analyzing document: ' + (data.error || data.detail || data.message || 'Unknown error') }];
      });
    } catch (err) {
      setIsAiProcessing(false);
      setProcessingState(null);
      setMessages(prev => prev.filter(m => m.id !== 'loading'));
      try { addNotification({ type: 'error', message: 'Analysis failed: ' + err.message }); } catch (e) {}
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      try { localStorage.removeItem('doctalk_token'); localStorage.removeItem('doctalk_session'); } catch (e) {}
    }
    navigate('/login');
  };

  if (!user) return <div style={{ height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#F5F5F7' }}><div style={{ transform: 'scale(1.3)' }}><AiProcessingCard active={true} status="Loading App Data..." /></div></div>;

  const activeSession = aiSessions.find((s) => s.id === (activeAiSessionId || ''));
  const isActiveDefault = !!(activeSession && activeSession.is_default);

  return (
    <div className="app-wrapper" style={{ height: '100vh', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
      <div style={{ position: 'absolute', top: '24px', left: '112px', zIndex: 100 }}>
        <div className="nav-text-logo" style={{ fontSize: '28px', margin: 0 }}>
          DocTalk<span className="logo-sup" style={{ fontSize: '14px' }}>AI</span>
        </div>
      </div>

      <div className="profile-container" style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', boxSizing: 'border-box', position: 'relative' }}>
        {/* Left Icon Sidebar (80px) -> Becomes Bottom Nav on Mobile */}
        <nav className="neu-left-sidebar" aria-label="Main navigation">
          <button className="neu-sidebar-logo" onClick={() => setActivePanelFromNav('explain')} title="DocTalk AI">
            D
          </button>

          <div className="neu-sidebar-nav">
            <button
              className={`neu-sidebar-item ${activePanel === 'overview' ? 'active' : ''}`}
              onClick={() => setActivePanelFromNav('overview')}
              title="Home"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9.5 21v-6h5v6"/></svg>
              <span className="tooltip">Home</span>
            </button>
            <button
              className={`neu-sidebar-item ${activePanel === 'explain' ? 'active' : ''}`}
              onClick={() => setActivePanelFromNav('explain')}
              title="AI Chat"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3Z"/></svg>
              <span className="tooltip">AI Chat</span>
            </button>
            <button
              className={`neu-sidebar-item ${activePanel === 'history' ? 'active' : ''}`}
              onClick={() => setActivePanelFromNav('history')}
              title="Dashboard"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
              <span className="tooltip">Dashboard</span>
            </button>
            <button
              className={`neu-sidebar-item ${activePanel === 'xray' ? 'active' : ''}`}
              onClick={() => setActivePanelFromNav('xray')}
              title="Med Image Analysis"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              <span className="tooltip">Med Image Analysis</span>
            </button>
            <button
              className={`neu-sidebar-item ${activePanel === 'appointments' ? 'active' : ''}`}
              onClick={() => setActivePanelFromNav('appointments')}
              title="Appointments"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
              <span className="tooltip">Appointments</span>
            </button>
            <button
              className={`neu-sidebar-item ${activePanel === 'docchat' ? 'active' : ''}`}
              onClick={() => setActivePanelFromNav('docchat')}
              title="Doctor Chat"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              <span className="tooltip">Doctor Chat</span>
            </button>
            <button
              className={`neu-sidebar-item ${activePanel === 'documents' ? 'active' : ''}`}
              onClick={() => setActivePanelFromNav('documents')}
              title="My Documents"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              <span className="tooltip">My Documents</span>
            </button>
          </div>

          <div className="neu-sidebar-spacer" />

          <div className="neu-sidebar-bottom" style={{ position: 'relative' }}>
            {isSettingsOpen && (
              <div className="neu-settings-popup">
                <button 
                  className="neu-settings-option" 
                  onClick={() => { setActivePanelFromNav('profile'); setIsSettingsOpen(false); }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  Profile
                </button>
                <button 
                  className="neu-settings-option logout" 
                  onClick={() => { handleLogout(); setIsSettingsOpen(false); }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                  Logout
                </button>
              </div>
            )}
            <button
              className={`neu-sidebar-item ${isSettingsOpen || activePanel === 'profile' ? 'active' : ''}`}
              onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              title="Settings"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
              <span className="tooltip">Settings</span>
            </button>
          </div>
        </nav>

        {/* Chat History Sidebar */}
        <aside className={`neu-chat-history-sidebar flex flex-col ${chatHistoryCollapsed ? 'collapsed' : ''}`}>
          <div className="neu-chat-history-header flex items-center justify-end mb-6" style={{ padding: '0 8px', marginTop: '64px' }}>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setChatHistoryCollapsed(true)}
                className="neu-convex-sm flex items-center justify-center"
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  border: 'none',
                  cursor: 'pointer',
                  transition: 'all 150ms ease-in-out',
                }}
                title="Collapse sidebar"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--text-secondary)' }}><polyline points="15 18 9 12 15 6"></polyline></svg>
              </button>
              <button
                onClick={handleNewChat}
                className="neu-btn-accent flex items-center justify-center gap-1.5"
                style={{
                  height: '32px',
                  padding: '0 14px',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 600,
                  fontFamily: 'var(--font-body)',
                }}
                title="New chat"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                New Chat
              </button>
            </div>
          </div>
          <div className="neu-chat-search">
            <input
              type="text"
              placeholder="Search chats..."
              value={chatSearchQuery}
              onChange={(e) => setChatSearchQuery(e.target.value)}
            />
          </div>
           <div className="neu-chat-history-list">
             {[...aiSessions]
              .sort((a, b) => {
                const dateA = new Date(a.updated_at || a.created_at || 0);
                const dateB = new Date(b.updated_at || b.created_at || 0);
                return dateB - dateA;
              })
              .filter((s) => {
                if (!chatSearchQuery.trim()) return true;
                const q = chatSearchQuery.toLowerCase();
                return (s.title || '').toLowerCase().includes(q);
              })
               .map((session) => (
                <div
                  key={session.id}
                  className={`neu-chat-history-item ${session.id === activeAiSessionId ? 'active' : ''}`}
                  onClick={() => {
                    setActiveAiSessionId(session.id);
                    setMessages([]);
                    setActivePanelFromNav('explain');
                  }}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      setActiveAiSessionId(session.id);
                      setMessages([]);
                      setActivePanelFromNav('explain');
                    }
                  }}
                >
                  <span className="neu-chat-history-item-title">{session.title || 'New Chat'}</span>
                  <span className="neu-chat-history-item-preview">
                    {'Medical analysis session'}
                  </span>
                  <span className="neu-chat-history-item-meta">
                    {session.updated_at || session.created_at ? new Date(session.updated_at || session.created_at).toLocaleDateString() : ''}
                  </span>
                  {aiSessions.length > 1 && (
                    <button
                      className="neu-chat-history-delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteSession(session.id);
                      }}
                      title="Delete chat"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
            {aiSessions.length === 0 && (
              <div style={{ textAlign: 'center', padding: '24px 16px', color: '#6E6E73', fontSize: '13px' }}>
                No chats yet
              </div>
            )}
          </div>
          <button className="neu-chat-expand-tab" onClick={() => setChatHistoryCollapsed(false)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>
          </button>
        </aside>

        {/* Mobile Drawer Overlay */}
        <div
          className={`mobile-drawer-overlay ${isMobileDrawerOpen || isRightDrawerOpen ? 'visible' : ''}`}
          onClick={() => { setIsMobileDrawerOpen(false); setIsRightDrawerOpen(false); }}
        />

        {/* Main Content */}
        <div className="main-content" style={{ flex: 1, minHeight: 0, overflow: 'hidden', background: 'var(--bg-base)', paddingTop: activePanel === 'explain' ? '0px' : '80px', position: 'relative' }}>
          {activePanel === 'overview' && (
            <PatientOverview
              user={user}
              appointments={appointments}
              vitals={vitals}
              lifestyle={lifestyle}
              medicalHistory={medicalHistory}
              onNavigate={setActivePanelFromNav}
            />
          )}

          {activePanel === 'explain' && (
            <PatientExplainPanel
              chatHistoryCollapsed={chatHistoryCollapsed}
              setIsMobileDrawerOpen={setIsMobileDrawerOpen}
              messages={messages}
              isAiProcessing={isAiProcessing}
              isOutgoingChatMessage={isOutgoingChatMessage}
              StructuredReply={StructuredReply}
              isJsonLike={isJsonLike}
              tryParseJson={tryParseJson}
              MarkdownMessage={MarkdownMessage}
              getCleanAnalysisText={getCleanAnalysisText}
              AiProcessingCard={AiProcessingCard}
              processingState={processingState}
              chatEndRef={chatEndRef}
              handleChatSubmit={handleChatSubmit}
              inputMsg={inputMsg}
              setInputMsg={setInputMsg}
              langDropdownOpen={langDropdownOpen}
              setLangDropdownOpen={setLangDropdownOpen}
              language={language}
              setLanguage={setLanguage}
              analysisMode={analysisMode}
              setAnalysisMode={setAnalysisMode}
              uploadedFiles={uploadedFiles}
              setUploadedFiles={setUploadedFiles}
              selectedDocForAnalysis={selectedDocForAnalysis}
              setSelectedDocForAnalysis={setSelectedDocForAnalysis}
              analysisCurrentFolder={analysisCurrentFolder}
              setAnalysisCurrentFolder={setAnalysisCurrentFolder}
              loadAssets={loadAssets}
              explainUploadInputRef={explainUploadInputRef}
              handleAddExplainFile={handleAddExplainFile}
              handleRemoveExplainFile={handleRemoveExplainFile}
              handleExplainUpload={handleExplainUpload}
              assets={assets}
              handleAnalyzeSelected={handleAnalyzeSelected}
            />
          )}
          {activePanel === 'history' && (
            <ErrorBoundary><PatientHistoryPanel
              healthView={healthView}
              setHealthView={setHealthView}
              medTab={medTab}
              setMedTab={setMedTab}
              conditions={conditions}
              medications={medications}
              allergies={allergies}
              surgeries={surgeries}
              familyHistory={familyHistory}
              lifestyle={lifestyle}
              vitals={vitals}
              vitalsForm={vitalsForm}
              setVitalsForm={setVitalsForm}
              editingVitals={editingVitals}
              setEditingVitals={setEditingVitals}
              saveVitals={saveVitals}
              bmiCalc={bmiCalc}
              lifestyleForm={lifestyleForm}
              setLifestyleForm={setLifestyleForm}
              editingLifestyle={editingLifestyle}
              setEditingLifestyle={setEditingLifestyle}
              appointments={appointments}
              latestRx={latestRx}
              immunizations={immunizations}
              setActivePanelFromNav={setActivePanelFromNav}
              prescriptionApi={prescriptionApi}
              navigate={navigate}
            /></ErrorBoundary>
          )}

          {activePanel === 'profile' && (
            <PatientProfilePanel
              user={user}
              handleProfileUpdate={handleProfileUpdate}
              isUploadingProfile={isUploadingProfile}
            />
          )}
          {activePanel === 'documents' && (
            <PatientDocumentsPanel
              currentFolder={currentFolder}
              setCurrentFolder={setCurrentFolder}
              getFolderDisplayName={getFolderDisplayName}
              handleUploadAssetV2={handleUploadAssetV2}
              previewFile={previewFile}
              setPreviewFile={setPreviewFile}
              renameTarget={renameTarget}
              setRenameTarget={setRenameTarget}
              renameValue={renameValue}
              setRenameValue={setRenameValue}
              submitRenameAsset={submitRenameAsset}
              assets={assets}
              handleRenameAsset={handleRenameAsset}
              handleDeleteAssetV2={handleDeleteAssetV2}
              uploadQueue={uploadQueue}
            />
          )}

          {activePanel === 'xray' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', paddingLeft: '32px', paddingRight: '32px', minHeight: 0 }}>
              <XrayAnalyzerPanel />
            </div>
          )}

          {activePanel === 'appointments' && (
            <ErrorBoundary><PatientAppointmentsPanel
              appointments={appointments}
              doctors={doctors}
              appointmentDraft={appointmentDraft}
              setAppointmentDraft={setAppointmentDraft}
              bookingMode={bookingMode}
              setBookingMode={setBookingMode}
              availableSlots={availableSlots}
              selectedSlotId={selectedSlotId}
              setSelectedSlotId={setSelectedSlotId}
              slotLoading={slotLoading}
              bookingInProgress={bookingInProgress}
              paymentProcessing={paymentProcessing}
              user={user}
              handlePayNow={handlePayNow}
              handleCancelAppointment={handleCancelAppointment}
              handleInitiatePayment={handleInitiatePayment}
              handleSelectDoctorForAppointment={handleSelectDoctorForAppointment}
              renderSlotLabel={renderSlotLabel}
            /></ErrorBoundary>
          )}

          {/* ── Razorpay Checkout Modal ─────────────────────────────── */}
          {pendingOrder && (
            <RazorpayCheckout
              order={pendingOrder}
              patientName={user?.name || user?.display_name || ''}
              patientEmail={user?.email || ''}
              patientPhone={user?.mobile || user?.phone || ''}
              onSuccess={handlePaymentSuccess}
              onFailure={handlePaymentFailure}
              onDismiss={handlePaymentDismiss}
              autoOpen={true}
            />
          )}

          {activePanel === 'docchat' && (
            <PatientDocChatPanel
              doctors={doctors}
              resolveConsultationForDoctor={resolveConsultationForDoctor}
              activeDocChat={activeDocChat}
              setActiveDocChat={setActiveDocChat}
              getDoctorChatStatus={getDoctorChatStatus}
              activeConsultationId={activeConsultationId}
              handleLoadOlderDocMessages={handleLoadOlderDocMessages}
              docMessages={docMessages}
              docChatEndRef={docChatEndRef}
              handleDocChatSubmit={handleDocChatSubmit}
              handleDocAttachChange={handleDocAttachChange}
              docAttachmentFile={docAttachmentFile}
              docMsgInput={docMsgInput}
              setDocMsgInput={setDocMsgInput}
              setDocInputFocused={setDocInputFocused}
              docChatDisabled={docChatDisabled}
              docSending={docSending}
            />
          )}
        </div>
        </div>
      
        {/* Delete Confirmation Modal */}
        {chatToDelete && (
          <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(255, 255, 255, 0.4)', backdropFilter: 'blur(8px)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div className="neu-flat" style={{ width: '380px', padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px', alignItems: 'center', textAlign: 'center' }}>
              <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: '#FEE2E2', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#EF4444' }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
              </div>
              <div>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>Delete Chat?</h3>
                <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>Are you sure you want to delete this chat? This action cannot be undone.</p>
              </div>
              <div style={{ display: 'flex', gap: '16px', width: '100%', marginTop: '8px' }}>
                <button 
                  className="neu-flat"
                  style={{ flex: 1, padding: '14px 0', borderRadius: '12px', border: 'none', cursor: 'pointer', fontWeight: 600, color: 'var(--text-secondary)' }}
                  onClick={() => setChatToDelete(null)}
                >
                  Cancel
                </button>
                <button 
                  className="neu-btn-accent"
                  style={{ flex: 1, padding: '14px 0', borderRadius: '12px', border: 'none', cursor: 'pointer', fontWeight: 600, background: 'linear-gradient(145deg, #EF4444, #DC2626)', boxShadow: '4px 4px 10px rgba(239, 68, 68, 0.3)' }}
                  onClick={confirmDeleteChat}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
    </div>
  );
}
