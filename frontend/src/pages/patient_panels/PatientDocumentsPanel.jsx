import React from 'react';
import BackButton from '../../components/BackButton';
import FileViewer from '../../components/FileViewer';

export default function PatientDocumentsPanel({
  currentFolder,
  setCurrentFolder,
  getFolderDisplayName,
  handleUploadAssetV2,
  previewFile,
  setPreviewFile,
  renameTarget,
  setRenameTarget,
  renameValue,
  setRenameValue,
  submitRenameAsset,
  assets,
  handleRenameAsset,
  handleDeleteAssetV2,
  uploadQueue
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, paddingLeft: '32px', paddingRight: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', paddingRight: '70px' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 style={{ margin: 0, fontSize: '18px', color: '#6C5CE7', fontWeight: 'bold', fontFamily: '"Poppins", sans-serif', letterSpacing: '-0.5px' }}>
            {currentFolder === null ? 'My Documents' : getFolderDisplayName(currentFolder)}
          </h2>
          {currentFolder !== null && (
            <BackButton onClick={() => setCurrentFolder(null)} label="Back to Root" style={{ marginTop: '8px', marginBottom: 0, alignSelf: 'flex-start' }} />
          )}
        </div>
         <div style={{display: 'flex', gap: '10px'}}>
          <input type="file" id="upload-doc-v2" style={{display: 'none'}} onChange={handleUploadAssetV2} />
          <button onClick={() => document.getElementById('upload-doc-v2').click()} className="neu-btn-accent" style={{ padding: '10px 20px', borderRadius: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: '600' }}>Upload Files</button>
        </div>
      </div>

      <div className="documents-container neu-convex" style={{ display: 'flex', flexDirection: 'column', flex: 1, borderRadius: '16px', padding: '32px', overflowY: 'auto', minHeight: 0, boxSizing: 'border-box' }}>
        {previewFile && (
          <FileViewer file={previewFile} onClose={() => setPreviewFile(null)} />
        )}
        {renameTarget && (
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(15,23,42,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}
            onClick={() => { setRenameTarget(null); setRenameValue(''); }}
          >
            <div
              onClick={(event) => event.stopPropagation()}
              style={{ width: 'min(92vw, 420px)', background: '#fff', borderRadius: 16, boxShadow: '0 20px 60px rgba(15,23,42,0.25)', padding: 20, border: '1px solid #E2E8F0' }}
            >
              <div style={{ fontSize: 16, fontWeight: 700, color: '#1E293B', marginBottom: 8 }}>Rename file</div>
              <div style={{ fontSize: 12, color: '#64748B', marginBottom: 12 }}>Rename the file name only for {renameTarget?.name || renameTarget?.original_name || 'this document'}. The extension stays unchanged.</div>
              <input
                type="text"
                value={renameValue}
                onChange={(event) => setRenameValue(event.target.value)}
                style={{ width: '100%', boxSizing: 'border-box', padding: '10px 12px', borderRadius: 10, border: '1px solid #CBD5E1', outline: 'none', fontSize: 14, marginBottom: 16 }}
                autoFocus
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button onClick={() => { setRenameTarget(null); setRenameValue(''); }} style={{ padding: '8px 14px', borderRadius: 999, border: '1px solid #E2E8F0', background: '#F8FAFC', color: '#475569', cursor: 'pointer' }}>Cancel</button>
                <button onClick={submitRenameAsset} disabled={!renameValue.trim()} style={{ padding: '8px 14px', borderRadius: 999, border: '1px solid #C4B5FD', background: renameValue.trim() ? '#6C5CE7' : '#C7D2FE', color: '#fff', cursor: renameValue.trim() ? 'pointer' : 'not-allowed' }}>Save</button>
              </div>
            </div>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {currentFolder === null && assets.folders.map((folderName, i) => (
            <div key={'f'+i} className="neu-flat" style={{ display: 'flex', alignItems: 'center', padding: '16px', marginBottom: '8px' }}>
              <div className="neu-convex" style={{ width: '40px', height: '40px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '16px', color: 'var(--accent-primary)' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="#8B7EFF"><path d="M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: '600', fontSize: '12px', color: '#1E293B', cursor: 'pointer' }} onClick={() => setCurrentFolder(folderName.path)}>{folderName.label}</div>
                <div style={{ fontSize: '10px', color: '#64748B', marginTop: '4px' }}>Folder</div>
              </div>
              <button onClick={() => setCurrentFolder(folderName.path)} className="neu-convex" style={{ textDecoration: 'none', padding: '8px 16px', borderRadius: '50px', fontSize: '11px', fontWeight: '600', cursor: 'pointer', transition: '0.2s', color: 'var(--text-secondary)' }}>Open</button>
            </div>
          ))}

          {assets.files.filter(f => (f.folder || '') === (currentFolder || '')).map((file, i) => (
            <div key={'file'+i} className="neu-flat" style={{ display: 'flex', alignItems: 'center', padding: '16px', marginBottom: '8px' }}>
              <div className="neu-convex" style={{ width: '40px', height: '40px', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginRight: '16px', color: file?.asset_kind === 'report' ? '#6366F1' : file?.asset_kind === 'prescription' ? '#16A34A' : 'var(--text-secondary)' }}>
                {(() => {
                  const kind = String(file?.asset_kind || 'medical_image');
                  const mime = String(file?.mime_type || '').toLowerCase();
                  if (kind === 'report') {
                    return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><path d="M8 13h8" /><path d="M8 17h8" /></svg>;
                  }
                  if (kind === 'prescription') {
                    return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h9l7 7v9H4z" /><path d="M13 4v7h7" /><path d="M8 14h8" /><path d="M10 10a2 2 0 1 1 0 4" /><path d="M12 10v4" /></svg>;
                  }
                  if (mime.startsWith('image/')) {
                    return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg>;
                  }
                  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>;
                })()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: '600', fontSize: '12px', color: '#1E293B' }}>{file?.name || file?.original_name || `File ${i+1}`} </div>
                <div style={{ fontSize: '10px', color: '#64748B', marginTop: '4px' }}>{file?.folder_label || 'General Uploads'}{file?.uploaded_at ? ` · ${new Date(file.uploaded_at).toLocaleString()}` : ''}</div>
              </div>

              <button onClick={() => setPreviewFile(file)} className="neu-convex" style={{ padding: '8px 16px', borderRadius: '50px', fontSize: '11px', fontWeight: '600', cursor: 'pointer', color: 'var(--text-secondary)' }}>View</button>
              
              <button onClick={() => handleRenameAsset(file)} title="Rename this file" className="neu-convex" style={{ marginLeft: '8px', padding: '8px 16px', borderRadius: '50px', fontSize: '11px', fontWeight: '600', cursor: 'pointer', color: '#D97706' }}>Rename</button>

              <button onClick={() => handleDeleteAssetV2(file)} title="Delete this file" className="neu-convex" style={{ marginLeft: '8px', padding: '8px 16px', borderRadius: '50px', fontSize: '11px', fontWeight: '600', cursor: 'pointer', color: 'var(--accent-tertiary)' }}>Delete</button>
            </div>
          ))}

          {currentFolder === null && assets.folders.length === 0 && assets.files.filter(f => !f.folder).length === 0 && (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748B' }}>No documents in root.</div>
          )}
          {currentFolder !== null && assets.files.filter(f => f.folder === currentFolder).length === 0 && (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748B' }}>No files found in this folder.</div>
          )}
        </div>

        {uploadQueue.length > 0 && (
          <div style={{ position: 'fixed', right: 24, bottom: 24, zIndex: 1600, width: 'min(360px, calc(100vw - 32px))', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {uploadQueue.map((q) => (
              <div key={q.id} style={{ background: '#FFF', border: '1px solid #E2E8F0', borderRadius: 14, boxShadow: '0 16px 32px rgba(15,23,42,0.14)', padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#1E293B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.name}</div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: q.status === 'error' ? '#DC2626' : q.status === 'done' ? '#16A34A' : '#6C5CE7' }}>{q.status === 'uploading' ? `${q.progress || 0}%` : q.status === 'done' ? 'Uploaded' : 'Failed'}</div>
                </div>
                <div style={{ height: 8, background: '#F1F5F9', borderRadius: 999, overflow: 'hidden' }}>
                  <div style={{ width: `${q.progress || 0}%`, height: '100%', background: q.status === 'error' ? '#ef4444' : q.status === 'done' ? '#16A34A' : '#6C5CE7', transition: 'width 0.2s' }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
