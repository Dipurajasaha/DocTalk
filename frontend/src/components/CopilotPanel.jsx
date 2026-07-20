import { useEffect, useMemo, useRef, useState } from 'react';
import MarkdownMessage from './chat/MarkdownMessage';
import { buildAiChatWebSocketUrl } from '../lib/realTimeClient';
import { sanitizeAiMessage } from '../utils/chatSanitizer';
import AiProcessingCard from './AiProcessingCard';

const normalizeMessage = (payload, fallbackText = '') => ({
  id: payload?.id || payload?.message_id || `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  senderId: payload?.sender_id || payload?.senderId || payload?.sender || '',
  senderRole: String(payload?.sender_role || payload?.senderRole || payload?.role || '').toLowerCase(),
  text: sanitizeAiMessage(String(payload?.content || payload?.text || payload?.chunk || payload?.message || fallbackText || '')),
  timestamp: payload?.timestamp || payload?.created_at || payload?.createdAt || new Date().toISOString(),
});

const appendOrReplaceAssistantMessage = (currentMessages, nextText, final = false) => {
  const assistantMessage = normalizeMessage(
    {
      id: final ? `assistant-final-${Date.now()}` : 'assistant-stream',
      sender_id: 'doctalk-ai',
      sender_role: 'doctor',
      content: nextText,
    },
    nextText,
  );
  const filtered = currentMessages.filter((item) => item.id !== 'assistant-loading');
  const existingIndex = filtered.findIndex((item) => item.id === 'assistant-stream' || item.id.startsWith('assistant-final-'));
  if (existingIndex >= 0 && !final) {
    const nextMessages = [...filtered];
    nextMessages[existingIndex] = assistantMessage;
    return nextMessages;
  }
  if (existingIndex >= 0 && final) {
    const nextMessages = [...filtered];
    nextMessages[existingIndex] = assistantMessage;
    return nextMessages;
  }
  return [...filtered, assistantMessage];
};

const normalizePatient = (patient) => ({
  id: String(patient?.id || '').trim(),
  name: String(patient?.name || patient?.label || patient?.id || '').trim(),
});

export default function CopilotPanel({ patientList = [] }) {
  const [targetPatientId, setTargetPatientId] = useState(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const [processingState, setProcessingState] = useState(null);
  const socketRef = useRef(null);
  const messageEndRef = useRef(null);
  const finalTextRef = useRef('');

  const normalizedPatients = useMemo(() => {
    const seen = new Set();
    return (Array.isArray(patientList) ? patientList : [])
      .map(normalizePatient)
      .filter((patient) => patient.id || patient.name)
      .filter((patient) => {
        const key = patient.id || patient.name;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  }, [patientList]);

  const selectedPatientName = useMemo(
    () => normalizedPatients.find((patient) => patient.id === targetPatientId)?.name || '',
    [normalizedPatients, targetPatientId],
  );

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, status]);

  useEffect(() => {
    const token = localStorage.getItem('doctalk_token');

    setMessages([]);
    setError('');
    setStatus('connecting');

    if (socketRef.current) {
      try {
        socketRef.current.close();
      } catch (closeError) {
        console.error('[CopilotPanel] websocket close error', closeError);
      }
      socketRef.current = null;
    }

    if (!token) {
      setStatus('idle');
      setError('Missing session token');
      return () => {};
    }

    if (typeof WebSocket === 'undefined') {
      setStatus('idle');
      setError('WebSocket is unavailable in this browser');
      return () => {};
    }

    const wsUrl = buildAiChatWebSocketUrl({
      role: 'doctor',
      token,
      targetPatientId: targetPatientId || '',
    });

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;
    finalTextRef.current = '';

    let cancelled = false;

    socket.onopen = () => {
      if (cancelled) return;
      setStatus('connected');
    };

    socket.onmessage = (event) => {
      if (cancelled) return;

      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (parseError) {
        payload = { type: 'token', content: String(event.data || '') };
      }

      const eventType = String(payload?.type || payload?.status || '').toLowerCase();
      const chunkText = String(payload?.content || payload?.text || payload?.chunk || '');

      if (eventType === 'history') {
        const historyItems = Array.isArray(payload?.messages) ? payload.messages : [];
        setMessages(historyItems.map((item) => normalizeMessage(item)));
        return;
      }

      if (eventType === 'status') {
        setProcessingState(String(payload?.node || ''));
        return;
      }

      if ((eventType === 'token' || eventType === 'message') && chunkText) {
        // Processing card stays visible during streaming.
        console.log('[FE-CP] TOKEN_RAW:', JSON.stringify(chunkText));
        const sanitizedChunk = sanitizeAiMessage(chunkText);
        console.log('[FE-CP] TOKEN_SANITIZED:', JSON.stringify(sanitizedChunk));
        finalTextRef.current += sanitizedChunk;
        console.log('[FE-CP] FINAL_ACCUMULATED:', JSON.stringify(finalTextRef.current));
        setMessages((currentMessages) => appendOrReplaceAssistantMessage(currentMessages, finalTextRef.current, false));
        return;
      }

      if (eventType === 'final' || eventType === 'done' || eventType === 'end' || payload?.isFinal === true) {
        setIsAiProcessing(false);
        setProcessingState(null);
        const rawReply = String(chunkText || finalTextRef.current || '');
        console.log('[FE-CP] FINAL_RAW:', JSON.stringify(rawReply));
        const replyText = rawReply.trim() || 'Doctor Copilot is ready.';
        console.log('[FE-CP] FINAL_TRIMMED:', JSON.stringify(replyText));
        setMessages((currentMessages) => appendOrReplaceAssistantMessage(currentMessages, replyText, true));
        finalTextRef.current = replyText;
        // IMPORTANT: do NOT close the socket here. The backend keeps the
        // WebSocket open after a final event so the doctor can send follow-up
        // messages. Closing it here drops the session and the next send()
        // would fail with "not connected". The socket is only closed when the
        // patient selection changes (effect cleanup) or the component unmounts.
        return;
      }

      if (eventType === 'error') {
        setIsAiProcessing(false);
        setProcessingState(null);
        const message = chunkText || 'Doctor copilot stream failed';
        setError(message);
        try {
          socket.close();
        } catch (closeError) {
          console.error('[CopilotPanel] websocket error close issue', closeError);
        }
      }
    };

    socket.onerror = () => {
      if (cancelled) return;
      setIsAiProcessing(false);
      setProcessingState(null);
      setError('Doctor copilot websocket connection failed');
      setStatus('idle');
    };

    socket.onclose = () => {
      if (cancelled) return;
      setIsAiProcessing(false);
      setProcessingState(null);
      if (finalTextRef.current) {
        console.log('[FE-CP] ONCLOSE_ACCUMULATED:', JSON.stringify(finalTextRef.current));
        setMessages((currentMessages) => {
          const hasFinal = currentMessages.some((item) => item.id.startsWith('assistant-final-'));
          if (hasFinal) return currentMessages;
          return appendOrReplaceAssistantMessage(currentMessages, finalTextRef.current, true);
        });
      }
      setStatus('idle');
    };

    return () => {
      cancelled = true;
      setStatus('idle');
      try {
        socket.close();
      } catch (closeError) {
        console.error('[CopilotPanel] websocket cleanup close error', closeError);
      }
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
    };
  }, [targetPatientId]);

  const handleSubmit = (event) => {
    event.preventDefault();
    const text = String(inputValue || '').trim();
    if (!text) return;

    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError('Doctor copilot is not connected');
      return;
    }

    const userMessage = normalizeMessage({
      id: `user-${Date.now()}`,
      sender_id: 'doctor',
      sender_role: 'doctor',
      content: text,
    }, text);

    setMessages((currentMessages) => [
      ...currentMessages.filter((item) => item.id !== 'assistant-loading'),
      userMessage,
    ]);
    setIsAiProcessing(true);
    setProcessingState(null);
    setInputValue('');
    setError('');

    // Reset the streaming text accumulator so the next response starts fresh
    finalTextRef.current = '';

    try {
      socket.send(text);
    } catch (sendError) {
      setError('Failed to send message');
      setMessages((currentMessages) => currentMessages.filter((item) => item.id !== 'assistant-loading'));
    }
  };

  const selectedPatientLabel = targetPatientId
    ? selectedPatientName || targetPatientId
    : 'General Medical Chat';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
      <div className="neu-flat" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '16px', borderRadius: '18px', flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a' }}>Doctor Copilot</div>
          <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>{status === 'connected' ? 'Connected' : status === 'connecting' ? 'Connecting...' : 'Idle'} {selectedPatientLabel ? `• ${selectedPatientLabel}` : ''}</div>
        </div>
          <div 
            style={{ position: 'relative', minWidth: '280px', flex: '1 1 320px', outline: 'none' }}
            tabIndex={0}
            onBlur={(e) => {
              if (!e.currentTarget.contains(e.relatedTarget)) {
                setIsDropdownOpen(false);
              }
            }}
          >
            <div
              className="neu-pressed"
              style={{ padding: '12px 16px', borderRadius: '12px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px', color: 'var(--text-primary)', fontWeight: '500' }}
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            >
              <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {targetPatientId ? (normalizedPatients.find(p => p.id === targetPatientId)?.name || targetPatientId) : 'General Medical Chat'}
              </span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ transform: isDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', flexShrink: 0, marginLeft: '8px', color: 'var(--text-secondary)' }}><polyline points="6 9 12 15 18 9"></polyline></svg>
            </div>
            
            {isDropdownOpen && (
              <div
                className="neu-convex"
                style={{ position: 'absolute', top: '100%', left: 0, right: 0, marginTop: '8px', borderRadius: '16px', zIndex: 10, maxHeight: '240px', overflowY: 'auto', display: 'flex', flexDirection: 'column', padding: '8px', gap: '4px' }}
              >
                <div
                  style={{ padding: '10px 14px', cursor: 'pointer', fontSize: '13px', color: !targetPatientId ? 'var(--accent-primary)' : 'var(--text-primary)', fontWeight: !targetPatientId ? '700' : '500', borderRadius: '10px', background: !targetPatientId ? 'rgba(123, 97, 255, 0.08)' : 'transparent', transition: 'background 0.2s' }}
                  onClick={() => { setTargetPatientId(null); setIsDropdownOpen(false); }}
                  onMouseEnter={(e) => { if (targetPatientId) e.currentTarget.style.background = 'rgba(0,0,0,0.03)'; }}
                  onMouseLeave={(e) => { if (targetPatientId) e.currentTarget.style.background = 'transparent'; }}
                >
                  General Medical Chat
                </div>
                {normalizedPatients.map((patient) => (
                  <div
                    key={patient.id || patient.name}
                    style={{ padding: '10px 14px', cursor: 'pointer', fontSize: '13px', color: targetPatientId === patient.id ? 'var(--accent-primary)' : 'var(--text-primary)', fontWeight: targetPatientId === patient.id ? '700' : '500', borderRadius: '10px', background: targetPatientId === patient.id ? 'rgba(123, 97, 255, 0.08)' : 'transparent', transition: 'background 0.2s' }}
                    onClick={() => { setTargetPatientId(patient.id); setIsDropdownOpen(false); }}
                    onMouseEnter={(e) => { if (targetPatientId !== patient.id) e.currentTarget.style.background = 'rgba(0,0,0,0.03)'; }}
                    onMouseLeave={(e) => { if (targetPatientId !== patient.id) e.currentTarget.style.background = 'transparent'; }}
                  >
                    {patient.name}
                  </div>
                ))}
              </div>
            )}
          </div>
      </div>

      <div className="neu-flat" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', borderRadius: '18px', overflow: 'hidden', padding: 0 }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid #eef2f7', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
          <div>
            <div style={{ fontSize: '14px', fontWeight: 700, color: '#1e293b' }}>Conversation</div>
            <div style={{ fontSize: '12px', color: '#64748b' }}>{selectedPatientLabel}</div>
          </div>
          <div style={{ fontSize: '12px', color: '#64748b' }}>{error || 'Ready'}</div>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '18px', background: 'transparent' }}>
          {messages.length === 0 && !error && !isAiProcessing && (
            <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '14px' }}>
              Pick a patient or stay in general chat, then send a prompt to the doctor copilot.
            </div>
          )}

          {messages.map((message) => {
            const isAssistant = message.senderId === 'doctalk-ai' || message.id === 'assistant-loading' || message.id.startsWith('assistant-');
            const isOutgoing = !isAssistant;

            return (
              <div key={message.id} style={{ display: 'flex', justifyContent: isOutgoing ? 'flex-end' : 'flex-start', marginBottom: '12px' }}>
                <div className={isOutgoing ? 'neu-convex' : 'neu-pressed'} style={{ maxWidth: '82%', padding: '12px 14px', borderRadius: '16px', background: isOutgoing ? 'var(--accent-primary)' : 'transparent', color: isOutgoing ? '#fff' : 'var(--text-primary)', border: 'none' }}>
                  {isAssistant ? (
                    <div style={{ lineHeight: 1.6, fontSize: '14px' }}>
                      <MarkdownMessage text={message.text} />
                    </div>
                  ) : (
                    <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, fontSize: '14px' }}>{message.text}</div>
                  )}
                  <div style={{ marginTop: '8px', fontSize: '11px', opacity: 0.72, display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                    <span>{isOutgoing ? 'Doctor' : 'Doctor Copilot'}</span>
                    <span>{message.timestamp ? new Date(message.timestamp).toLocaleString() : ''}</span>
                  </div>
                </div>
              </div>
            );
          })}
          {isAiProcessing && <AiProcessingCard active={isAiProcessing} status={processingState} />}
          <div ref={messageEndRef} />
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '14px', borderTop: '1px solid var(--border-subtle)', background: 'transparent' }}>
          <div className="neu-pressed" style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', borderRadius: '18px', padding: '10px 10px 10px 14px' }}>
            <textarea
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder={targetPatientId ? 'Ask about the selected patient...' : 'Ask a general medical question...'}
              rows={2}
              style={{ flex: 1, resize: 'none', border: 'none', background: 'transparent', outline: 'none', fontSize: '14px', lineHeight: 1.6, color: '#0f172a', minHeight: '48px' }}
            />
            <button type="submit" className="neu-btn-accent" style={{ padding: '12px 16px', borderRadius: '12px', cursor: 'pointer', fontWeight: 700 }}>
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
