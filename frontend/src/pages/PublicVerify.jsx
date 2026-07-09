import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { prescriptionApi } from '../lib/api';
import '../styles/prescription.css';

export default function PublicVerify() {
  const { qrToken } = useParams();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    prescriptionApi.verifyByQrToken(qrToken)
      .then(setResult)
      .catch(() => setError('Could not reach the verification service. Try again shortly.'))
      .finally(() => setLoading(false));
  }, [qrToken]);

  const renderOutcome = () => {
    if (!result || !result.found) {
      return (
        <>
          <div style={{ fontSize: 44, marginBottom: 8 }}>❌</div>
          <h1 className="rx-h1">Not found</h1>
          <p className="rx-sub">This code doesn't match any prescription in our records. It may be mistyped, or the document may not be genuine.</p>
        </>
      );
    }

    if (!result.valid_signature) {
      return (
        <>
          <div style={{ fontSize: 44, marginBottom: 8 }}>❌</div>
          <h1 className="rx-h1">Signature invalid</h1>
          <p className="rx-sub">This prescription's content does not match its original signature. Treat it as untrustworthy — do not dispense or accept it. Contact the issuing clinic directly to confirm.</p>
        </>
      );
    }

    if (result.status === 'REVOKED') {
      return (
        <>
          <div style={{ fontSize: 44, marginBottom: 8 }}>⚠️</div>
          <h1 className="rx-h1">Genuine, but revoked</h1>
          <p className="rx-sub">This prescription was authentically issued but has since been cancelled by the doctor{result.revoked_reason ? `: ${result.revoked_reason}` : '.'}</p>
        </>
      );
    }

    return (
      <>
        <div style={{ fontSize: 44, marginBottom: 8 }}>✅</div>
        <h1 className="rx-h1">Genuine &amp; unaltered</h1>
        <p className="rx-sub">This prescription's digital signature is valid and its contents have not been changed since it was issued.</p>
      </>
    );
  };

  return (
    <div className="rx-page" style={{ maxWidth: 480 }}>
      <div className="rx-card" style={{ textAlign: 'center' }}>
        {loading ? (
          <p style={{ color: '#8a8980' }}>Checking…</p>
        ) : error ? (
          <p style={{ color: '#c0392b' }}>{error}</p>
        ) : (
          <>
            {renderOutcome()}
            {result?.found && (
              <div style={{ textAlign: 'left', marginTop: 24, borderTop: '1px solid #f0efe9', paddingTop: 18, fontSize: 13, color: '#4a4942' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: '#8a8980' }}>Prescription no.</span>
                  <span style={{ fontWeight: 600 }}>{result.prescription_number}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: '#8a8980' }}>Issued by</span>
                  <span style={{ fontWeight: 600 }}>Dr. {result.doctor_name}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: '#8a8980' }}>Patient</span>
                  <span style={{ fontWeight: 600 }}>{result.patient_name_masked}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: '#8a8980' }}>Issued on</span>
                  <span style={{ fontWeight: 600 }}>{new Date(result.issued_at).toLocaleString()}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: '#8a8980' }}>Medicines</span>
                  <span style={{ fontWeight: 600 }}>{result.medicines_count}</span>
                </div>
              </div>
            )}
          </>
        )}
      </div>
      <p style={{ textAlign: 'center', fontSize: 12, color: '#a8a79f' }}>
        Verified against DocTalk Health's cryptographic signature — not dependent on trusting this webpage alone.
      </p>
    </div>
  );
}
