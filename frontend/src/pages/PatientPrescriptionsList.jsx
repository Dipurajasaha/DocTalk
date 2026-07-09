import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { prescriptionApi, medicinePriceApi } from '../lib/api';
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
  const [priceData, setPriceData] = useState({});       // { prescriptionId: { loading, results: [] } }
  const [priceError, setPriceError] = useState(null);
  const fetchedRef = useRef(new Set());

  useEffect(() => {
    prescriptionApi.listMine()
      .then((list) => setPrescriptions(Array.isArray(list) ? list : []))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (prescriptions.length === 0) return;

    prescriptions.forEach((p) => {
      if (fetchedRef.current.has(p.id)) return;
      fetchedRef.current.add(p.id);

      const medicines = (p.medicines || []).map((m) => m.name).filter(Boolean);
      if (medicines.length === 0) return;

      setPriceData((prev) => ({
        ...prev,
        [p.id]: { loading: true, results: [] },
      }));

      medicinePriceApi.lookupPrices(medicines)
        .then((response) => {
          const results = response?.results || [];
          setPriceData((prev) => ({
            ...prev,
            [p.id]: { loading: false, results },
          }));
        })
        .catch(() => {
          setPriceError('Failed to fetch medicine prices. Please try again later.');
          setPriceData((prev) => ({
            ...prev,
            [p.id]: { loading: false, results: [] },
          }));
        });
    });
  }, [prescriptions]);

  const handleShowPrices = async (prescriptionId, medicines) => {
    // Prevent re-fetching if already loaded or loading
    if (priceData[prescriptionId]?.loading || priceData[prescriptionId]?.results?.length > 0) return;

    setPriceData((prev) => ({
      ...prev,
      [prescriptionId]: { loading: true, results: [] },
    }));
    setPriceError(null);

    try {
      const medicineNames = medicines.map((m) => m.name).filter(Boolean);
      if (medicineNames.length === 0) {
        setPriceData((prev) => ({
          ...prev,
          [prescriptionId]: { loading: false, results: [] },
        }));
        return;
      }

      const response = await medicinePriceApi.lookupPrices(medicineNames);
      const results = response?.results || [];

      setPriceData((prev) => ({
        ...prev,
        [prescriptionId]: { loading: false, results },
      }));
    } catch (err) {
      setPriceError('Failed to fetch medicine prices. Please try again later.');
      setPriceData((prev) => ({
        ...prev,
        [prescriptionId]: { loading: false, results: [] },
      }));
    }
  };

  const getPriceInfo = (prescriptionId, medicineName) => {
    const data = priceData[prescriptionId];
    if (!data || !data.results) return null;
    return data.results.find(
      (r) => r.medicine_name?.toLowerCase() === medicineName?.toLowerCase()
    );
  };

  return (
    <div className="rx-page">
      <button onClick={() => navigate(-1)} className="rx-btn-ghost" style={{ marginBottom: 12 }}>← Back</button>
      <h1 className="rx-h1">My prescriptions</h1>
      <p className="rx-sub">Issued by your doctors, digitally signed, and verifiable by anyone via QR code.</p>

      {priceError && (
        <div style={{ background: '#fdecea', color: '#c0392b', padding: '10px 14px', borderRadius: 8, marginBottom: 16, fontSize: 13 }}>
          {priceError}
        </div>
      )}

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
                    <>
                      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', marginBottom: 14 }}>
                        <thead>
                          <tr style={{ color: '#8a8980', textAlign: 'left' }}>
                            <th style={{ fontWeight: 500, padding: '4px 8px 4px 0' }}>Medicine</th>
                            <th style={{ fontWeight: 500, padding: '4px 8px' }}>Dosage</th>
                            <th style={{ fontWeight: 500, padding: '4px 8px' }}>Frequency</th>
                            <th style={{ fontWeight: 500, padding: '4px 8px' }}>Duration</th>
                            <th style={{ fontWeight: 500, padding: '4px 8px' }}>Purpose</th>
                            <th style={{ fontWeight: 500, padding: '4px 8px' }}>Price</th>
                            <th style={{ fontWeight: 500, padding: '4px 8px' }}>Platform</th>
                          </tr>
                        </thead>
                        <tbody>
                          {p.medicines.map((m, i) => {
                            const priceInfo = getPriceInfo(p.id, m.name);
                            return (
                              <tr key={i}>
                                <td style={{ padding: '4px 8px 4px 0', fontWeight: 500 }}>{m.name}</td>
                                <td style={{ padding: '4px 8px' }}>{m.dosage}</td>
                                <td style={{ padding: '4px 8px' }}>{m.frequency}</td>
                                <td style={{ padding: '4px 8px' }}>{m.duration}</td>
                                <td style={{ padding: '4px 8px', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={priceInfo?.purpose || ''}>
                                  {priceInfo?.purpose || (
                                    <span style={{ color: '#bbb' }}>—</span>
                                  )}
                                </td>
                                <td style={{ padding: '4px 8px', fontWeight: 600, color: '#2e7d32' }}>
                                  {priceInfo?.price && priceInfo.price !== 'Not found' ? (
                                    priceInfo.price
                                  ) : (
                                    <span style={{ color: '#bbb' }}>—</span>
                                  )}
                                </td>
                                <td style={{ padding: '4px 8px' }}>
                                  {priceInfo?.platform_name && priceInfo.platform_name !== 'N/A' ? (
                                    priceInfo.source_url ? (
                                      <a
                                        href={priceInfo.source_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color: '#1a73e8', textDecoration: 'none' }}
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        {priceInfo.platform_name}
                                      </a>
                                    ) : (
                                      <span>{priceInfo.platform_name}</span>
                                    )
                                  ) : (
                                    <span style={{ color: '#bbb' }}>—</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>

                      {/* Show Prices button */}
                      {(!priceData[p.id] || (!priceData[p.id].loading && priceData[p.id].results.length === 0)) && (
                        <div style={{ marginBottom: 14 }}>
                          <button
                            className="rx-btn-secondary"
                            onClick={async (e) => {
                              e.stopPropagation();
                              await handleShowPrices(p.id, p.medicines);
                            }}
                            disabled={priceData[p.id]?.loading}
                            style={{ fontSize: 12, padding: '6px 14px' }}
                          >
                            {priceData[p.id]?.loading ? 'Loading prices…' : 'Show medicine prices'}
                          </button>
                        </div>
                      )}
                    </>
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