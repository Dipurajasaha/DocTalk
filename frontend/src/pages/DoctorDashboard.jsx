import { useState, useEffect, useMemo, useRef } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useLocation, useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { authApi, doctorApi, patientApi } from '../lib/api';
import { createRealTimeClient } from '../lib/realTimeClient';
import '../styles/doctor.css';
import '../styles/chat.css';
import CopilotPanel from '../components/CopilotPanel';
import { useNotifications } from '../contexts';
import DoctorPrescriptionsList from './DoctorPrescriptionsList';
import PrescriptionComposer from './PrescriptionComposer';
import AiProcessingCard from '../components/AiProcessingCard';

const timeSlots = [];
for (let h = 0; h < 24; h++) {
  for (let m = 0; m < 60; m += 30) {
    const hour = h === 0 ? 12 : (h > 12 ? h - 12 : h);
    const ampm = h < 12 ? 'AM' : 'PM';
    const mins = m === 0 ? '00' : '30';
    timeSlots.push(`${hour}:${mins} ${ampm}`);
  }
}

const specs = ['General Medicine', 'Cardiology', 'Neurology', 'Orthopedics', 'Dermatology', 'Pediatrics', 'Gynecology', 'Oncology', 'Ophthalmology', 'ENT', 'Psychiatry', 'Radiology', 'Anesthesiology', 'Urology', 'Endocrinology', 'Nephrology', 'Gastroenterology', 'Pulmonology', 'Rheumatology', 'Other'];

