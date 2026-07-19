import { useState, useCallback } from 'react'
import { Upload, FileText, Image, X, FolderOpen } from 'lucide-react'

interface UploadedFile {
  id: string
  name: string
  type: 'pdf' | 'image' | 'doc'
  size: string
  date: string
}

const mockFiles: UploadedFile[] = [
  { id: '1', name: 'Blood_Report_May.pdf', type: 'pdf', size: '2.4 MB', date: 'Jun 15' },
  { id: '2', name: 'Chest_XRay.jpg', type: 'image', size: '4.1 MB', date: 'Jun 14' },
  { id: '3', name: 'MRI_Scan_Results.pdf', type: 'pdf', size: '8.7 MB', date: 'Jun 10' },
  { id: '4', name: 'Prescription_Jun.doc', type: 'doc', size: '156 KB', date: 'Jun 8' },
]

export default function AnalysisPanel() {
  const [activeTab, setActiveTab] = useState<'upload' | 'documents'>('upload')
  const [isDragging, setIsDragging] = useState(false)
  const [files] = useState<UploadedFile[]>(mockFiles)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const getFileIcon = (type: string) => {
    switch (type) {
      case 'image':
        return <Image size={18} style={{ color: 'var(--accent-primary)' }} />
      case 'pdf':
        return <FileText size={18} style={{ color: '#FF3B30' }} />
      default:
        return <FolderOpen size={18} style={{ color: 'var(--text-secondary)' }} />
    }
  }

  return (
    <aside
      className="flex flex-col"
      style={{
        width: '320px',
        minWidth: '320px',
        height: '100vh',
        background: 'var(--bg-base)',
        boxShadow: 'inset 4px 0 8px rgba(209, 209, 214, 0.2), -4px 0 12px rgba(209, 209, 214, 0.1)',
        position: 'relative',
        zIndex: 5,
        padding: '20px 20px',
        overflow: 'hidden',
      }}
    >
      {/* Title */}
      <h2
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: '20px',
          fontWeight: 700,
          color: 'var(--text-primary)',
          letterSpacing: '-0.01em',
          marginBottom: '20px',
        }}
      >
        Analyze Medical Files
      </h2>

      {/* Tabs */}
      <div
        className="neu-flat-pill flex items-center p-1 mb-6"
        style={{ borderRadius: '9999px' }}
      >
        <button
          onClick={() => setActiveTab('upload')}
          className={activeTab === 'upload' ? 'neu-pressed-pill' : ''}
          style={{
            flex: 1,
            padding: '8px 0',
            borderRadius: '9999px',
            border: 'none',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: activeTab === 'upload' ? 600 : 500,
            color: activeTab === 'upload' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontFamily: 'var(--font-body)',
            background: activeTab === 'upload' ? 'transparent' : 'transparent',
            transition: 'all 150ms ease-in-out',
          }}
        >
          Upload New
        </button>
        <button
          onClick={() => setActiveTab('documents')}
          className={activeTab === 'documents' ? 'neu-pressed-pill' : ''}
          style={{
            flex: 1,
            padding: '8px 0',
            borderRadius: '9999px',
            border: 'none',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: activeTab === 'documents' ? 600 : 500,
            color: activeTab === 'documents' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontFamily: 'var(--font-body)',
            background: activeTab === 'documents' ? 'transparent' : 'transparent',
            transition: 'all 150ms ease-in-out',
          }}
        >
          My Documents
        </button>
      </div>

      {activeTab === 'upload' ? (
        <>
          {/* Dropzone */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={isDragging ? 'neu-pressed' : 'neu-flat'}
            style={{
              borderRadius: '20px',
              padding: '40px 24px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'all 200ms ease-in-out',
              border: isDragging
                ? '2px solid var(--accent-primary)'
                : '2px dashed var(--text-secondary)',
              boxShadow: isDragging
                ? 'inset 6px 6px 12px var(--shadow-dark), inset -6px -6px 12px var(--shadow-light), 0 0 20px rgba(123, 97, 255, 0.3)'
                : undefined,
            }}
          >
            <div
              className="neu-convex flex items-center justify-center mb-4"
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
              }}
            >
              <Upload size={28} style={{ color: 'var(--accent-primary)' }} />
            </div>
            <p
              style={{
                fontSize: '14px',
                fontWeight: 600,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-body)',
                marginBottom: '6px',
              }}
            >
              Upload Medical File
            </p>
            <p
              style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-body)',
                lineHeight: 1.5,
              }}
            >
              Drag & drop or click to browse
            </p>
            <p
              style={{
                fontSize: '11px',
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-body)',
                marginTop: '8px',
              }}
            >
              PDF, JPG, PNG, DICOM up to 50MB
            </p>
          </div>

          {/* Quick Upload Button */}
          <button
            className="neu-btn-accent w-full mt-4 flex items-center justify-center gap-2"
            style={{
              padding: '12px 0',
              border: 'none',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: 600,
              fontFamily: 'var(--font-body)',
            }}
          >
            <Upload size={16} />
            Select Files
          </button>

          {/* Recent Uploads */}
          <div className="mt-6 flex-1 overflow-y-auto">
            <p
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-body)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                marginBottom: '12px',
              }}
            >
              Recent Uploads
            </p>
            <div className="flex flex-col gap-2">
              {files.slice(0, 2).map((file) => (
                <div
                  key={file.id}
                  className="neu-flat-sm flex items-center gap-3"
                  style={{
                    padding: '12px 14px',
                    borderRadius: '14px',
                  }}
                >
                  <div
                    className="neu-pressed-sm flex items-center justify-center flex-shrink-0"
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                    }}
                  >
                    {getFileIcon(file.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p
                      style={{
                        fontSize: '12px',
                        fontWeight: 500,
                        color: 'var(--text-primary)',
                        fontFamily: 'var(--font-body)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {file.name}
                    </p>
                    <p
                      style={{
                        fontSize: '11px',
                        color: 'var(--text-secondary)',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {file.size} · {file.date}
                    </p>
                  </div>
                  <button
                    className="flex-shrink-0"
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '4px',
                    }}
                  >
                    <X size={14} style={{ color: 'var(--text-secondary)' }} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : (
        /* My Documents List */
        <div className="flex-1 overflow-y-auto">
          <div className="flex flex-col gap-2">
            {files.map((file) => (
              <div
                key={file.id}
                className="neu-flat-sm flex items-center gap-3"
                style={{
                  padding: '14px',
                  borderRadius: '14px',
                  cursor: 'pointer',
                  transition: 'all 150ms ease-in-out',
                }}
              >
                <div
                  className="neu-pressed-sm flex items-center justify-center flex-shrink-0"
                  style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '12px',
                  }}
                >
                  {getFileIcon(file.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--text-primary)',
                      fontFamily: 'var(--font-body)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      marginBottom: '2px',
                    }}
                  >
                    {file.name}
                  </p>
                  <p
                    style={{
                      fontSize: '11px',
                      color: 'var(--text-secondary)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {file.size} · {file.date}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}
