import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { prescriptionApi } from '../lib/api';
import '../styles/prescription.css';

const statusBadge = (status) => {
  if (status === 'ACTIVE') return <span className="rx-badge rx-badge-active">Active</span>;
  if (status === 'REVOKED') return <span className="rx-badge rx-badge-revoked">Revoked</span>;
  return <span className="rx-badge rx-badge-superseded">Superseded</span>;
};

export default function DoctorPrescriptionsList() {
  const navigate = useNavigate();
  const [prescriptions, setPrescriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hasSignature, setHasSignature] = useState(true);
  const [revokingId, setRevokingId] = useState(null);
  const [revokeReason, setRevokeReason] = useState('');

  const load = () => {
    setLoading(true);
    Promise.all([prescriptionApi.listIssued(), prescriptionApi.getSignatureStatus()])
      .then(([list, sig]) => {
        setPrescriptions(Array.isArray(list) ? list : []);
        setHasSignature(!!sig?.hasSignature);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleRevoke = async (id) => {
    if (!revokeReason.trim()) return;
    await prescriptionApi.revoke(id, revokeReason.trim());
    setRevokingId(null);
    setRevokeReason('');
    load();
  };

  return (
    <div className="rx-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <h1 className="rx-h1">Prescriptions</h1>
          <p className="rx-sub">Everything you've issued — signed, sealed, tamper-evident.</p>
        </div>
        <button className="rx-btn-secondary" onClick={() => navigate('/doctor/signature')}>
          {hasSignature ? 'Update signature' : 'Set up signature'}
        </button>
      </div>

      {!hasSignature && (
        <div className="rx-card" style={{ background: '#fdf3e3', border: '1px solid #f0d9a8' }}>
          <p style={{ margin: 0, fontSize: 14 }}>
            You haven't saved a signature yet — you'll need one before you can issue a prescription.{' '}
            <a onClick={() => navigate('/doctor/signature')} style={{ color: '#6C5CE7', cursor: 'pointer', fontWeight: 600 }}>Set it up now</a>
          </p>
        </div>
      )}

      <button className="rx-btn-primary" onClick={() => navigate('/doctor/prescriptions/new')} style={{ marginBottom: 20 }}>
        + New prescription
      </button>

      <div className="rx-card">
        {loading ? (
          <p style={{ color: '#8a8980' }}>Loading…</p>
        ) : prescriptions.length === 0 ? (
          <div className="rx-empty">No prescriptions issued yet.</div>
        ) : (
          prescriptions.map((p) => (
            <div className="rx-list-item" key={p.id}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{p.prescriptionNumber} · {p.patientName || p.patientUsername}</div>
                <div style={{ fontSize: 12, color: '#8a8980', marginTop: 2 }}>
                  {new Date(p.issuedAt).toLocaleDateString()} · {(p.medicines || []).length} medicine(s){p.sickNote ? ' · sick note' : ''}
                </div>
                {revokingId === p.id && (
                  <div style={{ marginTop: 10, display: 'flex', gap: 8 }}>
                    <input
                      className="rx-input"
                      placeholder="Reason for revoking"
                      value={revokeReason}
                      onChange={(e) => setRevokeReason(e.target.value)}
                      style={{ maxWidth: 260 }}
                    />
                    <button className="rx-btn-danger" onClick={() => handleRevoke(p.id)}>Confirm</button>
                    <button className="rx-btn-secondary" onClick={() => setRevokingId(null)}>Cancel</button>
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {statusBadge(p.status)}
                <button
                  className="rx-btn-ghost"
                  onClick={async () => {
                    const blob = await prescriptionApi.fetchPdfBlob(p.id);
                    window.open(URL.createObjectURL(blob), '_blank');
                  }}
                >
                  View
                </button>
                {p.status === 'ACTIVE' && (
                  <button className="rx-btn-danger" onClick={() => { setRevokingId(p.id); setRevokeReason(''); }}>Revoke</button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
