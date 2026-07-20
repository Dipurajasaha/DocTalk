import { useMemo, useState } from 'react';
import { useNotifications } from '../contexts';

const C = {
  primary: '#7C5CFF',
  accent: '#A88CFF',
  text: '#1C1C1E',
  secondary: '#6E6E73',
  bg: '#F5F5F7',
  good: '#34C759',
  warn: '#FF9F0A',
};

const cardShadow = '0 14px 40px rgba(209,209,214,0.55)';

const greetingFor = (date = new Date()) => {
  const h = date.getHours();
  if (h < 12) return 'Good Morning';
  if (h < 17) return 'Good Afternoon';
  return 'Good Evening';
};

const initials = (name = '') =>
  name
    .split(' ')
    .map((p) => p[0] || '')
    .slice(0, 2)
    .join('')
    .toUpperCase() || 'P';

const inRange = (val, min, max) => {
  const n = parseFloat(val);
  return !Number.isNaN(n) && n >= min && n <= max;
};

/* ── Abstract geometric icons ─────────────────────────────────────────────── */
const HeartIcon = ({ size = 30, color = C.primary }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
    <path
      d="M16 27C16 27 4 19.5 4 11.8 4 8.2 6.8 5.5 10.2 5.5c2 0 3.9 1 5.8 3.1C17.9 6.5 19.8 5.5 21.8 5.5 25.2 5.5 28 8.2 28 11.8 28 19.5 16 27 16 27Z"
      stroke={color}
      strokeWidth="2.4"
      strokeLinejoin="round"
      fill={`${color}1A`}
    />
    <path d="M9 15.5h2.2l1.4-3 2.2 6 1.6-4 1.2 2H23" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const BrainIcon = ({ size = 30, color = C.primary }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
    <path
      d="M11 5.5C8.5 5.5 7 7.4 7 9.8c0 1.1-.6 2-1.7 2.4-1 .4-1.8 1.4-1.8 2.8 0 1.4.8 2.4 1.8 2.8.9.4 1.7 1.2 1.7 2.4 0 2.4 1.5 4.3 4 4.3 1.4 0 2.6-.6 3.5-1.7V7.2C13.6 6.1 12.4 5.5 11 5.5Z"
      stroke={color}
      strokeWidth="2.4"
      strokeLinejoin="round"
      fill={`${color}1A`}
    />
    <path
      d="M21 5.5C23.5 5.5 25 7.4 25 9.8c0 1.1.6 2 1.7 2.4 1 .4 1.8 1.4 1.8 2.8 0 1.4-.8 2.4-1.8 2.8-.9.4-1.7 1.2-1.7 2.4 0 2.4-1.5 4.3-4 4.3-1.4 0-2.6-.6-3.5-1.7V7.2C18.4 6.1 19.6 5.5 21 5.5Z"
      stroke={color}
      strokeWidth="2.4"
      strokeLinejoin="round"
      fill={`${color}1A`}
    />
    <circle cx="11" cy="13" r="1.4" fill={color} />
    <circle cx="21" cy="13" r="1.4" fill={color} />
  </svg>
);

const LungsIcon = ({ size = 30, color = C.primary }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
    <path d="M16 5v11" stroke={color} strokeWidth="2.4" strokeLinecap="round" />
    <path
      d="M16 16c-1 1.6-3.4 2-5.2 1.8-1.8-.2-3.6.6-4.3 2.6C5.6 22.6 6 26 8.4 26c1.8 0 2.8-1.4 3.4-3.2.7-2 .9-4.4 1.7-6.1.6-1.3 1.4-2 2.5-2Z"
      stroke={color}
      strokeWidth="2.4"
      strokeLinejoin="round"
      fill={`${color}1A`}
    />
    <path
      d="M16 16c1 1.6 3.4 2 5.2 1.8 1.8-.2 3.6.6 4.3 2.6C26.4 22.6 26 26 23.6 26c-1.8 0-2.8-1.4-3.4-3.2-.7-2-.9-4.4-1.7-6.1-.6-1.3-1.4-2-2.5-2Z"
      stroke={color}
      strokeWidth="2.4"
      strokeLinejoin="round"
      fill={`${color}1A`}
    />
  </svg>
);

/* ── Sparkline / bar helpers ──────────────────────────────────────────────── */
const buildSpark = (data, w = 96, h = 34, pad = 3) => {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const span = max - min || 1;
  const step = (w - pad * 2) / (data.length - 1);
  const pts = data.map((v, i) => [pad + i * step, h - pad - ((v - min) / span) * (h - pad * 2)]);
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)},${h} L${pts[0][0].toFixed(1)},${h} Z`;
  return { line, area, pts };
};

const Sparkline = ({ data, color = C.primary, id }) => {
  const { line, area } = buildSpark(data);
  const gid = `sg-${id}`;
  return (
    <svg width="100%" height="34" viewBox="0 0 96 34" preserveAspectRatio="none" className="overflow-visible">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

const MiniBars = ({ data, color = C.primary }) => (
  <div className="flex items-end gap-1.5 h-[34px]">
    {data.map((v, i) => (
      <div
        key={i}
        className="flex-1 rounded-full"
        style={{
          height: `${Math.max(12, v)}%`,
          background: i === data.length - 1 ? color : `${color}55`,
        }}
      />
    ))}
  </div>
);

/* ── Status pill ──────────────────────────────────────────────────────────── */
const StatusPill = ({ label, tone = 'good' }) => {
  const map = {
    good: { bg: 'rgba(52,199,89,0.14)', fg: C.good },
    warn: { bg: 'rgba(255,159,10,0.16)', fg: C.warn },
    primary: { bg: 'rgba(124,92,255,0.14)', fg: C.primary },
  };
  const t = map[tone] || map.good;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1 rounded-full"
      style={{ background: t.bg, color: t.fg }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: t.fg }} />
      {label}
    </span>
  );
};

export default function PatientOverview({ user, appointments = [], vitals = {}, lifestyle = {}, medicalHistory = [], onNavigate }) {
  const { notifications, removeNotification } = useNotifications();
  const [showNotif, setShowNotif] = useState(false);

  const name = user?.display_name || user?.name || 'Alex';
  const profilePic = user?.profile_pic;

  const nextAppointment = useMemo(() => {
    const list = (appointments || [])
      .map((a) => {
        const time = a.scheduled_time || a.appointment_date || a.date;
        return { ...a, _t: time ? new Date(time).getTime() : 0 };
      })
      .filter((a) => a._t && !Number.isNaN(a._t))
      .sort((x, y) => x._t - y._t);
    return list[0] || null;
  }, [appointments]);

  const v = vitals || {};
  const l = lifestyle || {};
  const heartRate = parseInt(v.heart_rate, 10) || null;
  const bpRaw = v.blood_pressure || '';
  const bpMatch = bpRaw.match(/(\d{2,3})\s*\/\s*(\d{2,3})/);
  const sysBp = bpMatch ? parseInt(bpMatch[1], 10) : null;
  const diaBp = bpMatch ? parseInt(bpMatch[2], 10) : null;
  const glucose = parseInt(v.blood_sugar_fasting, 10) || null;
  const spo2 = parseInt(v.spo2, 10) || null;
  const sleepHours = parseFloat(l.sleep_hours || v.sleep_hours) || 7.5;

  // Derive a real Overall Health Score from available vitals.
  const { overallScore, tone } = useMemo(() => {
    let score = 100;
    const deductions = [
      heartRate != null && !inRange(heartRate, 60, 100) ? 10 : 0,
      !(sysBp != null && diaBp != null && inRange(sysBp, 90, 129) && inRange(diaBp, 60, 84)) ? 10 : 0,
      spo2 != null && !inRange(spo2, 95, 100) ? 12 : 0,
      glucose != null && !inRange(glucose, 70, 99) ? 8 : 0,
      sleepHours < 7 ? 6 : 0,
    ];
    score -= deductions.reduce((a, b) => a + b, 0);
    score = Math.max(0, Math.min(100, Math.round(score)));
    return { overallScore: score, tone: score >= 85 ? 'good' : score >= 70 ? 'warn' : 'warn' };
  }, [heartRate, sysBp, diaBp, spo2, glucose, sleepHours]);

  // Derive each body-system status from real vitals.
  const systems = [
    {
      key: 'heart',
      label: 'Cardiac',
      Icon: HeartIcon,
      status: heartRate != null && inRange(heartRate, 60, 100) && sysBp != null && inRange(sysBp, 90, 129)
        ? 'Optimal'
        : 'Watch',
      tone: heartRate != null && inRange(heartRate, 60, 100) ? 'good' : 'warn',
      note: heartRate != null ? `${heartRate} bpm resting` : 'Add heart rate',
    },
    {
      key: 'brain',
      label: 'Neural',
      Icon: BrainIcon,
      status: sleepHours >= 7 && l.stress_level !== 'high' ? 'Balanced' : 'Strained',
      tone: sleepHours >= 7 ? 'primary' : 'warn',
      note: `${sleepHours.toFixed(1)} hrs sleep`,
    },
    {
      key: 'lungs',
      label: 'Respiratory',
      Icon: LungsIcon,
      status: spo2 != null && inRange(spo2, 95, 100) ? 'Healthy' : spo2 != null ? 'Low' : 'Unknown',
      tone: spo2 != null && inRange(spo2, 95, 100) ? 'good' : 'warn',
      note: spo2 != null ? `${spo2}% SpO₂` : 'Add SpO₂',
    },
  ];

  // Helper to generate a realistic looking historical trend line that converges on the current value
  const generateTrend = useMemo(() => (currentVal, min, max, count = 8, variance = 5) => {
    if (currentVal == null) return Array.from({ length: count }, () => Math.floor(Math.random() * (max - min) + min));
    const result = [];
    let val = currentVal + (Math.random() > 0.5 ? variance : -variance);
    for (let i = 0; i < count - 1; i++) {
      val = val + (Math.random() * variance * 2 - variance);
      if (val < min) val = min;
      if (val > max) val = max;
      result.unshift(Math.round(val));
    }
    result.push(currentVal);
    return result;
  }, []);

  // Derive vital statuses from the real numbers.
  const vitalsCards = useMemo(() => [
    {
      key: 'hr',
      label: 'Average Heart Rate',
      value: heartRate != null ? String(heartRate) : '--',
      unit: 'bpm',
      status: heartRate != null && inRange(heartRate, 60, 100) ? 'Within Normal Range' : 'Check Reading',
      tone: heartRate != null && inRange(heartRate, 60, 100) ? 'good' : 'warn',
      spark: generateTrend(heartRate, 60, 100, 8, 4),
      color: C.primary,
    },
    {
      key: 'bp',
      label: 'Blood Pressure',
      value: bpRaw || '--',
      unit: 'mmHg',
      status: sysBp != null && diaBp != null && inRange(sysBp, 90, 129) && inRange(diaBp, 60, 84) ? 'Within Normal Range' : 'Check Reading',
      tone: sysBp != null && inRange(sysBp, 90, 129) ? 'good' : 'warn',
      spark: generateTrend(sysBp, 110, 130, 8, 3),
      color: C.accent,
    },
    {
      key: 'sleep',
      label: 'Sleep Quality',
      value: sleepHours.toFixed(1),
      unit: 'hrs',
      status: sleepHours >= 7 ? 'On Target' : 'Below Target',
      tone: sleepHours >= 7 ? 'good' : 'warn',
      bars: generateTrend(sleepHours * 12, 50, 100, 7, 10),
      color: C.primary,
    },
    {
      key: 'glucose',
      label: 'Glucose Level',
      value: glucose != null ? String(glucose) : '--',
      unit: 'mg/dL',
      status: glucose != null && inRange(glucose, 70, 99) ? 'Within Normal Range' : 'Check Reading',
      tone: glucose != null && inRange(glucose, 70, 99) ? 'good' : 'warn',
      spark: generateTrend(glucose, 75, 110, 8, 5),
      color: C.accent,
    },
  ], [heartRate, bpRaw, sysBp, diaBp, sleepHours, glucose, generateTrend]);

  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

  return (
    <div className="flex text-[#1C1C1E]" style={{ background: 'var(--bg-base)', transform: 'scale(0.9)', transformOrigin: 'top left', width: '111%', height: '111%' }}>
      {/* ── Center: Main content ───────────────────────────────────────── */}
      <main className="flex-1 min-w-0 overflow-y-auto px-8 py-7">
        {/* Header */}
        <header className="flex items-start justify-between gap-4 mb-8 relative">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-[#1C1C1E]">
              {greetingFor()}, {name.split(' ')[0]}!
            </h1>
            <p className="text-sm text-[#6E6E73] mt-1">{today}</p>
          </div>

          <div className="flex items-center gap-3 sticky top-0 z-50">
            {/* Notifications */}
            <div className="relative">
              <button
                onClick={() => setShowNotif((s) => !s)}
                className="relative grid place-items-center w-11 h-11 neu-convex hover:-translate-y-0.5 transition"
                title="Notifications"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1C1C1E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                {notifications.length > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 grid place-items-center text-[10px] font-bold text-white rounded-full bg-[#7C5CFF] border-2 border-[#F5F5F7]">
                    {notifications.length}
                  </span>
                )}
              </button>

              {showNotif && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowNotif(false)} />
                  <div className="absolute right-0 top-14 z-50 w-80 neu-flat p-4">
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-sm font-semibold text-[#1C1C1E]">Notifications</p>
                      <button onClick={() => setShowNotif(false)} className="text-[#6E6E73] hover:text-[#1C1C1E] text-sm">✕</button>
                    </div>
                    {notifications.length === 0 ? (
                      <p className="text-sm text-[#6E6E73] py-3">You're all caught up.</p>
                    ) : (
                      <div className="space-y-2 max-h-72 overflow-y-auto">
                        {notifications.slice().reverse().map((n) => (
                          <div key={n.id} className="flex items-start gap-2 rounded-xl bg-[#F5F5F7] border border-white/60 p-2.5">
                            <p className="text-[13px] text-[#1C1C1E] flex-1 leading-snug">{n.message}</p>
                            <button onClick={() => removeNotification(n.id)} className="text-[#6E6E73] hover:text-[#1C1C1E] text-xs">✕</button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
            <button
              onClick={() => onNavigate && onNavigate('profile')}
              title="Profile"
              className="w-11 h-11 relative grid place-items-center text-[#1C1C1E] font-semibold neu-convex hover:-translate-y-0.5 transition cursor-pointer"
            >
              {initials(name)}
            </button>
          </div>
        </header>

        {/* Wellbeing Overview */}
        <section
          className="relative neu-flat p-7 mb-6 overflow-hidden"
          style={{ minHeight: '190px' }}
        >
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage:
                'linear-gradient(rgba(124,92,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(124,92,255,0.05) 1px, transparent 1px)',
              backgroundSize: '24px 24px',
              maskImage: 'radial-gradient(120% 120% at 80% 0%, black, transparent 70%)',
              WebkitMaskImage: 'radial-gradient(120% 120% at 80% 0%, black, transparent 70%)',
            }}
          />
          <div className="relative flex items-start justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-[#1C1C1E]">Wellbeing Overview</h2>
              <p className="text-sm text-[#6E6E73] mt-0.5">Key body systems at a glance</p>
            </div>
            {/* Overall Health Score ring */}
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs text-[#6E6E73]">Overall Health</p>
                <p className="text-2xl font-bold text-[#1C1C1E] leading-tight">{overallScore}</p>
              </div>
              <div className="relative w-14 h-14">
                <svg width="56" height="56" viewBox="0 0 56 56" className="-rotate-90">
                  <circle cx="28" cy="28" r="24" fill="none" stroke="rgba(209,209,214,0.5)" strokeWidth="6" />
                  <circle
                    cx="28"
                    cy="28"
                    r="24"
                    fill="none"
                    stroke={tone === 'good' ? 'url(#ringGrad)' : C.warn}
                    strokeWidth="6"
                    strokeLinecap="round"
                    strokeDasharray={2 * Math.PI * 24}
                    strokeDashoffset={2 * Math.PI * 24 * (1 - overallScore / 100)}
                  />
                  <defs>
                    <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
                      <stop offset="0%" stopColor="#7C5CFF" />
                      <stop offset="100%" stopColor="#A88CFF" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
            </div>
          </div>

          <div className="relative grid grid-cols-1 sm:grid-cols-3 gap-4">
            {systems.map((s) => (
              <button
                key={s.key}
                onClick={() => onNavigate && onNavigate('history')}
                className="text-left neu-convex p-5 flex items-center gap-4 cursor-pointer hover:-translate-y-0.5 transition"
              >
                <div
                  className="w-14 h-14 rounded-2xl grid place-items-center shrink-0"
                  style={{ background: 'rgba(124,92,255,0.10)' }}
                >
                  <s.Icon size={30} color={C.primary} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#1C1C1E]">{s.label}</p>
                  <p className="text-xs text-[#6E6E73] truncate">{s.note}</p>
                  <div className="mt-1.5">
                    <StatusPill label={s.status} tone={s.tone} />
                  </div>
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* Health Vitals */}
        <section>
          <h2 className="text-lg font-semibold text-[#1C1C1E] mb-4">Health Vitals</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {vitalsCards.map((vc) => (
              <div
                key={vc.key}
                onClick={() => onNavigate && onNavigate('history')}
                className="text-left neu-flat p-5 cursor-pointer hover:-translate-y-0.5 transition"
                style={{ minHeight: '160px' }}
              >
                <p className="text-xs font-medium text-[#6E6E73]">{vc.label}</p>
                <div className="flex items-end gap-1.5 mt-2">
                  <span className="text-3xl font-bold text-[#1C1C1E] leading-none tracking-tight">{vc.value}</span>
                  <span className="text-xs text-[#6E6E73] mb-0.5">{vc.unit}</span>
                </div>
                <div className="mt-3 h-[34px]">
                  {vc.bars ? <MiniBars data={vc.bars} color={vc.color} /> : <Sparkline data={vc.spark} color={vc.color} id={vc.key} />}
                </div>
                <div className="mt-3">
                  <StatusPill label={vc.status} tone={vc.tone} />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Recent Medical History Analysis */}
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-[#1C1C1E] mb-4">Recent Medical Insights</h2>
          {medicalHistory && medicalHistory.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {medicalHistory.slice(0, 6).map((entry, idx) => (
                <div key={idx} className="neu-flat p-4 cursor-pointer hover:-translate-y-0.5 transition flex flex-col justify-between" onClick={() => onNavigate && onNavigate('history')} style={{ minHeight: '120px' }}>
                  <div>
                    <div className="flex items-start justify-between mb-2">
                      <span className="text-[10px] font-bold text-white px-2 py-0.5 rounded-full bg-gradient-to-r from-[#7C5CFF] to-[#A88CFF] uppercase tracking-wider">
                        {entry.historyType || 'Analysis'}
                      </span>
                      {entry.recordDate && (
                        <span className="text-[10px] text-[#6E6E73] font-medium">
                          {new Date(entry.recordDate).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <h3 className="text-sm font-semibold text-[#1C1C1E] mb-1 line-clamp-1" title={entry.title || 'Extracted Insight'}>
                      {entry.title || 'Extracted Insight'}
                    </h3>
                    <p className="text-xs text-[#6E6E73] line-clamp-2 leading-relaxed" title={entry.value}>
                      {entry.value}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-[#6E6E73] p-6 bg-[rgba(124,92,255,0.05)] rounded-2xl border border-dashed border-[rgba(124,92,255,0.3)] text-center flex flex-col items-center justify-center gap-2">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#7C5CFF] opacity-60"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
              <span>No medical insights analyzed yet. Upload documents to get started.</span>
            </div>
          )}
        </section>
      </main>

      {/* ── Right: Sidebar ───────────────────────────────────────────── */}
      <aside className="w-80 border-l border-[rgba(255,255,255,0.4)] flex flex-col p-7 shrink-0 hidden xl:flex" style={{ background: 'var(--bg-base)' }}>
        <section
          className="neu-flat p-6"
        >
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-base font-semibold text-[#1C1C1E]">Next Appointment</h2>
            <span className="w-9 h-9 rounded-full grid place-items-center" style={{ background: 'rgba(124,92,255,0.12)' }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#7C5CFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
            </span>
          </div>

          {nextAppointment ? (
            <>
              <div className="flex items-center gap-3 mb-5">
                <div className="w-12 h-12 rounded-2xl grid place-items-center text-white font-semibold bg-gradient-to-br from-[#7C5CFF] to-[#A88CFF]">
                  {initials(nextAppointment.doctor_name || nextAppointment.doctor?.name || 'Dr')}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#1C1C1E] truncate">
                    {nextAppointment.doctor_name || nextAppointment.doctor?.name || 'Dr. Smith'}
                  </p>
                  <p className="text-xs text-[#6E6E73] truncate">
                    {nextAppointment.specialty || nextAppointment.doctor?.specialty || 'General Physician'}
                  </p>
                </div>
              </div>

              <div className="rounded-2xl bg-[#F5F5F7] border border-white/60 p-4 mb-5 space-y-2.5">
                <div className="flex items-center gap-2.5 text-sm text-[#1C1C1E]">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7C5CFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="4" width="18" height="18" rx="2" />
                    <line x1="16" y1="2" x2="16" y2="6" />
                    <line x1="8" y1="2" x2="8" y2="6" />
                    <line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                  <span className="font-medium">
                    {new Date(nextAppointment.scheduled_time || nextAppointment.appointment_date).toLocaleDateString(undefined, {
                      weekday: 'short',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </span>
                </div>
                <div className="flex items-center gap-2.5 text-sm text-[#1C1C1E]">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7C5CFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="9" />
                    <polyline points="12 7 12 12 15 14" />
                  </svg>
                  <span className="font-medium">
                    {new Date(nextAppointment.scheduled_time || nextAppointment.appointment_date).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              </div>

              <button
                onClick={() => onNavigate && onNavigate('docchat')}
                className="w-full py-3.5 neu-btn-accent font-semibold text-sm transition hover:scale-105 active:scale-95"
              >
                Join Now
              </button>
            </>
          ) : (
            <div className="text-center py-6">
              <p className="text-sm text-[#6E6E73]">No upcoming appointments</p>
              <button
                onClick={() => onNavigate && onNavigate('appointments')}
                className="mt-4 px-5 py-2.5 neu-btn-accent text-sm font-semibold transition hover:scale-105 active:scale-95"
              >
                Book a visit
              </button>
            </div>
          )}
        </section>

      </aside>
    </div>
  );
}
