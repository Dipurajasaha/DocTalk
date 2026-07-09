import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { prescriptionApi } from '../lib/api';
import '../styles/prescription.css';

const statusBadge = (status) => {
  if (status === 'ACTIVE') return <span className="rx-badge rx-badge-active">Active</span>;
  if (status === 'REVOKED') return <span className="rx-badge rx-badge-revoked">Revoked</span>;
  return <span className="rx-badge rx-badge-superseded">Replaced by a newer version</span>;
};

export default function PatientPrescriptionsList() {
  const navigate = useNavigate();
  const [prescriptions, setPrescriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    prescriptionApi.listMine()
      .then((list) => setPrescriptions(Array.isArray(list) ? list : []))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="rx-page">
      <button onClick={() => navigate(-1)} className="rx-btn-ghost" style={{ marginBottom: 12 }}>← Back</button>
      <h1 className="rx-h1">My prescriptions</h1>
      <p className="rx-sub">Issued by your doctors, digitally signed, and verifiable by anyone via QR code.</p>

      <div className="rx-card">
        {loading ? (
          <p style={{ color: '#8a8980' }}>Loading…</p>
        ) : prescriptions.length === 0 ? (
          <div className="rx-empty">No prescriptions yet.</div>
        ) : (
          prescriptions.map((p) => (
            <div key={p.id}>
              <div className="rx-list-item" style={{ cursor: 'pointer' }} onClick={() => setExpandedId(expandedId === p.id ? null : p.id)}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{p.prescriptionNumber} · Dr. {p.doctorName}</div>
                  <div style={{ fontSize: 12, color: '#8a8980', marginTop: 2 }}>
                    {new Date(p.issuedAt).toLocaleDateString()} · {(p.medicines || []).length} medicine(s){p.sickNote ? ' · sick note' : ''}
                  </div>
                </div>
                {statusBadge(p.status)}
              </div>
              {expandedId === p.id && (
                <div style={{ padding: '4px 0 18px', borderBottom: '1px solid #f0efe9' }}>
                  {p.status === 'REVOKED' && (
                    <p style={{ fontSize: 13, color: '#c0392b', marginBottom: 12 }}>
                      Revoked: {p.revokedReason}
                    </p>
                  )}
                  {(p.medicines || []).length > 0 && (
                    <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', marginBottom: 14 }}>
                      <thead>
                        <tr style={{ color: '#8a8980', textAlign: 'left' }}>
                          <th style={{ fontWeight: 500, padding: '4px 8px 4px 0' }}>Medicine</th>
                          <th style={{ fontWeight: 500, padding: '4px 8px' }}>Dosage</th>
                          <th style={{ fontWeight: 500, padding: '4px 8px' }}>Frequency</th>
                          <th style={{ fontWeight: 500, padding: '4px 8px' }}>Duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {p.medicines.map((m, i) => (
                          <tr key={i}>
                            <td style={{ padding: '4px 8px 4px 0' }}>{m.name}</td>
                            <td style={{ padding: '4px 8px' }}>{m.dosage}</td>
                            <td style={{ padding: '4px 8px' }}>{m.frequency}</td>
                            <td style={{ padding: '4px 8px' }}>{m.duration}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {p.sickNote && (
                    <div style={{ background: '#fdf3e3', borderRadius: 8, padding: '8px 12px', fontSize: 13, marginBottom: 14 }}>
                      Sick note: {p.sickNote.reason} — rest advised {p.sickNote.startDate} to {p.sickNote.endDate}
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                    <button
                      className="rx-btn-primary"
                      onClick={async (e) => {
                        e.stopPropagation();
                        const blob = await prescriptionApi.fetchPdfBlob(p.id);
                        window.open(URL.createObjectURL(blob), '_blank');
                      }}
                    >
                      Download PDF
                    </button>
                    <button
                      className="rx-btn-secondary"
                      onClick={(e) => { e.stopPropagation(); navigate(`/verify/${p.qrToken}`); }}
                    >
                      Verify authenticity
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
