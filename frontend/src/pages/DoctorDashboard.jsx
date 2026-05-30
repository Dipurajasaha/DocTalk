import { useState, useEffect, useRef } from 'react';
import { useSession } from '../contexts/SessionContext';
import { useLocation, useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { authApi, doctorApi, patientApi } from '../lib/api';
import { createRealTimeClient } from '../lib/realTimeClient';
import '../styles/doctor.css';
import '../styles/chat.css';
import CopilotPanel from '../components/CopilotPanel';
import { useNotifications } from '../contexts';

const timeSlots = [];
for (let h = 0; h < 24; h++) {
  for (let m = 0; m < 60; m += 30) {
    const hour = h === 0 ? 12 : (h > 12 ? h - 12 : h);
    const ampm = h < 12 ? 'AM' : 'PM';
    const mins = m === 0 ? '00' : '30';
    timeSlots.push(`${hour}:${mins} ${ampm}`);
  }
}


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
    nextSlotsData[dayKey][label] = slot?.isBooked ? 'booked' : slot?.isActive === false ? 'inactive' : 'open';
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
      if (['dashboard', 'sessions', 'patientchats', 'assistant', 'payments', 'settings'].includes(tab)) return tab;
      return localStorage.getItem('doctalk_doctor_active_tab') || 'dashboard';
    } catch (e) {
      return 'dashboard';
    }
  });
  const [dashboardData, setDashboardData] = useState(null);
  const [manageSessionTab, setManageSessionTab] = useState(() => {
    try {
      return localStorage.getItem('doctalk_doctor_manage_session_tab') || 'upcoming';
    } catch (e) {
      return 'upcoming';
    }
  });
  const [slotDateObj, setSlotDateObj] = useState(new Date());
  // Helper to format local date YYYY-MM-DD
  const formatObjToDate = (d) => {
    const tzOffset = d.getTimezoneOffset() * 60000;
    return new Date(d.getTime() - tzOffset).toISOString().split('T')[0];
  };
  const [slotDate, setSlotDate] = useState(formatObjToDate(new Date()));
  const [slotsData, setSlotsData] = useState({});
  const { addNotification } = useNotifications();

  const setActiveTabFromNav = (tab) => {
    const nextTab = ['dashboard', 'sessions', 'patientchats', 'assistant', 'payments', 'settings'].includes(tab) ? tab : 'dashboard';
    setActiveTab(nextTab);
    navigate(`/doctor/dashboard?tab=${encodeURIComponent(nextTab)}`);
  };

  useEffect(() => {
    try {
      const tab = new URLSearchParams(location.search).get('tab');
      if (['dashboard', 'sessions', 'patientchats', 'assistant', 'payments', 'settings'].includes(tab)) {
        setActiveTab((current) => (current === tab ? current : tab));
      }
    } catch (e) {}
  }, [location.search]);

  // Patient Chat States
  const [patientChatList, setPatientChatList] = useState([]);
  const [activePatient, setActivePatient] = useState(null);
  const [consultations, setConsultations] = useState([]);
  const [patientMessagePage, setPatientMessagePage] = useState(1);
  const [patientMessages, setPatientMessages] = useState([]);
  const [patientMsgInput, setPatientMsgInput] = useState('');
  const [patientInputFocused, setPatientInputFocused] = useState(false);
  const [chatDisabled, setChatDisabled] = useState(false);
  const patientChatEndRef = useRef(null);
  const patientAutoScrollRef = useRef(false);
  const patientChatRealtimeRef = useRef(null);
  const patientChatSnapshotRef = useRef({ consultationId: null, fingerprint: '' });

  useEffect(() => {
    try {
      localStorage.setItem('doctalk_doctor_active_tab', activeTab);
    } catch (e) {}
  }, [activeTab]);

  useEffect(() => {
    try {
      localStorage.setItem('doctalk_doctor_manage_session_tab', manageSessionTab);
    } catch (e) {}
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
  }, [navigate, session]);

  // 2. Fetch Dashboard Data
  useEffect(() => {
    if (!user) return;

    let cancelled = false;

    const loadDashboard = async () => {
      try {
        const [consultationResult, dashboardResult] = await Promise.allSettled([
          patientApi.listConsultations(),
          doctorApi.dashboardData(),
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
            if (!pSet.has(pid)) pSet.set(pid, { id: pid, display: s.patient || s.patient_display || pid, lastStatus: 'scheduled' });
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
        try { if (err && (err.status === 401 || err.status === 403)) markExpired(); } catch (e) {}
        try { addNotification && addNotification({ type: 'error', message: 'Failed loading dashboard data' }); } catch (e) {}
      }
    };

    loadDashboard();
    const refreshTimer = setInterval(loadDashboard, 15000);

    return () => {
      cancelled = true;
      clearInterval(refreshTimer);
    };
  }, [user, activeTab]);

  function normalizeChatMessage(item) {
    return {
      id: item?.id,
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
        getSnapshotKey: (payload) => normalizeChatMessages(payload).map((message, index) => getChatMessageKey(message, index)).join('|'),
        onMessage: (payload) => {
          if (cancelled) return;
          const latestMessages = normalizeChatMessages(payload);
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
      const items = normalizeChatMessages(data);
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
    if(!patientMsgInput.trim() || !consultationId) return;
    try {
      await patientApi.postConsultationMessage(consultationId, patientMsgInput);
      patientAutoScrollRef.current = true;
      setPatientMsgInput('');
      loadPatientChat(consultationId, patientMessagePage);
    } catch(err) { console.error(err); }
  };

  useEffect(() => {
    if (patientAutoScrollRef.current) {
      patientChatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      patientAutoScrollRef.current = false;
    }
  }, [patientMessages]);

  // 3. Handle Logout
  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      try { localStorage.removeItem('doctalk_token'); localStorage.removeItem('doctalk_session'); } catch (e) {}
    }
    navigate('/login');
  };

  const renderDashboardTab = () => {
    if (!dashboardData) return <div>Loading dashboard data...</div>;
    
    // Mock Monthly Patients Data for Line Chart
    const monthlyData = [
      { name: 'Jan', patients: 12 }, { name: 'Feb', patients: 19 },
      { name: 'Mar', patients: 15 }, { name: 'Apr', patients: 22 },
      { name: 'May', patients: 28 }, { name: 'Jun', patients: 35 },
      { name: 'Jul', patients: 32 }
    ];

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
            <h3 style={{color: '#10b981'}}>Upcoming</h3>
            <div className="doc-value">{dashboardData.upcoming_schedules?.length || 0}</div>
          </div>
          <div className="doc-card">
            <h3 style={{color: '#f59e0b'}}>Pending Requests</h3>
            <div className="doc-value">{dashboardData.requests?.length || 0}</div>
          </div>
          <div className="doc-card">
            <h3 style={{color: '#6366f1'}}>Monthly Revenue</h3>
            <div className="doc-value">${dashboardData.monthly_revenue || '1,250'}</div>
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
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#6B6B6B', fontSize: 13}} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{fill: '#6B6B6B', fontSize: 13}} dx={-10} />
                  <Tooltip contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)'}} />
                  <Line type="monotone" dataKey="patients" stroke="#6C5CE7" strokeWidth={3} dot={{r: 4, fill: '#6C5CE7', strokeWidth: 2, stroke: '#fff'}} activeDot={{r: 6}} />
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
                  <span style={{color: '#64748B', fontSize: '15px'}}>
                    {dashboardData.upcoming_schedules?.length > 0 ? new Date(dashboardData.upcoming_schedules[0].scheduled_time).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}
                  </span>
              </div>
              <div style={{ background: '#F8FAFC', padding: '4px 12px', borderRadius: '50px', fontSize: '13px', color: '#334155', border: '1px solid #E2E8F0', fontWeight: '500' }}>
                  {dashboardData.upcoming_schedules?.length || 0} Sessions
              </div>
            </div>

            {/* Inner Content Box */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
              {dashboardData.upcoming_schedules?.length > 0 ? (
                (() => {
                  const s = dashboardData.upcoming_schedules[0];
                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', background: '#F8FAFC', borderRadius: '12px', padding: '20px 16px', border: '1px solid #E2E8F0' }}>
                      <div style={{ background: '#E6E3FF', color: '#8B7EFF', padding: '6px 16px', borderRadius: '50px', fontSize: '12px', fontWeight: '700', marginBottom: '10px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                        UPCOMING
                      </div>
                      <div style={{ fontSize: '22px', fontWeight: '700', color: '#1E293B', marginBottom: '12px' }}>
                        {s.patient}
                      </div>
                      <div style={{ fontSize: '14px', color: '#64748B', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '16px', fontWeight: '500' }}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                        {new Date(s.scheduled_time).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} at {new Date(s.scheduled_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                      </div>
                      <button style={{ background: '#8B7EFF', color: '#fff', border: 'none', borderRadius: '50px', padding: '12px 24px', fontSize: '15px', fontWeight: '600', cursor: 'pointer', transition: 'all 0.2s', width: '100%', maxWidth: '240px' }}>
                        Join Session
                      </button>
                    </div>
                  );
                })()
              ) : (
                <div style={{ background: '#F8FAFC', borderRadius: '12px', padding: '24px 20px', display: 'flex', flexDirection: 'column', alignItems: 'center', border: '1px solid #E2E8F0' }}>
                  <div style={{ width: '48px', height: '48px', background: '#E2E8F0', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px', color: '#94A3B8' }}>
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
                    <input type="datetime-local" id={`time-${r.id || r.appointment_id}`} style={{padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: '50px', fontSize: '11px', marginRight: '8px'}} />
                    <button onClick={() => {
                       const t = document.getElementById(`time-${r.id || r.appointment_id}`).value;
                       if(!t) return addNotification && addNotification({ type: 'error', message: 'Select time' });
                       fetch(`/api/appointments/${r.id || r.appointment_id}/action`, {
                         method: 'PUT', headers: {'Content-Type':'application/json'}, credentials: 'include',
                         body: JSON.stringify({ status: 'ACCEPT', assignedDate: t, doctorMessage: '' })
                       }).then(res=>res.json()).then(data=>{
                         if(data && (data.id || data.success)) {
                           addNotification && addNotification({ type: 'success', message: 'Scheduled!' });
                           // Refresh dashboard data
                           fetch('/api/doctor_dashboard_data', {credentials: 'include'}).then(res=>res.json()).then(newData=>setDashboardData(newData));
                         }
                       });
                    }} style={{background:'#8B7EFF', color:'#fff', border:'none', padding:'8px 16px', borderRadius:'50px', cursor:'pointer', fontSize:'12px', fontWeight:'600', transition:'0.2s'}}>Accept</button>
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
    switch(activeTab) {
      case 'dashboard': return renderDashboardTab();
      case 'sessions': return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', background: '#fff', borderRadius: '16px', padding: '24px', minHeight: '80vh', border: '1px solid #e2e8f0' }}>
            <h1 className="doc-h1">Manage Sessions</h1>
          {/* Top Tabs */}
          <div style={{ display: 'flex', borderBottom: '1px solid #e2e8f0', gap: '30px' }}>
            <button 
              onClick={() => setManageSessionTab('upcoming')}
              style={{ background: 'none', border: 'none', borderBottom: manageSessionTab === 'upcoming' ? '2px solid #8B7EFF' : '2px solid transparent', padding: '10px 0', fontSize: '15px', fontWeight: '500', color: manageSessionTab === 'upcoming' ? '#8B7EFF' : '#64748b', cursor: 'pointer', outline: 'none', transition: 'all 0.2s' }}
            >
              Upcoming Sessions
            </button>
            <button 
              onClick={() => setManageSessionTab('completed')}
              style={{ background: 'none', border: 'none', borderBottom: manageSessionTab === 'completed' ? '2px solid #8B7EFF' : '2px solid transparent', padding: '10px 0', fontSize: '15px', fontWeight: '500', color: manageSessionTab === 'completed' ? '#8B7EFF' : '#64748b', cursor: 'pointer', outline: 'none', transition: 'all 0.2s' }}
            >
              Completed Sessions
            </button>
            <button 
              onClick={() => setManageSessionTab('slots')}
              style={{ background: 'none', border: 'none', borderBottom: manageSessionTab === 'slots' ? '2px solid #8B7EFF' : '2px solid transparent', padding: '10px 0', fontSize: '15px', fontWeight: '500', color: manageSessionTab === 'slots' ? '#8B7EFF' : '#64748b', cursor: 'pointer', outline: 'none', transition: 'all 0.2s' }}
            >
              Manage Slots
            </button>
            <button 
              onClick={() => setManageSessionTab('requests')}
              style={{ background: 'none', border: 'none', borderBottom: manageSessionTab === 'requests' ? '2px solid #8B7EFF' : '2px solid transparent', padding: '10px 0', fontSize: '15px', fontWeight: '500', color: manageSessionTab === 'requests' ? '#8B7EFF' : '#64748b', cursor: 'pointer', outline: 'none', transition: 'all 0.2s', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              Appointment Requests
              {dashboardData?.requests?.length > 0 && <span style={{background: '#f59e0b', color: '#fff', fontSize: '11px', padding: '2px 8px', borderRadius: '50px'}}>{dashboardData.requests.length}</span>}
            </button>
          </div>

          {/* Filters Row (Hide for requests/slots tab) */}
          {!['requests', 'slots'].includes(manageSessionTab) && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginTop: '10px' }}>
                <span style={{ fontSize: '14px', fontWeight: '600', color: '#334155', whiteSpace: 'nowrap' }}>Filter by:</span>
                <select style={{ padding: '10px 16px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '14px', color: '#475569', minWidth: '180px', width: 'max-content', outline: 'none' }}>
                  <option value="">Session type</option>
                  <option value="video">Video Call</option>
                  <option value="inperson">In-person</option>
                </select>
                <div style={{ position: 'relative' }}>
                  <input type="date" style={{ padding: '9px 16px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '14px', color: '#475569', outline: 'none' }} />
                </div>
                <button style={{ padding: '10px 20px', borderRadius: '6px', background: '#8B7EFF', color: '#fff', border: 'none', fontSize: '14px', fontWeight: '500', cursor: 'pointer', whiteSpace: 'nowrap' }}>Apply filter</button>
                <button style={{ padding: '10px 10px', borderRadius: '6px', background: 'none', color: '#64748b', border: 'none', fontSize: '14px', cursor: 'pointer', whiteSpace: 'nowrap' }}>Clear filters</button>
              </div>
            )}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '10px', marginBottom: '15px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1e293b', margin: 0 }}>
              {manageSessionTab === 'requests' ? 'Pending Patient Requests' : manageSessionTab === 'slots' ? 'Manage Availability Slots' : 'Patient sessions'}    
            </h3>
            {manageSessionTab === 'slots' && (
              <div style={{ display: 'flex', gap: '15px', fontSize: '12px', color: '#64748B', alignItems: 'center', background: '#F8FAFC', padding: '8px 15px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
                <div style={{ fontWeight: '600', color: '#1E293B', marginRight: '5px' }}>Legend:</div>
                <span style={{display: 'flex', alignItems: 'center', gap: '6px'}}><div style={{width:'12px', height:'12px', border:'1px dashed #cbd5e1', borderRadius:'3px'}}></div> Uncreated</span>
                <span style={{display: 'flex', alignItems: 'center', gap: '6px'}}><div style={{width:'12px', height:'12px', background:'#ecfdf5', border:'1px solid #10b981', borderRadius:'3px'}}></div> Open</span>
                <span style={{display: 'flex', alignItems: 'center', gap: '6px'}}><div style={{width:'12px', height:'12px', background:'#f1f5f9', border:'1px solid #e2e8f0', borderRadius:'3px'}}></div> Booked</span>
              </div>
            )}
          </div>

          {/* Main View Area */}
          {manageSessionTab === 'slots' ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(250px, 350px) 1fr', gap: '20px', alignItems: 'start' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                
                <div className="doc-card" style={{ padding: '0', overflow: 'hidden', border: '1px solid #e2e8f0', borderRadius: '14px', background: '#fff', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)' }}>
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
                      if(ampm==='PM' && h !== 12) h += 12;
                      if(ampm==='AM' && h === 12) h = 0;
                      const now = new Date();
                      return (h < now.getHours()) || (h === now.getHours() && m < now.getMinutes());
                  })();
                  if (slotDate < formatObjToDate(new Date())) state = 'disabled';
                  else if(isPast) state = 'disabled';

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
                      if(isRealBooked) state = 'booked';
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
                  } else if (state === 'inactive') {
                    bg = '#f8fafc'; border = '1px solid #cbd5e1'; color = '#64748b'; text = time; cursor = 'pointer';
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
                      {state === 'open' && <span style={{fontSize:'10px', fontWeight: '500'}}>Open</span>}
                      {state === 'inactive' && <span style={{fontSize:'10px', fontWeight: '500'}}>Inactive</span>}
                      {state === 'booked' && <span style={{fontSize:'10px', fontWeight: '500'}}>Booked</span>}
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
                    doctorApi.createSlots(payload).then(() => doctorApi.dashboardData()).then((freshData) => {
                      if (freshData && freshData.success) {
                        setDashboardData(freshData);
                        setSlotsData(hydrateSlotsData(freshData.slots || []));
                      }
                      addNotification && addNotification({ type: 'success', message: 'Slots saved' });
                    }).catch(() => {
                      addNotification && addNotification({ type: 'error', message: 'Failed to save slots' });
                    });
                  }} style={{ background: '#8B7EFF', color: '#fff', border: 'none', padding: '10px 18px', borderRadius: '50px', cursor: 'pointer', fontSize: '13px', fontWeight: '600' }}>Save Slots</button>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
              {manageSessionTab === 'requests' ? (
              // Requests view
              dashboardData?.requests?.length > 0 ? dashboardData.requests.map((r, i) => (
                <div key={i} style={{ position: 'relative', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '15px', background: '#fff' }}>
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
                    <input type="datetime-local" id={`time-manage-${r.appointment_id}`} style={{padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: '8px', fontSize: '13px', width: '100%', boxSizing: 'border-box', outline: 'none'}} />
                    <div style={{ display: 'flex', gap: '10px' }}>
                      <button onClick={() => {
                        const t = document.getElementById(`time-manage-${r.appointment_id}`).value;
                        if(!t) return addNotification && addNotification({ type: 'error', message: 'Please select a date and time slot first' });
                        doctorApi.respondToAppointment(r.id || r.appointment_id, { status: 'ACCEPT', assignedDate: t, doctorMessage: '' }).then((data)=>{
                          if(data && (data.id || data.success)) doctorApi.dashboardData().then((newData)=>{
                            setDashboardData(newData);
                            setSlotsData(hydrateSlotsData(newData.slots || []));
                          });
                        });
                      }} style={{flex: 1, background:'#10b981', color:'#fff', border:'none', padding:'10px', borderRadius:'8px', cursor:'pointer', fontSize:'13px', fontWeight:'600'}}>Accept</button>
                      <button onClick={() => {
                        doctorApi.respondToAppointment(r.id || r.appointment_id, { status: 'REJECT', doctorMessage: 'Declined by doctor' }).then((data)=>{
                          if(data && (data.id || data.success)) doctorApi.dashboardData().then((newData)=>{
                            setDashboardData(newData);
                            setSlotsData(hydrateSlotsData(newData.slots || []));
                          });
                        });
                      }} style={{flex: 1, background:'#f1f5f9', color:'#64748b', border:'1px solid #e2e8f0', padding:'10px', borderRadius:'8px', cursor:'pointer', fontSize:'13px', fontWeight:'600'}}>Decline</button>
                    </div>
                  </div>
                </div>
              )) : (
                <div style={{ color: '#64748b', fontSize: '14px', padding: '20px 0' }}>No pending requests.</div>
              )
            ) : (
              // Upcoming/Completed view
              (manageSessionTab === 'upcoming' ? dashboardData?.upcoming_schedules : dashboardData?.completed_schedules)?.length > 0 ? (manageSessionTab === 'upcoming' ? dashboardData?.upcoming_schedules : dashboardData?.completed_schedules).map((s, i) => (
                <div key={i} style={{ 
                  position: 'relative', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '15px', background: '#fff', overflow: 'hidden'
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
                    {new Date(s.appointmentDate || s.scheduled_time).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })} at {new Date(s.appointmentDate || s.scheduled_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                  </div>

                  <div style={{ margin: 0, fontSize: '13px', color: '#64748b', lineHeight: '1.6', paddingLeft: '8px', display: 'grid', gap: '6px' }}>
                    <div><strong style={{ color: '#334155' }}>Reason:</strong> {s.reason || 'General follow-up'}</div>
                    {String(s.note || '').trim() && <div><strong style={{ color: '#334155' }}>Note:</strong> {s.note}</div>}
                  </div>

                  {manageSessionTab !== 'completed' && (
                  <div style={{ marginTop: 'auto', paddingTop: '10px', paddingLeft: '8px' }}>
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                      <button onClick={() => {
                          fetch(`/api/appointments/${s.id}/action`, {
                            method: 'PUT', headers: {'Content-Type': 'application/json'}, credentials: 'include',
                            body: JSON.stringify({ status: 'ACCEPT', assignedDate: s.appointmentDate || s.scheduled_time, doctorMessage: 'Completed session' })
                          }).then(r=>r.json()).then(d=>{
                              if(d && (d.id || d.success)) fetch('/api/doctor_dashboard_data', {credentials: 'include'}).then(res=>res.json()).then(newData=>{
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
                              return doctorApi.dashboardData().then((newData) => {
                                setDashboardData(newData);
                                setSlotsData(hydrateSlotsData(newData.slots || []));
                              });
                            }
                            throw new Error('Unable to cancel session');
                          }).catch(() => {
                            addNotification && addNotification({ type: 'error', message: 'Failed to cancel session' });
                          });
                        }}
                        style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#BE123C', background: '#FFF1F2', border: '1px solid #FCA5A5', borderRadius: '999px', fontSize: '14px', fontWeight: '600', cursor: 'pointer', padding: '8px 14px' }}
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="doc-section" style={{ display: 'flex', height: '80vh', padding: 0, overflow: 'hidden' }}>
              {/* Patient List Sidebar */}
          <div style={{ width: '250px', borderRight: '1px solid #eee', background: '#fafafa', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '15px', fontWeight: 'bold', borderBottom: '1px solid #eee' }}>Patients</div>
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {patientChatList.map(p => (
                <div 
                  key={p.id} 
                  onClick={() => setActivePatient(p.id)}
                  style={{ 
                    padding: '12px 15px', cursor: 'pointer', borderBottom: '1px solid #eee',
                    background: activePatient === p.id ? '#f3f0ff' : 'transparent',
                    borderLeft: activePatient === p.id ? '4px solid #8B7EFF' : '4px solid transparent'
                  }}
                >
                  <div style={{ fontWeight: '500', fontSize: '14px', color: '#333' }}>{p.display}</div>
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
            <form onSubmit={handlePatientChatSubmit} style={{ display: 'flex', padding: '15px', borderTop: '1px solid #eee', gap: '10px', border: `1px solid ${patientInputFocused ? 'rgba(139,126,255,0.35)' : '#e2e8f0'}`, borderRadius: '50px', background: '#fff', boxShadow: patientInputFocused ? '0 0 0 3px rgba(139,126,255,0.12)' : 'none', transition: 'border-color 0.18s ease, box-shadow 0.18s ease' }}>
              <input 
                type="text" 
                value={patientMsgInput} onChange={e=>setPatientMsgInput(e.target.value)}
                onFocus={() => setPatientInputFocused(true)}
                onBlur={() => setPatientInputFocused(false)}
                disabled={chatDisabled || !activePatient}
                placeholder={chatDisabled ? 'Chat closed' : 'Type message...'}
                style={{ flex: 1, padding: '12px 18px', border: 'none', background: 'transparent', borderRadius: '50px', outline: 'none', fontSize: '14px', lineHeight: '1.5', color: '#0F172A', boxShadow: 'none', caretColor: '#8B7EFF' }}
              />
              <button disabled={chatDisabled || !activePatient} className="doc-btn doc-btn-primary" style={{ padding: '10px 24px', borderRadius: '50px', background: '#8B7EFF', color: '#fff', border: 'none', fontWeight: '600', cursor: 'pointer' }}>Send</button>
            </form>
          </div>
        </div>
        </div>
      );
      case 'assistant': return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h1 className="doc-h1">AI Medical Assistant</h1>
          <div className="doc-section" style={{ display: 'flex', flexDirection: 'column', height: '80vh', padding: 0 }}>
            <div style={{ padding: '20px', borderBottom: '1px solid #f0f0f0', fontWeight: '700', color: '#8B7EFF', fontSize: '16px' }}>AI Medical Assistant</div>
            <div style={{ padding: '16px' }}>
              <CopilotPanel defaultPatientId={dashboardData?.upcoming_schedules?.[0]?.patient || ''} />
              <div style={{ marginTop: '12px', fontSize: '12px', color: '#64748B' }}>
                Read-only copilot output only. No assistant chat or write actions are exposed here.
              </div>
            </div>
          </div>
        </div>
      );
      case 'payments': return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h1 className="doc-h1">Earnings & Payments</h1>
          <div className="doc-section" style={{ display: 'flex', flexDirection: 'column' }}>
          
          <div style={{ background: '#FAFAFA', padding: '20px', borderRadius: '16px', border: '1px solid #e2e8f0', marginBottom: '20px' }}>
            <div style={{ fontSize: '14px', color: '#6B6B6B' }}>Total Earnings</div>
            <div style={{ fontSize: '32px', fontWeight: '700', color: '#0C0C0C' }}>$1,250.00</div>
          </div>
          <table className="doc-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Patient</th>
                <th>Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>2024-03-28</td>
                <td>Dip Saha</td>
                <td>$150.00</td>
                <td><span className="doc-badge success">Completed</span></td>
              </tr>
              <tr>
                <td>2024-03-27</td>
                <td>John Doe</td>
                <td>$150.00</td>
                <td><span className="doc-badge success">Completed</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        </div>
      );
      case 'settings': return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h1 className="doc-h1">Settings</h1>
          <div className="doc-section" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ paddingBottom: '20px', borderBottom: '1px solid #f0f0f0', fontWeight: '700', color: '#8B7EFF', fontSize: '18px', marginBottom: '20px' }}>Profile Settings</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '600px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '13px', fontWeight: '600', color: '#0C0C0C' }}>Full Name</label>
              <input type="text" defaultValue={user.display_name} style={{ padding: '12px 14px', border: '1px solid #e2e8f0', borderRadius: '12px', outline: 'none', fontSize: '14px' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '13px', fontWeight: '600', color: '#0C0C0C' }}>Specialization</label>
              <input type="text" defaultValue={user.specialization || ''} style={{ padding: '12px 14px', border: '1px solid #e2e8f0', borderRadius: '12px', outline: 'none', fontSize: '14px' }} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '13px', fontWeight: '600', color: '#0C0C0C' }}>Hospital Location</label>
              <input type="text" defaultValue={user.hospital_location || ''} style={{ padding: '12px 14px', border: '1px solid #e2e8f0', borderRadius: '12px', outline: 'none', fontSize: '14px' }} />
            </div>
            <div style={{ marginTop: '10px' }}>
              <button className="doc-btn doc-btn-primary" style={{ padding: '12px 24px', borderRadius: '50px', background: '#8B7EFF', color: '#fff', border: 'none', fontWeight: '600', cursor: 'pointer' }}>Save Changes</button>
            </div>
          </div>
        </div>
        </div>
      );
      default: return null;
    }
  };

  if (!user) return <div style={{padding: '50px', textAlign: 'center'}}>Loading Doctor Dashboard...</div>;

  return (
    <div className="app-wrapper">
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

      <div className="doc-layout">
        {/* Sidebar */}
        <div className="doc-sidebar">
        <img src={user.profile_pic} alt="Profile" />
        <div className="doc-name">{user.display_name}</div>
        
        <div className="doc-nav">
          {['dashboard', 'sessions', 'patientchats', 'assistant', 'payments', 'settings'].map(tab => (
            <button 
              key={tab} 
              onClick={() => setActiveTabFromNav(tab)}
              className={activeTab === tab ? 'active' : ''}
              style={tab === 'sessions' ? {textTransform: 'capitalize'} : {}}
            >
              {tab === 'patientchats' ? 'Patient Chats' : tab === 'sessions' ? 'Manage Sessions' : tab}
            </button>
          ))}
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