import { useEffect, useState } from 'react';
import { adminApi } from '../lib/api';
import { useSession } from '../contexts/SessionContext';
import { useNotifications } from '../contexts';

const pageStyles = {
  page: {
    minHeight: '100vh',
    background: 'radial-gradient(circle at top left, rgba(139,126,255,0.18), transparent 28%), linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%)',
    color: '#0f172a',
    padding: '24px',
    boxSizing: 'border-box',
  },
  shell: {
    maxWidth: '1400px',
    margin: '0 auto',
    display: 'grid',
    gap: '20px',
  },
  topbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '16px',
    padding: '22px 24px',
    borderRadius: '28px',
    background: 'linear-gradient(135deg, #111827 0%, #1f2a44 55%, #4f46e5 100%)',
    color: '#fff',
    boxShadow: '0 20px 60px rgba(15,23,42,0.22)',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
  },
  badge: {
    width: '54px',
    height: '54px',
    borderRadius: '18px',
    display: 'grid',
    placeItems: 'center',
    background: 'rgba(255,255,255,0.12)',
    border: '1px solid rgba(255,255,255,0.14)',
    fontSize: '22px',
  },
  title: {
    margin: 0,
    fontSize: '26px',
    lineHeight: 1.1,
    letterSpacing: '-0.03em',
  },
  subtitle: {
    margin: '4px 0 0',
    color: 'rgba(255,255,255,0.78)',
    fontSize: '14px',
  },
  actionRow: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
  },
  button: {
    border: '0',
    borderRadius: '14px',
    padding: '12px 16px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  primaryBtn: {
    background: '#8B7EFF',
    color: '#fff',
    boxShadow: '0 10px 24px rgba(139,126,255,0.28)',
  },
  ghostBtn: {
    background: 'rgba(255,255,255,0.12)',
    color: '#fff',
    border: '1px solid rgba(255,255,255,0.18)',
  },
  statGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    gap: '16px',
  },
  card: {
    background: '#fff',
    borderRadius: '24px',
    boxShadow: '0 16px 48px rgba(15,23,42,0.08)',
    border: '1px solid rgba(148,163,184,0.18)',
  },
  statCard: {
    padding: '22px',
    display: 'grid',
    gap: '12px',
    minHeight: '142px',
  },
  statLabel: {
    color: '#64748b',
    fontSize: '13px',
    fontWeight: 700,
    letterSpacing: '0.02em',
    textTransform: 'uppercase',
  },
  statValue: {
    fontSize: '38px',
    fontWeight: 800,
    letterSpacing: '-0.05em',
    color: '#111827',
  },
  statMeta: {
    fontSize: '13px',
    color: '#475569',
  },
  contentGrid: {
    display: 'grid',
    gridTemplateColumns: '1.35fr 1fr',
    gap: '18px',
    alignItems: 'start',
  },
  sectionCard: {
    padding: '22px',
  },
  sectionTitle: {
    margin: '0 0 4px',
    fontSize: '22px',
    letterSpacing: '-0.03em',
  },
  sectionSub: {
    margin: '0 0 18px',
    color: '#64748b',
    fontSize: '14px',
  },
  list: {
    display: 'grid',
    gap: '12px',
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '12px',
    padding: '14px 16px',
    borderRadius: '18px',
    background: '#f8fbff',
    border: '1px solid #e2e8f0',
  },
  rowMeta: {
    display: 'grid',
    gap: '4px',
    minWidth: 0,
  },
  rowTitle: {
    fontWeight: 700,
    fontSize: '14px',
    color: '#0f172a',
  },
  rowSub: {
    fontSize: '12px',
    color: '#64748b',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  pill: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    borderRadius: '999px',
    padding: '6px 10px',
    fontSize: '12px',
    fontWeight: 700,
  },
  dangerBtn: {
    border: '1px solid rgba(220,38,38,0.18)',
    background: '#fff1f2',
    color: '#b91c1c',
    borderRadius: '12px',
    padding: '8px 12px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  mutedBtn: {
    border: '1px solid #e2e8f0',
    background: '#fff',
    color: '#334155',
    borderRadius: '12px',
    padding: '8px 12px',
    fontWeight: 700,
    cursor: 'pointer',
  },
  profileGrid: {
    display: 'grid',
    gap: '14px',
  },
  field: {
    display: 'grid',
    gap: '6px',
  },
  label: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#475569',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
  },
  input: {
    width: '100%',
    boxSizing: 'border-box',
    padding: '12px 14px',
    borderRadius: '14px',
    border: '1px solid #dbe3ef',
    background: '#fff',
    color: '#0f172a',
    outline: 'none',
    fontSize: '14px',
  },
  textarea: {
    width: '100%',
    boxSizing: 'border-box',
    padding: '12px 14px',
    borderRadius: '14px',
    border: '1px solid #dbe3ef',
    background: '#fff',
    color: '#0f172a',
    outline: 'none',
    fontSize: '14px',
    minHeight: '110px',
    resize: 'vertical',
  },
  toast: {
    padding: '12px 14px',
    borderRadius: '14px',
    fontSize: '14px',
    fontWeight: 600,
  },
};

