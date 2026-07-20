import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { prescriptionApi } from '../lib/api';
import BackButton from '../components/BackButton';
import SignaturePad from '../components/SignaturePad';
import '../styles/prescription.css';

export default function DoctorSignatureSetup() {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    prescriptionApi.getSignatureStatus()
      .then(setStatus)
      .catch(() => setStatus({ hasSignature: false }))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (dataUrl) => {
    setSaving(true);
    setError('');
    try {
      await prescriptionApi.saveSignature(dataUrl);
      const updated = await prescriptionApi.getSignatureStatus();
      setStatus(updated);
    } catch (e) {
      setError(e.message || 'Could not save signature');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="rx-page">
      <BackButton />
      <h1 className="rx-h1">Your signature</h1>
      <p className="rx-sub">Saved once, then stamped automatically on every prescription you issue.</p>

      <div className="rx-card">
        {loading ? (
          <p style={{ color: '#8a8980' }}>Loading…</p>
        ) : status?.hasSignature ? (
          <div>
            <p className="rx-label">Currently saved signature</p>
            <img
              src={status.signatureImageBase64}
              alt="Your saved signature"
              style={{ background: '#fff', border: '1px solid #e6e5df', borderRadius: 12, padding: 12, maxWidth: 300, display: 'block', marginBottom: 16 }}
            />
            <p style={{ fontSize: 13, color: '#8a8980', marginBottom: 20 }}>
              Last updated {status.signatureUpdatedAt ? new Date(status.signatureUpdatedAt).toLocaleString() : ''}.
              Draw a new one below to replace it — this won't change any prescriptions already issued.
            </p>
            <SignaturePad onSave={handleSave} saving={saving} />
          </div>
        ) : (
          <SignaturePad onSave={handleSave} saving={saving} />
        )}
        {error && <p style={{ color: '#c0392b', fontSize: 13, marginTop: 12 }}>{error}</p>}
      </div>
    </div>
  );
}
