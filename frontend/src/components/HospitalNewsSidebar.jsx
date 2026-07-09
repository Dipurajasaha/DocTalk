import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../lib/apiClient';
import '../styles/hospital.css';

const CATEGORY_META = {
  research:       { icon: '🔬', label: 'Research',       color: '#8b5cf6' },
  'health-news':  { icon: '📰', label: 'Health News',    color: '#3b82f6' },
  'health-advisory': { icon: '⚠️', label: 'Advisory',   color: '#f59e0b' },
  vaccine:        { icon: '💉', label: 'Vaccine',        color: '#22c55e' },
  outbreak:       { icon: '🚨', label: 'Outbreak',       color: '#ef4444' },
  general:        { icon: '📋', label: 'General',        color: '#6C5CE7' },
};

const getCatMeta = (cat) => CATEGORY_META[cat] || { icon: '🏥', label: cat || 'Medical', color: '#64748b' };

function TimeAgo({ dateStr }) {
  if (!dateStr) return null;
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return <span style={{ fontSize: '10px', color: '#94a3b8' }}>{dateStr}</span>;
    const diff = Date.now() - d.getTime();
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor(diff / 3600000);
    const label = days > 30
      ? d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
      : days > 0 ? `${days}d ago`
      : hours > 0 ? `${hours}h ago`
      : 'Just now';
    return <span style={{ fontSize: '10px', color: '#94a3b8' }}>{label}</span>;
  } catch { return null; }
}