const getAvatarFallback = (name = 'Doctor') => {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
      <defs>
        <linearGradient id="docbg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#8B7EFF"/>
          <stop offset="100%" stop-color="#6C5CE7"/>
        </linearGradient>
      </defs>
      <rect width="160" height="160" rx="32" fill="url(#docbg)"/>
      <circle cx="80" cy="62" r="28" fill="rgba(255,255,255,0.9)"/>
      <path d="M34 138c8-22 25-34 46-34s38 12 46 34" fill="rgba(255,255,255,0.9)"/>
      <path d="M72 26h16v16h16v16H88v16H72V58H56V42h16z" fill="#6C5CE7"/>
    </svg>
  `.trim();
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
};

const CustomCalendar = ({ selectedDate, onDateSelect, dashboardData, slotsData }) => {
  const [currentMonth, setCurrentMonth] = useState(new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1));

  // Sync currentMonth with selectedDate if it moves completely
  useEffect(() => {
    setCurrentMonth(new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1));
  }, [selectedDate]);

  const formatObjToDate = (d) => {
    const tzOffset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - tzOffset).toISOString().split('T')[0];
  };

  const todayStr = formatObjToDate(new Date());

  const handlePrevMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };

  const getDaysInMonth = (year, month) => new Date(year, month + 1, 0).getDate();
  const getFirstDayOfMonth = (year, month) => {
    let day = new Date(year, month, 1).getDay();
    return day === 0 ? 6 : day - 1; // Mon-Sun
  };

  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);

  const days = [];
  for (let i = 0; i < firstDay; i++) days.push(null);
  for (let i = 1; i <= daysInMonth; i++) days.push(new Date(year, month, i));

  const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  return (
    <div style={{ padding: '20px', fontFamily: 'inherit', minHeight: '320px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <button onClick={handlePrevMonth} style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', cursor: 'pointer', padding: '6px 12px', fontSize: '14px', color: '#64748B', transition: 'all 0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
        </button>
        <span style={{ fontWeight: '600', fontSize: '15px', color: '#1E293B', letterSpacing: '0.02em' }}>{monthNames[month]} {year}</span>
        <button onClick={handleNextMonth} style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', cursor: 'pointer', padding: '6px 12px', fontSize: '14px', color: '#64748B', transition: 'all 0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: '0 0 auto' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '5px', textAlign: 'center', marginBottom: '12px' }}>
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(d => (
          <div key={d} style={{ fontSize: '11px', fontWeight: '700', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{d}</div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px' }}>
        {days.map((date, i) => {
          if (!date) return <div key={`empty-${i}`} />;

          const dateStr = formatObjToDate(date);
          const isPast = dateStr < todayStr;
          const isSelected = formatObjToDate(selectedDate) === dateStr;

          const hasSession = dashboardData?.upcoming_schedules?.some(s => formatObjToDate(new Date(s.appointmentDate || s.scheduled_time)) === dateStr);
          const hasRequest = dashboardData?.requests?.some(r => formatObjToDate(new Date(r.requested_at || r.created_at || r.appointmentDate || Date.now())) === dateStr);
          const hasOpen = slotsData && slotsData[dateStr] && Object.values(slotsData[dateStr]).includes('open');

          const hasPending = hasRequest || hasOpen;

          let circleBg = "transparent";
          let textColor = "#334155";
          let dotColor = null;

          if (!isPast) {
            if (hasPending) {
              circleBg = "#fef3c7"; // yellow-100
              dotColor = "#f59e0b"; // amber-500
            } else if (hasSession) {
              circleBg = "#dcfce7"; // emerald-100
              dotColor = "#10b981"; // emerald-500
            }
          }

          if (isSelected) {
            circleBg = "#8B7EFF";
            textColor = "#fff";
            dotColor = null;
          }

          return (
            <div
              key={i}
              onClick={() => !isPast && onDateSelect(date)}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '44px',
                cursor: isPast ? 'not-allowed' : 'pointer',
                opacity: isPast ? 0.4 : 1,
                pointerEvents: isPast ? 'none' : 'auto'
              }}
            >
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: circleBg,
                color: textColor,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '13px',
                fontWeight: isSelected ? '600' : '500',
                transition: 'all 0.2s',
                border: (!isSelected && (hasPending || hasSession) && !isPast) ? '1px solid #e2e8f0' : '1px solid transparent'
              }}>
                {date.getDate()}
              </div>
              <div style={{ height: '4px', marginTop: '3px' }}>
                {dotColor && !isSelected && (
                  <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: dotColor }} />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const hydrateSlotsData = (slots = []) => {
  const nextSlotsData = {};

  (Array.isArray(slots) ? slots : []).forEach((slot) => {
    const start = new Date(slot?.startTime);
    if (Number.isNaN(start.getTime())) return;
    const tzOffset = start.getTimezoneOffset() * 60000;
    const dayKey = new Date(start.getTime() - tzOffset).toISOString().split('T')[0];
    const hour = start.getHours();
    const minute = start.getMinutes();
    const displayHour = hour === 0 ? 12 : (hour > 12 ? hour - 12 : hour);
    const ampm = hour < 12 ? 'AM' : 'PM';
    const mins = minute === 0 ? '00' : String(minute).padStart(2, '0');
    const label = `${displayHour}:${mins} ${ampm}`;

    if (!nextSlotsData[dayKey]) nextSlotsData[dayKey] = {};
    nextSlotsData[dayKey][label] = slot?.isBooked ? 'booked' : slot?.isActive === false ? 'none' : 'open';
  });

  return nextSlotsData;
};

export default function DoctorDashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(null);
  const { markExpired, logout, session } = useSession();
  const [activeTab, setActiveTab] = useState(() => {
    try {
      const tab = new URLSearchParams(window.location.search).get('tab');
      if (['dashboard', 'sessions', 'patientchats', 'assistant', 'payments', 'settings', 'prescriptions'].includes(tab)) return tab;
      return localStorage.getItem('doctalk_doctor_active_tab') || 'dashboard';
    } catch (e) {
      return 'dashboard';
    }
  });
  const [dashboardData, setDashboardData] = useState(null);
  const [earningsData, setEarningsData] = useState(null);
  const [manageSessionTab, setManageSessionTab] = useState(() => {
    try {
      return localStorage.getItem('doctalk_doctor_manage_session_tab') || 'upcoming';
    } catch (e) {
      return 'upcoming';
    }
  });
  const [slotDateObj, setSlotDateObj] = useState(new Date());
  const currentDoctorId = String(user?.doctor_id || user?.doctorId || user?.user_id || '').trim();
  // Helper to format local date YYYY-MM-DD
  const formatObjToDate = (d) => {
    const tzOffset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - tzOffset).toISOString().split('T')[0];
  };
  const [slotDate, setSlotDate] = useState(formatObjToDate(new Date()));
  const [slotsData, setSlotsData] = useState({});
  const { addNotification } = useNotifications();
  const [sessionTypeFilterOpen, setSessionTypeFilterOpen] = useState(false);
  const [sessionTypeFilter, setSessionTypeFilter] = useState('');

  const patientList = useMemo(() => {
    const appointments = Array.isArray(dashboardData?.appointments) ? dashboardData.appointments : [];
    const patientMap = new Map();

    appointments.forEach((appointment) => {
      const patient = appointment?.patient || {};
      const patientId = String(
        patient?.id
        || appointment?.patient_id
        || appointment?.patientId
        || appointment?.patientUsername
        || appointment?.patient
        || '',
      ).trim();
      const patientName = String(
        patient?.user?.username
        || patient?.user?.name
        || patient?.name
        || appointment?.patient_display
        || appointment?.patient
        || patientId,
      ).trim();
      const uniqueKey = patientId || patientName;

      if (!uniqueKey || patientMap.has(uniqueKey)) return;
      patientMap.set(uniqueKey, {
        id: patientId || uniqueKey,
        name: patientName || patientId || uniqueKey,
      });
    });

    return Array.from(patientMap.values());
  }, [dashboardData?.appointments]);

  const setActiveTabFromNav = (tab) => {
    const nextTab = ['dashboard', 'sessions', 'patientchats', 'assistant', 'payments', 'settings', 'prescriptions'].includes(tab) ? tab : 'dashboard';
    setActiveTab(nextTab);
    if (nextTab === 'prescriptions') setPrescriptionView('list');
    navigate(`/doctor/dashboard?tab=${encodeURIComponent(nextTab)}`);
  };

  useEffect(() => {
    try {
      const tab = new URLSearchParams(location.search).get('tab');
      if (['dashboard', 'sessions', 'patientchats', 'assistant', 'payments', 'settings', 'prescriptions'].includes(tab)) {
        setActiveTab((current) => (current === tab ? current : tab));
      }
    } catch (e) { }
  }, [location.search]);

  useEffect(() => {
    if (activeTab !== 'prescriptions') return;
    setPrescriptionView((current) => current || 'list');
  }, [activeTab]);

  // Patient Chat States
  const [patientChatList, setPatientChatList] = useState([]);
  const [activePatient, setActivePatient] = useState(null);
  const [consultations, setConsultations] = useState([]);
  const [patientMessagePage, setPatientMessagePage] = useState(1);
  const [patientMessages, setPatientMessages] = useState([]);
  const [patientMsgInput, setPatientMsgInput] = useState('');
  const [patientInputFocused, setPatientInputFocused] = useState(false);
  const [chatDisabled, setChatDisabled] = useState(false);
  const [prescriptionView, setPrescriptionView] = useState('list');
  const patientChatEndRef = useRef(null);
  const patientAutoScrollRef = useRef(false);
  const patientChatRealtimeRef = useRef(null);
  const patientChatSnapshotRef = useRef({ consultationId: null, fingerprint: '' });

  useEffect(() => {
    try {
      localStorage.setItem('doctalk_doctor_active_tab', activeTab);
    } catch (e) { }
  }, [activeTab]);

  useEffect(() => {
    try {
      localStorage.setItem('doctalk_doctor_manage_session_tab', manageSessionTab);
    } catch (e) { }
  }, [manageSessionTab]);

  // 1. Fetch Doctor Session on Mount
  useEffect(() => {
    // Prefer session from central provider when available
    if (session) {
      setUser(session);
      return;
    }

    const token = localStorage.getItem('doctalk_token');
    if (!token) {
      navigate('/login');
      return;
    }
    authApi.me(token)
      .then(data => {
        if (!data) {
          console.error('Session fetch returned empty/malformed payload');
          try { markExpired(); } catch (e) { }
          navigate('/login');
          return;
        }
        setUser(data);
      })
      .catch((err) => {
        console.error('Session fetch failed:', err);
        try { markExpired(); } catch (e) { }
        navigate('/login');
      });
  }, [navigate, session]);

  // 2. Fetch Dashboard Data
  useEffect(() => {
    if (!user) return;

    let cancelled = false;

    const loadDashboard = async () => {
      try {
        const [consultationResult, dashboardResult] = await Promise.allSettled([
          patientApi.listConsultations(),
          doctorApi.dashboardData(currentDoctorId),
        ]);

        if (cancelled) return;

        const consultationData = consultationResult.status === 'fulfilled' ? consultationResult.value : [];
        const dashboardDataResponse = dashboardResult.status === 'fulfilled' ? dashboardResult.value : null;

        setConsultations(Array.isArray(consultationData) ? consultationData : []);

        if (!dashboardDataResponse) {
          if (dashboardResult.status === 'rejected') {
            console.error('Failed loading doctor dashboard:', dashboardResult.reason);
          }
          console.error('Doctor dashboard returned empty/malformed payload');
          return;
        }

        if (dashboardDataResponse.success) {
          setDashboardData(dashboardDataResponse);
          setSlotsData(hydrateSlotsData(dashboardDataResponse.slots || []));

          const pSet = new Map();
          (dashboardDataResponse.upcoming_schedules || []).forEach(s => {
            const pid = String(s.patient || s.patient_id || '').trim();
            if (!pid) return;
            if (!pSet.has(pid)) pSet.set(pid, { id: pid, display: s.patient || s.patient_display || pid, lastStatus: 'confirmed' });
          });
          (dashboardDataResponse.requests || []).forEach(r => {
            const pid = String(r.patient || r.patient_id || '').trim();
            if (!pid) return;
            if (!pSet.has(pid)) pSet.set(pid, { id: pid, display: r.patient_display || r.patient || pid, lastStatus: r.status || 'requested' });
          });
          (dashboardDataResponse.patient_chat_patients || []).forEach(p => {
            const pid = String(p || '').trim();
            if (!pid) return;
            if (!pSet.has(pid)) pSet.set(pid, { id: pid, display: pid, lastStatus: (dashboardDataResponse.closed_chats || []).includes(pid) ? 'closed' : 'chat' });
            else if ((dashboardDataResponse.closed_chats || []).includes(pid)) pSet.get(pid).lastStatus = 'closed';
          });

          const plist = Array.from(pSet.values()).sort((a, b) => a.id.localeCompare(b.id));
          setPatientChatList(plist);
          if (plist.length > 0 && !activePatient) {
            setActivePatient(plist[0].id);
          }
        }
      } catch (err) {
        if (cancelled) return;
        console.error('Failed loading doctor dashboard:', err);
        try { if (err && (err.status === 401 || err.status === 403)) markExpired(); } catch (e) { }
        try { addNotification && addNotification({ type: 'error', message: 'Failed loading dashboard data' }); } catch (e) { }
      }
    };

    loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [user, activeTab, currentDoctorId]);

  // Fetch real earnings from DB whenever the payments tab becomes active
  useEffect(() => {
    if (activeTab !== 'payments' || !user) return;
    let cancelled = false;
    doctorApi.getEarnings()
      .then((data) => { if (!cancelled) setEarningsData(data); })
      .catch((err) => { console.error('Failed to load earnings:', err); });
    return () => { cancelled = true; };
  }, [activeTab, user]);

  function normalizeChatMessage(item) {
    return {
      id: item?.id,
      senderId: item?.sender_id || item?.senderId || item?.sender || '',
      sender: item?.sender_role || item?.senderRole || item?.sender || '',
      text: item?.message ?? item?.text ?? '',
      timestamp: item?.timestamp || item?.created_at || item?.createdAt || null,
    };
  }

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

  const resolveConsultationForPatient = (patientId) => {
    const matchId = String(patientId || '');
    return consultations.find((item) => String(item.patient_id || item.patientId || item.patientUsername || '') === matchId) || null;
  };

  const resolveAppointmentForPatient = (patientId) => {
    const matchId = String(patientId || '');
    const candidates = (dashboardData?.upcoming_schedules || []).filter((item) => String(item.patient || item.patient_id || item.patientUsername || '') === matchId)
      .concat((dashboardData?.requests || []).filter((item) => String(item.patient || item.patient_id || item.patientUsername || '') === matchId));
    return candidates[0] || null;
  };

  const ensureConsultationForPatient = async (patientId) => {
    const existing = resolveConsultationForPatient(patientId);
    if (existing?.id) return existing.id;

    const appointment = resolveAppointmentForPatient(patientId);
    if (!appointment?.appointment_id && !appointment?.id) return null;

    const created = await patientApi.createConsultation(appointment.appointment_id || appointment.id);
    return created?.id || created?.consultation_id || created?.consultationId || null;
  };

  // Handle Loading Patient Chat
  useEffect(() => {
    if (activeTab !== 'patientchats' || !activePatient) {
      patientChatRealtimeRef.current?.stop();
      patientChatRealtimeRef.current = null;
      patientChatSnapshotRef.current = { consultationId: null, fingerprint: '' };
      return;
    }

    let cancelled = false;

    const bootstrapPatientChat = async () => {
      const consultationId = await ensureConsultationForPatient(activePatient);
      if (cancelled) return;

      if (!consultationId) {
        patientChatRealtimeRef.current?.stop();
        patientChatRealtimeRef.current = null;
        patientChatSnapshotRef.current = { consultationId: null, fingerprint: '' };
        setPatientMessages([]);
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
          const latestMessages = normalizeChatMessages(payload).filter((message) => String(message.senderId || '').toLowerCase() !== 'doctalk-ai');
          patientChatSnapshotRef.current = {
            consultationId,
            fingerprint: latestMessages.map((message, index) => getChatMessageKey(message, index)).join('|'),
          };
          setPatientMessages((currentMessages) => mergeChronologicalMessages(currentMessages, latestMessages));
          setPatientMessagePage(1);
          setChatDisabled(false);
          patientAutoScrollRef.current = true;
        },
        onError: (error) => {
          if (!cancelled) {
            console.error('Doctor chat realtime error:', error);
          }
        },
      });

      patientChatRealtimeRef.current?.stop();
      patientChatRealtimeRef.current = client;

      await loadPatientChat(consultationId, 1);
      if (!cancelled && patientChatRealtimeRef.current === client) {
        client.start();
      }
    };

    bootstrapPatientChat();

    return () => {
      cancelled = true;
      patientChatRealtimeRef.current?.stop();
      patientChatRealtimeRef.current = null;
    };
  }, [activeTab, activePatient, consultations, dashboardData]);

  const loadPatientChat = async (consultationId, page = 1) => {
    try {
      if (!consultationId) {
        setPatientMessages([]);
        return;
      }
      patientAutoScrollRef.current = true;
      const data = await patientApi.getConsultationMessages(consultationId, page, 20);
      const items = normalizeChatMessages(data).filter((message) => String(message.senderId || '').toLowerCase() !== 'doctalk-ai');
      setPatientMessages((currentMessages) => page === 1
        ? mergeChronologicalMessages(currentMessages, items)
        : mergeChronologicalMessages(items, currentMessages));
      setPatientMessagePage(page);
      setChatDisabled(false);
      patientChatSnapshotRef.current = {
        consultationId,
        fingerprint: items.map((message, index) => getChatMessageKey(message, index)).join('|'),
      };
    } catch (err) { console.error(err); }
  };

  const handlePatientChatSubmit = async (e) => {
    e.preventDefault();
    const consultationId = await ensureConsultationForPatient(activePatient);
    if (!patientMsgInput.trim() || !consultationId) return;
    try {
      await patientApi.postConsultationMessage(consultationId, patientMsgInput);
      patientAutoScrollRef.current = true;
      setPatientMsgInput('');
      loadPatientChat(consultationId, patientMessagePage);
    } catch (err) { console.error(err); }
  };

  useEffect(() => {
    if (patientAutoScrollRef.current) {
      patientChatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      patientAutoScrollRef.current = false;
    }
  }, [patientMessages]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (!e.target.closest('.settings-dropdown-container')) {
        const dropdown = document.querySelector('.settings-dropdown-container > div.neu-convex');
        if (dropdown) dropdown.style.display = 'none';
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 3. Handle Logout
  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      try { localStorage.removeItem('doctalk_token'); localStorage.removeItem('doctalk_session'); } catch (e) { }
    }
    navigate('/login');
  };

  const [isUploadingProfilePic, setIsUploadingProfilePic] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const handleDoctorProfilePicUpload = async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    setIsUploadingProfilePic(true);
    try {
      const formData = new FormData();
      formData.append('profile_pic', file);
      const token = localStorage.getItem('doctalk_token');
      const res = await fetch('/api/update_patient_profile', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
        credentials: 'include',
      });
      const data = await res.json();
      if (data && data.success) {
        setUser((prev) => ({ ...prev, profile_pic: data.profile_pic }));
        try { addNotification({ type: 'success', message: 'Profile picture updated' }); } catch (e) { }
      } else {
        try { addNotification({ type: 'error', message: 'Failed to update profile picture' }); } catch (e) { }
      }
    } catch (err) {
      console.error(err);
      try { addNotification({ type: 'error', message: 'Error updating profile picture' }); } catch (e) { }
    } finally {
      setIsUploadingProfilePic(false);
      if (event.target) event.target.value = '';
    }
  };

  const renderDashboardTab = () => {
    if (!dashboardData) return <div style={{ height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}><div style={{ transform: 'scale(1.1)' }}><AiProcessingCard active={true} status="Loading Dashboard..." /></div></div>;

    // Real monthly patient data from DB (last 6 months), falls back to empty months
    const monthlyData = dashboardData.monthly_patient_data?.length
      ? dashboardData.monthly_patient_data
      : [];

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <h1 className="doc-h1">Dashboard</h1>

        <div className="doc-cards" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
          <div className="doc-card">
            <h3>Total Requests</h3>
            <div className="doc-value">{dashboardData.total_requests || 0}</div>
          </div>
          <div className="doc-card">
            <h3>Unique Patients</h3>
            <div className="doc-value">{dashboardData.total_patients || 0}</div>
          </div>
          <div className="doc-card">
            <h3 style={{ color: 'var(--accent-primary)' }}>Upcoming</h3>
            <div className="doc-value">{dashboardData.upcoming_schedules?.length || 0}</div>
          </div>
          <div className="doc-card">
            <h3 style={{ color: 'var(--accent-primary)' }}>Pending Requests</h3>
            <div className="doc-value">{dashboardData.requests?.length || 0}</div>
          </div>
          <div className="doc-card">
            <h3 style={{ color: 'var(--accent-primary)' }}>Monthly Revenue</h3>
            <div className="doc-value">₹{(dashboardData.monthly_revenue ?? 0).toLocaleString('en-IN')}</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', alignItems: 'stretch' }}>
          {/* Monthly Patients Chart */}
          <div className="doc-section line-chart-container" style={{ flex: '2 1 400px', margin: 0, outline: 'none', display: 'flex', flexDirection: 'column' }}>
            <h3>Monthly Patients</h3>

            <div style={{ width: '100%', flex: 1, minHeight: '220px', marginTop: '10px', outline: 'none' }}>
              <ResponsiveContainer width="100%" height="100%" style={{ outline: 'none' }}>
                <LineChart data={monthlyData} style={{ outline: 'none' }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#6B6B6B', fontSize: 13 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#6B6B6B', fontSize: 13 }} dx={-10} />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', background: 'var(--bg-base)', boxShadow: '6px 6px 12px var(--shadow-dark), -6px -6px 12px var(--shadow-light)' }} />
                  <Line type="monotone" dataKey="patients" stroke="#6C5CE7" strokeWidth={3} dot={{ r: 4, fill: '#6C5CE7', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 6 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Sessions Card */}
          <div className="doc-section" style={{ flex: '1 1 300px', margin: 0, display: 'flex', flexDirection: 'column' }}>
            {/* Header Row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
              <h3 style={{ margin: 0, color: '#6C5CE7', fontSize: '18px', fontWeight: '700' }}>Sessions</h3>
              <a href="#" onClick={(e) => { e.preventDefault(); setActiveTabFromNav('sessions'); setManageSessionTab('upcoming'); }} style={{ color: '#0ea5e9', textDecoration: 'none', fontSize: '14px', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '4px' }}>
                View all Sessions <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
              </a>
            </div>

            {/* Sub-title */}
            <div style={{ color: '#64748B', fontSize: '14px', marginBottom: '10px' }}>
              You have {dashboardData.upcoming_schedules?.length || 0} sessions this week
            </div>

            {/* Divider */}
            <div style={{ borderBottom: '1px solid #E2E8F0', marginBottom: '12px', width: '100%' }}></div>

            {/* Context Row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ margin: 0, fontSize: '15px', color: '#1E293B', fontWeight: '700' }}>
                  {dashboardData.upcoming_schedules?.length > 0 ? "Next Session" : "Today"}
                </span>
                <span style={{ color: '#64748B', fontSize: '15px' }}>
                  {dashboardData.upcoming_schedules?.length > 0 ? new Date(dashboardData.upcoming_schedules[0].scheduled_time).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                </span>
              </div>
              <div className="neu-convex" style={{ padding: '4px 12px', borderRadius: '50px', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: '500' }}>
                {dashboardData.upcoming_schedules?.length || 0} Sessions
              </div>
            </div>

            {/* Inner Content Box */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              {dashboardData.upcoming_schedules?.length > 0 ? (
                (() => {
                  const s = dashboardData.upcoming_schedules[0];
                  return (
                    <div className="neu-flat" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', borderRadius: '12px', padding: '20px 16px' }}>
                      <div className="neu-convex" style={{ color: 'var(--accent-primary)', padding: '6px 16px', borderRadius: '50px', fontSize: '12px', fontWeight: '700', marginBottom: '10px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                        UPCOMING
                      </div>
                      <div style={{ fontSize: '22px', fontWeight: '700', color: '#1E293B', marginBottom: '12px' }}>
                        {s.patient}
                      </div>
                      <div style={{ fontSize: '14px', color: '#64748B', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '16px', fontWeight: '500' }}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                        {new Date(s.scheduled_time).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} at {new Date(s.scheduled_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                      <button className="neu-btn-accent" style={{ borderRadius: '50px', padding: '12px 24px', fontSize: '15px', fontWeight: '600', cursor: 'pointer', transition: 'all 0.2s', width: '100%', maxWidth: '240px' }}>
                        Join Session
                      </button>
                    </div>
                  );
                })()
              ) : (
                <div className="neu-flat" style={{ borderRadius: '12px', padding: '24px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <div className="neu-convex" style={{ width: '48px', height: '48px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px', color: 'var(--text-secondary)' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65  0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
                  </div>
                  <span style={{ color: '#64748B', fontSize: '14px', fontWeight: '500' }}>No upcoming sessions</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="doc-section doc-table-wrapper">
          <h3>Requested Appointments</h3>
          <table className="doc-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Requested At</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {dashboardData.requests?.length > 0 ? dashboardData.requests.map((r, i) => (
                <tr key={i}>
                  <td>{r.patient_display || r.patient}</td>
                  <td>{new Date(r.requested_at).toLocaleString()}</td>
                  <td><span className="doc-badge">{String(r.status || '').toUpperCase()}</span></td>
                  <td>
                    <input type="datetime-local" id={`time-${r.id || r.appointment_id}`} className="neu-input" style={{ fontSize: '11px', marginRight: '8px' }} />
                    <button onClick={() => {
                      const t = document.getElementById(`time-${r.id || r.appointment_id}`).value;
                      if (!t) return addNotification && addNotification({ type: 'error', message: 'Select time' });
                      const token = localStorage.getItem('doctalk_token');
                      fetch(`/api/appointments/${r.id || r.appointment_id}/action`, {
                        method: 'PUT', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, credentials: 'include',
                        body: JSON.stringify({ status: 'ACCEPT', assignedDate: t, doctorMessage: '' })
                      }).then(res => res.json()).then(data => {
                        if (data && (data.id || data.success)) {
                          addNotification && addNotification({ type: 'success', message: 'Scheduled!' });
                          // Refresh dashboard data
                          doctorApi.dashboardData(currentDoctorId).then((newData) => setDashboardData(newData));
                        }
                      });
                    }} className="neu-btn-accent" style={{ padding: '8px 16px', borderRadius: '50px', cursor: 'pointer', fontSize: '12px', fontWeight: '600', transition: '0.2s' }}>Accept</button>
                  </td>
                </tr>
              )) : (
                <tr><td colSpan="4" style={{ textAlign: 'center', color: '#777' }}>No requests pending</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderTabs = () => {
    switch (activeTab) {
      case 'dashboard': return renderDashboardTab();
      case 'sessions': return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', minHeight: '100%', flex: 1 }}>
          <h1 className="doc-h1">Manage Sessions</h1>
          {/* Top Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', gap: '30px' }}>
            <button
              onClick={() => setManageSessionTab('upcoming')}
              style={{ background: 'none', border: 'none', borderBottom: manageSessionTab === 'upcoming' ? '2px solid var(--accent-primary)' : '2px solid transparent', padding: '10px 0', fontSize: '15px', fontWeight: '500', color: manageSessionTab === 'upcoming' ? 'var(--accent-primary)' : 'var(--text-secondary)', cursor: 'pointer', outline: 'none', transition: 'all 0.2s' }}
            >
              Upcoming Sessions
            </button>
            <button
              onClick={() => setManageSessionTab('completed')}
              style={{ background: 'none', border: 'none', borderBottom: manageSessionTab === 'completed' ? '2px solid var(--accent-primary)' : '2px solid transparent', padding: '10px 0', fontSize: '15px', fontWeight: '500', color: manageSessionTab === 'completed' ? 'var(--accent-primary)' : 'var(--text-secondary)', cursor: 'pointer', outline: 'none', transition: 'all 0.2s' }}
            >
              Completed Sessions
            </button>
            <button
              onClick={() => setManageSessionTab('slots')}
              style={{ background: 'none', border: 'none', borderBottom: manageSessionTab === 'slots' ? '2px solid var(--accent-primary)' : '2px solid transparent', padding: '10px 0', fontSize: '15px', fontWeight: '500', color: manageSessionTab === 'slots' ? 'var(--accent-primary)' : 'var(--text-secondary)', cursor: 'pointer', outline: 'none', transition: 'all 0.2s' }}
            >
              Manage Slots
            </button>
            <button
              onClick={() => setManageSessionTab('requests')}
              style={{ background: 'none', border: 'none', borderBottom: manageSessionTab === 'requests' ? '2px solid var(--accent-primary)' : '2px solid transparent', padding: '10px 0', fontSize: '15px', fontWeight: '500', color: manageSessionTab === 'requests' ? 'var(--accent-primary)' : 'var(--text-secondary)', cursor: 'pointer', outline: 'none', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              Appointment Requests
              {dashboardData?.requests?.length > 0 && <span style={{ background: '#f59e0b', color: '#fff', fontSize: '11px', padding: '2px 8px', borderRadius: '50px' }}>{dashboardData.requests.length}</span>}
            </button>
          </div>

          {/* Filters Row (Hide for requests/slots tab) */}
          {!['requests', 'slots'].includes(manageSessionTab) && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginTop: '10px' }}>
              <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>Filter by:</span>

              <div
                style={{ position: 'relative', minWidth: '180px', outline: 'none' }}
                tabIndex={0}
                onBlur={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget)) {
                    setSessionTypeFilterOpen(false);
                  }
                }}
              >
                <div
                  className="neu-pressed"
                  style={{ padding: '10px 16px', borderRadius: '12px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px', color: 'var(--text-primary)', fontWeight: '500' }}
                  onClick={() => setSessionTypeFilterOpen(!sessionTypeFilterOpen)}
                >
                  <span>
                    {sessionTypeFilter === 'video' ? 'Video Call' : sessionTypeFilter === 'inperson' ? 'In-person' : 'Session type'}
                  </span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ transform: sessionTypeFilterOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0, marginLeft: '8px', color: 'var(--text-secondary)' }}><polyline points="6 9 12 15 18 9"></polyline></svg>
                </div>

                {sessionTypeFilterOpen && (
                  <div
                    className="neu-convex"
                    style={{ position: 'absolute', top: '100%', left: 0, right: 0, marginTop: '8px', borderRadius: '16px', zIndex: 10, overflowY: 'auto', display: 'flex', flexDirection: 'column', padding: '8px', gap: '4px' }}
                  >
                    {[
                      { id: '', label: 'Session type' },
                      { id: 'video', label: 'Video Call' },
                      { id: 'inperson', label: 'In-person' }
                    ].map((opt) => (
                      <div
                        key={opt.id}
                        style={{ padding: '10px 14px', cursor: 'pointer', fontSize: '13px', color: sessionTypeFilter === opt.id ? 'var(--accent-primary)' : 'var(--text-primary)', fontWeight: sessionTypeFilter === opt.id ? '700' : '500', borderRadius: '10px', background: sessionTypeFilter === opt.id ? 'rgba(123, 97, 255, 0.08)' : 'transparent', transition: 'background 0.2s' }}
                        onClick={() => { setSessionTypeFilter(opt.id); setSessionTypeFilterOpen(false); }}
                        onMouseEnter={(e) => { if (sessionTypeFilter !== opt.id) e.currentTarget.style.background = 'rgba(0,0,0,0.03)'; }}
                        onMouseLeave={(e) => { if (sessionTypeFilter !== opt.id) e.currentTarget.style.background = 'transparent'; }}
                      >
                        {opt.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ position: 'relative' }}>
                <input type="date" className="neu-pressed" style={{ fontSize: '13px', padding: '10px 16px', borderRadius: '12px', border: 'none', background: 'transparent', outline: 'none', color: 'var(--text-primary)', fontWeight: '500', minWidth: '150px' }} />
              </div>
              <button className="neu-btn-accent" style={{ padding: '10px 20px', borderRadius: '12px', fontSize: '13px', fontWeight: '600', cursor: 'pointer', whiteSpace: 'nowrap' }}>Apply filter</button>
              <button style={{ padding: '10px 10px', borderRadius: '12px', background: 'none', color: 'var(--text-secondary)', border: 'none', fontSize: '13px', fontWeight: '600', cursor: 'pointer', whiteSpace: 'nowrap' }}>Clear filters</button>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', marginBottom: '15px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b', margin: 0 }}>
              {manageSessionTab === 'requests' ? 'Pending Patient Requests' : manageSessionTab === 'slots' ? 'Manage Availability Slots' : 'Patient sessions'}
            </h3>
            {manageSessionTab === 'slots' && (
              <div className="neu-pressed" style={{ display: 'flex', gap: '15px', fontSize: '12px', color: '#64748B', alignItems: 'center', padding: '8px 15px', borderRadius: '12px' }}>
                <div style={{ fontWeight: '600', color: 'var(--text-primary)', marginRight: '5px' }}>Legend:</div>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: '12px', height: '12px', border: '1px dashed var(--border-subtle)', borderRadius: '3px' }}></div> Uncreated</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: '12px', height: '12px', background: 'var(--bg-base)', border: '1px solid var(--accent-primary)', borderRadius: '3px' }}></div> Open</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: '12px', height: '12px', background: 'var(--bg-base)', border: '1px solid var(--border-subtle)', borderRadius: '3px' }}></div> Booked</span>
              </div>
            )}
          </div>

          {/* Main View Area */}
          {manageSessionTab === 'slots' ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(250px, 350px) 1fr', gap: '20px', alignItems: 'start' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>

                <div className="doc-card neu-flat" style={{ padding: '0', overflow: 'hidden' }}>
                  <CustomCalendar selectedDate={slotDateObj} onDateSelect={(val) => { setSlotDateObj(val); setSlotDate(formatObjToDate(val)); }} dashboardData={dashboardData} slotsData={slotsData} />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))', gap: '10px' }}>
                {timeSlots.map((time, i) => {
                  const dayData = slotsData[slotDate] || {};
                  let state = dayData[time] || 'none';

                  // Past Date Check
                  const isPast = slotDate === formatObjToDate(new Date()) && (() => {
                    let [t, ampm] = time.split(' ');
                    let [h, m] = t.split(':').map(Number);
                    if (ampm === 'PM' && h !== 12) h += 12;
                    if (ampm === 'AM' && h === 12) h = 0;
                    const now = new Date();
                    return (h < now.getHours()) || (h === now.getHours() && m < now.getMinutes());
                  })();
                  if (slotDate < formatObjToDate(new Date())) state = 'disabled';
                  else if (isPast) state = 'disabled';

                  // Mock booking from active schedules
                  if (state !== 'disabled') {
                    const mappedSchedules = dashboardData?.upcoming_schedules || [];
                    const isRealBooked = mappedSchedules.some(s => {
                      const sDate = new Date(s.appointmentDate || s.scheduled_time);
                      if (formatObjToDate(sDate) === slotDate) {
                        const h = sDate.getHours();
                        const m = sDate.getMinutes();
                        const hour = h === 0 ? 12 : (h > 12 ? h - 12 : h);
                        const ampm = h < 12 ? 'AM' : 'PM';
                        const mins = m === 0 ? '00' : '30';
                        return `${hour}:${mins} ${ampm}` === time;
                      }
                      return false;
                    });
                    if (isRealBooked) state = 'booked';
                  }

                  const toggleSlot = () => {
                    if (state === 'booked' || state === 'disabled') return;
                    setSlotsData(prev => ({
                      ...prev, [slotDate]: { ...(prev[slotDate] || {}), [time]: state === 'open' ? 'none' : 'open' }
                    }));
                  };

                  let bg = '#fff', border = '1px dashed #cbd5e1', color = '#64748b', text = `+ ${time}`, cursor = 'pointer';
                  if (state === 'open') {
                    bg = '#ecfdf5'; border = '1px solid #10b981'; color = '#059669'; text = time;
                  } else if (state === 'booked') {
                    bg = '#f1f5f9'; border = '1px solid #e2e8f0'; color = '#94a3b8'; text = time; cursor = 'not-allowed';
                  } else if (state === 'disabled') {
                    bg = '#f8fafc'; border = '1px solid #e2e8f0'; color = '#cbd5e1'; text = time; cursor = 'not-allowed';
                  }

                  return (
                    <button key={i} onClick={toggleSlot} disabled={state === 'disabled'} style={{
                      background: bg, border: border, color: color, padding: '10px 8px', borderRadius: '8px',
                      fontSize: '12px', fontWeight: '600', cursor: cursor, transition: 'all 0.2s',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px',
                      opacity: state === 'disabled' ? 0.6 : 1
                    }}>
                      {text}
                      {state === 'open' && <span style={{ fontSize: '10px', fontWeight: '500' }}>Open</span>}
                      {state === 'booked' && <span style={{ fontSize: '10px', fontWeight: '500' }}>Booked</span>}
                    </button>
                  );
                })}
                <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end', paddingTop: '10px' }}>
                  <button onClick={() => {
                    const openSlots = Object.entries(slotsData).flatMap(([day, times]) => Object.entries(times || {}).filter(([, state]) => state === 'open').map(([time]) => ({ day, time })));
                    const payload = openSlots.map(({ day, time }) => {
                      const [t, ampm] = time.split(' ');
                      let [h, m] = t.split(':').map(Number);
                      if (ampm === 'PM' && h !== 12) h += 12;
                      if (ampm === 'AM' && h === 12) h = 0;
                      const start = new Date(`${day}T00:00:00`);
                      start.setHours(h, m, 0, 0);
                      const end = new Date(start.getTime() + 30 * 60 * 1000);
                      return { startTime: start.toISOString(), endTime: end.toISOString() };
                    });
                    doctorApi.createSlots(payload).then(() => doctorApi.dashboardData(currentDoctorId)).then((freshData) => {
                      if (freshData && freshData.success) {
                        setDashboardData(freshData);
                        setSlotsData(hydrateSlotsData(freshData.slots || []));
                      }
                      addNotification && addNotification({ type: 'success', message: 'Slots saved' });
                    }).catch(() => {
                      addNotification && addNotification({ type: 'error', message: 'Failed to save slots' });
                    });
                  }} className="neu-btn-accent" style={{ padding: '10px 18px', borderRadius: '50px', cursor: 'pointer', fontSize: '13px', fontWeight: '600' }}>Save Slots</button>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
              {manageSessionTab === 'requests' ? (
                // Requests view
                dashboardData?.requests?.length > 0 ? dashboardData.requests.map((r, i) => (
                  <div key={i} className="neu-flat" style={{ position: 'relative', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '15px', aspectRatio: '2 / 1' }}>
                    <div style={{ position: 'absolute', left: 0, top: '24px', bottom: 'auto', width: '6px', height: '40px', background: '#f59e0b', borderRadius: '0 4px 4px 0' }}></div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', paddingLeft: '8px' }}>
                      <h4 style={{ margin: 0, fontSize: '15px', fontWeight: '600', color: '#334155', lineHeight: '1.4' }}>
                        Request | {r.patient_display || r.patient}
                      </h4>
                      <span style={{ padding: '4px 12px', border: '1px solid #fcd34d', borderRadius: '50px', color: '#d97706', fontSize: '12px', fontWeight: '500', marginLeft: '10px' }}>
                        Pending
                      </span>
                    </div>

                    <div style={{ color: '#64748b', fontSize: '13px', paddingLeft: '8px' }}>
                      Requested: {new Date(r.requested_at || r.created_at || Date.now()).toLocaleDateString('en-GB')}
                    </div>

                    <div style={{ marginTop: 'auto', paddingTop: '10px', paddingLeft: '8px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      <input type="datetime-local" id={`time-manage-${r.appointment_id}`} className="neu-input" style={{ fontSize: '13px', width: '100%', boxSizing: 'border-box' }} />
                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button onClick={() => {
                          const t = document.getElementById(`time-manage-${r.appointment_id}`).value;
                          if (!t) return addNotification && addNotification({ type: 'error', message: 'Please select a date and time slot first' });
                          doctorApi.respondToAppointment(r.id || r.appointment_id, { status: 'ACCEPT', assignedDate: t, doctorMessage: '' }).then((data) => {
                            if (data && (data.id || data.success)) doctorApi.dashboardData(currentDoctorId).then((newData) => {
                              setDashboardData(newData);
                              setSlotsData(hydrateSlotsData(newData.slots || []));
                            });
                          });
                        }} className="neu-btn-accent" style={{ flex: 1, padding: '10px', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: '600' }}>Accept</button>
                        <button onClick={() => {
                          doctorApi.respondToAppointment(r.id || r.appointment_id, { status: 'REJECT', doctorMessage: 'Declined by doctor' }).then((data) => {
                            if (data && (data.id || data.success)) doctorApi.dashboardData(currentDoctorId).then((newData) => {
                              setDashboardData(newData);
                              setSlotsData(hydrateSlotsData(newData.slots || []));
                            });
                          });
                        }} style={{ flex: 1, background: '#f1f5f9', color: '#64748b', border: '1px solid #e2e8f0', padding: '10px', borderRadius: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: '600' }}>Decline</button>
                      </div>
                    </div>
                  </div>
                )) : (
                  <div style={{ color: '#64748b', fontSize: '14px', padding: '20px 0' }}>No pending requests.</div>
                )
              ) : (
                // Upcoming/Completed view
                (manageSessionTab === 'upcoming' ? dashboardData?.upcoming_schedules : dashboardData?.completed_schedules)?.length > 0 ? (manageSessionTab === 'upcoming' ? dashboardData?.upcoming_schedules : dashboardData?.completed_schedules).map((s, i) => (
                  <div key={i} className="neu-flat" style={{
                    position: 'relative', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '15px', overflow: 'hidden', aspectRatio: '2 / 1'
                  }}>
                    {/* Left accent */}
                    <div style={{ position: 'absolute', left: 0, top: '24px', bottom: 'auto', width: '6px', height: '40px', background: manageSessionTab === 'completed' ? '#10b981' : '#8B7EFF', borderRadius: '0 4px 4px 0' }}></div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', paddingLeft: '8px' }}>
                      <h4 style={{ margin: 0, fontSize: '15px', fontWeight: '600', color: '#334155', lineHeight: '1.4' }}>
                        Consultation | {s.patient_display || s.patient} | {s.reason || 'General Follow-up'}
                      </h4>
                      <span style={{ padding: '4px 12px', border: manageSessionTab === 'completed' ? '1px solid #10b981' : '1px solid #c4b5fd', borderRadius: '50px', color: manageSessionTab === 'completed' ? '#10b981' : '#8B7EFF', fontSize: '12px', fontWeight: '500', marginLeft: '10px', background: manageSessionTab === 'completed' ? '#ecfdf5' : '#f3f0ff' }}>
                        {manageSessionTab === 'completed' ? 'COMPLETED' : 'CONFIRMED'}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '13px', paddingLeft: '8px' }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                      {new Date(s.appointmentDate || s.scheduled_time).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })} at {new Date(s.appointmentDate || s.scheduled_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>

                    <div style={{ margin: 0, fontSize: '13px', color: '#64748b', lineHeight: '1.6', paddingLeft: '8px', display: 'grid', gap: '6px' }}>
                      <div><strong style={{ color: '#334155' }}>Reason:</strong> {s.reason || 'General follow-up'}</div>
                      {String(s.note || '').trim() && <div><strong style={{ color: '#334155' }}>Note:</strong> {s.note}</div>}
                    </div>

                    {manageSessionTab !== 'completed' && (
                      <div style={{ marginTop: 'auto', paddingTop: '10px', paddingLeft: '8px' }}>
                        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                          <button onClick={() => {
                            const token = localStorage.getItem('doctalk_token');
                            fetch(`/api/appointments/${s.id}/action`, {
                              method: 'PUT', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, credentials: 'include',
                              body: JSON.stringify({ status: 'COMPLETE', doctorMessage: 'Completed session' })
                            }).then(r => r.json()).then(d => {
                              if (d && (d.id || d.success)) doctorApi.dashboardData(currentDoctorId).then((newData) => {
                                setDashboardData(newData);
                                setSlotsData(hydrateSlotsData(newData.slots || []));
                              });
                            });
                          }}
                            style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#8B7EFF', background: 'none', border: 'none', fontSize: '14px', fontWeight: '500', cursor: 'pointer', padding: 0 }}
                          >
                            Complete Session <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 16 16 12 12 8"></polyline><line x1="8" y1="12" x2="16" y2="12"></line></svg>
                          </button>
                          <button onClick={() => {
                            if (!window.confirm('Cancel this session?')) return;
                            doctorApi.cancelAppointment(s.id).then((response) => {
                              if (response && (response.id || response.success || response.message)) {
                                return doctorApi.dashboardData(currentDoctorId).then((newData) => {
                                  setDashboardData(newData);
                                  setSlotsData(hydrateSlotsData(newData.slots || []));
                                });
                              }
                              throw new Error('Unable to cancel session');
                            }).catch(() => {
                              addNotification && addNotification({ type: 'error', message: 'Failed to cancel session' });
                            });
                          }}
                            style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#ef4444', background: 'transparent', border: '1px solid #ef4444', borderRadius: '999px', fontSize: '14px', fontWeight: '600', cursor: 'pointer', padding: '8px 14px' }}
                          >
                            Cancel Session
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )) : (
                  <div style={{ color: '#64748b', fontSize: '14px', padding: '20px 0' }}>No {manageSessionTab} sessions found.</div>
                )
              )}
            </div>
          )}
        </div>
      );
      case 'patientchats': return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', height: '100%' }}>
          <div className="neu-flat" style={{ display: 'flex', flex: 1, padding: 0, overflow: 'hidden', borderRadius: '18px', minHeight: '500px' }}>
            {/* Patient List Sidebar */}
            <div style={{ width: '250px', borderRight: '1px solid var(--border-subtle)', background: 'transparent', display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '15px', fontWeight: 'bold', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}>Patients</div>
              <div style={{ overflowY: 'auto', flex: 1 }}>
                {patientChatList.map(p => (
                  <div
                    key={p.id}
                    onClick={() => setActivePatient(p.id)}
                    style={{
                      padding: '12px 15px', cursor: 'pointer', borderBottom: '1px solid var(--border-subtle)',
                      borderLeft: activePatient === p.id ? '4px solid var(--accent-primary)' : '4px solid transparent'
                    }}
                    className={activePatient === p.id ? 'neu-pressed' : ''}
                  >
                    <div style={{ fontWeight: '500', fontSize: '14px', color: 'var(--text-primary)' }}>{p.display}</div>
                    <div style={{ fontSize: '11px', color: p.lastStatus === 'closed' ? 'red' : 'green' }}>{p.lastStatus}</div>
                  </div>
                ))}
                {patientChatList.length === 0 && <div style={{ padding: '15px', fontSize: '13px', color: '#999' }}>No patients available.</div>}
              </div>
            </div>
            {/* Chat Area */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <div className="chat-main">
                <div className="chat-header">
                  <div>
                    <div className="chat-title">Chat with {activePatient || '...'}</div>
                    <div className="chat-subtitle">{/* subtitle can show status */}</div>
                  </div>
                </div>
                <div className="chat-list">
                  {patientMessages.map((m, i) => {
                    const isOutgoing = String(m.sender || '').toLowerCase() === 'doctor';
                    return (
                      <div className={`chat-row ${isOutgoing ? 'outgoing' : 'incoming'}`} key={m.id || i}>
                        <div className={`chat-bubble ${isOutgoing ? 'outgoing' : 'incoming'}`}>
                          <div className="chat-text">{m.text}</div>
                          <div className="chat-meta"><span className="chat-time">{m.timestamp ? new Date(m.timestamp).toLocaleString() : ''}</span></div>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={patientChatEndRef} />
                </div>
              </div>
              <form onSubmit={handlePatientChatSubmit} className="neu-pressed" style={{ display: 'flex', padding: '10px 10px 10px 15px', margin: '15px', borderRadius: '9999px', gap: '10px' }}>
                <input
                  type="text"
                  value={patientMsgInput} onChange={e => setPatientMsgInput(e.target.value)}
                  onFocus={() => setPatientInputFocused(true)}
                  onBlur={() => setPatientInputFocused(false)}
                  disabled={chatDisabled || !activePatient}
                  placeholder={chatDisabled ? 'Chat closed' : 'Type message...'}
                  style={{ flex: 1, fontSize: '14px', background: 'transparent', border: 'none', outline: 'none' }}
                />
                <button disabled={chatDisabled || !activePatient} className="neu-btn-accent" style={{ padding: '10px 24px', borderRadius: '50px', cursor: 'pointer', fontWeight: '600' }}>Send</button>
              </form>
            </div>
          </div>
        </div>
      );
      case 'assistant': return (
        <CopilotPanel patientList={patientList} />
      );
      case 'payments': return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h1 className="doc-h1">Earnings & Payments</h1>
          <div className="neu-flat" style={{ display: 'flex', flexDirection: 'column', padding: '24px', borderRadius: '16px' }}>

            {/* Summary cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
              <div className="neu-convex" style={{ padding: '20px', borderRadius: '16px' }}>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', fontWeight: '600', marginBottom: '6px' }}>Total Earnings</div>
                <div style={{ fontSize: '32px', fontWeight: '700', color: 'var(--text-primary)' }}>
                  {earningsData
                    ? `₹${Math.round(earningsData.total_earnings_paise / 100).toLocaleString('en-IN')}`
                    : '...'}
                </div>
              </div>
              <div className="neu-convex" style={{ padding: '20px', borderRadius: '16px' }}>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', fontWeight: '600', marginBottom: '6px' }}>This Month</div>
                <div style={{ fontSize: '32px', fontWeight: '700', color: 'var(--accent-primary)' }}>
                  {earningsData
                    ? `₹${Math.round(earningsData.monthly_earnings_paise / 100).toLocaleString('en-IN')}`
                    : '...'}
                </div>
              </div>
              <div className="neu-convex" style={{ padding: '20px', borderRadius: '16px' }}>
                <div style={{ fontSize: '13px', color: 'var(--text-secondary)', fontWeight: '600', marginBottom: '6px' }}>Transactions</div>
                <div style={{ fontSize: '32px', fontWeight: '700', color: '#10b981' }}>
                  {earningsData ? earningsData.transactions.length : '...'}
                </div>
              </div>
            </div>

            {/* Transactions table */}
            <div className="doc-section doc-table-wrapper">
              <table className="doc-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Patient</th>
                    <th>Amount</th>
                    <th>Razorpay ID</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {!earningsData ? (
                    <tr><td colSpan="5" style={{ textAlign: 'center', color: '#777' }}>Loading...</td></tr>
                  ) : earningsData.transactions.length === 0 ? (
                    <tr><td colSpan="5" style={{ textAlign: 'center', color: '#777' }}>No payments received yet.</td></tr>
                  ) : earningsData.transactions.map((txn, i) => (
                    <tr key={i}>
                      <td>{txn.date ? new Date(txn.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}</td>
                      <td>{txn.patient}</td>
                      <td>₹{Math.round(txn.amount_paise / 100).toLocaleString('en-IN')}</td>
                      <td style={{ fontSize: '12px', color: '#64748b', fontFamily: 'monospace' }}>{txn.razorpay_payment_id || '—'}</td>
                      <td><span className="doc-badge success">Captured</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      );
      case 'prescriptions':
        return prescriptionView === 'new' ? (
          <PrescriptionComposer
            embedded
            onBack={() => setPrescriptionView('list')}
            onDone={() => setPrescriptionView('list')}
          />
        ) : (
          <DoctorPrescriptionsList
            embedded
            onCreateNew={() => setPrescriptionView('new')}
          />
        );
      case 'settings':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <h1 className="doc-h1">Settings</h1>
            <div className="neu-flat" style={{ display: 'flex', flexDirection: 'column', padding: '24px', borderRadius: '16px' }}>
              <div style={{ paddingBottom: '20px', borderBottom: '1px solid var(--border-subtle)', fontWeight: '700', color: 'var(--accent-primary)', fontSize: '18px', marginBottom: '20px' }}>Profile Settings</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '600px' }}>

                {/* ── Read-Only Fields ── */}
                <div className="neu-convex" style={{ borderRadius: '12px', padding: '16px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    <div>
                      <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', marginBottom: '4px', display: 'block' }}>Doctor ID</label>
                      <div style={{ fontSize: '14px', color: '#1e293b', fontWeight: '500' }}>{user.doctor_id || user.doctorId || user.user_id || '—'}</div>
                    </div>
                    <div>
                      <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', marginBottom: '4px', display: 'block' }}>Full Name</label>
                      <div style={{ fontSize: '14px', color: '#1e293b', fontWeight: '500' }}>{user.display_name || user.name || '—'}</div>
                    </div>
                    <div>
                      <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', marginBottom: '4px', display: 'block' }}>Gender</label>
                      <div style={{ fontSize: '14px', color: '#1e293b', fontWeight: '500' }}>{user.gender || '—'}</div>
                    </div>
                    <div>
                      <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', marginBottom: '4px', display: 'block' }}>Registration No.</label>
                      <div style={{ fontSize: '14px', color: '#1e293b', fontWeight: '500' }}>{user.registration_number || user.registrationNumber || '—'}</div>
                    </div>
                    <div>
                      <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', marginBottom: '4px', display: 'block' }}>Hospital / Clinic Name</label>
                      <div style={{ fontSize: '14px', color: '#1e293b', fontWeight: '500' }}>{user.hospital_name || user.hospitalName || '—'}</div>
                    </div>
                    <div>
                      <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', marginBottom: '4px', display: 'block' }}>Address</label>
                      <div style={{ fontSize: '14px', color: '#1e293b', fontWeight: '500' }}>{user.address || '—'}</div>
                    </div>
                    <div style={{ gridColumn: 'span 2' }}>
                      <label style={{ fontSize: '12px', fontWeight: '600', color: '#64748B', marginBottom: '4px', display: 'block' }}>Bio / About</label>
                      <div style={{ fontSize: '14px', color: '#1e293b', fontWeight: '500', whiteSpace: 'pre-wrap' }}>{user.bio || '—'}</div>
                    </div>
                  </div>
                </div>

                <div style={{ fontSize: '14px', fontWeight: '700', color: 'var(--text-primary)', marginTop: '8px' }}>Editable Fields</div>

                {/* ── Profile Picture ── */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <img
                    src={user.profile_pic || getAvatarFallback(user.display_name || user.name || 'Doctor')}
                    alt="Profile"
                    onError={(e) => { e.currentTarget.src = getAvatarFallback(user.display_name || user.name || 'Doctor'); }}
                    style={{ width: '72px', height: '72px', borderRadius: '50%', objectFit: 'cover', boxShadow: '4px 4px 8px var(--shadow-dark), -4px -4px 8px var(--shadow-light)' }}
                  />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>Profile Picture</label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleDoctorProfilePicUpload}
                      disabled={isUploadingProfilePic}
                      style={{ fontSize: '12px', color: 'var(--text-secondary)' }}
                    />
                    {isUploadingProfilePic && <span style={{ fontSize: '12px', color: 'var(--accent-primary)' }}>Uploading…</span>}
                  </div>
                </div>

                {/* ── Editable Fields ── */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>Email Address</label>
                    <input id="doc-setting-email" className="neu-input" type="email" defaultValue={user.email || ''} style={{ width: '100%', fontSize: '14px', marginTop: '6px' }} />
                  </div>
                  <div>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>Specialization</label>
                    <select id="doc-setting-specialization" className="neu-input" defaultValue={user.specialization || ''} style={{ width: '100%', fontSize: '14px', marginTop: '6px' }}>
                      <option value="">— Select specialization —</option>
                      {specs.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>Years of Experience</label>
                    <input id="doc-setting-experience" className="neu-input" type="text" defaultValue={user.experience || ''} style={{ width: '100%', fontSize: '14px', marginTop: '6px' }} />
                  </div>
                  <div>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>Hospital Location</label>
                    <input id="doc-setting-location" className="neu-input" type="text" defaultValue={user.location || user.hospital_location || user.hospitalLocation || ''} style={{ width: '100%', fontSize: '14px', marginTop: '6px' }} />
                  </div>
                  <div>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)' }}>Mobile Number</label>
                    <input id="doc-setting-mobile" className="neu-input" type="text" defaultValue={user.mobile || ''} style={{ width: '100%', fontSize: '14px', marginTop: '6px' }} />
                  </div>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <label style={{ fontSize: '13px', fontWeight: '600', color: 'var(--accent-primary)' }}>💳 Consultation Fee (₹)</label>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '6px' }}>
                      <input id="doc-setting-fee" className="neu-input" type="number" min="0" step="50" defaultValue={user.consultation_fee ? Math.round(user.consultation_fee / 100) : ''} placeholder="e.g. 500" style={{ flex: 1, fontSize: '14px' }} />
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', minWidth: '160px' }}>Patients pay this amount before an appointment is confirmed. Leave blank for the default (₹500).</div>
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <button
                    onClick={async () => {
                      const payload = {
                        email: document.getElementById('doc-setting-email').value || undefined,
                        specialization: document.getElementById('doc-setting-specialization').value || undefined,
                        experience: document.getElementById('doc-setting-experience').value || undefined,
                        location: document.getElementById('doc-setting-location').value || undefined,
                        hospital_location: document.getElementById('doc-setting-location').value || undefined,
                        mobile: document.getElementById('doc-setting-mobile').value || undefined,
                        consultation_fee: (() => {
                          const v = document.getElementById('doc-setting-fee')?.value;
                          return v && !isNaN(Number(v)) && Number(v) > 0 ? Math.round(Number(v) * 100) : undefined;
                        })(),
                      };
                      // Remove undefined/empty keys
                      Object.keys(payload).forEach(k => { if (payload[k] === undefined) delete payload[k]; });
                      try {
                        const token = localStorage.getItem('doctalk_token');
                        const res = await fetch('/api/users/me', {
                          method: 'PUT',
                          headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
                          body: JSON.stringify(payload),
                        });
                        const data = await res.json();
                        if (res.ok) {
                          addNotification && addNotification({ type: 'success', message: 'Profile updated successfully' });
                          setUser(prev => ({ ...prev, ...data }));
                        } else {
                          addNotification && addNotification({ type: 'error', message: data?.detail || 'Failed to update profile' });
                        }
                      } catch (err) {
                        addNotification && addNotification({ type: 'error', message: 'Network error' });
                      }
                    }}
                    className="neu-btn-accent"
                    style={{ padding: '12px 24px', borderRadius: '50px', cursor: 'pointer', fontWeight: '600' }}
                  >
                    Save Changes
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      default: return null;
    }
  };

  if (!user) return <div style={{ height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#F5F5F7' }}><div style={{ transform: 'scale(1.3)' }}><AiProcessingCard active={true} status="Loading Doctor Dashboard..." /></div></div>;

  return (
    <div className="doc-app-wrapper">


      <div className="doc-layout">
        {/* Mobile Header (Hidden on Desktop via CSS) */}
        <div className="doc-mobile-header" style={{ display: 'none' }}>
          <button className="doc-mobile-menu-btn" onClick={() => setIsMobileSidebarOpen(true)}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" /></svg>
          </button>
          <div className="nav-text-logo" style={{ fontSize: '24px', margin: 0 }}>
            DocTalk<span className="logo-sup" style={{ fontSize: '14.4px' }}>AI</span>
          </div>
          <div style={{ width: 24 }} /> {/* Spacer for centering */}
        </div>

        {/* Mobile Drawer Overlay */}
        <div
          className={`doc-mobile-overlay ${isMobileSidebarOpen ? 'visible' : ''}`}
          onClick={() => setIsMobileSidebarOpen(false)}
        />

        {/* Sidebar */}
        <div className={`doc-sidebar ${isMobileSidebarOpen ? 'mobile-open' : ''}`}>
          {/* Logo at the top of the sidebar */}
          <div className="nav-text-logo" style={{ alignSelf: 'flex-start', marginBottom: '30px', transform: 'scale(1.2)', transformOrigin: 'left center' }}>
            DocTalk<span className="logo-sup">AI</span>
          </div>

          <img
            src={user.profile_pic || getAvatarFallback(user.display_name || user.name || 'Doctor')}
            alt="Profile"
            onError={(e) => { e.currentTarget.src = getAvatarFallback(user.display_name || user.name || 'Doctor'); }}
          />
          <div className="doc-name">{user.display_name}</div>

          <div className="doc-nav">
            {['dashboard', 'sessions', 'patientchats', 'assistant', 'payments', 'prescriptions'].map(tab => (
              <button
                key={tab}
                onClick={() => { setActiveTabFromNav(tab); setIsMobileSidebarOpen(false); }}
                className={activeTab === tab ? 'active' : ''}
                style={tab === 'sessions' ? { textTransform: 'capitalize' } : {}}
              >
                {tab === 'patientchats' ? 'Patient Chats' : tab === 'sessions' ? 'Manage Sessions' : tab === 'prescriptions' ? 'Prescriptions' : tab}
              </button>
            ))}
          </div>

          {/* Settings Dropdown at the bottom */}
          <div style={{ marginTop: 'auto', width: '100%', position: 'relative' }} className="settings-dropdown-container">
            <button
              className="neu-flat"
              style={{ width: '100%', padding: '12px 18px', borderRadius: '9999px', textTransform: 'capitalize', color: 'var(--text-secondary)', border: 'none', cursor: 'pointer', fontSize: '14px', fontWeight: '600', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              onClick={(e) => {
                const dropdown = e.currentTarget.nextElementSibling;
                dropdown.style.display = dropdown.style.display === 'none' ? 'flex' : 'none';
              }}
            >
              Settings
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </button>
            <div style={{ display: 'none', flexDirection: 'column', position: 'absolute', bottom: '100%', left: 0, width: '100%', marginBottom: '8px', borderRadius: '14px', overflow: 'hidden', zIndex: 100 }} className="neu-convex">
              <button onClick={() => { setActiveTabFromNav('settings'); document.querySelector('.settings-dropdown-container > div').style.display = 'none'; setIsMobileSidebarOpen(false); }} style={{ padding: '12px 18px', background: 'transparent', border: 'none', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-primary)', textAlign: 'left', cursor: 'pointer', fontWeight: '500', fontSize: '13px' }}>Profile</button>
              <button onClick={handleLogout} style={{ padding: '12px 18px', background: 'transparent', border: 'none', color: '#ef4444', textAlign: 'left', cursor: 'pointer', fontWeight: '500', fontSize: '13px' }}>Logout</button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="doc-main">
          {renderTabs()}
        </div>
      </div>
    </div>
  );
}
