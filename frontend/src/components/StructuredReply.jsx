import React from 'react';

export default function StructuredReply({ data }) {
  if (!data) return null;
  const { title, description, key_points, observations, recommendations } = data;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {title && (
        <div style={{ fontWeight: 700, fontSize: '14px', color: '#111' }}>{title}</div>
      )}

      {description && (
        <div style={{ fontSize: '13px', color: '#334155' }}>{description}</div>
      )}

      {key_points && key_points.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B' }}>Key points</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
            {key_points.map((kp, i) => (
              <div key={i} style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '10px', padding: '8px', fontSize: '12px', color: '#0F172A' }}>
                {kp}
              </div>
            ))}
          </div>
        </div>
      )}

      {observations && observations.length > 0 && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B', marginBottom: '6px' }}>Observations</div>
          <ul style={{ margin: 0, paddingLeft: '18px', color: '#334155' }}>
            {observations.map((o, i) => (
              <li key={i} style={{ fontSize: '12px', marginBottom: '6px' }}>{o}</li>
            ))}
          </ul>
        </div>
      )}

      {recommendations && recommendations.length > 0 && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B', marginBottom: '6px' }}>Recommendations</div>
          <ul style={{ margin: 0, paddingLeft: '18px', color: '#334155' }}>
            {recommendations.map((r, i) => (
              <li key={i} style={{ fontSize: '12px', marginBottom: '6px' }}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
