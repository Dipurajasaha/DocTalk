import { useState, useEffect } from 'react';
import { hospitalApi } from '../lib/api';
import '../styles/hospital.css';

export default function HospitalNewsSidebar({ collapsed, onToggle }) {
  const [news, setNews] = useState([]);
  const [diseaseSummary, setDiseaseSummary] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const [newsData, summaryData] = await Promise.allSettled([
          hospitalApi.getGlobalNews(8),
          hospitalApi.getDiseaseSummary(),
        ]);
        if (!cancelled) {
          if (newsData.status === 'fulfilled') setNews(newsData.value || []);
          if (summaryData.status === 'fulfilled') setDiseaseSummary(summaryData.value || []);
        }
      } catch (err) {
        // fail silently
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, []);

  return (
    <aside className={`hospital-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <h3>🏥 Hospital Network</h3>
        <button className="sidebar-toggle" onClick={onToggle} title={collapsed ? 'Expand' : 'Collapse'}>
          {collapsed ? '▶' : '◀'}
        </button>
      </div>

      {!collapsed && (
        <div className="sidebar-content">
          {/* ─── News Feed ─── */}
          <div className="sidebar-section">
            <h4>📰 Latest Updates</h4>
            {loading ? (
              <div className="sidebar-loader"><div className="mini-spinner"></div></div>
            ) : news.length === 0 ? (
              <p className="sidebar-empty">No updates yet</p>
            ) : (
              <div className="sidebar-news-list">
                {news.map((item) => (
                  <div key={item.id} className="sidebar-news-item">
                    <div className="sidebar-news-header">
                      <span className="sidebar-news-title">{item.title}</span>
                      {item.is_global && <span className="mini-badge global">🌍</span>}
                    </div>
                    <p className="sidebar-news-preview">
                      {item.content?.length > 80 ? item.content.slice(0, 80) + '…' : item.content}
                    </p>
                    <div className="sidebar-news-meta">
                      <span className="sidebar-hospital-name">{item.hospital_name || 'Hospital'}</span>
                      <span className="sidebar-news-category">{item.category}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ─── Disease Summary ─── */}
          <div className="sidebar-section">
            <h4>🦠 Disease Watch</h4>
            {diseaseSummary.length === 0 ? (
              <p className="sidebar-empty">No data</p>
            ) : (
              <div className="sidebar-disease-list">
                {diseaseSummary.slice(0, 8).map((item, i) => (
                  <div key={i} className="sidebar-disease-row">
                    <span className="sidebar-disease-name">{item.disease}</span>
                    <span className="sidebar-disease-count">{item.count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ─── Call to action ─── */}
          <div className="sidebar-cta">
            <p>Hospitals can share symptom data and updates.</p>
            <a href="/login" className="sidebar-cta-link">Join the Network →</a>
          </div>
        </div>
      )}
    </aside>
  );
}