const statusPill = (label, tone = 'neutral') => ({
  ...pageStyles.pill,
  background: tone === 'danger' ? '#fee2e2' : tone === 'success' ? '#dcfce7' : tone === 'warn' ? '#fef3c7' : '#eef2ff',
  color: tone === 'danger' ? '#b91c1c' : tone === 'success' ? '#166534' : tone === 'warn' ? '#92400e' : '#4338ca',
});

function StatCard({ label, value, meta }) {
  return (
    <div style={{ ...pageStyles.card, ...pageStyles.statCard }}>
      <div style={pageStyles.statLabel}>{label}</div>
      <div style={pageStyles.statValue}>{value}</div>
      <div style={pageStyles.statMeta}>{meta}</div>
    </div>
  );
}

export default function AdminDashboard() {
  const { session, logout } = useSession();
  const { addNotification } = useNotifications();
  const [dashboard, setDashboard] = useState(null);
  const [patients, setPatients] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [profileForm, setProfileForm] = useState({ name: '', display_name: '', email: '', bio: '', profile_pic: '' });
  const [inviteResult, setInviteResult] = useState(null);
  const [inviteForm, setInviteForm] = useState({ invitee_email: '', note: '', expires_in_minutes: 60 });
  const [mfaSetup, setMfaSetup] = useState(null);
  const [mfaCode, setMfaCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const [dashboardData, patientData, doctorData, profileData] = await Promise.all([
          adminApi.dashboard(),
          adminApi.listPatients(),
          adminApi.listDoctors(),
          adminApi.getProfile(),
        ]);

        if (cancelled) return;

        setDashboard(dashboardData || null);
        setPatients(Array.isArray(patientData) ? patientData : []);
        setDoctors(Array.isArray(doctorData) ? doctorData : []);
        setProfileForm({
          name: profileData?.name || '',
          display_name: profileData?.display_name || '',
          email: profileData?.email || '',
          bio: profileData?.bio || '',
          profile_pic: profileData?.profile_pic || '',
        });
      } catch (err) {
        if (!cancelled) {
          setError(err?.message || 'Failed to load admin dashboard.');
          try { addNotification?.({ type: 'error', message: 'Failed to load admin dashboard.' }); } catch (e) {}
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [addNotification]);

  const refresh = async () => {
    const [dashboardData, patientData, doctorData, profileData] = await Promise.all([
      adminApi.dashboard(),
      adminApi.listPatients(),
      adminApi.listDoctors(),
      adminApi.getProfile(),
    ]);
    setDashboard(dashboardData || null);
    setPatients(Array.isArray(patientData) ? patientData : []);
    setDoctors(Array.isArray(doctorData) ? doctorData : []);
    setProfileForm({
      name: profileData?.name || '',
      display_name: profileData?.display_name || '',
      email: profileData?.email || '',
      bio: profileData?.bio || '',
      profile_pic: profileData?.profile_pic || '',
    });
  };

  const handleDeletePatient = async (username) => {
    if (!username) return;
    const ok = window.confirm(`Remove patient ${username}? This will delete their account and linked records.`);
    if (!ok) return;
    try {
      setBusyId(`patient:${username}`);
      await adminApi.deletePatient(username);
      await refresh();
      try { addNotification?.({ type: 'success', message: `Removed patient ${username}.` }); } catch (e) {}
    } catch (err) {
      setError(err?.message || 'Could not remove patient.');
    } finally {
      setBusyId(null);
    }
  };

  const handleBanDoctor = async (doctorId) => {
    if (!doctorId) return;
    const reason = window.prompt(`Ban doctor ${doctorId}. Optional reason:`) || '';
    try {
      setBusyId(`doctor:${doctorId}`);
      await adminApi.banDoctor(doctorId, reason.trim());
      await refresh();
      try { addNotification?.({ type: 'success', message: `Doctor ${doctorId} banned.` }); } catch (e) {}
    } catch (err) {
      setError(err?.message || 'Could not ban doctor.');
    } finally {
      setBusyId(null);
    }
  };

  const handleSaveProfile = async (event) => {
    event.preventDefault();
    try {
      setSavingProfile(true);
      setError('');
      await adminApi.updateProfile(profileForm);
      await refresh();
      try { addNotification?.({ type: 'success', message: 'Admin profile updated.' }); } catch (e) {}
    } catch (err) {
      setError(err?.message || 'Failed to update profile.');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleCreateInvite = async (event) => {
    event.preventDefault();
    try {
      const response = await adminApi.createInvite(inviteForm);
      setInviteResult(response);
      try { addNotification?.({ type: 'success', message: 'Invite token created.' }); } catch (e) {}
    } catch (err) {
      setError(err?.message || 'Failed to create invite token.');
    }
  };

  const handleSetupMfa = async () => {
    try {
      const response = await adminApi.setupMfa();
      setMfaSetup(response);
      try { addNotification?.({ type: 'success', message: 'MFA secret generated.' }); } catch (e) {}
    } catch (err) {
      setError(err?.message || 'Failed to start MFA setup.');
    }
  };

  const handleConfirmMfa = async () => {
    try {
      await adminApi.confirmMfa(mfaCode);
      setMfaSetup(null);
      setMfaCode('');
      await refresh();
      try { addNotification?.({ type: 'success', message: 'MFA enabled for this admin.' }); } catch (e) {}
    } catch (err) {
      setError(err?.message || 'Failed to confirm MFA code.');
    }
  };

  const adminName = dashboard?.admin_name || profileForm.name || session?.user_id || 'Admin';
  const initials = adminName.split(' ').slice(0, 2).map((part) => part?.[0]?.toUpperCase() || '').join('') || 'AD';
  const recentPatients = dashboard?.recent_patients || patients.slice(0, 8);
  const recentDoctors = dashboard?.recent_doctors || doctors.slice(0, 8);

  return (
    <div style={pageStyles.page}>
      <div style={pageStyles.shell}>
        <header style={pageStyles.topbar}>
          <div style={pageStyles.brand}>
            <div style={pageStyles.badge}>{initials}</div>
            <div>
              <h1 style={pageStyles.title}>Admin Control Center</h1>
              <p style={pageStyles.subtitle}>Patient and doctor governance, profile settings, and system oversight in one place.</p>
            </div>
          </div>
          <div style={pageStyles.actionRow}>
            <button type="button" style={{ ...pageStyles.button, ...pageStyles.ghostBtn }} onClick={() => refresh()}>
              Refresh
            </button>
            <button
              type="button"
              style={{ ...pageStyles.button, ...pageStyles.primaryBtn }}
              onClick={async () => { await logout(); }}
            >
              Sign Out
            </button>
          </div>
        </header>

        {error && <div style={{ ...pageStyles.card, ...pageStyles.toast, background: '#fff1f2', color: '#b91c1c', borderColor: '#fecdd3' }}>{error}</div>}

        <section style={pageStyles.statGrid}>
          <StatCard label="Patients" value={loading ? '...' : (dashboard?.patient_count ?? patients.length)} meta="Registered patient accounts" />
          <StatCard label="Doctors" value={loading ? '...' : (dashboard?.doctor_count ?? doctors.length)} meta="All doctor accounts in the database" />
          <StatCard label="Active Doctors" value={loading ? '...' : (dashboard?.active_doctor_count ?? doctors.filter((item) => !item.is_banned).length)} meta="Doctors currently allowed to log in" />
          <StatCard label="Banned Doctors" value={loading ? '...' : (dashboard?.banned_doctor_count ?? doctors.filter((item) => item.is_banned).length)} meta="Accounts blocked by admin action" />
        </section>

        <section style={pageStyles.contentGrid}>
          <div style={{ ...pageStyles.card, ...pageStyles.sectionCard }}>
            <h2 style={pageStyles.sectionTitle}>Patient Management</h2>
            <p style={pageStyles.sectionSub}>Remove patient accounts when needed. Linked data is deleted by the database cascade.</p>
            <div style={pageStyles.list}>
              {(recentPatients || []).map((patient) => (
                <div key={patient.username} style={pageStyles.row}>
                  <div style={pageStyles.rowMeta}>
                    <div style={pageStyles.rowTitle}>{patient.name || patient.username}</div>
                    <div style={pageStyles.rowSub}>{patient.username}{patient.email ? ` · ${patient.email}` : ''}{patient.mobile ? ` · ${patient.mobile}` : ''}</div>
                  </div>
                  <button
                    type="button"
                    style={pageStyles.dangerBtn}
                    disabled={busyId === `patient:${patient.username}`}
                    onClick={() => handleDeletePatient(patient.username)}
                  >
                    {busyId === `patient:${patient.username}` ? 'Removing...' : 'Remove'}
                  </button>
                </div>
              ))}
              {recentPatients.length === 0 && <div style={{ color: '#64748b', fontSize: '14px' }}>No patients found.</div>}
            </div>
          </div>

          <div style={{ ...pageStyles.card, ...pageStyles.sectionCard }}>
            <h2 style={pageStyles.sectionTitle}>Admin Profile Settings</h2>
            <p style={pageStyles.sectionSub}>Update the public-facing profile attached to this admin account.</p>
            <form onSubmit={handleSaveProfile} style={pageStyles.profileGrid}>
              <div style={pageStyles.field}>
                <label style={pageStyles.label}>Name</label>
                <input
                  style={pageStyles.input}
                  value={profileForm.name}
                  onChange={(event) => setProfileForm((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder="Admin name"
                />
              </div>
              <div style={pageStyles.field}>
                <label style={pageStyles.label}>Display Name</label>
                <input
                  style={pageStyles.input}
                  value={profileForm.display_name}
                  onChange={(event) => setProfileForm((prev) => ({ ...prev, display_name: event.target.value }))}
                  placeholder="How your name appears in the app"
                />
              </div>
              <div style={pageStyles.field}>
                <label style={pageStyles.label}>Email</label>
                <input
                  style={pageStyles.input}
                  type="email"
                  value={profileForm.email}
                  onChange={(event) => setProfileForm((prev) => ({ ...prev, email: event.target.value }))}
                  placeholder="admin@doctalk.local"
                />
              </div>
              <div style={pageStyles.field}>
                <label style={pageStyles.label}>Profile Picture URL</label>
                <input
                  style={pageStyles.input}
                  value={profileForm.profile_pic}
                  onChange={(event) => setProfileForm((prev) => ({ ...prev, profile_pic: event.target.value }))}
                  placeholder="https://..."
                />
              </div>
              <div style={pageStyles.field}>
                <label style={pageStyles.label}>Bio</label>
                <textarea
                  style={pageStyles.textarea}
                  value={profileForm.bio}
                  onChange={(event) => setProfileForm((prev) => ({ ...prev, bio: event.target.value }))}
                  placeholder="Brief admin bio or role description"
                />
              </div>
              <button type="submit" style={{ ...pageStyles.button, ...pageStyles.primaryBtn }} disabled={savingProfile}>
                {savingProfile ? 'Saving...' : 'Save Profile'}
              </button>
            </form>
          </div>
        </section>

        <section style={pageStyles.contentGrid}>
          <div style={{ ...pageStyles.card, ...pageStyles.sectionCard }}>
            <h2 style={pageStyles.sectionTitle}>Doctors</h2>
            <p style={pageStyles.sectionSub}>Ban accounts that violate policy or no longer meet platform requirements.</p>
            <div style={pageStyles.list}>
              {(recentDoctors || []).map((doctor) => (
                <div key={doctor.doctor_id} style={pageStyles.row}>
                  <div style={pageStyles.rowMeta}>
                    <div style={pageStyles.rowTitle}>{doctor.name || doctor.doctor_id}</div>
                    <div style={pageStyles.rowSub}>
                      {doctor.doctor_id}
                      {doctor.specialization ? ` · ${doctor.specialization}` : ''}
                      {doctor.hospital_name ? ` · ${doctor.hospital_name}` : ''}
                    </div>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={statusPill(doctor.is_banned ? 'Banned' : 'Active', doctor.is_banned ? 'danger' : 'success')}>
                        {doctor.is_banned ? 'Banned' : 'Active'}
                      </span>
                      {doctor.ban_reason && <span style={statusPill('Reason', 'warn')}>{doctor.ban_reason}</span>}
                    </div>
                  </div>
                  <button
                    type="button"
                    style={pageStyles.mutedBtn}
                    disabled={doctor.is_banned || busyId === `doctor:${doctor.doctor_id}`}
                    onClick={() => handleBanDoctor(doctor.doctor_id)}
                  >
                    {doctor.is_banned ? 'Banned' : busyId === `doctor:${doctor.doctor_id}` ? 'Banning...' : 'Ban doctor'}
                  </button>
                </div>
              ))}
              {recentDoctors.length === 0 && <div style={{ color: '#64748b', fontSize: '14px' }}>No doctors found.</div>}
            </div>
          </div>

          <div style={{ ...pageStyles.card, ...pageStyles.sectionCard }}>
            <h2 style={pageStyles.sectionTitle}>Account Snapshot</h2>
            <p style={pageStyles.sectionSub}>Current profile and system state for the signed-in admin.</p>
            <div style={{ display: 'grid', gap: '12px' }}>
              <div style={pageStyles.row}>
                <div style={pageStyles.rowMeta}>
                  <div style={pageStyles.rowTitle}>Signed in as</div>
                  <div style={pageStyles.rowSub}>{session?.user_id || adminName}</div>
                </div>
                <span style={statusPill('Admin', 'success')}>Admin</span>
              </div>
              <div style={pageStyles.row}>
                <div style={pageStyles.rowMeta}>
                  <div style={pageStyles.rowTitle}>Total admins</div>
                  <div style={pageStyles.rowSub}>Accounts with administrative access</div>
                </div>
                <span style={statusPill(String(dashboard?.admin_count ?? 1), 'warn')}>{dashboard?.admin_count ?? 1}</span>
              </div>
              <div style={pageStyles.row}>
                <div style={pageStyles.rowMeta}>
                  <div style={pageStyles.rowTitle}>Profile status</div>
                  <div style={pageStyles.rowSub}>{profileForm.bio || 'No bio set yet'}</div>
                </div>
                <span style={statusPill(profileForm.email ? 'Complete' : 'Incomplete', profileForm.email ? 'success' : 'warn')}>
                  {profileForm.email ? 'Complete' : 'Incomplete'}
                </span>
              </div>
            </div>

            <div style={{ marginTop: '18px', display: 'grid', gap: '14px' }}>
              <div style={pageStyles.row}>
                <div style={pageStyles.rowMeta}>
                  <div style={pageStyles.rowTitle}>Create invite token</div>
                  <div style={pageStyles.rowSub}>Invite another admin without exposing a public signup form.</div>
                </div>
                <button type="button" style={pageStyles.mutedBtn} onClick={handleCreateInvite}>Generate</button>
              </div>
              <form onSubmit={handleCreateInvite} style={{ display: 'grid', gap: '10px' }}>
                <input style={pageStyles.input} type="email" value={inviteForm.invitee_email} onChange={(event) => setInviteForm((prev) => ({ ...prev, invitee_email: event.target.value }))} placeholder="Invitee email (optional)" />
                <input style={pageStyles.input} value={inviteForm.note} onChange={(event) => setInviteForm((prev) => ({ ...prev, note: event.target.value }))} placeholder="Short note (optional)" />
                <input style={pageStyles.input} type="number" min="5" max="10080" value={inviteForm.expires_in_minutes} onChange={(event) => setInviteForm((prev) => ({ ...prev, expires_in_minutes: Number(event.target.value) || 60 }))} placeholder="Expiry in minutes" />
              </form>
              {inviteResult && (
                <div style={{ ...pageStyles.row, alignItems: 'flex-start', flexDirection: 'column' }}>
                  <div style={pageStyles.rowTitle}>Invite token</div>
                  <div style={pageStyles.rowSub}>
                    Share this token once: {inviteResult.invite_token}
                  </div>
                  <div style={pageStyles.rowSub}>
                    Expires at: {inviteResult.expires_at ? new Date(inviteResult.expires_at).toLocaleString() : 'unknown'}
                  </div>
                </div>
              )}

              <div style={pageStyles.row}>
                <div style={pageStyles.rowMeta}>
                  <div style={pageStyles.rowTitle}>Enable MFA</div>
                  <div style={pageStyles.rowSub}>Generate a TOTP secret, then confirm with a 6-digit code.</div>
                </div>
                <button type="button" style={pageStyles.mutedBtn} onClick={handleSetupMfa}>Setup</button>
              </div>
              {mfaSetup && (
                <div style={{ display: 'grid', gap: '10px' }}>
                  <div style={pageStyles.rowSub}>Secret: {mfaSetup.mfa_secret}</div>
                  <div style={pageStyles.rowSub}>OTP URL: {mfaSetup.otpauth_url}</div>
                  <input
                    style={pageStyles.input}
                    value={mfaCode}
                    onChange={(event) => setMfaCode(event.target.value)}
                    placeholder="Enter the 6-digit code from your authenticator app"
                  />
                  <button type="button" style={pageStyles.primaryBtn} onClick={handleConfirmMfa}>Confirm MFA</button>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
