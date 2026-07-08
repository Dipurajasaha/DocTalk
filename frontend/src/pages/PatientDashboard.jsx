import { useState, useEffect, useRef } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useNotifications, useAssetCache } from '../contexts';
import { useLocation, useNavigate } from 'react-router-dom';
import { authApi, patientApi, buildAssetDownloadUrl } from '../lib/api';
import { buildAiChatWebSocketUrl, createRealTimeClient } from '../lib/realTimeClient';
import '../styles/patient.css';
import XrayAnalyzerPanel from '../components/XrayAnalyzerPanel';
import MarkdownMessage from '../components/chat/MarkdownMessage';
import FileViewer from '../components/FileViewer';
import AiProcessingCard from '../components/AiProcessingCard';
import StructuredReply from '../components/StructuredReply';

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

export default function PatientDashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(null);
  const { markExpired, logout } = useSession();
  const [messages, setMessages] = useState([]);
  const [inputMsg, setInputMsg] = useState('');
  const [language, setLanguage] = useState('en');
  const VALID_PANELS = ['explain', 'documents', 'xray', 'appointments', 'docchat', 'history', 'profile'];

  const [activePanel, setActivePanel] = useState(() => {
    try {
      const panel = new URLSearchParams(window.location.search).get('panel');
      return VALID_PANELS.includes(panel) ? panel : 'explain';
    } catch (e) {
      return 'explain';
    }
  });

  const setActivePanelFromNav = (panel) => {
    const nextPanel = VALID_PANELS.includes(panel) ? panel : 'explain';
    setActivePanel(nextPanel);
    navigate(`/patient/dashboard?panel=${encodeURIComponent(nextPanel)}`);
  };

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
  const docChatEndRef = useRef(null);
  const docAutoScrollRef = useRef(false);
  const [docInputFocused, setDocInputFocused] = useState(false);
  const docChatRealtimeRef = useRef(null);
  const docChatSnapshotRef = useRef({ consultationId: null, fingerprint: '' });

  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
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

  // Vitals
  const [vitals, setVitals] = useState(() => loadMed('dtalk_vitals', {
    height: '', weight: '', blood_group: '', bmi: '',
    blood_pressure: '', heart_rate: '', blood_sugar_fasting: '',
    blood_sugar_pp: '', spo2: '', temperature: '',
  }));
  const [editingVitals, setEditingVitals] = useState(false);
  const [vitalsForm, setVitalsForm] = useState(vitals);
  const saveVitals = (v) => { setVitals(v); saveMed('dtalk_vitals', v); };
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
  const saveConditions = (r) => { setConditions(r); saveMed('dtalk_conditions', r); };
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
  const saveMedications = (r) => { setMedications(r); saveMed('dtalk_medications', r); };
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
  const saveAllergies = (r) => { setAllergies(r); saveMed('dtalk_allergies', r); };
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
  const saveSurgeries = (r) => { setSurgeries(r); saveMed('dtalk_surgeries', r); };
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
  }, [activePanel]);

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
      const data = await patientApi.getAiChatHistory('patient_ai');
      const items = Array.isArray(data?.messages) ? data.messages : [];
      setMessages(items.map((item) => ({
        senderId: item?.sender_id || item?.senderId || (String(item?.role || '').toLowerCase() === 'assistant' ? 'doctalk-ai' : 'user'),
        sender: String(item?.role || '').toLowerCase() === 'assistant' ? 'model' : 'user',
        text: item?.message || item?.content || item?.text || '',
        id: item?.id || `${item?.timestamp || Date.now()}-${Math.random().toString(16).slice(2)}`,
        timestamp: item?.timestamp || item?.created_at || item?.createdAt || null,
      })));
    } catch (e) {
      console.error(e);
      setMessages([]);
    }
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

  const handleCreateAppointment = async (e) => {
    e.preventDefault();

    if (bookingInProgress) return;

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
      const data = bookingMode === 'direct'
        ? await patientApi.bookDirectAppointment(selectedSlotId, reason, appointmentDraft.note.trim())
        : await patientApi.bookOpenAppointment(doctorId, reason, appointmentDraft.note.trim());

      if (data && (data.id || data.success)) {
        try { addNotification({ type: 'success', message: bookingMode === 'direct' ? 'Appointment booked successfully' : 'Open request sent successfully' }); } catch (e) {}
        await refreshAvailableSlotsForDoctor(doctorId);
        setAppointmentDraft(prev => ({
          ...prev,
          reason: 'General consultation',
          note: '',
        }));
        loadAppointments();
      } else {
        try { addNotification({ type: 'error', message: 'Error creating appointment: ' + (data && (data.error || data.detail) || 'unknown') }); } catch (e) {}
      }
    } catch (err) {
      console.error('create appointment failed', err);
      if (err?.status === 409) {
        await refreshAvailableSlotsForDoctor(doctorId);
        try { window.alert('That slot was just booked by someone else. Please choose another available slot.'); } catch (e) {}
        try { addNotification({ type: 'error', message: 'That slot was just booked by someone else. Please choose another available slot.' }); } catch (e) {}
      } else {
        try { addNotification({ type: 'error', message: 'Error creating appointment: ' + (err?.message || 'server error') }); } catch (e) {}
      }
    } finally {
      setBookingInProgress(false);
    }
  };

  useEffect(() => {
    if (!user || activePanel !== 'explain') return;
    loadChatHistory();
  }, [user, activePanel]);

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

  useEffect(() => {
    if (messages.length > 0) {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [messages]);

  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!inputMsg.trim()) return;

    const newMsg = { sender: 'user', text: inputMsg, id: Date.now() };
    setMessages(prev => [...prev, newMsg]);
    setInputMsg('');
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

      const wsUrl = buildAiChatWebSocketUrl({ role: 'patient', token });
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
          socket.send(inputMsg);
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

    setMessages(prev => [...prev, { sender: 'model', id: 'loading', text: 'Analyzing files... Please wait.' }]);

    try {
      for (const fileObj of uploadedFiles) {
        const formData = new FormData();

        if (fileObj.type === 'application/pdf' || fileObj.name.toLowerCase().endsWith('.pdf')) {
          formData.append('report', fileObj.file);
        } else {
          formData.append('medical_image', fileObj.file);
        }

        formData.append('language', language);

        const token = localStorage.getItem('doctalk_token');
        const response = await fetch('/api/explain_report', {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: 'include',
          body: formData
        });
        const data = await response.json();

        setMessages(prev => {
          const filtered = prev.filter(m => m.id !== 'loading');
          if (data.success) {
            const reply = data.reply;
            let textReply = '';
            if (typeof reply === 'object' && reply) {
              const parts = [];
              if (reply.summary) parts.push(reply.summary);
              if (reply.key_findings && Array.isArray(reply.key_findings)) {
                parts.push('Key Findings: ' + reply.key_findings.join(', '));
              }
              if (reply.observations && Array.isArray(reply.observations)) {
                parts.push('Observations: ' + reply.observations.join(', '));
              }
              if (reply.risks && Array.isArray(reply.risks)) {
                parts.push('Risks: ' + reply.risks.join(', '));
              }
              if (reply.recommendations && Array.isArray(reply.recommendations)) {
                parts.push('Recommendations: ' + reply.recommendations.join(', '));
              }
              if (reply.notes) {
                const notesText = Array.isArray(reply.notes) ? reply.notes.join('. ') : reply.notes;
                parts.push('Notes: ' + notesText);
              }
              textReply = parts.filter(p => p).join('\n\n');
            } else {
              textReply = String(reply);
            }
            return [...filtered, { sender: 'model', text: textReply }];
          }
          return [...filtered, { sender: 'model', text: 'Error analyzing ' + fileObj.name + ': ' + data.error }];
        });
      }

      setUploadedFiles([]);
    } catch (err) {
      setMessages(prev => prev.filter(m => m.id !== 'loading'));
      try { addNotification({ type: 'error', message: 'Analysis failed: ' + err.message }); } catch (e) {}
    }
  };

  const handleAnalyzeSelected = async () => {
    if (!selectedDocForAnalysis) {
      try { addNotification({ type: 'error', message: 'Please select a document to analyze.' }); } catch (e) {}
      return;
    }

    setMessages(prev => [...prev, { sender: 'model', id: 'loading', text: 'Analyzing selected document... Please wait.' }]);

    try {
      const formData = new FormData();
      formData.append('file_id', selectedDocForAnalysis);
      formData.append('language', language);

      const token = localStorage.getItem('doctalk_token');
      const response = await fetch('/api/analyze_document', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
        body: formData
      });
      const data = await response.json();

      setMessages(prev => {
        const filtered = prev.filter(m => m.id !== 'loading');
        if (data.success) {
          const reply = data.reply;
          if (reply && typeof reply === 'object') return [...filtered, { sender: 'model', structured: reply }];
          return [...filtered, { sender: 'model', text: String(reply) }];
        }
        return [...filtered, { sender: 'model', text: 'Error analyzing document: ' + data.error }];
      });
    } catch (err) {
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

  if (!user) return <div style={{padding: '50px', textAlign: 'center'}}>Loading App Data...</div>;

  return (
    <div className="app-wrapper" style={{ height: '100vh', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
      {/* Top Navigation Bar */}
      <nav className="top-navbar">
        <div className="nav-text-logo">
          DocTalk<span className="logo-sup">AI</span>
        </div>
        <div style={{ flex: 1 }} />
        <button 
          onClick={handleLogout} 
          style={{ background: '#fff', color: '#ff4b5c', border: '1px solid #ff4b5c', padding: '8px 20px', borderRadius: '50px', fontWeight: '600', cursor: 'pointer', transition: '0.2s', fontSize: '11px', boxShadow: '0 2px 4px rgba(0,0,0,0.15)' }}
          onMouseEnter={(e) => { e.target.style.background = '#ff4b5c'; e.target.style.color = '#fff'; }}
          onMouseLeave={(e) => { e.target.style.background = '#fff'; e.target.style.color = '#ff4b5c'; }}
        >
          Logout
        </button>
      </nav>

      <div className="profile-container" style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', boxSizing: 'border-box' }}>
        {/* Sidebar */}
        <div className="sidebar patient-sidebar-override">
          <img src={user.profile_pic} alt="Profile" className="patient-sidebar-img" />
          <div className="patient-sidebar-name">{user.name}</div>

          <div className="patient-nav">
            <button 
              className={activePanel === 'explain' ? 'active' : ''}
              onClick={() => setActivePanelFromNav('explain')}
            >
              Analyze Report
            </button>
            <button
              className={activePanel === 'documents' ? 'active' : ''}
              onClick={() => setActivePanelFromNav('documents')}
            >
              My Documents
            </button>
            <button onClick={() => navigate('/patient/prescriptions')}>
              Prescriptions
            </button>
            <button 
              className={activePanel === 'xray' ? 'active' : ''}
              onClick={() => setActivePanelFromNav('xray')}
            >
              X-Ray Analysis
            </button>
            <button 
              className={activePanel === 'appointments' ? 'active' : ''}
              onClick={() => setActivePanelFromNav('appointments')}
            >
              Appointments
            </button>
            <button 
              className={activePanel === 'docchat' ? 'active' : ''}
              onClick={() => setActivePanelFromNav('docchat')}
            >
              Doctor Chat
            </button>
            <button 
              className={activePanel === 'history' ? 'active' : ''}
              onClick={() => setActivePanelFromNav('history')}
            >
              Medical History
            </button>
            <button 
              className={activePanel === 'profile' ? 'active' : ''}
              onClick={() => setActivePanelFromNav('profile')}
            >
              Profile
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="main-content" style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: '24px', gap: '24px', background: '#F0F2F5', borderTopLeftRadius: '40px', overflow: 'hidden', minHeight: 0, boxSizing: 'border-box' }}>
          
          {/* ═══════════════════════ MEDICAL HISTORY PANEL (Full Clinical Profile) ═══════════════════════ */}
          {activePanel === 'history' && (() => {
            // ── Shared helpers ──────────────────────────────────────────────
            const S = {
              card:   { background:'#fff', borderRadius:'14px', padding:'20px 24px', boxShadow:'0 2px 12px rgba(0,0,0,0.06)', border:'1px solid #E2E8F0' },
              label:  { fontSize:'11px', fontWeight:'700', color:'#64748B', textTransform:'uppercase', letterSpacing:'0.5px', marginBottom:'4px', display:'block' },
              input:  { padding:'9px 13px', borderRadius:'8px', border:'1px solid #E2E8F0', fontSize:'13px', outline:'none', width:'100%', boxSizing:'border-box', fontFamily:'inherit' },
              select: { padding:'9px 13px', borderRadius:'8px', border:'1px solid #E2E8F0', fontSize:'13px', outline:'none', width:'100%', boxSizing:'border-box', fontFamily:'inherit', background:'#fff' },
              addBtn: { padding:'8px 18px', background:'linear-gradient(135deg,#8B7EFF,#6C5CE7)', color:'#fff', border:'none', borderRadius:'50px', cursor:'pointer', fontWeight:'600', fontSize:'12px', display:'inline-flex', alignItems:'center', gap:'5px' },
              cancelBtn: { padding:'8px 18px', borderRadius:'50px', border:'1px solid #E2E8F0', background:'#fff', cursor:'pointer', fontSize:'12px', fontWeight:'600', color:'#64748B' },
              saveBtn:   { padding:'8px 22px', borderRadius:'50px', background:'linear-gradient(135deg,#8B7EFF,#6C5CE7)', color:'#fff', border:'none', cursor:'pointer', fontSize:'12px', fontWeight:'600', boxShadow:'0 3px 10px rgba(108,92,231,0.3)' },
              delBtn:    { padding:'5px 10px', borderRadius:'7px', border:'1px solid #fecaca', background:'#fef2f2', cursor:'pointer', fontSize:'11px', color:'#ef4444', fontWeight:'600' },
              editBtn:   { padding:'5px 10px', borderRadius:'7px', border:'1px solid #E2E8F0', background:'#F8FAFC', cursor:'pointer', fontSize:'11px', color:'#6C5CE7', fontWeight:'600' },
            };
            const FG = ({ label, children }) => (
              <div style={{ display:'flex', flexDirection:'column', gap:'4px' }}>
                <span style={S.label}>{label}</span>
                {children}
              </div>
            );
            const severityColor  = { mild:'#22c55e', moderate:'#f59e0b', severe:'#ef4444', critical:'#7c3aed' };
            const statusColor    = { active:'#ef4444', resolved:'#22c55e', chronic:'#f97316', monitoring:'#3b82f6' };
            const statusBg       = { active:'#fef2f2', resolved:'#f0fdf4', chronic:'#fff7ed', monitoring:'#eff6ff' };
            const allergyColor   = { mild:'#22c55e', moderate:'#f59e0b', severe:'#ef4444', 'life-threatening':'#7c3aed' };

            const hasAlerts = allergies.filter(a=>a.severity==='severe'||a.severity==='life-threatening').length > 0;
            const currentMeds = medications.filter(m=>m.is_ongoing);
            const activeConditions = conditions.filter(c=>c.status==='active'||c.status==='chronic');

            const TABS = [
              { id:'overview',      label:'Overview',          icon:'🏠' },
              { id:'vitals',        label:'Vitals',            icon:'❤️' },
              { id:'conditions',    label:'Conditions',        icon:'🩺' },
              { id:'medications',   label:'Medications',       icon:'💊' },
              { id:'allergies',     label:'Allergies',         icon:'⚠️' },
              { id:'surgeries',     label:'Surgeries',         icon:'🔪' },
              { id:'family',        label:'Family History',    icon:'👨‍👩‍👧' },
              { id:'immunizations', label:'Immunisations',     icon:'💉' },
              { id:'lifestyle',     label:'Lifestyle',         icon:'🌿' },
            ];

            return (
              <div style={{ display:'flex', flexDirection:'column', flex:1, minHeight:0, gap:'0' }}>
                {/* ── Page header ── */}
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'16px', flexShrink:0 }}>
                  <div>
                    <h2 style={{ margin:0, fontSize:'18px', color:'#6C5CE7', fontWeight:'800', letterSpacing:'-0.5px' }}>Medical Profile</h2>
                    <p style={{ margin:'3px 0 0', fontSize:'12px', color:'#8B7EFF' }}>Complete clinical record — visible to your treating doctors</p>
                  </div>
                  {hasAlerts && (
                    <div style={{ display:'flex', alignItems:'center', gap:'6px', background:'#fef2f2', border:'1px solid #fecaca', borderRadius:'8px', padding:'8px 14px' }}>
                      <span style={{ fontSize:'14px' }}>🚨</span>
                      <span style={{ fontSize:'12px', color:'#ef4444', fontWeight:'700' }}>Severe Allergy on Record</span>
                    </div>
                  )}
                </div>

                {/* ── Tab bar ── */}
                <div style={{ display:'flex', gap:'4px', overflowX:'auto', flexShrink:0, paddingBottom:'2px', marginBottom:'16px', scrollbarWidth:'none' }}>
                  {TABS.map(t => (
                    <button key={t.id} onClick={() => setMedTab(t.id)}
                      style={{ padding:'8px 14px', borderRadius:'50px', border:'none', cursor:'pointer', fontSize:'12px', fontWeight:'600', whiteSpace:'nowrap', transition:'all 0.2s',
                        background: medTab===t.id ? '#6C5CE7' : '#F1F5F9',
                        color:      medTab===t.id ? '#fff'    : '#64748B',
                        boxShadow:  medTab===t.id ? '0 4px 12px rgba(108,92,231,0.3)' : 'none' }}>
                      {t.icon} {t.label}
                    </button>
                  ))}
                </div>

                <div style={{ flex:1, overflowY:'auto', display:'flex', flexDirection:'column', gap:'16px', minHeight:0 }}>

                  {/* ════════ OVERVIEW TAB ════════ */}
                  {medTab === 'overview' && (
                    <div style={{ display:'flex', flexDirection:'column', gap:'14px' }}>
                      {/* Alert bar */}
                      {hasAlerts && (
                        <div style={{ background:'#fef2f2', border:'1px solid #fecaca', borderRadius:'12px', padding:'14px 18px', display:'flex', alignItems:'flex-start', gap:'10px' }}>
                          <span style={{ fontSize:'18px', flexShrink:0 }}>🚨</span>
                          <div>
                            <div style={{ fontSize:'13px', fontWeight:'700', color:'#ef4444', marginBottom:'4px' }}>Critical Allergy Alert</div>
                            <div style={{ fontSize:'12px', color:'#ef4444' }}>
                              {allergies.filter(a=>a.severity==='severe'||a.severity==='life-threatening').map(a=>`${a.allergen} (${a.reaction})`).join(' · ')}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Quick-stats grid */}
                      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(150px,1fr))', gap:'12px' }}>
                        {[
                          { icon:'🩸', label:'Blood Group', value: vitals.blood_group || '—', color:'#ef4444' },
                          { icon:'📏', label:'Height / Weight', value: vitals.height && vitals.weight ? `${vitals.height}cm · ${vitals.weight}kg` : '—', color:'#3b82f6' },
                          { icon:'⚖️', label:'BMI', value: vitals.bmi || '—', color: parseFloat(vitals.bmi)>=25?'#f97316':'#22c55e' },
                          { icon:'💓', label:'Blood Pressure', value: vitals.blood_pressure || '—', color:'#8b5cf6' },
                          { icon:'🔵', label:'SpO₂', value: vitals.spo2 ? `${vitals.spo2}%` : '—', color:'#06b6d4' },
                          { icon:'🩺', label:'Active Conditions', value: activeConditions.length || '0', color:'#f97316' },
                          { icon:'💊', label:'Current Meds', value: currentMeds.length || '0', color:'#6C5CE7' },
                          { icon:'⚠️', label:'Known Allergies', value: allergies.length || '0', color: hasAlerts?'#ef4444':'#64748B' },
                        ].map(k => (
                          <div key={k.label} style={{ ...S.card, textAlign:'center', padding:'16px 12px' }}>
                            <div style={{ fontSize:'20px', marginBottom:'6px' }}>{k.icon}</div>
                            <div style={{ fontSize:'18px', fontWeight:'800', color:k.color, letterSpacing:'-0.5px' }}>{k.value}</div>
                            <div style={{ fontSize:'11px', color:'#94a3b8', marginTop:'3px', fontWeight:'500' }}>{k.label}</div>
                          </div>
                        ))}
                      </div>

                      {/* Active conditions + current meds side by side */}
                      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'14px' }}>
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>🩺 Active Conditions</div>
                          {activeConditions.length === 0 ? <p style={{ color:'#94a3b8', fontSize:'12px', margin:0 }}>None recorded</p> : activeConditions.map(c=>(
                            <div key={c.id} style={{ display:'flex', alignItems:'center', gap:'8px', padding:'6px 0', borderBottom:'1px solid #f1f5f9' }}>
                              <span style={{ width:'8px', height:'8px', borderRadius:'50%', background:statusColor[c.status]||'#6C5CE7', flexShrink:0, display:'inline-block' }}></span>
                              <span style={{ fontSize:'12px', fontWeight:'600', color:'#1e293b', flex:1 }}>{c.condition}</span>
                              {c.icd_code && <span style={{ fontSize:'10px', color:'#94a3b8', background:'#f1f5f9', padding:'2px 6px', borderRadius:'4px' }}>{c.icd_code}</span>}
                            </div>
                          ))}
                        </div>
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>💊 Current Medications</div>
                          {currentMeds.length === 0 ? <p style={{ color:'#94a3b8', fontSize:'12px', margin:0 }}>None recorded</p> : currentMeds.map(m=>(
                            <div key={m.id} style={{ padding:'6px 0', borderBottom:'1px solid #f1f5f9' }}>
                              <div style={{ fontSize:'12px', fontWeight:'700', color:'#1e293b' }}>{m.name}</div>
                              <div style={{ fontSize:'11px', color:'#64748B' }}>{m.dosage} · {m.frequency}</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Allergies + Surgeries summary */}
                      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'14px' }}>
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>⚠️ Allergies</div>
                          {allergies.length === 0 ? <p style={{ color:'#94a3b8', fontSize:'12px', margin:0 }}>NKDA (No known drug allergies)</p> : allergies.map(a=>(
                            <div key={a.id} style={{ display:'flex', alignItems:'center', gap:'8px', padding:'5px 0', borderBottom:'1px solid #f1f5f9' }}>
                              <span style={{ fontSize:'11px', fontWeight:'700', padding:'2px 8px', borderRadius:'50px', background: a.severity==='severe'||a.severity==='life-threatening'?'#fef2f2':'#fff7ed', color:allergyColor[a.severity]||'#f97316' }}>{a.severity}</span>
                              <span style={{ fontSize:'12px', fontWeight:'600', color:'#1e293b' }}>{a.allergen}</span>
                              <span style={{ fontSize:'11px', color:'#94a3b8', marginLeft:'auto' }}>{a.reaction}</span>
                            </div>
                          ))}
                        </div>
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>🔪 Surgical History</div>
                          {surgeries.length === 0 ? <p style={{ color:'#94a3b8', fontSize:'12px', margin:0 }}>No surgeries recorded</p> : surgeries.map(s=>(
                            <div key={s.id} style={{ padding:'5px 0', borderBottom:'1px solid #f1f5f9' }}>
                              <div style={{ fontSize:'12px', fontWeight:'700', color:'#1e293b' }}>{s.procedure}</div>
                              <div style={{ fontSize:'11px', color:'#64748B' }}>{s.date ? new Date(s.date).toLocaleDateString('en-IN',{month:'short',year:'numeric'}) : ''}{s.hospital ? ` · ${s.hospital}` : ''}</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Lifestyle snapshot */}
                      {(lifestyle.smoking !== 'never' || lifestyle.alcohol !== 'never' || lifestyle.exercise) && (
                        <div style={S.card}>
                          <div style={{ fontSize:'13px', fontWeight:'700', color:'#0f172a', marginBottom:'10px' }}>🌿 Lifestyle Snapshot</div>
                          <div style={{ display:'flex', flexWrap:'wrap', gap:'8px' }}>
                            {lifestyle.smoking !== 'never' && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#fef3c7', color:'#d97706', fontSize:'12px', fontWeight:'600' }}>🚬 Smoker ({lifestyle.smoking})</span>}
                            {lifestyle.alcohol !== 'never' && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#fef3c7', color:'#d97706', fontSize:'12px', fontWeight:'600' }}>🍺 Alcohol ({lifestyle.alcohol})</span>}
                            {lifestyle.exercise && lifestyle.exercise !== 'sedentary' && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#f0fdf4', color:'#16a34a', fontSize:'12px', fontWeight:'600' }}>🏃 {lifestyle.exercise} activity</span>}
                            {lifestyle.diet && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#eff6ff', color:'#2563eb', fontSize:'12px', fontWeight:'600' }}>🥗 {lifestyle.diet} diet</span>}
                            {lifestyle.occupation && <span style={{ padding:'5px 12px', borderRadius:'50px', background:'#f1f5f9', color:'#475569', fontSize:'12px', fontWeight:'600' }}>💼 {lifestyle.occupation}</span>}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ════════ VITALS TAB ════════ */}
                  {medTab === 'vitals' && (
                    <div style={{ display:'flex', flexDirection:'column', gap:'14px' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                        <span style={{ fontSize:'14px', fontWeight:'700', color:'#0f172a' }}>Physical Measurements & Vitals</span>
                        <button style={S.addBtn} onClick={() => { setVitalsForm(vitals); setEditingVitals(true); }}>✏️ Edit Vitals</button>
                      </div>
                      {editingVitals ? (
                        <div style={S.card}>
                          <form onSubmit={e => { e.preventDefault(); const bmi = bmiCalc(vitalsForm.height, vitalsForm.weight); const v = {...vitalsForm, bmi}; saveVitals(v); setEditingVitals(false); }}>
                            <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:'14px 20px' }}>
                              {[
                                { label:'Height (cm)',           name:'height',               type:'number', placeholder:'e.g. 170' },
                                { label:'Weight (kg)',           name:'weight',               type:'number', placeholder:'e.g. 68' },
                                { label:'Blood Group',           name:'blood_group',           type:'select', options:['A+','A-','B+','B-','AB+','AB-','O+','O-'] },
                                { label:'Blood Pressure',        name:'blood_pressure',        type:'text',   placeholder:'e.g. 120/80' },
                                { label:'Heart Rate (bpm)',      name:'heart_rate',            type:'number', placeholder:'e.g. 72' },
                                { label:'SpO₂ (%)',              name:'spo2',                  type:'number', placeholder:'e.g. 98' },
                                { label:'Fasting Blood Sugar',   name:'blood_sugar_fasting',   type:'text',   placeholder:'e.g. 95 mg/dL' },
                                { label:'Post-Prandial Sugar',   name:'blood_sugar_pp',        type:'text',   placeholder:'e.g. 130 mg/dL' },
                                { label:'Temperature (°F)',      name:'temperature',           type:'number', placeholder:'e.g. 98.6' },
                              ].map(f => (
                                <FG key={f.name} label={f.label}>
                                  {f.type === 'select'
                                    ? <select style={S.select} value={vitalsForm[f.name]||''} onChange={e=>setVitalsForm(p=>({...p,[f.name]:e.target.value}))}>
                                        <option value="">— Select —</option>
                                        {f.options.map(o=><option key={o} value={o}>{o}</option>)}
                                      </select>
                                    : <input type={f.type} style={S.input} placeholder={f.placeholder} value={vitalsForm[f.name]||''} onChange={e=>setVitalsForm(p=>({...p,[f.name]:e.target.value}))} />
                                  }
                                </FG>
                              ))}
                              <div style={{ gridColumn:'span 3', display:'flex', gap:'10px', justifyContent:'flex-end', borderTop:'1px solid #f1f5f9', paddingTop:'14px', marginTop:'4px' }}>
                                <button type="button" style={S.cancelBtn} onClick={()=>setEditingVitals(false)}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save Vitals</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      ) : (
                        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(180px,1fr))', gap:'12px' }}>
                          {[
                            { icon:'📏', label:'Height', value: vitals.height ? `${vitals.height} cm` : '—' },
                            { icon:'⚖️', label:'Weight', value: vitals.weight ? `${vitals.weight} kg` : '—' },
                            { icon:'🧮', label:'BMI', value: vitals.bmi || (vitals.height&&vitals.weight ? bmiCalc(vitals.height,vitals.weight) : '—'), note: parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=30?'Obese':parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=25?'Overweight':parseFloat(vitals.bmi||bmiCalc(vitals.height,vitals.weight))>=18.5?'Normal':vitals.height?'Underweight':'' },
                            { icon:'🩸', label:'Blood Group', value: vitals.blood_group || '—' },
                            { icon:'💓', label:'Blood Pressure', value: vitals.blood_pressure || '—' },
                            { icon:'❤️', label:'Heart Rate', value: vitals.heart_rate ? `${vitals.heart_rate} bpm` : '—' },
                            { icon:'🔵', label:'SpO₂', value: vitals.spo2 ? `${vitals.spo2}%` : '—' },
                            { icon:'🌡️', label:'Temperature', value: vitals.temperature ? `${vitals.temperature}°F` : '—' },
                            { icon:'🍬', label:'Sugar (Fasting)', value: vitals.blood_sugar_fasting || '—' },
                            { icon:'🍬', label:'Sugar (PP)', value: vitals.blood_sugar_pp || '—' },
                          ].map(v => (
                            <div key={v.label} style={{ ...S.card, padding:'16px', textAlign:'center' }}>
                              <div style={{ fontSize:'22px', marginBottom:'6px' }}>{v.icon}</div>
                              <div style={{ fontSize:'17px', fontWeight:'800', color:'#0f172a', letterSpacing:'-0.3px' }}>{v.value}</div>
                              {v.note && <div style={{ fontSize:'10px', fontWeight:'700', color:'#f97316', marginTop:'2px' }}>{v.note}</div>}
                              <div style={{ fontSize:'11px', color:'#94a3b8', marginTop:'3px' }}>{v.label}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ════════ CONDITIONS TAB ════════ */}
                  {medTab === 'conditions' && (
                    <div style={{ display:'flex', flexDirection:'column', gap:'12px' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                        <div style={{ display:'flex', gap:'6px', flexWrap:'wrap' }}>
                          {['all','active','chronic','resolved','monitoring'].map(f=>(
                            <button key={f} onClick={()=>setCondFilter(f)} style={{ padding:'5px 12px', borderRadius:'50px', border:'none', cursor:'pointer', fontSize:'11px', fontWeight:'600', background:condFilter===f?'#6C5CE7':'#F1F5F9', color:condFilter===f?'#fff':'#64748B' }}>{f.charAt(0).toUpperCase()+f.slice(1)}</button>
                          ))}
                        </div>
                        <button style={S.addBtn} onClick={()=>{setShowCondForm(true);setEditCondId(null);setCondForm({condition:'',icd_code:'',diagnosed_date:'',doctor_name:'',hospital:'',status:'active',severity:'moderate',is_hereditary:false,notes:''});}}>+ Add</button>
                      </div>
                      {showCondForm && (
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editCondId?'Edit Condition':'New Condition'}</h4>
                          <form onSubmit={submitCondition}>
                            <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:'12px 18px' }}>
                              <FG label="Condition / Diagnosis *"><input required style={S.input} placeholder="e.g. Type 2 Diabetes Mellitus" value={condForm.condition} onChange={e=>setCondForm(p=>({...p,condition:e.target.value}))} /></FG>
                              <FG label="ICD-10 Code"><input style={S.input} placeholder="e.g. E11.9" value={condForm.icd_code} onChange={e=>setCondForm(p=>({...p,icd_code:e.target.value}))} /></FG>
                              <FG label="Date Diagnosed"><input type="date" style={S.input} value={condForm.diagnosed_date} onChange={e=>setCondForm(p=>({...p,diagnosed_date:e.target.value}))} /></FG>
                              <FG label="Treating Doctor"><input style={S.input} placeholder="Dr. Full Name" value={condForm.doctor_name} onChange={e=>setCondForm(p=>({...p,doctor_name:e.target.value}))} /></FG>
                              <FG label="Hospital / Clinic"><input style={S.input} placeholder="Hospital name" value={condForm.hospital} onChange={e=>setCondForm(p=>({...p,hospital:e.target.value}))} /></FG>
                              <FG label="Status"><select style={S.select} value={condForm.status} onChange={e=>setCondForm(p=>({...p,status:e.target.value}))}><option value="active">Active</option><option value="chronic">Chronic</option><option value="resolved">Resolved</option><option value="monitoring">Monitoring</option></select></FG>
                              <FG label="Severity"><select style={S.select} value={condForm.severity} onChange={e=>setCondForm(p=>({...p,severity:e.target.value}))}><option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option><option value="critical">Critical</option></select></FG>
                              <FG label="Hereditary?"><select style={S.select} value={condForm.is_hereditary} onChange={e=>setCondForm(p=>({...p,is_hereditary:e.target.value==='true'}))}><option value="false">No</option><option value="true">Yes</option></select></FG>
                              <div style={{gridColumn:'span 2'}}><FG label="Notes / Details"><input style={S.input} placeholder="Additional clinical notes" value={condForm.notes} onChange={e=>setCondForm(p=>({...p,notes:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowCondForm(false);setEditCondId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {(condFilter==='all'?conditions:conditions.filter(c=>c.status===condFilter)).length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>🩺</div>No conditions recorded.</div>
                        : (condFilter==='all'?conditions:conditions.filter(c=>c.status===condFilter)).map(c=>(
                          <div key={c.id} style={{...S.card,borderLeft:`4px solid ${statusColor[c.status]||'#6C5CE7'}`}}>
                            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                              <div style={{flex:1}}>
                                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px',flexWrap:'wrap'}}>
                                  <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{c.condition}</span>
                                  {c.icd_code&&<span style={{fontSize:'10px',background:'#f1f5f9',color:'#64748B',padding:'2px 8px',borderRadius:'4px',fontWeight:'600'}}>{c.icd_code}</span>}
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:statusBg[c.status]||'#f1f5f9',color:statusColor[c.status]||'#6C5CE7',textTransform:'uppercase'}}>{c.status}</span>
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:'#f8fafc',color:severityColor[c.severity]||'#64748B',textTransform:'uppercase'}}>{c.severity}</span>
                                  {c.is_hereditary&&<span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:'#fdf4ff',color:'#9333ea'}}>Hereditary</span>}
                                </div>
                                <div style={{display:'flex',flexWrap:'wrap',gap:'12px'}}>
                                  {c.diagnosed_date&&<span style={{fontSize:'12px',color:'#64748B'}}>📅 {new Date(c.diagnosed_date).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span>}
                                  {c.doctor_name&&<span style={{fontSize:'12px',color:'#64748B'}}>👨‍⚕️ Dr. {c.doctor_name}</span>}
                                  {c.hospital&&<span style={{fontSize:'12px',color:'#64748B'}}>🏥 {c.hospital}</span>}
                                </div>
                                {c.notes&&<p style={{margin:'6px 0 0',fontSize:'12px',color:'#94a3b8',fontStyle:'italic'}}>{c.notes}</p>}
                              </div>
                              <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                <button style={S.editBtn} onClick={()=>{setCondForm({...c});setEditCondId(c.id);setShowCondForm(true);}}>Edit</button>
                                <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveConditions(conditions.filter(x=>x.id!==c.id));}}>✕</button>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {/* ════════ MEDICATIONS TAB ════════ */}
                  {medTab === 'medications' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <span style={{fontSize:'13px',color:'#64748B'}}>{currentMeds.length} active · {medications.filter(m=>!m.is_ongoing).length} past</span>
                        <button style={S.addBtn} onClick={()=>{setShowMedForm(true);setEditMedId(null);setMedForm({name:'',dosage:'',frequency:'',route:'oral',prescribed_by:'',prescribed_date:'',start_date:'',end_date:'',reason:'',is_ongoing:true,side_effects:'',notes:''});}}>+ Add</button>
                      </div>
                      {showMedForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editMedId?'Edit Medication':'New Medication'}</h4>
                          <form onSubmit={submitMedication}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Drug Name *"><input required style={S.input} placeholder="e.g. Metformin" value={medForm.name} onChange={e=>setMedForm(p=>({...p,name:e.target.value}))} /></FG>
                              <FG label="Dosage"><input style={S.input} placeholder="e.g. 500mg" value={medForm.dosage} onChange={e=>setMedForm(p=>({...p,dosage:e.target.value}))} /></FG>
                              <FG label="Frequency"><input style={S.input} placeholder="e.g. Twice daily after meals" value={medForm.frequency} onChange={e=>setMedForm(p=>({...p,frequency:e.target.value}))} /></FG>
                              <FG label="Route"><select style={S.select} value={medForm.route} onChange={e=>setMedForm(p=>({...p,route:e.target.value}))}>
                                {['oral','intravenous','intramuscular','topical','sublingual','inhalation','subcutaneous','other'].map(r=><option key={r} value={r}>{r.charAt(0).toUpperCase()+r.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Prescribed By"><input style={S.input} placeholder="Dr. Name" value={medForm.prescribed_by} onChange={e=>setMedForm(p=>({...p,prescribed_by:e.target.value}))} /></FG>
                              <FG label="Reason / Indication"><input style={S.input} placeholder="e.g. Type 2 Diabetes" value={medForm.reason} onChange={e=>setMedForm(p=>({...p,reason:e.target.value}))} /></FG>
                              <FG label="Start Date"><input type="date" style={S.input} value={medForm.start_date} onChange={e=>setMedForm(p=>({...p,start_date:e.target.value}))} /></FG>
                              <FG label="End Date"><input type="date" style={S.input} value={medForm.end_date} onChange={e=>setMedForm(p=>({...p,end_date:e.target.value}))} /></FG>
                              <FG label="Known Side Effects"><input style={S.input} placeholder="e.g. Nausea, dizziness" value={medForm.side_effects} onChange={e=>setMedForm(p=>({...p,side_effects:e.target.value}))} /></FG>
                              <FG label="Ongoing?"><select style={S.select} value={medForm.is_ongoing} onChange={e=>setMedForm(p=>({...p,is_ongoing:e.target.value==='true'}))}>
                                <option value="true">Yes (current)</option><option value="false">No (stopped)</option>
                              </select></FG>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowMedForm(false);setEditMedId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {medications.length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>💊</div>No medications logged.</div>
                        : medications.map(m=>(
                          <div key={m.id} style={{...S.card,borderLeft:`4px solid ${m.is_ongoing?'#6C5CE7':'#94a3b8'}`}}>
                            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                              <div style={{flex:1}}>
                                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px',flexWrap:'wrap'}}>
                                  <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{m.name}</span>
                                  {m.dosage&&<span style={{fontSize:'12px',color:'#6C5CE7',fontWeight:'600',background:'#EDE9FE',padding:'2px 8px',borderRadius:'4px'}}>{m.dosage}</span>}
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:m.is_ongoing?'#f0fdf4':'#f1f5f9',color:m.is_ongoing?'#16a34a':'#94a3b8',textTransform:'uppercase'}}>{m.is_ongoing?'Current':'Stopped'}</span>
                                  {m.route&&<span style={{fontSize:'10px',color:'#64748B',background:'#f8fafc',padding:'2px 8px',borderRadius:'4px',textTransform:'capitalize'}}>{m.route}</span>}
                                </div>
                                <div style={{display:'flex',flexWrap:'wrap',gap:'10px'}}>
                                  {m.frequency&&<span style={{fontSize:'12px',color:'#64748B'}}>🕐 {m.frequency}</span>}
                                  {m.reason&&<span style={{fontSize:'12px',color:'#64748B'}}>📋 For: {m.reason}</span>}
                                  {m.prescribed_by&&<span style={{fontSize:'12px',color:'#64748B'}}>👨‍⚕️ Dr. {m.prescribed_by}</span>}
                                  {m.start_date&&<span style={{fontSize:'12px',color:'#64748B'}}>📅 Since {new Date(m.start_date).toLocaleDateString('en-IN',{month:'short',year:'numeric'})}</span>}
                                </div>
                                {m.side_effects&&<p style={{margin:'5px 0 0',fontSize:'12px',color:'#f97316'}}>⚠️ Side effects: {m.side_effects}</p>}
                              </div>
                              <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                <button style={S.editBtn} onClick={()=>{setMedForm({...m});setEditMedId(m.id);setShowMedForm(true);}}>Edit</button>
                                <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveMedications(medications.filter(x=>x.id!==m.id));}}>✕</button>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {/* ════════ ALLERGIES TAB ════════ */}
                  {medTab === 'allergies' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <span style={{fontSize:'13px',color: hasAlerts?'#ef4444':'#64748B',fontWeight: hasAlerts?'700':'400'}}>{hasAlerts?'⚠️ Severe allergy on record':'All allergies'}</span>
                        <button style={S.addBtn} onClick={()=>{setShowAllergyForm(true);setEditAllergyId(null);setAllergyForm({allergen:'',type:'drug',reaction:'',severity:'moderate',onset_date:'',notes:''});}}>+ Add</button>
                      </div>
                      {showAllergyForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editAllergyId?'Edit Allergy':'New Allergy'}</h4>
                          <form onSubmit={submitAllergy}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Allergen *"><input required style={S.input} placeholder="e.g. Penicillin / Peanuts / Dust" value={allergyForm.allergen} onChange={e=>setAllergyForm(p=>({...p,allergen:e.target.value}))} /></FG>
                              <FG label="Type"><select style={S.select} value={allergyForm.type} onChange={e=>setAllergyForm(p=>({...p,type:e.target.value}))}>
                                {['drug','food','environmental','insect','latex','chemical','other'].map(t=><option key={t} value={t}>{t.charAt(0).toUpperCase()+t.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Reaction / Symptoms"><input style={S.input} placeholder="e.g. Anaphylaxis, Hives, Swelling" value={allergyForm.reaction} onChange={e=>setAllergyForm(p=>({...p,reaction:e.target.value}))} /></FG>
                              <FG label="Severity"><select style={S.select} value={allergyForm.severity} onChange={e=>setAllergyForm(p=>({...p,severity:e.target.value}))}>
                                <option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option><option value="life-threatening">Life-threatening / Anaphylaxis</option>
                              </select></FG>
                              <FG label="First Onset Date"><input type="date" style={S.input} value={allergyForm.onset_date} onChange={e=>setAllergyForm(p=>({...p,onset_date:e.target.value}))} /></FG>
                              <FG label="Notes"><input style={S.input} placeholder="e.g. Carry EpiPen" value={allergyForm.notes} onChange={e=>setAllergyForm(p=>({...p,notes:e.target.value}))} /></FG>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowAllergyForm(false);setEditAllergyId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {allergies.length===0
                        ? <div style={{...S.card,textAlign:'center',padding:'32px',color:'#22c55e',fontWeight:'700',fontSize:'14px'}}>✅ NKDA — No Known Drug Allergies</div>
                        : allergies.map(a=>(
                          <div key={a.id} style={{...S.card,borderLeft:`4px solid ${allergyColor[a.severity]||'#f97316'}`}}>
                            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                              <div style={{flex:1}}>
                                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px',flexWrap:'wrap'}}>
                                  <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{a.allergen}</span>
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background: a.severity==='life-threatening'?'#fdf4ff':a.severity==='severe'?'#fef2f2':'#fff7ed',color:allergyColor[a.severity]||'#f97316',textTransform:'uppercase'}}>{a.severity}</span>
                                  <span style={{fontSize:'10px',color:'#64748B',background:'#f1f5f9',padding:'2px 8px',borderRadius:'4px',textTransform:'capitalize'}}>{a.type}</span>
                                </div>
                                <div style={{display:'flex',flexWrap:'wrap',gap:'10px'}}>
                                  {a.reaction&&<span style={{fontSize:'12px',color:'#64748B'}}>🤒 Reaction: {a.reaction}</span>}
                                  {a.onset_date&&<span style={{fontSize:'12px',color:'#64748B'}}>📅 Since {new Date(a.onset_date).toLocaleDateString('en-IN',{month:'short',year:'numeric'})}</span>}
                                </div>
                                {a.notes&&<p style={{margin:'5px 0 0',fontSize:'12px',color:'#94a3b8',fontStyle:'italic'}}>{a.notes}</p>}
                              </div>
                              <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                <button style={S.editBtn} onClick={()=>{setAllergyForm({...a});setEditAllergyId(a.id);setShowAllergyForm(true);}}>Edit</button>
                                <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveAllergies(allergies.filter(x=>x.id!==a.id));}}>✕</button>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {/* ════════ SURGERIES TAB ════════ */}
                  {medTab === 'surgeries' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',justifyContent:'flex-end'}}>
                        <button style={S.addBtn} onClick={()=>{setShowSurgForm(true);setEditSurgId(null);setSurgForm({procedure:'',date:'',surgeon:'',hospital:'',anesthesia:'general',outcome:'successful',complications:'',notes:''});}}>+ Add</button>
                      </div>
                      {showSurgForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editSurgId?'Edit Surgery':'New Surgical Record'}</h4>
                          <form onSubmit={submitSurgery}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Procedure / Surgery *"><input required style={S.input} placeholder="e.g. Appendectomy" value={surgForm.procedure} onChange={e=>setSurgForm(p=>({...p,procedure:e.target.value}))} /></FG>
                              <FG label="Date"><input type="date" style={S.input} value={surgForm.date} onChange={e=>setSurgForm(p=>({...p,date:e.target.value}))} /></FG>
                              <FG label="Surgeon"><input style={S.input} placeholder="Dr. Name" value={surgForm.surgeon} onChange={e=>setSurgForm(p=>({...p,surgeon:e.target.value}))} /></FG>
                              <FG label="Hospital"><input style={S.input} placeholder="Hospital name" value={surgForm.hospital} onChange={e=>setSurgForm(p=>({...p,hospital:e.target.value}))} /></FG>
                              <FG label="Anaesthesia"><select style={S.select} value={surgForm.anesthesia} onChange={e=>setSurgForm(p=>({...p,anesthesia:e.target.value}))}>
                                {['general','local','regional','spinal','epidural','sedation','none'].map(a=><option key={a} value={a}>{a.charAt(0).toUpperCase()+a.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Outcome"><select style={S.select} value={surgForm.outcome} onChange={e=>setSurgForm(p=>({...p,outcome:e.target.value}))}>
                                {['successful','complicated','ongoing','unknown'].map(o=><option key={o} value={o}>{o.charAt(0).toUpperCase()+o.slice(1)}</option>)}
                              </select></FG>
                              <div style={{gridColumn:'span 2'}}><FG label="Complications (if any)"><input style={S.input} placeholder="e.g. Post-op infection, bleeding" value={surgForm.complications} onChange={e=>setSurgForm(p=>({...p,complications:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2'}}><FG label="Notes"><input style={S.input} value={surgForm.notes} onChange={e=>setSurgForm(p=>({...p,notes:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowSurgForm(false);setEditSurgId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {surgeries.length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>🔪</div>No surgeries recorded.</div>
                        : surgeries.map(s=>(
                          <div key={s.id} style={{...S.card,borderLeft:`4px solid ${s.outcome==='successful'?'#22c55e':s.outcome==='complicated'?'#ef4444':'#94a3b8'}`}}>
                            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                              <div style={{flex:1}}>
                                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px',flexWrap:'wrap'}}>
                                  <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{s.procedure}</span>
                                  <span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:s.outcome==='successful'?'#f0fdf4':'#fef2f2',color:s.outcome==='successful'?'#16a34a':'#ef4444',textTransform:'capitalize'}}>{s.outcome}</span>
                                  <span style={{fontSize:'10px',color:'#64748B',background:'#f1f5f9',padding:'2px 8px',borderRadius:'4px',textTransform:'capitalize'}}>{s.anesthesia} anaesthesia</span>
                                </div>
                                <div style={{display:'flex',flexWrap:'wrap',gap:'10px'}}>
                                  {s.date&&<span style={{fontSize:'12px',color:'#64748B'}}>📅 {new Date(s.date).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span>}
                                  {s.surgeon&&<span style={{fontSize:'12px',color:'#64748B'}}>👨‍⚕️ Dr. {s.surgeon}</span>}
                                  {s.hospital&&<span style={{fontSize:'12px',color:'#64748B'}}>🏥 {s.hospital}</span>}
                                </div>
                                {s.complications&&<p style={{margin:'5px 0 0',fontSize:'12px',color:'#ef4444'}}>⚠️ Complications: {s.complications}</p>}
                                {s.notes&&<p style={{margin:'3px 0 0',fontSize:'12px',color:'#94a3b8',fontStyle:'italic'}}>{s.notes}</p>}
                              </div>
                              <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                <button style={S.editBtn} onClick={()=>{setSurgForm({...s});setEditSurgId(s.id);setShowSurgForm(true);}}>Edit</button>
                                <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveSurgeries(surgeries.filter(x=>x.id!==s.id));}}>✕</button>
                              </div>
                            </div>
                          </div>
                        ))
                      }
                    </div>
                  )}

                  {/* ════════ FAMILY HISTORY TAB ════════ */}
                  {medTab === 'family' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                        <p style={{margin:0,fontSize:'12px',color:'#94a3b8'}}>Hereditary conditions inform risk assessment for the patient and their doctor.</p>
                        <button style={S.addBtn} onClick={()=>{setShowFamForm(true);setEditFamId(null);setFamForm({relation:'',condition:'',age_of_onset:'',deceased:false,notes:''});}}>+ Add</button>
                      </div>
                      {showFamForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editFamId?'Edit Entry':'Family History Entry'}</h4>
                          <form onSubmit={submitFamily}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Relation *"><select required style={S.select} value={famForm.relation} onChange={e=>setFamForm(p=>({...p,relation:e.target.value}))}>
                                <option value="">— Select —</option>
                                {['Father','Mother','Paternal Grandfather','Paternal Grandmother','Maternal Grandfather','Maternal Grandmother','Brother','Sister','Son','Daughter','Uncle','Aunt'].map(r=><option key={r} value={r}>{r}</option>)}
                              </select></FG>
                              <FG label="Condition *"><input required style={S.input} placeholder="e.g. Hypertension, Diabetes" value={famForm.condition} onChange={e=>setFamForm(p=>({...p,condition:e.target.value}))} /></FG>
                              <FG label="Age of Onset"><input type="number" style={S.input} placeholder="Age in years" value={famForm.age_of_onset} onChange={e=>setFamForm(p=>({...p,age_of_onset:e.target.value}))} /></FG>
                              <FG label="Status"><select style={S.select} value={famForm.deceased} onChange={e=>setFamForm(p=>({...p,deceased:e.target.value==='true'}))}>
                                <option value="false">Alive</option><option value="true">Deceased</option>
                              </select></FG>
                              <div style={{gridColumn:'span 2'}}><FG label="Notes"><input style={S.input} placeholder="Any relevant detail" value={famForm.notes} onChange={e=>setFamForm(p=>({...p,notes:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowFamForm(false);setEditFamId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {familyHistory.length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>👨‍👩‍👧</div>No family history recorded.</div>
                        : (
                          <div style={{overflowX:'auto'}}>
                            <table style={{width:'100%',borderCollapse:'collapse',fontSize:'13px',background:'#fff',borderRadius:'14px',overflow:'hidden'}}>
                              <thead><tr style={{background:'#f8fafc'}}>
                                {['Relation','Condition','Age of Onset','Status','Notes',''].map(h=><th key={h} style={{padding:'10px 14px',textAlign:'left',fontSize:'11px',fontWeight:'700',color:'#64748B',letterSpacing:'0.5px',textTransform:'uppercase',borderBottom:'1px solid #E2E8F0'}}>{h}</th>)}
                              </tr></thead>
                              <tbody>
                                {familyHistory.map(f=>(
                                  <tr key={f.id} style={{borderBottom:'1px solid #f1f5f9'}}>
                                    <td style={{padding:'10px 14px',fontWeight:'600',color:'#1e293b'}}>{f.relation}</td>
                                    <td style={{padding:'10px 14px',color:'#334155'}}>{f.condition}</td>
                                    <td style={{padding:'10px 14px',color:'#64748B'}}>{f.age_of_onset ? `~${f.age_of_onset} yrs` : '—'}</td>
                                    <td style={{padding:'10px 14px'}}><span style={{padding:'3px 8px',borderRadius:'50px',fontSize:'10px',fontWeight:'700',background:f.deceased?'#fef2f2':'#f0fdf4',color:f.deceased?'#ef4444':'#16a34a'}}>{f.deceased?'Deceased':'Alive'}</span></td>
                                    <td style={{padding:'10px 14px',color:'#94a3b8',fontSize:'12px',fontStyle:'italic'}}>{f.notes||'—'}</td>
                                    <td style={{padding:'10px 14px'}}>
                                      <div style={{display:'flex',gap:'4px'}}>
                                        <button style={S.editBtn} onClick={()=>{setFamForm({...f});setEditFamId(f.id);setShowFamForm(true);}}>Edit</button>
                                        <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveFamilyHistory(familyHistory.filter(x=>x.id!==f.id));}}>✕</button>
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )
                      }
                    </div>
                  )}

                  {/* ════════ IMMUNIZATIONS TAB ════════ */}
                  {medTab === 'immunizations' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'12px'}}>
                      <div style={{display:'flex',justifyContent:'flex-end'}}>
                        <button style={S.addBtn} onClick={()=>{setShowImmuForm(true);setEditImmuId(null);setImmuForm({vaccine:'',date_given:'',dose:'',administered_by:'',next_due:'',notes:''});}}>+ Add</button>
                      </div>
                      {showImmuForm&&(
                        <div style={S.card}>
                          <h4 style={{margin:'0 0 14px',fontSize:'14px',color:'#0f172a'}}>{editImmuId?'Edit Record':'Add Immunisation'}</h4>
                          <form onSubmit={submitImmunization}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'12px 18px'}}>
                              <FG label="Vaccine Name *"><input required style={S.input} placeholder="e.g. COVID-19 Booster / Flu / Hepatitis B" value={immuForm.vaccine} onChange={e=>setImmuForm(p=>({...p,vaccine:e.target.value}))} /></FG>
                              <FG label="Dose Number / Type"><input style={S.input} placeholder="e.g. Dose 2 / Booster" value={immuForm.dose} onChange={e=>setImmuForm(p=>({...p,dose:e.target.value}))} /></FG>
                              <FG label="Date Given"><input type="date" style={S.input} value={immuForm.date_given} onChange={e=>setImmuForm(p=>({...p,date_given:e.target.value}))} /></FG>
                              <FG label="Next Due Date"><input type="date" style={S.input} value={immuForm.next_due} onChange={e=>setImmuForm(p=>({...p,next_due:e.target.value}))} /></FG>
                              <FG label="Administered By"><input style={S.input} placeholder="Doctor / Clinic" value={immuForm.administered_by} onChange={e=>setImmuForm(p=>({...p,administered_by:e.target.value}))} /></FG>
                              <FG label="Notes"><input style={S.input} placeholder="Batch no., reactions, etc." value={immuForm.notes} onChange={e=>setImmuForm(p=>({...p,notes:e.target.value}))} /></FG>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>{setShowImmuForm(false);setEditImmuId(null);}}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      )}
                      {immunizations.length===0
                        ? <div style={{textAlign:'center',padding:'40px',color:'#94a3b8',background:'#fff',borderRadius:'14px',border:'2px dashed #E2E8F0'}}><div style={{fontSize:'32px',marginBottom:'8px'}}>💉</div>No immunisation records added.</div>
                        : immunizations.map(i=>{
                          const isDue = i.next_due && new Date(i.next_due) <= new Date();
                          return (
                            <div key={i.id} style={{...S.card,borderLeft:`4px solid ${isDue?'#ef4444':'#22c55e'}`}}>
                              <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px'}}>
                                <div style={{flex:1}}>
                                  <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'6px',flexWrap:'wrap'}}>
                                    <span style={{fontSize:'14px',fontWeight:'700',color:'#0f172a'}}>{i.vaccine}</span>
                                    {i.dose&&<span style={{fontSize:'11px',color:'#6C5CE7',background:'#EDE9FE',padding:'2px 8px',borderRadius:'4px',fontWeight:'600'}}>{i.dose}</span>}
                                    {isDue&&<span style={{fontSize:'10px',fontWeight:'700',padding:'2px 8px',borderRadius:'50px',background:'#fef2f2',color:'#ef4444'}}>⏰ Due / Overdue</span>}
                                  </div>
                                  <div style={{display:'flex',flexWrap:'wrap',gap:'10px'}}>
                                    {i.date_given&&<span style={{fontSize:'12px',color:'#64748B'}}>💉 Given: {new Date(i.date_given).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span>}
                                    {i.next_due&&<span style={{fontSize:'12px',color:isDue?'#ef4444':'#64748B'}}>🔔 Next due: {new Date(i.next_due).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span>}
                                    {i.administered_by&&<span style={{fontSize:'12px',color:'#64748B'}}>👨‍⚕️ {i.administered_by}</span>}
                                  </div>
                                  {i.notes&&<p style={{margin:'5px 0 0',fontSize:'12px',color:'#94a3b8',fontStyle:'italic'}}>{i.notes}</p>}
                                </div>
                                <div style={{display:'flex',gap:'5px',flexShrink:0}}>
                                  <button style={S.editBtn} onClick={()=>{setImmuForm({...i});setEditImmuId(i.id);setShowImmuForm(true);}}>Edit</button>
                                  <button style={S.delBtn} onClick={()=>{if(window.confirm('Delete?'))saveImmunizations(immunizations.filter(x=>x.id!==i.id));}}>✕</button>
                                </div>
                              </div>
                            </div>
                          );
                        })
                      }
                    </div>
                  )}

                  {/* ════════ LIFESTYLE TAB ════════ */}
                  {medTab === 'lifestyle' && (
                    <div style={{display:'flex',flexDirection:'column',gap:'14px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <span style={{fontSize:'13px',color:'#64748B'}}>Lifestyle factors are clinically relevant for diagnosis and treatment planning.</span>
                        <button style={S.addBtn} onClick={()=>{setLifestyleForm(lifestyle);setEditingLifestyle(true);}}>✏️ Edit</button>
                      </div>
                      {editingLifestyle ? (
                        <div style={S.card}>
                          <form onSubmit={e=>{e.preventDefault();saveLifestyle(lifestyleForm);setEditingLifestyle(false);}}>
                            <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:'14px 20px'}}>
                              <FG label="Smoking Status"><select style={S.select} value={lifestyleForm.smoking} onChange={e=>setLifestyleForm(p=>({...p,smoking:e.target.value}))}>
                                {['never','ex-smoker','occasional','current'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              {lifestyleForm.smoking!=='never'&&<>
                                <FG label="Packs/day"><input type="number" style={S.input} placeholder="e.g. 0.5" value={lifestyleForm.smoking_packs_per_day} onChange={e=>setLifestyleForm(p=>({...p,smoking_packs_per_day:e.target.value}))} /></FG>
                                <FG label="Years smoked"><input type="number" style={S.input} placeholder="e.g. 10" value={lifestyleForm.smoking_years} onChange={e=>setLifestyleForm(p=>({...p,smoking_years:e.target.value}))} /></FG>
                              </>}
                              <FG label="Alcohol Use"><select style={S.select} value={lifestyleForm.alcohol} onChange={e=>setLifestyleForm(p=>({...p,alcohol:e.target.value}))}>
                                {['never','social','occasional','moderate','heavy'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              {lifestyleForm.alcohol!=='never'&&<FG label="Units/week"><input type="number" style={S.input} placeholder="e.g. 7" value={lifestyleForm.alcohol_units_per_week} onChange={e=>setLifestyleForm(p=>({...p,alcohol_units_per_week:e.target.value}))} /></FG>}
                              <FG label="Tobacco Chewing"><select style={S.select} value={lifestyleForm.tobacco_chewing} onChange={e=>setLifestyleForm(p=>({...p,tobacco_chewing:e.target.value==='true'}))}>
                                <option value="false">No</option><option value="true">Yes</option>
                              </select></FG>
                              <FG label="Exercise Level"><select style={S.select} value={lifestyleForm.exercise} onChange={e=>setLifestyleForm(p=>({...p,exercise:e.target.value}))}>
                                {['sedentary','light','moderate','vigorous','athlete'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Exercise days/week"><input type="number" style={S.input} placeholder="0–7" min="0" max="7" value={lifestyleForm.exercise_days_per_week} onChange={e=>setLifestyleForm(p=>({...p,exercise_days_per_week:e.target.value}))} /></FG>
                              <FG label="Diet Type"><select style={S.select} value={lifestyleForm.diet} onChange={e=>setLifestyleForm(p=>({...p,diet:e.target.value}))}>
                                {['mixed','vegetarian','vegan','keto','diabetic','low-sodium','other'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Avg Sleep (hrs/night)"><input type="number" style={S.input} placeholder="e.g. 7" value={lifestyleForm.sleep_hours} onChange={e=>setLifestyleForm(p=>({...p,sleep_hours:e.target.value}))} /></FG>
                              <FG label="Occupation"><input style={S.input} placeholder="e.g. Software Engineer" value={lifestyleForm.occupation} onChange={e=>setLifestyleForm(p=>({...p,occupation:e.target.value}))} /></FG>
                              <FG label="Stress Level"><select style={S.select} value={lifestyleForm.stress_level} onChange={e=>setLifestyleForm(p=>({...p,stress_level:e.target.value}))}>
                                {['low','moderate','high','very high'].map(v=><option key={v} value={v}>{v.charAt(0).toUpperCase()+v.slice(1)}</option>)}
                              </select></FG>
                              <FG label="Recreational Drugs"><select style={S.select} value={lifestyleForm.recreational_drugs} onChange={e=>setLifestyleForm(p=>({...p,recreational_drugs:e.target.value==='true'}))}>
                                <option value="false">None</option><option value="true">Yes</option>
                              </select></FG>
                              <div style={{gridColumn:'span 2'}}><FG label="Additional Lifestyle Notes"><input style={S.input} placeholder="Diet restrictions, hobbies, or other relevant factors" value={lifestyleForm.notes} onChange={e=>setLifestyleForm(p=>({...p,notes:e.target.value}))} /></FG></div>
                              <div style={{gridColumn:'span 2',display:'flex',gap:'8px',justifyContent:'flex-end'}}>
                                <button type="button" style={S.cancelBtn} onClick={()=>setEditingLifestyle(false)}>Cancel</button>
                                <button type="submit" style={S.saveBtn}>Save Lifestyle</button>
                              </div>
                            </div>
                          </form>
                        </div>
                      ) : (
                        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:'12px' }}>
                          {[
                            { icon:'🚬', label:'Smoking', value: lifestyle.smoking, note: lifestyle.smoking_packs_per_day?`${lifestyle.smoking_packs_per_day} packs/day`:'', warn: lifestyle.smoking==='current' },
                            { icon:'🍺', label:'Alcohol', value: lifestyle.alcohol, note: lifestyle.alcohol_units_per_week?`${lifestyle.alcohol_units_per_week} units/wk`:'', warn: lifestyle.alcohol==='heavy' },
                            { icon:'🏃', label:'Exercise', value: lifestyle.exercise, note: lifestyle.exercise_days_per_week?`${lifestyle.exercise_days_per_week}×/wk`:'' },
                            { icon:'🥗', label:'Diet', value: lifestyle.diet || '—' },
                            { icon:'😴', label:'Sleep', value: lifestyle.sleep_hours?`${lifestyle.sleep_hours} hrs/night`:'—' },
                            { icon:'💼', label:'Occupation', value: lifestyle.occupation || '—' },
                            { icon:'🧠', label:'Stress Level', value: lifestyle.stress_level, warn: lifestyle.stress_level==='high'||lifestyle.stress_level==='very high' },
                            { icon:'🌿', label:'Tobacco Chewing', value: lifestyle.tobacco_chewing?'Yes':'No', warn: lifestyle.tobacco_chewing },
                          ].map(v=>(
                            <div key={v.label} style={{...S.card,padding:'16px'}}>
                              <div style={{fontSize:'20px',marginBottom:'6px'}}>{v.icon}</div>
                              <div style={{fontSize:'14px',fontWeight:'700',color:v.warn?'#ef4444':'#0f172a',textTransform:'capitalize'}}>{v.value||'—'}</div>
                              {v.note&&<div style={{fontSize:'11px',color:'#94a3b8',marginTop:'2px'}}>{v.note}</div>}
                              <div style={{fontSize:'11px',color:'#94a3b8',marginTop:'3px'}}>{v.label}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                </div>
              </div>
            );
          })()}

          {activePanel === 'profile' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center' }}>
                  <h2 style={{ margin: 0, fontSize: '18px', color: '#6C5CE7', fontWeight: 'bold', textAlign: 'left', width: '100%', fontFamily: '"Inter", system-ui, -apple-system, sans-serif', letterSpacing: '-0.5px' }}>Edit Profile</h2>
                </div>
              </div>
              
              <div className="profile-edit-container" style={{ display: 'flex', flexDirection: 'column', background: '#FFF', borderRadius: '16px', padding: '32px', overflowY: 'auto', boxShadow: '0 24px 48px rgba(0,0,0,0.15), 0 12px 24px rgba(0,0,0,0.1)', border: '1px solid #e1e4e8', maxWidth: '500px', width: '100%', boxSizing: 'border-box' }}>
                <form onSubmit={handleProfileUpdate} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B' }}>Display Name</label>
                    <input type="text" name="display_name" defaultValue={user?.name || user?.display_name || ''} style={{ padding: '12px 16px', borderRadius: '8px', border: '1px solid #E2E8F0', outline: 'none', fontSize: '14px', background: '#F8FAFC' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B' }}>Profile Picture</label>
                    <input type="file" name="profile_pic" accept="image/*" style={{ padding: '12px 16px', borderRadius: '8px', border: '1px solid #E2E8F0', outline: 'none', fontSize: '14px', background: '#F8FAFC' }} />
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B' }}>New Password (leave blank to keep current)</label>
                    <input type="password" name="password" placeholder="Enter new password..." style={{ padding: '12px 16px', borderRadius: '8px', border: '1px solid #E2E8F0', outline: 'none', fontSize: '14px', background: '#F8FAFC' }} />
                  </div>
                  <button type="submit" disabled={isUploadingProfile} style={{ marginTop: '12px', padding: '14px', borderRadius: '50px', background: 'linear-gradient(to right, #D67CFF, #6B5CE7)', color: '#FFF', border: 'none', fontWeight: 'bold', cursor: 'pointer', fontSize: '14px', transition: 'all 0.3s', opacity: isUploadingProfile ? 0.7 : 1, boxShadow: '0 4px 12px rgba(107, 92, 231, 0.3)' }}>
                    {isUploadingProfile ? 'Saving...' : 'Save Profile Changes'}
                  </button>
                </form>
              </div>
            </div>
          )}

          {activePanel === 'explain' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, gap: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center' }}>
                  <h2 style={{ margin: 0, fontSize: '18px', color: '#6C5CE7', fontWeight: 'bold', textAlign: 'left', width: '100%', fontFamily: '"Inter", system-ui, -apple-system, sans-serif', letterSpacing: '-0.5px' }}>AI Health Assistant</h2>
                  <p style={{ margin: '6px 0 0 0', fontSize: '11px', color: '#8B7EFF', fontWeight: '500', textAlign: 'left', width: '100%', fontFamily: '"Inter", system-ui, -apple-system, sans-serif' }}>*Not a substitute for professional medical advice*</p>
                </div>
                <div style={{ width: '160px' }}>
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    style={{ width: '100%', padding: '10px 14px', border: '1px solid #E2E8F0', borderRadius: '8px', outline: 'none', fontSize: '11px', backgroundColor: '#FFF', boxShadow: '0 2px 4px rgba(0,0,0,0.15)' }}
                  >
                    <option value="en">English</option>
                    <option value="es">Español</option>
                    <option value="hi">Hindi</option>
                    <option value="bn">Bengali</option>
                  </select>
                </div>
              </div>

              <div className="analyze-view-container" style={{ display: 'flex', flex: 1, gap: '24px', minHeight: 0 }}>
                <div className="ai-chat-column" style={{ position: 'relative', flex: 7, display: 'flex', flexDirection: 'column', overflow: 'visible', minHeight: 0, gap: '0' }}>
                  <div className="chat-box-container" style={{ position: 'relative', flex: 1, display: 'flex', flexDirection: 'column', background: '#FFF', borderRadius: '16px', boxShadow: '0 24px 48px rgba(0,0,0,0.15), 0 12px 24px rgba(0,0,0,0.1)', border: '1px solid #e1e4e8', overflow: 'hidden', minHeight: 0 }}>
                    <div className="chat-box" style={{ flex: 1, overflowY: 'auto', padding: '24px 24px 100px 24px', minHeight: 0 }}>
                      {messages.length === 0 && !isAiProcessing && <div style={{textAlign: "center", color: "#6B6B6B", marginTop: "20px"}}>Start chatting with your AI Medical Assistant!</div>}
                      {messages.map((msg, idx) => (
                        <div key={idx} className={`chat-message ${isOutgoingChatMessage(msg) ? 'user' : 'model'}`} style={{ marginBottom: '16px', display: 'flex', alignItems: 'flex-start', justifyContent: isOutgoingChatMessage(msg) ? 'flex-end' : 'flex-start' }}>
                          {!isOutgoingChatMessage(msg) && <div className="emoji" style={{ marginRight: '8px', fontSize: '18px' }}></div>}
                          <div className="bubble" style={{ background: isOutgoingChatMessage(msg) ? '#8B7EFF' : '#F1F5F9', color: isOutgoingChatMessage(msg) ? '#FFF' : '#1E293B', padding: '12px 16px', borderRadius: '16px', maxWidth: '80%', boxShadow: '0 8px 16px rgba(0,0,0,0.08), 0 4px 6px rgba(0,0,0,0.04)' }}>
                            {isOutgoingChatMessage(msg) ? (
                              <div className="content" style={{ whiteSpace: 'pre-wrap' }}>{msg.text || ''}</div>
                            ) : msg.structured ? (
                              <div className="content"><StructuredReply data={msg.structured} /></div>
                            ) : isJsonLike(msg.text) && tryParseJson(msg.text) ? (
                              <div className="content"><StructuredReply data={tryParseJson(msg.text)} /></div>
                            ) : isJsonLike(msg.text) ? (
                              <div className="content"><MarkdownMessage text={getCleanAnalysisText(msg.text)} /></div>
                            ) : (
                              <div className="content"><MarkdownMessage text={msg.text || ''} /></div>
                            )}
                          </div>
                        </div>
                      ))}
                      {isAiProcessing && <AiProcessingCard active={isAiProcessing} status={processingState} />}
                      <div ref={chatEndRef} />
                    </div>
                    <form id="chatInputForm" style={{ position: 'absolute', bottom: '24px', left: '50%', transform: 'translateX(-50%)', width: 'calc(90% - 48px)', maxWidth: '720px', display: 'flex', alignItems: 'center', padding: '6px 6px 6px 12px', background: '#ffffff', borderRadius: '50px', boxShadow: '0 16px 32px rgba(0,0,0,0.15), 0 8px 16px rgba(0,0,0,0.1)', border: '1px solid #e1e4e8', zIndex: 10 }} onSubmit={handleChatSubmit}>
                      <span style={{ color: '#64748b', fontSize: '22px', marginRight: '16px', cursor: 'pointer' }}>+</span>
                      <input
                        type="text"
                        placeholder="Ask AI Health Assistant..."
                        value={inputMsg}
                        onChange={e => setInputMsg(e.target.value)}
                        style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: '15px', color: '#1E293B', fontWeight: '500' }}
                      />
                      <button type="submit" disabled={!inputMsg.trim()} style={{ marginLeft: '12px', width: '40px', height: '40px', borderRadius: '50%', background: !inputMsg.trim() ? '#E2E8F0' : 'linear-gradient(to right, #D67CFF, #6B5CE7)', color: !inputMsg.trim() ? '#94A3B8' : '#FFF', border: 'none', cursor: !inputMsg.trim() ? 'default' : 'pointer', transition: 'all 0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: !inputMsg.trim() ? 'none' : '0 4px 12px rgba(214, 124, 255, 0.4)' }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="22" y1="2" x2="11" y2="13"></line>
                          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                      </button>  
                    </form>
                  </div>
                </div>

                <div className="action-panel-column" style={{ flex: 3, display: 'flex', flexDirection: 'column', gap: '16px', minHeight: 0 }}>
                  <div className="floating-box panel" style={{ background: '#FFF', padding: '24px', borderRadius: '16px', boxShadow: '0 24px 48px rgba(0,0,0,0.15), 0 12px 24px rgba(0,0,0,0.1)', border: '1px solid #e1e4e8', flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflowY: 'auto' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', gap: '12px' }}>
                      <h4 style={{ margin: 0, fontSize: '13px', color: '#6C5CE7', fontWeight: 'bold', flex: 1 }}>Analyze Medical Files</h4>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button 
                          onClick={() => { setAnalysisMode('upload'); setUploadedFiles([]); setSelectedDocForAnalysis(null); }}
                          style={{ padding: '6px 12px', fontSize: '10px', fontWeight: '600', borderRadius: '50px', border: '1px solid', background: analysisMode === 'upload' ? '#6C5CE7' : '#F1F5F9', color: analysisMode === 'upload' ? '#FFF' : '#475569', cursor: 'pointer', transition: '0.2s' }}
                        >
                          Upload New
                        </button>
                        <button 
                          onClick={() => { setAnalysisMode('select'); setUploadedFiles([]); setSelectedDocForAnalysis(null); setAnalysisCurrentFolder(null); loadAssets(); }}
                          style={{ padding: '6px 12px', fontSize: '10px', fontWeight: '600', borderRadius: '50px', border: '1px solid', background: analysisMode === 'select' ? '#6C5CE7' : '#F1F5F9', color: analysisMode === 'select' ? '#FFF' : '#475569', cursor: 'pointer', transition: '0.2s' }}
                        >
                          My Documents
                        </button>
                      </div>
                    </div>

                    {analysisMode === 'upload' ? (
                      uploadedFiles.length === 0 ? (
                        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '16px' }}>
                          <div className="styled-dropzone" style={{ border: '2px dashed #CBD5E1', borderRadius: '16px', padding: '48px 24px', textAlign: 'center', background: '#F8FAFC', position: 'relative', transition: 'all 0.2s', cursor: 'pointer', width: '100%', boxSizing: 'border-box' }} onMouseEnter={(e) => e.currentTarget.style.borderColor='#8B7EFF'} onMouseLeave={(e) => e.currentTarget.style.borderColor='#CBD5E1'}>
                            <label style={{ cursor: 'pointer', display: 'block', width: '100%', height: '100%' }}>
                              <div style={{ fontSize: '32px', marginBottom: '12px' }}>+</div>
                              <div style={{ fontSize: '12px', fontWeight: '600', color: '#475569', marginBottom: '6px' }}>Upload Medical File</div>
                              <div style={{ fontSize: '10px', color: '#64748B' }}>Any supported document or image</div>
                              <input type="file" ref={explainUploadInputRef} accept=".pdf,.jpg,.jpeg,.png" onChange={handleAddExplainFile} style={{ position: 'absolute', top:0, left:0, width:'100%', height:'100%', opacity:0, cursor: 'pointer' }} />
                            </label>
                          </div>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
                          <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {uploadedFiles.map((fileObj) => (
                              <div key={fileObj.id} style={{ display: 'flex', alignItems: 'center', padding: '12px', background: '#F8FAFC', borderRadius: '12px', border: '1px solid #E2E8F0', gap: '12px' }}>
                                <div style={{ width: '36px', height: '36px', background: '#EEF2FF', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6366F1', flexShrink: 0 }}>
                                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div style={{ fontWeight: '600', fontSize: '12px', color: '#1E293B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fileObj.name}</div>
                                  <div style={{ fontSize: '10px', color: '#64748B', marginTop: '2px' }}>{(fileObj.file.size / 1024 / 1024).toFixed(2)} MB</div>
                                </div>
                                <button 
                                  onClick={() => handleRemoveExplainFile(fileObj.id)} 
                                  style={{ padding: '6px 12px', background: '#fee2e2', color: '#ef4444', border: '1px solid #fecaca', borderRadius: '50px', fontSize: '10px', fontWeight: '600', cursor: 'pointer', transition: '0.2s', flexShrink: 0 }}
                                  onMouseEnter={(e) => { e.target.style.background = '#ef4444'; e.target.style.color = '#FFF'; }}
                                  onMouseLeave={(e) => { e.target.style.background = '#fee2e2'; e.target.style.color = '#ef4444'; }}
                                >
                                  Remove
                                </button>
                              </div>
                            ))}
                          </div>
                          
                          <div className="styled-dropzone" style={{ border: '2px dashed #CBD5E1', borderRadius: '12px', padding: '16px', textAlign: 'center', background: '#F8FAFC', position: 'relative', transition: 'all 0.2s', cursor: 'pointer', marginTop: '8px' }} onMouseEnter={(e) => e.currentTarget.style.borderColor='#8B7EFF'} onMouseLeave={(e) => e.currentTarget.style.borderColor='#CBD5E1'}>
                            <label style={{ cursor: 'pointer', display: 'block' }}>
                              <div style={{ fontSize: '20px', color: '#8B7EFF', fontWeight: 'bold' }}>+</div>
                              <div style={{ fontSize: '10px', color: '#64748B', marginTop: '4px' }}>Add More Files</div>
                              <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={handleAddExplainFile} style={{ position: 'absolute', top:0, left:0, width:'100%', height:'100%', opacity:0, cursor: 'pointer' }} />
                            </label>
                          </div>
                          
                          <button 
                            onClick={handleExplainUpload} 
                            style={{ width: '100%', padding: '14px', borderRadius: '50px', background: 'linear-gradient(to right, #D67CFF, #6B5CE7)', color: '#FFF', border: 'none', fontWeight: 'bold', cursor: 'pointer', fontSize: '14px', boxShadow: '0 3px 5px rgba(0,0,0,0.3)', transition: 'all 0.3s ease', marginTop: '8px' }}
                            onMouseEnter={(e) => e.target.style.boxShadow = '0 6px 12px rgba(214, 124, 255, 0.4)'}
                            onMouseLeave={(e) => e.target.style.boxShadow = '0 3px 5px rgba(0,0,0,0.3)'}
                          >
                            Analyze {uploadedFiles.length} File{uploadedFiles.length !== 1 ? 's' : ''}
                          </button>
                        </div>
                      )
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
                        {analysisCurrentFolder !== null && (
                          <span onClick={() => setAnalysisCurrentFolder(null)} style={{ color: '#8B7EFF', cursor: 'pointer', fontSize: '11px', fontWeight: '600' }}>
                            ← Back to Root
                          </span>
                        )}

                        {analysisCurrentFolder === null && assets.folders.length === 0 && assets.files.length === 0 ? (
                          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748B', textAlign: 'center', padding: '32px 16px' }}>
                            <div>
                              <div style={{ fontSize: '32px', marginBottom: '12px' }}>📁</div>
                              <div style={{ fontSize: '12px' }}>No documents uploaded yet.</div>
                              <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '8px' }}>Upload files using the "Upload New" tab or "My Documents" page.</div>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div style={{ fontSize: '11px', color: '#64748B', marginBottom: '8px', fontWeight: '600' }}>
                              Select a document to analyze: {analysisCurrentFolder === null ? 'Root' : getFolderDisplayName(analysisCurrentFolder)}
                            </div>
                            <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: '6px', padding: '2px' }}>
                              {analysisCurrentFolder === null && assets.folders.map((folderName, i) => (
                                <div
                                  key={'analysis-folder-' + i}
                                  onClick={() => setAnalysisCurrentFolder(folderName.path)}
                                  style={{ display: 'flex', alignItems: 'center', padding: '8px 10px', background: '#FAFAFA', borderRadius: '10px', border: '1px solid #E2E8F0', gap: '8px', cursor: 'pointer' }}
                                  onMouseEnter={(e) => { e.currentTarget.style.background = '#F1F5F9'; }}
                                  onMouseLeave={(e) => { e.currentTarget.style.background = '#FAFAFA'; }}
                                >
                                  <div style={{ width: '24px', height: '24px', background: '#E2E8F0', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8B7EFF', flexShrink: 0, fontSize: '12px' }}>
                                    📁
                                  </div>
                                  <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontWeight: '600', fontSize: '10px', color: '#1E293B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{folderName.label}</div>
                                    <div style={{ fontSize: '8px', color: '#94A3B8', marginTop: '1px' }}>Folder</div>
                                  </div>
                                </div>
                              ))}

                              {assets.files
                                .filter((f) => (f.folder || '') === (analysisCurrentFolder || ''))
                                .map((doc) => (
                                <div 
                                  key={doc.id}
                                  onClick={() => setSelectedDocForAnalysis(doc.id)}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    padding: '8px 10px',
                                    background: selectedDocForAnalysis === doc.id ? '#EEF2FF' : '#F8FAFC',
                                    borderRadius: '10px',
                                    border: selectedDocForAnalysis === doc.id ? '2px solid #6C5CE7' : '1px solid #E2E8F0',
                                    gap: '8px',
                                    cursor: 'pointer',
                                    transition: '0.2s',
                                    minHeight: '42px'
                                  }}
                                  onMouseEnter={(e) => { if (selectedDocForAnalysis !== doc.id) e.currentTarget.style.background = '#F1F5F9'; }}
                                  onMouseLeave={(e) => { if (selectedDocForAnalysis !== doc.id) e.currentTarget.style.background = '#F8FAFC'; }}
                                >
                                  <div style={{ width: '24px', height: '24px', background: '#EEF2FF', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6366F1', flexShrink: 0, fontSize: '12px' }}>
                                    {String(doc?.name || '').toLowerCase().endsWith('.pdf') ? '📄' : '🖼️'}
                                  </div>
                                  <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontWeight: '600', fontSize: '10px', color: '#1E293B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.name}</div>
                                    <div style={{ fontSize: '8px', color: '#94A3B8', marginTop: '1px', lineHeight: '1.2' }}>{doc.folder || 'Root'} • {doc.uploaded_at || 'Unknown'}</div>
                                  </div>
                                  <input
                                    type="radio"
                                    checked={selectedDocForAnalysis === doc.id}
                                    onChange={() => setSelectedDocForAnalysis(doc.id)}
                                    style={{
                                      width: '14px',
                                      height: '14px',
                                      margin: 0,
                                      padding: 0,
                                      flex: '0 0 auto',
                                      cursor: 'pointer',
                                      accentColor: '#6C5CE7'
                                    }}
                                  />
                                </div>
                              ))}

                              {assets.files.filter((f) => (f.folder || '') === (analysisCurrentFolder || '')).length === 0 && (
                                <div style={{ padding: '24px', textAlign: 'center', color: '#64748B', fontSize: '11px' }}>
                                  No files found in this folder.
                                </div>
                              )}
                            </div>
                            
                            <button 
                              onClick={handleAnalyzeSelected}
                              disabled={!selectedDocForAnalysis}
                              style={{ width: '100%', padding: '14px', borderRadius: '50px', background: selectedDocForAnalysis ? 'linear-gradient(to right, #D67CFF, #6B5CE7)' : '#E2E8F0', color: selectedDocForAnalysis ? '#FFF' : '#94A3B8', border: 'none', fontWeight: 'bold', cursor: selectedDocForAnalysis ? 'pointer' : 'default', fontSize: '14px', boxShadow: selectedDocForAnalysis ? '0 3px 5px rgba(0,0,0,0.3)' : 'none', transition: 'all 0.3s ease', marginTop: '8px' }}
                              onMouseEnter={(e) => { if (selectedDocForAnalysis) e.target.style.boxShadow = '0 6px 12px rgba(214, 124, 255, 0.4)'; }}
                              onMouseLeave={(e) => { if (selectedDocForAnalysis) e.target.style.boxShadow = '0 3px 5px rgba(0,0,0,0.3)'; }}
                            >
                              Analyze Selected
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activePanel === 'documents' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <h2 style={{ margin: 0, fontSize: '18px', color: '#6C5CE7', fontWeight: 'bold', fontFamily: '"Inter", sans-serif', letterSpacing: '-0.5px' }}>
                    {currentFolder === null ? 'My Documents' : getFolderDisplayName(currentFolder)}
                  </h2>
                  {currentFolder !== null && (
                    <span onClick={() => setCurrentFolder(null)} style={{ color: '#8B7EFF', cursor: 'pointer', fontSize: '12px', marginTop: '8px', fontWeight: '600' }}>
                      &larr; Back to Root
                    </span>
                  )}
                </div>
                <div style={{display: 'flex', gap: '8px'}}>
                  <input type="file" id="upload-doc-v2" style={{display: 'none'}} onChange={handleUploadAssetV2} />
                  <button onClick={() => document.getElementById('upload-doc-v2').click()} style={{ background: '#6C5CE7', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>Upload Files</button>
                </div>
              </div>

              <div className="documents-container" style={{ display: 'flex', flexDirection: 'column', flex: 1, background: '#FFF', borderRadius: '16px', padding: '32px', overflowY: 'auto', boxShadow: '0 24px 48px rgba(0,0,0,0.15), 0 12px 24px rgba(0,0,0,0.1)', border: '1px solid #e1e4e8', minHeight: 0, boxSizing: 'border-box' }}>
                {previewFile && (
                  <FileViewer file={previewFile} onClose={() => setPreviewFile(null)} />
                )}
                {renameTarget && (
                  <div
                    style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(15,23,42,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}
                    onClick={() => { setRenameTarget(null); setRenameValue(''); }}
                  >
                    <div
                      onClick={(event) => event.stopPropagation()}
                      style={{ width: 'min(92vw, 420px)', background: '#fff', borderRadius: 16, boxShadow: '0 20px 60px rgba(15,23,42,0.25)', padding: 20, border: '1px solid #E2E8F0' }}
                    >
                      <div style={{ fontSize: 16, fontWeight: 700, color: '#1E293B', marginBottom: 8 }}>Rename file</div>
                      <div style={{ fontSize: 12, color: '#64748B', marginBottom: 12 }}>Rename the file name only for {renameTarget?.name || renameTarget?.original_name || 'this document'}. The extension stays unchanged.</div>
                      <input
                        type="text"
                        value={renameValue}
                        onChange={(event) => setRenameValue(event.target.value)}
                        style={{ width: '100%', boxSizing: 'border-box', padding: '10px 12px', borderRadius: 10, border: '1px solid #CBD5E1', outline: 'none', fontSize: 14, marginBottom: 16 }}
                        autoFocus
                      />
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                        <button onClick={() => { setRenameTarget(null); setRenameValue(''); }} style={{ padding: '8px 14px', borderRadius: 999, border: '1px solid #E2E8F0', background: '#F8FAFC', color: '#475569', cursor: 'pointer' }}>Cancel</button>
                        <button onClick={submitRenameAsset} disabled={!renameValue.trim()} style={{ padding: '8px 14px', borderRadius: 999, border: '1px solid #C4B5FD', background: renameValue.trim() ? '#6C5CE7' : '#C7D2FE', color: '#fff', cursor: renameValue.trim() ? 'pointer' : 'not-allowed' }}>Save</button>
                      </div>
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {currentFolder === null && assets.folders.map((folderName, i) => (
                    <div key={'f'+i} style={{ display: 'flex', alignItems: 'center', padding: '16px', border: '1px solid #E2E8F0', borderRadius: '12px', background: '#FAFAFA' }}>
                      <div style={{ width: '40px', height: '40px', background: '#E2E8F0', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '16px', color: '#8B7EFF' }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="#8B7EFF"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: '600', fontSize: '12px', color: '#1E293B', cursor: 'pointer' }} onClick={() => setCurrentFolder(folderName.path)}>{folderName.label}</div>
                        <div style={{ fontSize: '10px', color: '#64748B', marginTop: '4px' }}>Folder</div>
                      </div>
                      <button onClick={() => setCurrentFolder(folderName.path)} style={{ textDecoration: 'none', padding: '8px 16px', background: '#F1F5F9', color: '#475569', borderRadius: '50px', fontSize: '11px', fontWeight: '600', cursor: 'pointer', transition: '0.2s', border: '1px solid #E2E8F0' }} onMouseEnter={(e)=> {e.target.style.background='#8B7EFF'; e.target.style.color='#FFF';}} onMouseLeave={(e)=> {e.target.style.background='#F1F5F9'; e.target.style.color='#475569';}}>Open</button>
                    </div>
                  ))}

                  {assets.files.filter(f => (f.folder || '') === (currentFolder || '')).map((file, i) => (
                    <div key={'file'+i} style={{ display: 'flex', alignItems: 'center', padding: '16px', border: '1px solid #E2E8F0', borderRadius: '12px', background: '#FFF' }}>
                      <div style={{ width: '40px', height: '40px', background: file?.asset_kind === 'report' ? '#EEF2FF' : file?.asset_kind === 'prescription' ? '#ECFDF5' : '#F8FAFC', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '16px', color: file?.asset_kind === 'report' ? '#6366F1' : file?.asset_kind === 'prescription' ? '#16A34A' : '#475569' }}>
                        {(() => {
                          const kind = String(file?.asset_kind || 'medical_image');
                          const mime = String(file?.mime_type || '').toLowerCase();
                          if (kind === 'report') {
                            return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><path d="M8 13h8" /><path d="M8 17h8" /></svg>;
                          }
                          if (kind === 'prescription') {
                            return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h9l7 7v9H4z" /><path d="M13 4v7h7" /><path d="M8 14h8" /><path d="M10 10a2 2 0 1 1 0 4" /><path d="M12 10v4" /></svg>;
                          }
                          if (mime.startsWith('image/')) {
                            return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg>;
                          }
                          return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>;
                        })()}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: '600', fontSize: '12px', color: '#1E293B' }}>{file?.name || file?.original_name || `File ${i+1}`} </div>
                        <div style={{ fontSize: '10px', color: '#64748B', marginTop: '4px' }}>{file?.folder_label || 'General Uploads'}{file?.uploaded_at ? ` · ${new Date(file.uploaded_at).toLocaleString()}` : ''}</div>
                      </div>

                      <button onClick={() => setPreviewFile(file)} style={{ textDecoration: 'none', padding: '8px 16px', background: '#F1F5F9', color: '#475569', borderRadius: '50px', fontSize: '11px', fontWeight: '600', transition: '0.2s', border: '1px solid #E2E8F0' }} onMouseEnter={(e)=> {e.target.style.background='#8B7EFF'; e.target.style.color='#FFF';}} onMouseLeave={(e)=> {e.target.style.background='#F1F5F9'; e.target.style.color='#475569';}}>View</button>
                      
                      <button onClick={() => handleRenameAsset(file)} title="Rename this file" style={{ marginLeft: '8px', border: 'none', background: '#FFFBEB', color: '#D97706', padding: '8px 16px', borderRadius: '50px', fontSize: '11px', fontWeight: '600', cursor: 'pointer', transition: '0.2s', border: '1px solid #FEF3C7' }}>Rename</button>

                      <button onClick={() => handleDeleteAssetV2(file)} title="Delete this file" style={{ marginLeft: '8px', border: 'none', background: '#fee2e2', color: '#ef4444', padding: '8px 16px', borderRadius: '50px', fontSize: '11px', fontWeight: '600', cursor: 'pointer', transition: '0.2s', border: '1px solid #fecaca' }} onMouseEnter={(e)=> {e.target.style.background='#ef4444'; e.target.style.color='#FFF';}} onMouseLeave={(e)=> {e.target.style.background='#fee2e2'; e.target.style.color='#ef4444';}}>Delete</button>
                    </div>
                  ))}

                  {currentFolder === null && assets.folders.length === 0 && assets.files.filter(f => !f.folder).length === 0 && (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#64748B' }}>No documents in root.</div>
                  )}
                  {currentFolder !== null && assets.files.filter(f => f.folder === currentFolder).length === 0 && (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#64748B' }}>No files found in this folder.</div>
                  )}
                </div>

                {uploadQueue.length > 0 && (
                  <div style={{ position: 'fixed', right: 24, bottom: 24, zIndex: 1600, width: 'min(360px, calc(100vw - 32px))', display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {uploadQueue.map((q) => (
                      <div key={q.id} style={{ background: '#FFF', border: '1px solid #E2E8F0', borderRadius: 14, boxShadow: '0 16px 32px rgba(15,23,42,0.14)', padding: 14 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                          <div style={{ fontSize: 12, fontWeight: 700, color: '#1E293B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.name}</div>
                          <div style={{ fontSize: 11, fontWeight: 700, color: q.status === 'error' ? '#DC2626' : q.status === 'done' ? '#16A34A' : '#6C5CE7' }}>{q.status === 'uploading' ? `${q.progress || 0}%` : q.status === 'done' ? 'Uploaded' : 'Failed'}</div>
                        </div>
                        <div style={{ height: 8, background: '#F1F5F9', borderRadius: 999, overflow: 'hidden' }}>
                          <div style={{ width: `${q.progress || 0}%`, height: '100%', background: q.status === 'error' ? '#ef4444' : q.status === 'done' ? '#16A34A' : '#6C5CE7', transition: 'width 0.2s' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {activePanel === 'xray' && (
            <XrayAnalyzerPanel />
          )}

          {activePanel === 'appointments' && (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center' }}>
                  <h2 style={{ margin: 0, fontSize: '18px', color: '#6C5CE7', fontWeight: 'bold', textAlign: 'left', width: '100%', fontFamily: '"Inter", system-ui, -apple-system, sans-serif', letterSpacing: '-0.5px' }}>Appointments Hub</h2>
                </div>
              </div>
              <div className="appointments-container" style={{ display: 'flex', flexDirection: 'column', flex: 1, background: '#FFF', borderRadius: '16px', padding: '32px', overflowY: 'auto', boxShadow: '0 24px 48px rgba(0,0,0,0.15), 0 12px 24px rgba(0,0,0,0.1)', border: '1px solid #e1e4e8', minHeight: 0, boxSizing: 'border-box' }}>
              
                <div style={{ display: 'flex', gap: '40px' }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: '11px', marginBottom: '24px', color: '#475569', borderBottom: '2px solid #F1F5F9', paddingBottom: '12px' }}>Your Scheduled Sessions</h3>
                    {appointments.length === 0 ? (
                      <div style={{ padding: '48px 32px', textAlign: 'center', background: '#F8FAFC', borderRadius: '16px', border: '1px dashed #CBD5E1' }}>
                        <div style={{ fontSize: '20px', marginBottom: '16px' }}></div>
                        <p style={{ color: '#64748B', margin: 0, fontSize: '11px' }}>No upcoming appointments scheduled.</p>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {appointments.map((appt, i) => (
                          <div key={i} className="session-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 24px', background: '#FFF', border: '1px solid #E2E8F0', borderRadius: '16px', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
                            <div>
                              <strong style={{ fontSize: '11px', color: '#1E293B' }}>Dr. {appt.doctor_display}</strong>
                              <div style={{ fontSize: '11px', color: '#64748B', marginTop: '6px' }}>Reason: {appt.reason}</div>
                              {(appt.appointmentDate || appt.scheduled_time) && <div style={{ fontSize: '11px', color: '#8B7EFF', marginTop: '4px', fontWeight: '500' }}>Time: {new Date(appt.appointmentDate || appt.scheduled_time).toLocaleString()}</div>}
                              {String(appt.doctorMessage || '').trim() && String(appt.status || '').toUpperCase() === 'REJECTED' && <div style={{ fontSize: '11px', color: '#B45309', marginTop: '4px' }}>Doctor note: {appt.doctorMessage}</div>}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                              <span style={{ display: 'inline-block', padding: '8px 16px', borderRadius: '50px', fontSize: '11px', fontWeight: '700', background: String(appt.status || '').toUpperCase() === 'PENDING' ? '#FEF3C7' : String(appt.status || '').toUpperCase() === 'CONFIRMED' ? '#DCFCE7' : String(appt.status || '').toUpperCase() === 'REJECTED' ? '#FEE2E2' : '#E2E8F0', color: String(appt.status || '').toUpperCase() === 'PENDING' ? '#D97706' : String(appt.status || '').toUpperCase() === 'CONFIRMED' ? '#166534' : String(appt.status || '').toUpperCase() === 'REJECTED' ? '#B91C1C' : '#475569' }}>
                                {String(appt.status || '').toUpperCase()}
                              </span>
                              {String(appt.status || '').toUpperCase() !== 'CANCELLED' && String(appt.status || '').toUpperCase() !== 'COMPLETED' && String(appt.status || '').toUpperCase() !== 'REJECTED' && (
                                <button type="button" onClick={() => handleCancelAppointment(appt.id)} style={{ padding: '8px 14px', borderRadius: '50px', border: '1px solid #FCA5A5', background: '#FFF1F2', color: '#BE123C', fontSize: '11px', fontWeight: '700', cursor: 'pointer' }}>
                                  Cancel
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div style={{ flex: 1 }}>
                    <h3 style={{ fontSize: '11px', marginBottom: '24px', color: '#475569', borderBottom: '2px solid #F1F5F9', paddingBottom: '12px' }}>Book New Appointment</h3>
                    <form onSubmit={handleCreateAppointment} style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '12px', padding: '20px', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '16px', marginBottom: '24px' }}>
                      <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '10px' }}>
                        <button type="button" onClick={() => setBookingMode('direct')} style={{ flex: 1, padding: '10px 14px', borderRadius: '999px', border: bookingMode === 'direct' ? 'none' : '1px solid #CBD5E1', background: bookingMode === 'direct' ? '#6C5CE7' : '#FFF', color: bookingMode === 'direct' ? '#FFF' : '#475569', fontSize: '11px', fontWeight: '700', cursor: 'pointer' }}>Pick a Time</button>
                        <button type="button" onClick={() => setBookingMode('open')} style={{ flex: 1, padding: '10px 14px', borderRadius: '999px', border: bookingMode === 'open' ? 'none' : '1px solid #CBD5E1', background: bookingMode === 'open' ? '#6C5CE7' : '#FFF', color: bookingMode === 'open' ? '#FFF' : '#475569', fontSize: '11px', fontWeight: '700', cursor: 'pointer' }}>Send Open Request</button>
                      </div>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: '#475569' }}>
                        Doctor
                        <select value={appointmentDraft.doctor_id} onChange={e => setAppointmentDraft(prev => ({ ...prev, doctor_id: e.target.value }))} style={{ padding: '10px 12px', border: '1px solid #E2E8F0', borderRadius: '12px', fontSize: '11px', background: '#FFF' }}>
                          <option value="">Select a doctor</option>
                          {doctors.map(doc => {
                            const doctorId = doc.doctor_id || doc.id;
                            return <option key={doctorId} value={doctorId}>Dr. {doc.name} {doc.category ? `- ${doc.category}` : ''}</option>;
                          })}
                        </select>
                      </label>
                      {bookingMode === 'direct' ? (
                        <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: '#475569' }}>
                          Available Slots
                          <select value={selectedSlotId} onChange={e => setSelectedSlotId(e.target.value)} disabled={!appointmentDraft.doctor_id || slotLoading} style={{ padding: '10px 12px', border: '1px solid #E2E8F0', borderRadius: '12px', fontSize: '11px', background: '#FFF' }}>
                            <option value="">{slotLoading ? 'Loading slots...' : 'Choose an available slot'}</option>
                            {availableSlots.map(slot => (
                              <option key={slot.id} value={slot.id}>{renderSlotLabel(slot)}</option>
                            ))}
                          </select>
                        </label>
                      ) : (
                        <div style={{ gridColumn: '1 / -1', padding: '12px 14px', background: '#FFF7ED', border: '1px solid #FED7AA', borderRadius: '12px', color: '#9A3412', fontSize: '11px', lineHeight: 1.5 }}>
                          Send an open request when you do not see a slot that fits. The doctor will confirm a time later.
                        </div>
                      )}
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: '#475569' }}>
                        Reason
                        <input type="text" value={appointmentDraft.reason} onChange={e => setAppointmentDraft(prev => ({ ...prev, reason: e.target.value }))} placeholder="General consultation" style={{ padding: '10px 12px', border: '1px solid #E2E8F0', borderRadius: '12px', fontSize: '11px', background: '#FFF' }} />
                      </label>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: '#475569', gridColumn: '1 / -1' }}>
                        Note
                        <textarea value={appointmentDraft.note} onChange={e => setAppointmentDraft(prev => ({ ...prev, note: e.target.value }))} placeholder="Optional context for the doctor" rows="3" style={{ padding: '10px 12px', border: '1px solid #E2E8F0', borderRadius: '12px', fontSize: '11px', background: '#FFF', resize: 'vertical' }} />
                      </label>
                      <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end' }}>
                        <button
                          type="submit"
                          disabled={bookingInProgress || (bookingMode === 'direct' && (!selectedSlotId || slotLoading))}
                          style={{ padding: '12px 18px', borderRadius: '999px', border: 'none', background: bookingInProgress || (bookingMode === 'direct' && (!selectedSlotId || slotLoading)) ? '#C4B5FD' : '#8B7EFF', color: '#FFF', fontSize: '11px', fontWeight: '700', cursor: bookingInProgress || (bookingMode === 'direct' && (!selectedSlotId || slotLoading)) ? 'not-allowed' : 'pointer', boxShadow: '0 8px 18px rgba(139,126,255,0.28)' }}>
                          {bookingInProgress ? 'Booking...' : bookingMode === 'direct' ? 'Book Slot' : 'Send Request'}
                        </button>
                      </div>
                    </form>

                    <div className="doctor-profile-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '20px' }}>
                      {doctors.map(doc => {
                        const doctorId = String(doc.doctor_id || doc.id || '');
                        return (
                          <div key={doctorId} style={{ padding: '24px', border: '1px solid #E2E8F0', borderRadius: '16px', background: appointmentDraft.doctor_id === doctorId ? '#F3F0FF' : '#F8FAFC', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', transition: 'all 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.boxShadow='0 4px 12px rgba(0,0,0,0.05)'} onMouseLeave={(e) => e.currentTarget.style.boxShadow='none'}>
                            <div style={{ width: '80px', height: '80px', borderRadius: '50%', background: '#E2E8F0', marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}></div>
                            <div style={{ fontWeight: '700', fontSize: '11px', color: '#1E293B' }}>Dr. {doc.name}</div>
                            <div style={{ fontSize: '11px', color: '#64748B', marginBottom: '20px' }}>{doc.category}</div>
                            <button onClick={() => handleSelectDoctorForAppointment(doctorId)} style={{ width: '100%', background: appointmentDraft.doctor_id === doctorId ? '#6C5CE7' : '#8B7EFF', color: '#fff', border: 'none', padding: '12px 16px', borderRadius: '50px', cursor: 'pointer', fontSize: '11px', fontWeight: '600' }}>Select Doctor</button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activePanel === 'docchat' && (
            <div className="human-chat-wrapper" style={{ display: 'flex', flex: 1, background: '#FFF', borderRadius: '16px', boxShadow: '0 24px 48px rgba(0,0,0,0.15), 0 12px 24px rgba(0,0,0,0.1)', overflow: 'hidden', border: '1px solid #E2E8F0', minHeight: 0 }}>
              
              <div className="contact-sidebar" style={{ width: '300px', borderRight: '1px solid #E2E8F0', display: 'flex', flexDirection: 'column', background: '#FAFAFA' }}>
                <div style={{ padding: '24px', borderBottom: '1px solid #E2E8F0', background: '#FFF' }}>
                  <h2 style={{ margin: 0, fontSize: '11px', color: '#1E293B' }}>My Doctors</h2>
                </div>
                <div style={{ flex: 1, overflowY: 'auto' }}>
                  {doctors.map(d => {
                    const doctorId = String(d.doctor_id || d.id || d.username || '');
                    const consultation = resolveConsultationForDoctor(doctorId);
                    return (
                      <div 
                        key={doctorId || d.name} 
                        onClick={() => setActiveDocChat(doctorId)}
                        style={{ padding: '16px 24px', borderBottom: '1px solid #F1F5F9', cursor: 'pointer', background: activeDocChat === doctorId ? '#F3F0FF' : 'transparent', borderLeft: activeDocChat === doctorId ? '4px solid #8B7EFF' : '4px solid transparent', display: 'flex', alignItems: 'center', gap: '16px' }}
                      >
                        <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: '#E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px', position: 'relative' }}>
                          <div style={{ position: 'absolute', bottom: 0, right: 0, width: '12px', height: '12px', background: '#22C55E', borderRadius: '50%', border: '2px solid #FFF' }}></div>
                        </div>
                        <div>
                          <div style={{ fontWeight: '600', fontSize: '11px', color: '#1E293B' }}>Dr. {d.name}</div>
                          <div style={{ fontSize: '11px', color: '#64748B' }}>{d.category}</div>
                          <div style={{ fontSize: '10px', color: '#94A3B8' }}>{consultation ? 'Consultation ready' : 'No consultation yet'}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="active-conversation" style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#FFF' }}>
                {activeDocChat ? (
                  <>
                    <div className="conversation-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 32px', borderBottom: '1px solid #E2E8F0', height: '80px', boxSizing: 'border-box' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: '#E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}></div>
                        <div>
                          <div style={{ fontWeight: '700', fontSize: '11px', color: '#1E293B' }}>Dr. {doctors.find(d => String(d.doctor_id || d.id || d.username || '') === String(activeDocChat))?.name}</div>
                          <div style={{ fontSize: '11px', color: getDoctorChatStatus(activeDocChat).color, fontWeight: '600' }}>{getDoctorChatStatus(activeDocChat).label}</div>
                          <div style={{ fontSize: '10px', color: '#94A3B8' }}>{activeConsultationId ? `Consultation ${activeConsultationId}` : 'Waiting for consultation'}</div>
                        </div>
                      </div>
                      <div style={{ color: '#8B7EFF', cursor: 'pointer', fontWeight: '600', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', background: '#F3F0FF', borderRadius: '50px' }}>
                        Book Video Call
                      </div>
                    </div>
                    
                    <div style={{ flex: 1, padding: '24px 28px 24px 28px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '18px', background: '#F8FAFC' }}>
                      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
                        <button onClick={handleLoadOlderDocMessages} style={{ fontSize: '12px', padding: '7px 14px', borderRadius: '999px', border: '1px solid #E2E8F0', background: '#FFF', color: '#334155', fontWeight: '600' }}>Load older messages</button>
                      </div>
                      {docMessages.length === 0 && <div style={{textAlign: 'center', fontSize: '11px', color: '#94A3B8', marginTop: '40px'}}>Start a secure end-to-end conversation with your doctor.</div>}
                      {docMessages.map((m, idx) => {
                        const isPatient = String(m.sender || '').toLowerCase().includes('patient') || String(m.sender || '').toLowerCase() === 'user';
                        return (
                          <div key={m.id || idx} style={{ display: 'flex', flexDirection: 'column', alignItems: isPatient ? 'flex-end' : 'flex-start', gap: '4px' }}>
                            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', marginBottom: '2px', width: '100%', justifyContent: isPatient ? 'flex-end' : 'flex-start' }}>
                              <div style={{ maxWidth: '74%' , background: isPatient ? '#8B7EFF' : '#FFF', color: isPatient ? '#FFF' : '#1E293B', padding: '14px 16px', borderRadius: isPatient ? '18px 18px 4px 18px' : '18px 18px 18px 4px', boxShadow: '0 2px 8px rgba(15,23,42,0.06)', border: isPatient ? '1px solid rgba(139,126,255,0.18)' : '1px solid #E2E8F0' }}>
                                <div style={{ fontSize: '14px', lineHeight: '1.55', fontWeight: '500', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{m.text}</div>
                                {m.attachments && m.attachments.length > 0 && (
                                  <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {m.attachments.map((a, ai) => (
                                      <div key={ai} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        {a.url && a.url.match(/\.pdf$/i) ? (
                                          <a href={a.url} target="_blank" rel="noreferrer" style={{ color: isPatient ? '#FFF' : '#1E293B', textDecoration: 'underline', fontSize: '12px' }}>{a.name || 'Document'}</a>
                                        ) : a.url && a.url.match(/\.(png|jpg|jpeg|gif)$/i) ? (
                                          <img src={a.url} alt={a.name || 'img'} style={{ maxWidth: '220px', borderRadius: '8px', border: '1px solid #E2E8F0' }} />
                                        ) : (
                                          <div style={{ fontSize: '12px', color: isPatient ? '#FFF' : '#1E293B' }}>{a.name || 'Attachment'}</div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                            <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '2px', paddingRight: isPatient ? '8px' : '0' }}>{m.sending ? 'Sending...' : m.failed ? 'Failed' : (m.timestamp ? new Date(m.timestamp).toLocaleString() : '')}</div>
                          </div>
                        );
                      })}
                      <div ref={docChatEndRef} />
                    </div>

                    <div style={{ padding: '12px 32px 32px 32px', background: 'transparent', flexShrink: 0 }}>
                      <form onSubmit={handleDocChatSubmit} className="rich-input-row" style={{ display: 'flex', alignItems: 'center', padding: '8px 8px 8px 24px', background: '#F1F5F9', borderRadius: '50px', border: `1px solid ${docInputFocused ? 'rgba(139, 126, 255, 0.45)' : '#E2E8F0'}`, boxShadow: docInputFocused ? '0 0 0 3px rgba(139, 126, 255, 0.10), 0 8px 24px rgba(0,0,0,0.06)' : '0 8px 24px rgba(0,0,0,0.06)', transition: 'border-color 0.18s ease, box-shadow 0.18s ease' }}>
                        <label title="Attach media" style={{ color: '#64748B', fontWeight: '300', fontSize: '18px', marginRight: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                          <input type="file" accept=".pdf,.png,.jpg,.jpeg,.gif" onChange={handleDocAttachChange} style={{ display: 'none' }} />
                          +
                        </label>
                        <div style={{ display: 'flex', flexDirection: 'column', marginRight: '12px' }}>
                          {docAttachmentFile && (
                            <div style={{ fontSize: '11px', color: '#475569', background: '#FFF', padding: '6px 8px', borderRadius: '8px', border: '1px solid #E2E8F0' }}>{docAttachmentFile.name}</div>
                          )}
                        </div>
                        <input type="text" value={docMsgInput} onChange={e=>setDocMsgInput(e.target.value)} onFocus={() => setDocInputFocused(true)} onBlur={() => setDocInputFocused(false)} disabled={docChatDisabled || docSending} placeholder={docChatDisabled ? 'Chat disabled' : 'Type a secure message...'} style={{flex: 1, padding: '10px 0', border: 'none', background: 'transparent', outline: 'none', boxShadow: 'none', fontSize: '14px', lineHeight: '1.5', color: '#0F172A', caretColor: '#8B7EFF', borderRadius: '12px'}} />
                        <button disabled={docChatDisabled || docSending || !activeDocChat || !docMsgInput.trim()} type="submit" style={{ marginLeft: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '42px', height: '42px', borderRadius: '50%', background: docChatDisabled || !activeDocChat || !docMsgInput.trim() ? '#E2E8F0' : '#8B7EFF', color: docChatDisabled || !activeDocChat || !docMsgInput.trim() ? '#94A3B8' : '#FFF', border: 'none', cursor: docChatDisabled || !activeDocChat || !docMsgInput.trim() ? 'default' : 'pointer', fontWeight: '700', fontSize: '11px', transition: 'all 0.2s', boxShadow: docChatDisabled || !activeDocChat || !docMsgInput.trim() ? 'none' : '0 4px 12px rgba(139, 126, 255, 0.3)' }}>
                          {docSending ? '...' : (
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                          )}
                        </button>
                      </form>
                    </div>
                  </>
                ) : (
                  <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#94A3B8', background: '#F8FAFC' }}>
                    <div style={{ fontSize: '32px', marginBottom: '24px' }}></div>
                    <div style={{ fontSize: '11px', fontWeight: '500' }}>Select a doctor from the sidebar to start corresponding.</div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}