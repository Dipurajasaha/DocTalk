import React, { useState, useEffect } from 'react';
import BackButton from '../../components/BackButton';

export default function PatientExplainPanel({
  setIsMobileDrawerOpen,
  messages,
  isAiProcessing,
  isOutgoingChatMessage,
  StructuredReply,
  isJsonLike,
  tryParseJson,
  MarkdownMessage,
  getCleanAnalysisText,
  AiProcessingCard,
  processingState,
  chatEndRef,
  handleChatSubmit,
  inputMsg,
  setInputMsg,
  langDropdownOpen,
  setLangDropdownOpen,
  language,
  setLanguage,
  analysisMode,
  setAnalysisMode,
  uploadedFiles,
  setUploadedFiles,
  selectedDocForAnalysis,
  setSelectedDocForAnalysis,
  analysisCurrentFolder,
  setAnalysisCurrentFolder,
  loadAssets,
  explainUploadInputRef,
  handleAddExplainFile,
  handleRemoveExplainFile,
  handleExplainUpload,
  assets,
  handleAnalyzeSelected,
  chatHistoryCollapsed
}) {
  return (
    <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
      {/* Chat Area */}
      <div className="neu-chat-area">
        <div className="neu-chat-header" style={{ paddingLeft: chatHistoryCollapsed ? '160px' : undefined }}>
          <button
            className="mobile-menu-btn"
            style={{ display: 'none' }}
            onClick={() => setIsMobileDrawerOpen(true)}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" /></svg>
          </button>
          <div className="neu-chat-header-greeting">
            <h2>AI Health Assistant</h2>
            <p>*Not a substitute for professional medical advice*</p>
          </div>
        </div>

        <div className={`neu-chat-messages ${messages.length > 0 || isAiProcessing ? 'has-conversation' : 'is-empty'}`}>
          <div className="ai-chat-ambient-bg" aria-hidden="true">
            <div className="ai-chat-ambient-grid" />
            <div className="ai-chat-ambient-panel">
              <svg className="ai-chat-ambient-ecg" viewBox="0 0 720 240" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="ai-chat-ecg-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#34C759" stopOpacity="0.15" />
                    <stop offset="45%" stopColor="#7B61FF" stopOpacity="0.55" />
                    <stop offset="100%" stopColor="#22D3EE" stopOpacity="0.18" />
                  </linearGradient>
                </defs>
                <path
                  className="ai-chat-ambient-ecg-line"
                  d="M0 130 H120 L146 130 L164 98 L186 162 L216 78 L248 130 H346 L370 130 L388 108 L406 146 L430 130 H720"
                />
              </svg>
              <div className="ai-chat-ambient-node node-a" />
              <div className="ai-chat-ambient-node node-b" />
              <div className="ai-chat-ambient-node node-c" />
            </div>
          </div>
          {messages.length === 0 && !isAiProcessing && (
            <div className="ai-chat-empty-prompt">
              Start chatting with your AI Medical Assistant!
            </div>
          )}
          {messages.map((msg, idx) => {
            const isUser = isOutgoingChatMessage(msg);
            return (
              <div key={msg.id || idx} style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', marginBottom: '4px' }}>
                <div className={`neu-chat-bubble ${isUser ? 'user' : 'assistant'}`}>
                  {isUser ? (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text || ''}</div>
                  ) : msg.structured ? (
                    <div><StructuredReply data={msg.structured} /></div>
                  ) : isJsonLike(msg.text) && tryParseJson(msg.text) ? (
                    <div><MarkdownMessage text={getCleanAnalysisText(msg.text)} /></div>
                  ) : (
                    <div><MarkdownMessage text={msg.text || ''} /></div>
                  )}
                  <div className="timestamp">
                    <span>{isUser ? 'You' : 'AI Assistant'}</span>
                    <span>{msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                  </div>
                </div>
              </div>
            );
          })}
          {isAiProcessing && <AiProcessingCard active={isAiProcessing} status={processingState} />}
          <div ref={chatEndRef} />
        </div>

        <form className="neu-chat-input-area" onSubmit={handleChatSubmit}>
          {messages.length === 0 && !isAiProcessing && (
            <div className="suggested-prompts-container" style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center', marginBottom: '50px', padding: '0 12px', pointerEvents: 'auto' }}>
              {[
                "Summarize my last lab report",
                "Are there any upcoming appointments?",
                "Analyze my recent blood tests",
                "What are the side effects of my medication?",
                "How do I improve my sleep quality?",
                "Show me a summary of my health"
              ].map((prompt, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={(e) => handleChatSubmit(e, prompt)}
                  className="neu-suggested-prompt-btn"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
          <div className="neu-chat-input-form">
            <textarea
              id="chat-input-textarea"
              value={inputMsg}
              onChange={(e) => {
                setInputMsg(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
              placeholder="Ask AI Health Assistant..."
              rows={1}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleChatSubmit(e);
                }
              }}
            />
            <div className="neu-chat-input-actions">
              <div style={{ position: 'relative' }}>
                <button
                  type="button"
                  className="neu-chat-language-select"
                  onClick={() => setLangDropdownOpen(!langDropdownOpen)}
                >
                  {language.toUpperCase()}
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ transform: langDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', marginLeft: '2px' }}><polyline points="6 9 12 15 18 9"></polyline></svg>
                </button>
                {langDropdownOpen && (
                  <div className="neu-flat" style={{ position: 'absolute', bottom: 'calc(100% + 12px)', right: 0, display: 'flex', flexDirection: 'column', padding: '8px', borderRadius: '12px', gap: '4px', zIndex: 50, minWidth: '80px', background: 'var(--bg-base)' }}>
                    {[{ code: 'en', label: 'EN' }, { code: 'es', label: 'ES' }, { code: 'hi', label: 'HI' }, { code: 'bn', label: 'BN' }].map(lang => (
                      <button
                        key={lang.code}
                        type="button"
                        onClick={() => { setLanguage(lang.code); setLangDropdownOpen(false); }}
                        style={{ background: language === lang.code ? 'var(--accent-primary)' : 'transparent', color: language === lang.code ? '#fff' : 'var(--text-secondary)', border: 'none', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, fontSize: '13px', textAlign: 'center', transition: 'all 0.2s' }}
                      >
                        {lang.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <button type="submit" className="neu-chat-send-btn" disabled={!inputMsg.trim()}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
              </button>
            </div>
          </div>
        </form>
      </div>


      <div className="neu-analysis-panel">
        <div className="neu-analysis-panel-header">
          <h3>Quick Analysis</h3>
          <div className="neu-analysis-tabs">
            <button
              className={`neu-analysis-tab ${analysisMode === 'upload' ? 'active' : ''}`}
              onClick={() => { setAnalysisMode('upload'); setUploadedFiles([]); setSelectedDocForAnalysis(null); }}
            >
              Upload New
            </button>
            <button
              className={`neu-analysis-tab ${analysisMode === 'select' ? 'active' : ''}`}
              onClick={() => { setAnalysisMode('select'); setUploadedFiles([]); setSelectedDocForAnalysis(null); setAnalysisCurrentFolder(null); loadAssets(); }}
            >
              My Documents
            </button>
          </div>
        </div>
        <div className="neu-analysis-content">
          {analysisMode === 'upload' ? (
            uploadedFiles.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="neu-dropzone" onClick={() => explainUploadInputRef.current?.click()}>
                  <div className="neu-dropzone-circle-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#7C5CFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                  </div>
                  <p className="neu-dropzone-title">Upload Medical File</p>
                  <p className="neu-dropzone-subtitle">Drag & drop or click to browse</p>
                  <p className="neu-dropzone-subtitle">PDF, JPG, PNG, DICOM up to 50MB</p>
                  <input
                    type="file"
                    ref={explainUploadInputRef}
                    accept=".pdf,.jpg,.jpeg,.png,.dcm"
                    onChange={handleAddExplainFile}
                    style={{ display: 'none' }}
                  />
                </div>
                <button className="neu-select-files-btn" onClick={() => explainUploadInputRef.current?.click()}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                  Select Files
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {uploadedFiles.map((fileObj) => (
                  <div key={fileObj.id} className="neu-document-card">
                    <div className="neu-document-icon">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><polyline points="13 2 13 9 20 9" /></svg>
                    </div>
                    <div className="neu-document-info">
                      <div className="neu-document-name">{fileObj.name}</div>
                      <div className="neu-document-meta">{(fileObj.file.size / 1024 / 1024).toFixed(2)} MB</div>
                    </div>
                    <button className="neu-document-delete" onClick={() => handleRemoveExplainFile(fileObj.id)} title="Remove">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                    </button>
                  </div>
                ))}
                <div className="neu-dropzone" style={{ padding: '20px 16px' }} onClick={() => explainUploadInputRef.current?.click()}>
                  <span className="neu-dropzone-icon" style={{ fontSize: '24px' }}>+</span>
                  <p className="neu-dropzone-title" style={{ fontSize: '12px' }}>Add More Files</p>
                  <input
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png"
                    onChange={handleAddExplainFile}
                    style={{ display: 'none' }}
                  />
                </div>
                <button
                  onClick={handleExplainUpload}
                  style={{
                    width: '100%',
                    padding: '14px',
                    borderRadius: '50px',
                    background: 'linear-gradient(135deg, #7C5CFF, #A88CFF)',
                    color: '#FFF',
                    border: 'none',
                    fontWeight: '700',
                    fontSize: '13px',
                    cursor: 'pointer',
                    boxShadow: '4px 4px 10px rgba(124,92,255,.3)',
                    transition: 'all 0.2s ease',
                    marginTop: '8px',
                  }}
                >
                  Analyze {uploadedFiles.length} File{uploadedFiles.length !== 1 ? 's' : ''}
                </button>
              </div>
            )
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {analysisCurrentFolder !== null && (
                <BackButton onClick={() => setAnalysisCurrentFolder(null)} label="Back to Root" style={{ marginBottom: 0, alignSelf: 'flex-start' }} />
              )}
              {analysisCurrentFolder === null && assets.folders.length === 0 && assets.files.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '32px 16px', color: '#6E6E73' }}>
                  <div style={{ fontSize: '32px', marginBottom: '12px' }}>📁</div>
                  <div style={{ fontSize: '13px' }}>No documents uploaded yet.</div>
                </div>
              ) : (
                <>
                  {assets.folders
                    .filter((f) => analysisCurrentFolder === null)
                    .map((folderName, i) => (
                      <div
                        key={'analysis-folder-' + i}
                        onClick={() => setAnalysisCurrentFolder(folderName.path)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          padding: '10px 12px',
                          background: '#F5F5F7',
                          borderRadius: '12px',
                          border: '1px solid rgba(255,255,255,.6)',
                          boxShadow: '3px 3px 6px rgba(209,209,214,.4), -3px -3px 6px rgba(255,255,255,.8)',
                          gap: '10px',
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: '#F5F5F7', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px', boxShadow: 'inset 2px 2px 4px rgba(209,209,214,.4), inset -2px -2px 4px rgba(255,255,255,.8)' }}>📁</div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, fontSize: '12px', color: '#1C1C1E' }}>{folderName.label}</div>
                          <div style={{ fontSize: '10px', color: '#6E6E73' }}>Folder</div>
                        </div>
                      </div>
                    ))}
                  {assets.files
                    .filter((f) => (f.folder || '') === (analysisCurrentFolder || ''))
                    .map((doc) => (
                      <div
                        key={doc.id}
                        onClick={() => setSelectedDocForAnalysis(doc.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          padding: '10px 12px',
                          background: selectedDocForAnalysis === doc.id ? 'rgba(124,92,255,.08)' : '#F5F5F7',
                          borderRadius: '12px',
                          border: selectedDocForAnalysis === doc.id ? '2px solid #7C5CFF' : '1px solid rgba(255,255,255,.6)',
                          boxShadow: selectedDocForAnalysis === doc.id ? 'none' : '3px 3px 6px rgba(209,209,214,.4), -3px -3px 6px rgba(255,255,255,.8)',
                          gap: '10px',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <div className="neu-document-icon" style={{ width: '32px', height: '32px', fontSize: '14px', borderRadius: '8px' }}>
                          {String(doc?.name || '').toLowerCase().endsWith('.pdf') ? '📄' : '🖼️'}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, fontSize: '12px', color: '#1C1C1E', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{doc.name}</div>
                          <div style={{ fontSize: '10px', color: '#6E6E73', marginTop: '2px' }}>{doc.folder || 'Root'} • {doc.uploaded_at || 'Unknown'}</div>
                        </div>
                        <input
                          type="radio"
                          checked={selectedDocForAnalysis === doc.id}
                          onChange={() => setSelectedDocForAnalysis(doc.id)}
                          style={{ width: '14px', height: '14px', accentColor: '#7C5CFF', cursor: 'pointer' }}
                        />
                      </div>
                    ))}
                  <button
                    onClick={handleAnalyzeSelected}
                    disabled={!selectedDocForAnalysis}
                    style={{
                      width: '100%',
                      padding: '14px',
                      borderRadius: '50px',
                      background: selectedDocForAnalysis ? 'linear-gradient(135deg, #7C5CFF, #A88CFF)' : '#F5F5F7',
                      color: selectedDocForAnalysis ? '#FFF' : '#6E6E73',
                      border: 'none',
                      fontWeight: '700',
                      fontSize: '13px',
                      cursor: selectedDocForAnalysis ? 'pointer' : 'default',
                      boxShadow: selectedDocForAnalysis ? '4px 4px 10px rgba(124,92,255,.3)' : 'inset 3px 3px 6px rgba(209,209,214,.4), inset -3px -3px 6px rgba(255,255,255,.8)',
                      transition: 'all 0.2s ease',
                      marginTop: '8px',
                    }}
                  >
                    Analyze Selected
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
