import React from 'react';

export default function PatientDocChatPanel({
  doctors,
  resolveConsultationForDoctor,
  activeDocChat,
  setActiveDocChat,
  getDoctorChatStatus,
  activeConsultationId,
  handleLoadOlderDocMessages,
  docMessages,
  docChatEndRef,
  handleDocChatSubmit,
  handleDocAttachChange,
  docAttachmentFile,
  docMsgInput,
  setDocMsgInput,
  setDocInputFocused,
  docChatDisabled,
  docSending
}) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', paddingLeft: '32px', paddingRight: '32px', paddingBottom: '32px', minHeight: 0 }}>
      <div className="human-chat-wrapper neu-convex" style={{ display: 'flex', flex: 1, borderRadius: '24px', overflow: 'hidden', minHeight: 0 }}>
        
      <div className="contact-sidebar" style={{ width: '300px', borderRight: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', background: 'var(--bg-base)' }}>
        <div style={{ padding: '24px', borderBottom: '1px solid var(--border-subtle)' }}>
          <h2 style={{ margin: 0, fontSize: '11px', color: '#1E293B' }}>My Doctors</h2>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {doctors.map(d => {
            const doctorId = String(d.doctor_id || d.id || d.username || '');
            const consultation = resolveConsultationForDoctor(doctorId);
            return (
              <div 
                key={doctorId || d.name} 
                onClick={() => setActiveDocChat(doctorId)}
                style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer', background: activeDocChat === doctorId ? 'var(--shadow-light)' : 'transparent', borderLeft: activeDocChat === doctorId ? '4px solid var(--accent-primary)' : '4px solid transparent', display: 'flex', alignItems: 'center', gap: '16px' }}
              >
                <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: '#E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px', position: 'relative' }}>
                  <div style={{ position: 'absolute', bottom: 0, right: 0, width: '12px', height: '12px', background: '#22C55E', borderRadius: '50%', border: '2px solid #FFF' }}></div>
                </div>
                <div>
                  <div style={{ fontWeight: '600', fontSize: '11px', color: '#1E293B' }}>Dr. {d.name}</div>
                  <div style={{ fontSize: '11px', color: '#64748B' }}>{d.category}</div>
                  <div style={{ fontSize: '10px', color: '#94A3B8' }}>{consultation ? 'Consultation ready' : 'No consultation yet'}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="active-conversation" style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg-base)' }}>
        {activeDocChat ? (
          <>
            <div className="conversation-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 32px', borderBottom: '1px solid var(--border-subtle)', height: '80px', boxSizing: 'border-box' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: '#E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '18px' }}></div>
                <div>
                  <div style={{ fontWeight: '700', fontSize: '11px', color: '#1E293B' }}>Dr. {doctors.find(d => String(d.doctor_id || d.id || d.username || '') === String(activeDocChat))?.name}</div>
                  <div style={{ fontSize: '11px', color: getDoctorChatStatus(activeDocChat).color, fontWeight: '600' }}>{getDoctorChatStatus(activeDocChat).label}</div>
                  <div style={{ fontSize: '10px', color: '#94A3B8' }}>{activeConsultationId ? `Consultation ${activeConsultationId}` : 'Waiting for consultation'}</div>
                </div>
              </div>
              <div className="neu-convex" style={{ color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: '600', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', borderRadius: '50px' }}>
                Book Video Call
              </div>
            </div>
            
            <div style={{ flex: 1, padding: '24px 28px 24px 28px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '18px', background: 'transparent' }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '8px' }}>
                <button onClick={handleLoadOlderDocMessages} style={{ fontSize: '12px', padding: '7px 14px', borderRadius: '999px', border: '1px solid #E2E8F0', background: '#FFF', color: '#334155', fontWeight: '600' }}>Load older messages</button>
              </div>
              {docMessages.length === 0 && <div style={{textAlign: 'center', fontSize: '11px', color: '#94A3B8', marginTop: '40px'}}>Start a secure end-to-end conversation with your doctor.</div>}
              {docMessages.map((m, idx) => {
                const isPatient = String(m.sender || '').toLowerCase().includes('patient') || String(m.sender || '').toLowerCase() === 'user';
                return (
                  <div key={m.id || idx} style={{ display: 'flex', flexDirection: 'column', alignItems: isPatient ? 'flex-end' : 'flex-start', gap: '4px' }}>
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', marginBottom: '2px', width: '100%', justifyContent: isPatient ? 'flex-end' : 'flex-start' }}>
                      <div className={`neu-chat-bubble ${isPatient ? 'user' : 'assistant'}`}>
                        <div style={{ fontSize: '14px', lineHeight: '1.55', fontWeight: '500', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{m.text}</div>
                        {m.attachments && m.attachments.length > 0 && (
                          <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {m.attachments.map((a, ai) => (
                              <div key={ai} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                {a.url && a.url.match(/\.pdf$/i) ? (
                                  <a href={a.url} target="_blank" rel="noreferrer" style={{ color: isPatient ? '#FFF' : '#1E293B', textDecoration: 'underline', fontSize: '12px' }}>{a.name || 'Document'}</a>
                                ) : a.url && a.url.match(/\.(png|jpg|jpeg|gif)$/i) ? (
                                  <img src={a.url} alt={a.name || 'img'} style={{ maxWidth: '220px', borderRadius: '8px', border: '1px solid #E2E8F0' }} />
                                ) : (
                                  <div style={{ fontSize: '12px', color: isPatient ? '#FFF' : '#1E293B' }}>{a.name || 'Attachment'}</div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '2px', paddingRight: isPatient ? '8px' : '0' }}>{m.sending ? 'Sending...' : m.failed ? 'Failed' : (m.timestamp ? new Date(m.timestamp).toLocaleString() : '')}</div>
                  </div>
                );
              })}
              <div ref={docChatEndRef} />
            </div>

            <div style={{ padding: '12px 32px 32px 32px', background: 'transparent', flexShrink: 0 }}>
              <form onSubmit={handleDocChatSubmit} className="neu-chat-input-form" style={{ borderRadius: '50px', paddingLeft: '24px' }}>
                <label title="Attach media" style={{ color: '#64748B', fontWeight: '300', fontSize: '18px', marginRight: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                  <input type="file" accept=".pdf,.png,.jpg,.jpeg,.gif" onChange={handleDocAttachChange} style={{ display: 'none' }} />
                  +
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', marginRight: '12px' }}>
                  {docAttachmentFile && (
                    <div style={{ fontSize: '11px', color: '#475569', background: '#FFF', padding: '6px 8px', borderRadius: '8px', border: '1px solid #E2E8F0' }}>{docAttachmentFile.name}</div>
                  )}
                </div>
                <input type="text" value={docMsgInput} onChange={e=>setDocMsgInput(e.target.value)} onFocus={() => setDocInputFocused(true)} onBlur={() => setDocInputFocused(false)} disabled={docChatDisabled || docSending} placeholder={docChatDisabled ? 'Chat disabled' : 'Type a secure message...'} style={{flex: 1, padding: '10px 0', border: 'none', background: 'transparent', outline: 'none', boxShadow: 'none', fontSize: '14px', lineHeight: '1.5', color: '#0F172A', caretColor: '#8B7EFF', borderRadius: '12px'}} />
                <button disabled={docChatDisabled || docSending || !activeDocChat || !docMsgInput.trim()} type="submit" style={{ marginLeft: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', width: '42px', height: '42px', borderRadius: '50%', background: docChatDisabled || !activeDocChat || !docMsgInput.trim() ? '#E2E8F0' : '#8B7EFF', color: docChatDisabled || !activeDocChat || !docMsgInput.trim() ? '#94A3B8' : '#FFF', border: 'none', cursor: docChatDisabled || !activeDocChat || !docMsgInput.trim() ? 'default' : 'pointer', fontWeight: '700', fontSize: '11px', transition: 'all 0.2s', boxShadow: docChatDisabled || !activeDocChat || !docMsgInput.trim() ? 'none' : '0 4px 12px rgba(139, 126, 255, 0.3)' }}>
                  {docSending ? '...' : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                  )}
                </button>
              </form>
            </div>
          </>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', color: '#94A3B8', background: '#F8FAFC' }}>
            <div style={{ fontSize: '32px', marginBottom: '24px' }}></div>
            <div style={{ fontSize: '11px', fontWeight: '500' }}>Select a doctor from the sidebar to start corresponding.</div>
          </div>
        )}
      </div>
    </div>
    </div>
  );
}
