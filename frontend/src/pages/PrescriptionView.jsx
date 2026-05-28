import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { patientApi } from '../lib/api';
import { useSession } from '../contexts/SessionContext';
import FileViewer from '../components/FileViewer';

export default function PrescriptionView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { markExpired } = useSession();
  const [prescription, setPrescription] = useState(null);
  const [consultations, setConsultations] = useState([]);
  const [selectedConsultation, setSelectedConsultation] = useState('');
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('doctalk_token');
    if (!token) { navigate('/login'); return; }

    (async () => {
      try {
        const data = await patientApi.getPrescription(id);
        setPrescription(data || null);
      } catch (err) {
        console.error('Failed fetching prescription', err);
        if (err?.status === 401 || err?.status === 403) { try { markExpired(); } catch (e) {} navigate('/login'); return; }
      }

      try {
        const c = await patientApi.listConsultations();
        setConsultations(Array.isArray(c) ? c : (c.sessions || c.consultations || []));
      } catch (err) {
        console.warn('Failed fetching consultations', err);
        setConsultations([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [id, navigate, markExpired]);

  const handleAttach = async () => {
    if (!selectedConsultation) { alert('Choose a consultation to attach to'); return; }
    try {
      const res = await patientApi.attachPrescriptionToConsultation(id, selectedConsultation);
      if (res && (res.success || res.message)) {
        alert('Prescription attached to consultation');
      } else {
        alert('Attach succeeded');
      }
    } catch (err) {
      console.error('Attach failed', err);
      if (err?.status === 404) alert('Attach not supported by backend');
      else alert('Attach failed: ' + (err?.message || 'server error'));
    }
  };

  if (loading) return <div style={{padding:40}}>Loading...</div>;
  if (!prescription) return <div style={{padding:40}}>Prescription not found or access denied.</div>;

  const file = prescription.file || { download_url: prescription.url, mime_type: prescription.mime_type, original_name: prescription.filename || prescription.original_name || prescription.name };

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginTop: 0 }}>Prescription</h2>
      <div style={{ background: '#fff', padding: 16, borderRadius: 12, maxWidth: 860 }}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>{prescription.title || prescription.name || file.original_name}</div>
        <div style={{ color: '#6b7280', marginBottom: 12 }}>{prescription.notes || prescription.summary || ''}</div>
        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          <button onClick={() => setPreviewOpen(true)} style={{ padding: '8px 12px', borderRadius: 8 }}>Preview</button>
          {file.download_url && (
            <a href={file.download_url} target="_blank" rel="noreferrer" style={{ padding: '8px 12px', borderRadius: 8, background: '#f3f4f6', textDecoration: 'none' }}>Download</a>
          )}
        </div>

        <div style={{ marginTop: 16 }}>
          <label style={{ display: 'block', marginBottom: 6, fontWeight: 600 }}>Attach to consultation</label>
          <select value={selectedConsultation} onChange={(e) => setSelectedConsultation(e.target.value)} style={{ padding: '8px 10px', borderRadius: 8 }}>
            <option value="">-- choose consultation --</option>
            {consultations.map(c => (
              <option key={c.id || c.consultation_id || c.uuid} value={c.id || c.consultation_id || c.uuid}>{c.id || c.consultation_id || c.uuid} {c.appointment_id ? `(${c.appointment_id})` : ''}</option>
            ))}
          </select>
          <button onClick={handleAttach} style={{ marginLeft: 12, padding: '8px 12px', borderRadius: 8 }}>Attach</button>
        </div>
      </div>

      {previewOpen && <FileViewer file={file} onClose={() => setPreviewOpen(false)} />}
    </div>
  );
}
