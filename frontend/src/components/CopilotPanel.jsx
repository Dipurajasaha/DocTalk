import React, { useState } from 'react';
import StructuredReply from './StructuredReply';
import { doctorApi, patientApi } from '../lib/api';

const normalizeCopilotResponse = (payload) => {
  if (!payload || typeof payload !== 'object') return null;
  return {
    title: 'Doctor Copilot',
    description: payload.patient_summary?.text || '',
    key_points: Array.isArray(payload.key_findings)
      ? payload.key_findings.map((item) => item?.finding || '').filter(Boolean)
      : [],
    observations: Array.isArray(payload.recent_reports)
      ? payload.recent_reports.map((item) => item?.original_name || item?.id || '').filter(Boolean)
      : [],
    recommendations: Array.isArray(payload.warnings) ? payload.warnings.filter(Boolean) : [],
    raw: payload,
  };
};

export default function CopilotPanel({ defaultPatientId = '' }) {
  const [patientId, setPatientId] = useState(defaultPatientId || '');
  const [consultationId, setConsultationId] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  React.useEffect(() => {
    console.error('[CopilotPanel] state', {
      loading,
      hasError: Boolean(error),
      hasResult: Boolean(result),
      resultType: result ? typeof result : 'null',
    });
  }, [loading, error, result]);

  const fetchForPatient = async () => {
    if (!patientId) return;
    setLoading(true); setError(null); setResult(null);
    try {
      console.error('[CopilotPanel] patient fetch start', { patientId });
      const data = await doctorApi.getCopilotForPatient(patientId);
      console.error('[CopilotPanel] patient fetch response', data);
      setResult(normalizeCopilotResponse(data) || data);
    } catch (err) {
      console.error('[CopilotPanel] patient fetch error', err);
      setError(err?.message || 'Failed fetching copilot output');
    } finally { setLoading(false); }
  };

  const fetchForConsultation = async () => {
    if (!consultationId) return;
    setLoading(true); setError(null); setResult(null);
    try {
      console.error('[CopilotPanel] consultation fetch start', { consultationId });
      const data = await doctorApi.getCopilotForConsultation(consultationId);
      console.error('[CopilotPanel] consultation fetch response', data);
      setResult(normalizeCopilotResponse(data) || data);
    } catch (err) {
      console.error('[CopilotPanel] consultation fetch direct error', err);
      try {
        const consultation = await patientApi.getConsultation(consultationId);
        console.error('[CopilotPanel] consultation lookup response', consultation);
        const patientId = consultation?.patientUsername || consultation?.patient_id || consultation?.patientId;
        if (!patientId) throw err;
        const fallback = await doctorApi.getCopilotForPatient(patientId, consultationId);
        console.error('[CopilotPanel] consultation fallback response', fallback);
        setResult(normalizeCopilotResponse(fallback) || fallback);
        return;
      } catch (fallbackError) {
        console.error('[CopilotPanel] consultation fetch fallback error', fallbackError);
        setError(fallbackError?.message || err?.message || 'Failed fetching copilot output');
      }
    } finally { setLoading(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <input placeholder="Patient id (username)" value={patientId} onChange={e=>setPatientId(e.target.value)} style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #e2e8f0', flex: 1 }} />
        <button onClick={fetchForPatient} disabled={loading || !patientId} style={{ background:'#8B7EFF', color:'#fff', border:'none', padding:'8px 14px', borderRadius:'8px', cursor:'pointer' }}>{loading ? 'Loading...' : 'Fetch'}</button>
      </div>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <input placeholder="Consultation id (optional)" value={consultationId} onChange={e=>setConsultationId(e.target.value)} style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #e2e8f0', flex: 1 }} />
        <button onClick={fetchForConsultation} disabled={loading || !consultationId} style={{ background:'#0ea5e9', color:'#fff', border:'none', padding:'8px 14px', borderRadius:'8px', cursor:'pointer' }}>{loading ? 'Loading...' : 'Fetch (consultation)'}</button>
      </div>

      <div style={{ minHeight: '120px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '12px' }}>
        {error && <div style={{ color: 'red' }}>{String(error)}</div>}
        {!error && !result && <div style={{ color: '#64748B' }}>No results. Run a fetch to load copilot output (read-only).</div>}
        {result && (
          <div>
            {/* If structured reply, render using StructuredReply */}
            <StructuredReply data={result} />
          </div>
        )}
      </div>
    </div>
  );
}
