import { useEffect, useState } from 'react';
import { useAssetCache } from '../contexts';

export default function FileViewer({ file, onClose }) {
  const [objectUrl, setObjectUrl] = useState(null);
  const [loadError, setLoadError] = useState('');
  const { getAsset, setAsset } = useAssetCache();

  useEffect(() => {
    let active = true;
    let createdObjectUrl = null;

    const loadPreview = async () => {
      if (!file?.download_url) {
        if (active) setLoadError('Preview unavailable: missing file URL.');
        return;
      }

      try {
        const cacheKey = `preview:${file.download_url}`;
        const cachedBlob = getAsset && getAsset(cacheKey);
        if (cachedBlob instanceof Blob) {
          createdObjectUrl = URL.createObjectURL(cachedBlob);
          if (active) setObjectUrl(createdObjectUrl);
          return;
        }

        const token = localStorage.getItem('doctalk_token');
        const response = await fetch(file.download_url, {
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });

        if (!response.ok) {
          throw new Error(`Preview request failed (${response.status})`);
        }

        const blob = await response.blob();
  try { setAsset && setAsset(cacheKey, blob); } catch (e) {}
        createdObjectUrl = URL.createObjectURL(blob);
        if (active) setObjectUrl(createdObjectUrl);
      } catch (error) {
        console.error('Failed to load preview', error);
        if (active) {
          setObjectUrl(null);
          setLoadError('Preview unavailable: the file could not be loaded.');
        }
      }
    };

    setObjectUrl(null);
    setLoadError('');
    loadPreview();

    return () => {
      active = false;
      if (createdObjectUrl) URL.revokeObjectURL(createdObjectUrl);
    };
  }, [file?.download_url]);

  if (!file) return null;

  const mimeType = String(file?.mime_type || file?.mimeType || '').toLowerCase();
  const isImage = mimeType.startsWith('image/') || /\.(png|jpg|jpeg|gif|webp)$/i.test(file?.original_name || file?.name || '');
  const isPdf = mimeType === 'application/pdf' || /\.pdf($|\?)/i.test(file?.original_name || file?.name || '');

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{ width: '90%', height: '90%', background: '#fff', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #eee', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ fontWeight: '700' }}>{file?.original_name || file?.name || 'Document'}</div>
          <button onClick={onClose} style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontSize: '16px' }}>✕</button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 12 }}>
          {isImage && objectUrl && <img src={objectUrl} alt={file?.original_name || file?.name || 'Document'} style={{ maxWidth: '100%', maxHeight: '100%', borderRadius: 8 }} />}
          {isPdf && objectUrl && <iframe title={file?.original_name || file?.name || 'Document'} src={objectUrl} style={{ width: '100%', height: '100%', border: 'none' }} />}
          {(isImage || isPdf) && !objectUrl && !loadError && <div style={{ color: '#64748B' }}>Loading preview...</div>}
          {(isImage || isPdf) && loadError && (
            <div style={{ padding: 20, color: '#64748B', textAlign: 'center' }}>
              <div style={{ marginBottom: 8 }}>{loadError}</div>
              {file?.download_url && (
                <a href={file.download_url} target="_blank" rel="noreferrer" style={{ color: '#2b6cb0' }}>Open file in new tab</a>
              )}
            </div>
          )}
          {!isImage && !isPdf && (
            <div style={{ padding: 20 }}>
              {file?.download_url ? (
                <a href={file.download_url} target="_blank" rel="noreferrer" style={{ color: '#2b6cb0' }}>Open {file?.original_name || file?.name || 'file'} in new tab</a>
              ) : (
                <span style={{ color: '#64748B' }}>Preview unavailable: missing file URL.</span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
