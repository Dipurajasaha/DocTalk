import React from 'react';

const toText = (value) => {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '';
};

const toArray = (value) => (Array.isArray(value) ? value : []);

export default function StructuredReply({ data }) {
  if (!data || typeof data !== 'object') {
    return <pre style={{ whiteSpace: 'pre-wrap', margin: 0, color: '#0f172a' }}>{toText(data) || 'No structured data available.'}</pre>;
  }

  const title = toText(data.title);
  const description = toText(data.description);
  const keyPoints = toArray(data.key_points).map((item) => toText(item)).filter(Boolean);
  const observations = toArray(data.observations).map((item) => toText(item)).filter(Boolean);
  const recommendations = toArray(data.recommendations).map((item) => toText(item)).filter(Boolean);
  const medicines = toArray(data.medicines).map((item) => {
    if (typeof item === 'string') {
      try { return JSON.parse(item); } catch { return null; }
    }
    return item;
  }).filter(Boolean);
  const rawData = data?.raw;
  const hasRawData = rawData && (typeof rawData !== 'object' || Object.keys(rawData).length > 0);
  const fallbackJson = hasRawData ? JSON.stringify(rawData, null, 2) : '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>


      {description && (
        <div style={{ fontSize: '13px', color: '#334155' }}>{description}</div>
      )}

      {keyPoints.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B' }}>Key points</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
            {keyPoints.map((kp, i) => (
              <div key={i} style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '10px', padding: '8px', fontSize: '12px', color: '#0F172A' }}>
                {kp}
              </div>
            ))}
          </div>
        </div>
      )}

      {observations.length > 0 && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B', marginBottom: '6px' }}>Observations</div>
          <ul style={{ margin: 0, paddingLeft: '18px', color: '#334155' }}>
            {observations.map((o, i) => (
              <li key={i} style={{ fontSize: '12px', marginBottom: '6px' }}>{o}</li>
            ))}
          </ul>
        </div>
      )}

      {recommendations.length > 0 && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B', marginBottom: '6px' }}>Recommendations</div>
          <ul style={{ margin: 0, paddingLeft: '18px', color: '#334155' }}>
            {recommendations.map((r, i) => (
              <li key={i} style={{ fontSize: '12px', marginBottom: '6px' }}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {medicines.length > 0 && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B', marginBottom: '8px' }}>Medicines</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {medicines.map((med, i) => (
              <div key={i} style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '10px', padding: '10px', fontSize: '12px' }}>
                <div style={{ fontWeight: 700, color: '#0F172A', marginBottom: '4px' }}>{med.medicine_name || med.name || 'Unknown'}</div>
                {med.purpose && <div style={{ color: '#334155', marginBottom: '4px' }}>{med.purpose}</div>}
                <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', color: '#475569' }}>
                  {med.price && med.price !== 'Not found' && (
                    <span style={{ fontWeight: 600, color: '#2e7d32' }}>{med.price}</span>
                  )}
                  {med.platform_name && med.platform_name !== 'N/A' && (
                    <span>{med.platform_name}</span>
                  )}
                  {med.source_url && (
                    <a href={med.source_url} target="_blank" rel="noopener noreferrer" style={{ color: '#1a73e8', textDecoration: 'none' }}>
                      View link
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}


    </div>
  );
}
