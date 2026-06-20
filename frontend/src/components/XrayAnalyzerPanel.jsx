import { useState } from 'react';

const isJsonLike = (text) => {
  if (!text) return false;
  const trimmed = text.trim();
  if (trimmed.startsWith('```json')) return true;
  if (trimmed.startsWith('{')) return true;
  if (trimmed.startsWith('[')) return true;
  return false;
};

const tryParseJson = (text) => {
  if (!text) return null;
  const trimmed = text.trim();
  const stripped = trimmed.startsWith('```')
    ? trimmed.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
    : trimmed;
  try {
    const parsed = JSON.parse(stripped);
    if (parsed && typeof parsed === 'object') return parsed;
    return null;
  } catch {
    return null;
  }
};

const getCleanAnalysisText = (analysis) => {
  if (!analysis) return '';
  const trimmed = analysis.trim();
  if (isJsonLike(trimmed)) {
    const parsed = tryParseJson(trimmed);
    if (parsed) {
      return parsed.analysis || parsed.findings || parsed.summary || parsed.description || JSON.stringify(parsed, null, 2);
    }

    // Fallback: Regex extraction for truncated JSON
    const getValFor = (key) => {
      const regex = new RegExp(`"${key}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)`, 'i');
      const match = trimmed.match(regex);
      if (match && match[1]) {
        let val = match[1];
        // Clean up unmatched escape quotes or JSON syntax characters at the end
        val = val.replace(/\\"/g, '"').replace(/\\n/g, '\n').trim();
        // If it was truncated, clean up trailing comma, closing quote, etc. if any matched
        if (val.endsWith('"')) {
          val = val.slice(0, -1);
        }
        return val;
      }
      return '';
    };

    const extractedAnalysis = getValFor('analysis');
    if (extractedAnalysis) return extractedAnalysis;
    const extractedFindings = getValFor('findings');
    if (extractedFindings) return extractedFindings;
    const extractedSummary = getValFor('summary');
    if (extractedSummary) return extractedSummary;
  }
  return analysis;
};

export default function XrayAnalyzerPanel() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [language, setLanguage] = useState('en');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!selectedFile) {
      setErrorMsg('Select an X-ray image first.');
      return;
    }

    const formData = new FormData();
    formData.append('xray', selectedFile);
    formData.append('language', language);

    setIsSubmitting(true);
    setErrorMsg('');
    setResult(null);

    try {
      const token = localStorage.getItem('doctalk_token');
      const response = await fetch('/api/analyze_xray', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
        credentials: 'include',
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.error || 'X-ray analysis failed');
      }

      setResult(data);
    } catch (error) {
      setErrorMsg(error.message || 'Unable to analyze the X-ray image.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const resolveImageUrl = (path) => {
    if (!path) return '';
    if (path.startsWith('http://') || path.startsWith('https://')) return path;
    if (path.startsWith('/')) return path;
    return path;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, gap: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <h2 style={{ margin: 0, fontSize: '18px', color: '#6C5CE7', fontWeight: 'bold', fontFamily: '"Inter", system-ui, -apple-system, sans-serif', letterSpacing: '-0.5px' }}>
            X-Ray Analysis
          </h2>
          <p style={{ margin: 0, fontSize: '11px', color: '#8B7EFF', fontWeight: '500' }}>
            Educational comparison and defect highlighting only.
          </p>
        </div>

        <div style={{ width: '160px' }}>
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value)}
            style={{ width: '100%', padding: '10px 14px', border: '1px solid #E2E8F0', borderRadius: '8px', outline: 'none', fontSize: '11px', backgroundColor: '#FFF', boxShadow: '0 2px 4px rgba(0,0,0,0.15)' }}
          >
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="hi">Hindi</option>
            <option value="bn">Bengali</option>
          </select>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 340px) minmax(0, 1fr)', gap: '24px', flex: 1, minHeight: 0 }}>
        <div style={{ background: '#FFF', borderRadius: '16px', padding: '24px', boxShadow: '0 24px 48px rgba(0,0,0,0.15), 0 12px 24px rgba(0,0,0,0.1)', border: '1px solid #e1e4e8' }}>
          <h4 style={{ margin: '0 0 14px', fontSize: '13px', color: '#6C5CE7', fontWeight: 'bold' }}>Upload X-Ray Image</h4>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <label style={{ border: '2px dashed #CBD5E1', borderRadius: '16px', padding: '28px 16px', textAlign: 'center', background: '#F8FAFC', cursor: 'pointer', color: '#475569', fontSize: '12px', fontWeight: '600' }}>
              <input
                type="file"
                accept=".jpg,.jpeg,.png,.gif"
                onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                style={{ display: 'none' }}
              />
              {selectedFile ? selectedFile.name : 'Choose an X-ray image'}
            </label>

            <div style={{ fontSize: '11px', color: '#64748B' }}>
              Supported: JPG, JPEG, PNG, GIF
            </div>

            <button
              type="submit"
              disabled={isSubmitting || !selectedFile}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '50px',
                border: 'none',
                cursor: isSubmitting || !selectedFile ? 'not-allowed' : 'pointer',
                opacity: isSubmitting || !selectedFile ? 0.65 : 1,
                color: '#FFF',
                background: 'linear-gradient(to right, #D67CFF, #6B5CE7)',
                fontWeight: '700',
                fontSize: '12px',
              }}
            >
              {isSubmitting ? 'Analyzing...' : 'Analyze X-Ray'}
            </button>

            {errorMsg && (
              <div style={{ background: '#FEF2F2', color: '#B91C1C', border: '1px solid #FECACA', borderRadius: '12px', padding: '12px', fontSize: '12px', fontWeight: '600' }}>
                {errorMsg}
              </div>
            )}
          </form>
        </div>

        <div style={{ background: '#FFF', borderRadius: '16px', padding: '24px', boxShadow: '0 24px 48px rgba(0,0,0,0.15), 0 12px 24px rgba(0,0,0,0.1)', border: '1px solid #e1e4e8', overflowY: 'auto', minHeight: 0 }}>
          <h4 style={{ margin: '0 0 12px', fontSize: '13px', color: '#6C5CE7', fontWeight: 'bold' }}>Analysis Results</h4>

          {!result ? (
            <div style={{ fontSize: '11px', color: '#64748B', background: '#F8FAFC', border: '1px dashed #CBD5E1', borderRadius: '12px', padding: '20px' }}>
              Upload an X-ray image to view the defect summary, highlighted image, and healthy comparison.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ background: result.has_defect ? '#FEE2E2' : '#DCFCE7', border: `1px solid ${result.has_defect ? '#FECACA' : '#BBF7D0'}`, borderRadius: '12px', padding: '14px' }}>
                <div style={{ fontWeight: '700', fontSize: '12px', color: result.has_defect ? '#991B1B' : '#166534' }}>
                  {result.has_defect ? '⚠️ Abnormality Detected' : '✅ No Abnormalities Detected'}
                </div>
                <div style={{ marginTop: '6px', fontSize: '11px', color: result.has_defect ? '#7F1D1D' : '#15803D' }}>
                  Severity: {result.severity}/10
                </div>
                {result.defect_type && (
                  <div style={{ marginTop: '4px', fontSize: '11px', color: result.has_defect ? '#7F1D1D' : '#15803D' }}>
                    Type: {result.defect_type}
                  </div>
                )}
              </div>

              {Array.isArray(result.warnings) && result.warnings.length > 0 && (
                <div style={{ background: '#FFFBEB', color: '#92400E', border: '1px solid #FDE68A', borderRadius: '12px', padding: '12px', fontSize: '11px', fontWeight: '600', lineHeight: '1.5' }}>
                  {result.warnings.join(' ')}
                </div>
              )}

              <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '16px' }}>
                <div style={{ fontSize: '12px', fontWeight: '700', color: '#1E293B', marginBottom: '8px' }}>Educational Summary</div>
                <div style={{ fontSize: '12px', color: '#334155', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                  {getCleanAnalysisText(result.analysis)}
                </div>
              </div>

              {result.images && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
                  {result.images.defect_marked && (
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: '700', color: '#1E293B', marginBottom: '8px' }}>Defect Highlighted</div>
                      <img src={resolveImageUrl(result.images.defect_marked)} alt="Defect marked" style={{ width: '100%', borderRadius: '12px', border: '1px solid #E2E8F0', display: 'block' }} />
                    </div>
                  )}

                  {result.images.healthy_version && (
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: '700', color: '#1E293B', marginBottom: '8px' }}>Healthy Comparison</div>
                      <img src={resolveImageUrl(result.images.healthy_version)} alt="Healthy comparison" style={{ width: '100%', borderRadius: '12px', border: '1px solid #E2E8F0', display: 'block' }} />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}