function NewsCard({ item }) {
  const meta = getCatMeta(item.category);
  const title = item.title || '';
  const summary = item.summary || '';
  const url = item.url || null;
  const icon = item.icon || meta.icon;

  return (
    <div
      style={{
        padding: '12px',
        borderRadius: '10px',
        background: '#fff',
        border: '1px solid #e2e8f0',
        marginBottom: '8px',
        cursor: url ? 'pointer' : 'default',
        transition: 'box-shadow 0.15s',
      }}
      onClick={() => url && window.open(url, '_blank', 'noopener,noreferrer')}
      onMouseEnter={(e) => { if (url) e.currentTarget.style.boxShadow = '0 2px 8px rgba(108,92,231,0.12)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'none'; }}
      title={url ? 'Click to read full article' : undefined}
    >
      <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
        <span style={{ fontSize: '16px', flexShrink: 0, marginTop: '1px' }}>{icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: '11.5px', fontWeight: '600', color: '#1e293b',
            lineHeight: '1.4', marginBottom: '4px',
            display: '-webkit-box', WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>
            {title}
          </div>
          {summary && (
            <p style={{
              margin: 0, fontSize: '10.5px', color: '#64748b', lineHeight: '1.4',
              display: '-webkit-box', WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical', overflow: 'hidden',
            }}>
              {summary}
            </p>
          )}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px', gap: '6px' }}>
            <span style={{
              fontSize: '9.5px', fontWeight: '700', padding: '2px 7px',
              borderRadius: '50px', background: meta.color + '18',
              color: meta.color, textTransform: 'uppercase', letterSpacing: '0.3px',
            }}>
              {meta.icon} {meta.label}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              {item.source && (
                <span style={{ fontSize: '9.5px', color: '#94a3b8' }}>{item.source.split('/')[0].split('—')[0].trim()}</span>
              )}
              <TimeAgo dateStr={item.published_at} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function HospitalNewsSidebar({ collapsed, onToggle }) {
  const [articles, setArticles] = useState([]);
  const [diseaseSummary, setDiseaseSummary] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all');

  const fetchNews = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const [newsResult, diseaseResult] = await Promise.allSettled([
        force
          ? apiClient.post('/api/medical-news/refresh', {})
          : apiClient.get('/api/medical-news/feed?limit=30'),
        apiClient.get('/api/hospital/public/disease-summary'),
      ]);

      if (newsResult.status === 'fulfilled') {
        const data = newsResult.value;
        const items = force ? data.article_count > 0
          ? (await apiClient.get('/api/medical-news/feed?limit=30')).articles
          : []
          : (data.articles || []);
        setArticles(items);
        setLastUpdated(new Date());
      } else {
        setError('Could not load medical news');
      }

      if (diseaseResult.status === 'fulfilled') {
        setDiseaseSummary(diseaseResult.value || []);
      }
    } catch (err) {
      setError('Failed to load news');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchNews(); }, [fetchNews]);

  const FILTERS = ['all', 'research', 'health-news', 'health-advisory'];
  const filtered = activeFilter === 'all'
    ? articles
    : articles.filter(a => a.category === activeFilter);

  return (
    <aside className={`hospital-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <h3>🏥 Medical News</h3>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          {!collapsed && (
            <button
              onClick={() => fetchNews(true)}
              disabled={refreshing || loading}
              title="Refresh news"
              style={{
                background: 'none', border: '1px solid #e2e8f0', borderRadius: '6px',
                padding: '3px 7px', cursor: 'pointer', fontSize: '12px',
                color: '#6C5CE7', opacity: refreshing ? 0.5 : 1,
              }}
            >
              {refreshing ? '⟳' : '↺'}
            </button>
          )}
          <button className="sidebar-toggle" onClick={onToggle} title={collapsed ? 'Expand' : 'Collapse'}>
            {collapsed ? '▶' : '◀'}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="sidebar-content">
          {/* ─── Category Filters ─── */}
          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '10px' }}>
            {FILTERS.map(f => (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                style={{
                  padding: '3px 9px', borderRadius: '50px', border: '1px solid',
                  fontSize: '9.5px', fontWeight: '600', cursor: 'pointer',
                  background: activeFilter === f ? '#6C5CE7' : '#fff',
                  color: activeFilter === f ? '#fff' : '#64748b',
                  borderColor: activeFilter === f ? '#6C5CE7' : '#e2e8f0',
                  textTransform: 'capitalize',
                }}
              >
                {getCatMeta(f).icon} {f === 'all' ? 'All' : getCatMeta(f).label}
              </button>
            ))}
          </div>

          {/* ─── News Feed ─── */}
          <div className="sidebar-section">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <h4 style={{ margin: 0 }}>📰 Latest Medical News</h4>
              {lastUpdated && (
                <span style={{ fontSize: '9px', color: '#94a3b8' }}>
                  Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>

            {loading ? (
              <div className="sidebar-loader">
                <div className="mini-spinner" />
                <span style={{ fontSize: '11px', color: '#94a3b8', marginTop: '8px' }}>Fetching medical news…</span>
              </div>
            ) : error ? (
              <div style={{ textAlign: 'center', padding: '20px', color: '#ef4444', fontSize: '12px' }}>
                <div>⚠️ {error}</div>
                <button
                  onClick={() => fetchNews()}
                  style={{ marginTop: '8px', padding: '5px 12px', background: '#6C5CE7', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '11px' }}
                >
                  Retry
                </button>
              </div>
            ) : filtered.length === 0 ? (
              <p className="sidebar-empty">No articles found for this filter.</p>
            ) : (
              <div style={{ maxHeight: '420px', overflowY: 'auto', paddingRight: '2px' }}>
                {filtered.map(item => <NewsCard key={item.id} item={item} />)}
              </div>
            )}
          </div>

          {/* ─── Disease Watch ─── */}
          {diseaseSummary.length > 0 && (
            <div className="sidebar-section">
              <h4>🦠 Disease Watch</h4>
              <div className="sidebar-disease-list">
                {diseaseSummary.slice(0, 8).map((item, i) => (
                  <div key={i} className="sidebar-disease-row">
                    <span className="sidebar-disease-name">{item.disease}</span>
                    <span className="sidebar-disease-count">{item.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ─── Sources note ─── */}
          <div className="sidebar-cta" style={{ marginTop: '12px' }}>
            <p style={{ fontSize: '10px', color: '#94a3b8' }}>
              Sources: PubMed, WHO, NIH, MedlinePlus. Updated every 30 min.
            </p>
            <a href="/login" className="sidebar-cta-link">Join Hospital Network →</a>
          </div>
        </div>
      )}
    </aside>
  );
}
