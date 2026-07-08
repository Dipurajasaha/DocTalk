import { useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { prescriptionApi } from '../lib/api';
import '../styles/prescription.css';

const emptyMedicine = () => ({ name: '', dosage: '', frequency: '', duration: '', notes: '' });

export default function PrescriptionComposer() {
  const { patientUsername: routePatient } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [patientUsername, setPatientUsername] = useState(routePatient || searchParams.get('patient') || '');
  const [consultationId] = useState(searchParams.get('consultationId') || null);
  const [medicines, setMedicines] = useState([emptyMedicine()]);
  const [includeSickNote, setIncludeSickNote] = useState(false);
  const [sickNote, setSickNote] = useState({ reason: '', startDate: '', endDate: '' });
  const [doctorNotes, setDoctorNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [issued, setIssued] = useState(null);

  const updateMedicine = (i, field, value) => {
    setMedicines((prev) => prev.map((m, idx) => (idx === i ? { ...m, [field]: value } : m)));
  };
  const addMedicine = () => setMedicines((prev) => [...prev, emptyMedicine()]);
  const removeMedicine = (i) => setMedicines((prev) => prev.filter((_, idx) => idx !== i));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const cleanedMedicines = medicines
      .filter((m) => m.name.trim() && m.dosage.trim())
      .map((m) => ({ ...m }));

    if (!patientUsername.trim()) {
      setError('Enter the patient\'s username');
      return;
    }
    if (cleanedMedicines.length === 0 && !includeSickNote) {
      setError('Add at least one medicine, or include a sick note');
      return;
    }
    if (includeSickNote && (!sickNote.reason.trim() || !sickNote.startDate || !sickNote.endDate)) {
      setError('Fill in the sick note reason and both dates, or turn it off');
      return;
    }

    setSubmitting(true);
    try {
      const result = await prescriptionApi.issue({
        patientUsername: patientUsername.trim(),
        consultationId,
        medicines: cleanedMedicines,
        sickNote: includeSickNote ? sickNote : null,
        doctorNotes: doctorNotes.trim() || null,
      });
      setIssued(result);
    } catch (e2) {
      if (e2.status === 422 && String(e2.message || '').toLowerCase().includes('signature')) {
        setError('You need to save your signature before issuing prescriptions.');
      } else {
        setError(e2.message || 'Could not issue prescription');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (issued) {
    return (
      <div className="rx-page">
        <div className="rx-card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>✓</div>
          <h1 className="rx-h1">Prescription issued</h1>
          <p className="rx-sub">{issued.prescriptionNumber} · signed and sealed</p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 20 }}>
            <button className="rx-btn-secondary" onClick={() => navigate(-1)}>Done</button>
            <button
              className="rx-btn-primary"
              onClick={async () => {
                const blob = await prescriptionApi.fetchPdfBlob(issued.id);
                const url = URL.createObjectURL(blob);
                window.open(url, '_blank');
              }}
            >
              View PDF
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rx-page">
      <button onClick={() => navigate(-1)} className="rx-btn-ghost" style={{ marginBottom: 12 }}>← Back</button>
      <h1 className="rx-h1">New prescription</h1>
      <p className="rx-sub">Signed, sealed, and tamper-evident once issued — corrections require a new version.</p>

      <form onSubmit={handleSubmit}>
        <div className="rx-card">
          <label className="rx-label">Patient username</label>
          <input
            className="rx-input"
            value={patientUsername}
            onChange={(e) => setPatientUsername(e.target.value)}
            disabled={!!routePatient}
            placeholder="e.g. rohit_b21"
          />
        </div>

        <div className="rx-card">
          <label className="rx-label" style={{ marginBottom: 14 }}>Medicines</label>
          {medicines.map((m, i) => (
            <div className="rx-med-row" key={i}>
              <div>
                {i === 0 && <div style={{ fontSize: 11, color: '#8a8980', marginBottom: 4 }}>Name</div>}
                <input className="rx-input" value={m.name} onChange={(e) => updateMedicine(i, 'name', e.target.value)} placeholder="Amoxicillin" />
              </div>
              <div>
                {i === 0 && <div style={{ fontSize: 11, color: '#8a8980', marginBottom: 4 }}>Dosage</div>}
                <input className="rx-input" value={m.dosage} onChange={(e) => updateMedicine(i, 'dosage', e.target.value)} placeholder="500mg" />
              </div>
              <div>
                {i === 0 && <div style={{ fontSize: 11, color: '#8a8980', marginBottom: 4 }}>Frequency</div>}
                <input className="rx-input" value={m.frequency} onChange={(e) => updateMedicine(i, 'frequency', e.target.value)} placeholder="3x/day" />
              </div>
              <div>
                {i === 0 && <div style={{ fontSize: 11, color: '#8a8980', marginBottom: 4 }}>Duration</div>}
                <input className="rx-input" value={m.duration} onChange={(e) => updateMedicine(i, 'duration', e.target.value)} placeholder="7 days" />
              </div>
              <button type="button" className="rx-btn-ghost" onClick={() => removeMedicine(i)} disabled={medicines.length === 1}>✕</button>
            </div>
          ))}
          <button type="button" className="rx-btn-secondary" onClick={addMedicine} style={{ marginTop: 4 }}>+ Add medicine</button>
        </div>

        <div className="rx-card">
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input type="checkbox" checked={includeSickNote} onChange={(e) => setIncludeSickNote(e.target.checked)} />
            <span className="rx-label" style={{ margin: 0 }}>Include a sick note / fitness certificate</span>
          </label>
          {includeSickNote && (
            <div className="rx-row" style={{ marginTop: 14 }}>
              <div>
                <label className="rx-label">Reason</label>
                <input className="rx-input" value={sickNote.reason} onChange={(e) => setSickNote({ ...sickNote, reason: e.target.value })} placeholder="Viral fever, advised rest" />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div>
                  <label className="rx-label">From</label>
                  <input type="date" className="rx-input" value={sickNote.startDate} onChange={(e) => setSickNote({ ...sickNote, startDate: e.target.value })} />
                </div>
                <div>
                  <label className="rx-label">To</label>
                  <input type="date" className="rx-input" value={sickNote.endDate} onChange={(e) => setSickNote({ ...sickNote, endDate: e.target.value })} />
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="rx-card">
          <label className="rx-label">Doctor's notes (optional)</label>
          <textarea className="rx-textarea" value={doctorNotes} onChange={(e) => setDoctorNotes(e.target.value)} placeholder="Follow up if fever persists beyond 3 days" />
        </div>

        {error && <p style={{ color: '#c0392b', fontSize: 14, marginBottom: 14 }}>{error}</p>}

        <button type="submit" className="rx-btn-primary" disabled={submitting}>
          {submitting ? 'Issuing…' : 'Issue prescription'}
        </button>
      </form>
    </div>
  );
}
