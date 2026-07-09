import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSession } from '../contexts/SessionContext';
import { useNotifications, useAssetCache } from '../contexts';
import { patientApi } from '../lib/api';
import FileViewer from '../components/FileViewer';

export default function ReportView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { markExpired } = useSession();
  const { addNotification } = useNotifications();
  const { getAsset, setAsset } = useAssetCache();
  const [asset, setAssetState] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('doctalk_token');
    if (!token) { navigate('/login'); return; }

    (async () => {
      try {
        const cacheKey = `asset:${id}`;
        const cached = getAsset && getAsset(cacheKey);
        if (cached) {
          setAssetState(cached);
        } else {
          const data = await patientApi.getAsset(id);
          setAssetState(data || null);
          try { setAsset && setAsset(cacheKey, data || null); } catch (e) {}
        }
      } catch (err) {
        console.error('Failed fetching asset', err);
        if (err?.status === 401 || err?.status === 403) { try { markExpired(); } catch (e) {} navigate('/login'); return; }
      }
      setLoading(false);
    })();
  }, [id, navigate, markExpired]);

  if (loading) return <div style={{padding:40}}>Loading...</div>;
  if (!asset) return <div style={{padding:40}}>Asset not found or access denied.</div>;

  const file = asset;

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginTop: 0 }}>Asset</h2>
      <div style={{ background: '#fff', padding: 16, borderRadius: 12, maxWidth: 860 }}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>{asset.file_name || asset.fileName || file.original_name || file.name}</div>
        <div style={{ color: '#6b7280', marginBottom: 12 }}>{asset.asset_category || asset.assetCategory || asset.processing_status || ''}</div>
        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
          <button onClick={() => setPreviewOpen(true)} style={{ padding: '8px 12px', borderRadius: 8 }}>Preview</button>
          {(file.download_url || file.id) && (
            <a href={file.download_url || `/api/assets/${encodeURIComponent(file.id)}/download`} target="_blank" rel="noreferrer" style={{ padding: '8px 12px', borderRadius: 8, background: '#f3f4f6', textDecoration: 'none' }}>Download</a>
          )}
        </div>
      </div>

      {previewOpen && <FileViewer file={file} onClose={() => setPreviewOpen(false)} />}
    </div>
  );
}
