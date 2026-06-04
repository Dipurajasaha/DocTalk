import { useEffect, useMemo, useRef, useState } from 'react';
import MarkdownMessage from './chat/MarkdownMessage';
import { patientApi } from '../lib/api';
import { buildAiChatWebSocketUrl } from '../lib/realTimeClient';
import StructuredReply from './StructuredReply';
import { sanitizeAiMessage } from '../utils/chatSanitizer';
import AiProcessingCard from './AiProcessingCard';

const isJsonLike = (text) => {
  if (!text) return false;
  const trimmed = text.trim();
  if (trimmed.startsWith('```json') && trimmed.endsWith('```')) return true;
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) return true;
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) return true;
  return false;
};

const tryParseJson = (text) => {
  if (!text) return null;
  const trimmed = text.trim();
  const stripped = trimmed.startsWith('```')
    ? trimmed.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '')
    : trimmed;
  try {
    const parsed = JSON.parse(stripped);
    if (parsed && typeof parsed === 'object') return parsed;
    return null;
  } catch {
    return null;
  }
};

const renderMessageContent = (text) => {
  if (isJsonLike(text)) {
    const parsed = tryParseJson(text);
    if (parsed) return <StructuredReply data={parsed} />;
  }
  return <MarkdownMessage text={text} />;
};

function normalizeMessage(item) {
  return {
    id: item?.id || `${item?.timestamp || Date.now()}-${Math.random().toString(16).slice(2)}`,
    senderId: item?.sender_id || item?.senderId || '',
    senderRole: String(item?.sender_role || item?.senderRole || '').toLowerCase(),
    text: sanitizeAiMessage(item?.message || item?.text || ''),
    timestamp: item?.timestamp || item?.created_at || item?.createdAt || null,
  };
}

function normalizeConsultationLabel(item) {
  const consultationId = String(item?.id || item?.consultation_id || item?.consultationId || '').trim();
  const patientId = String(item?.patient_id || item?.patientId || item?.patientUsername || item?.patient || '').trim();
  const doctorId = String(item?.doctor_id || item?.doctorId || '').trim();
  const createdAt = item?.created_at || item?.createdAt || '';
  return {
    id: consultationId,
    patientId,
    label: [patientId ? `Patient: ${patientId}` : 'Patient', doctorId ? `Doctor: ${doctorId}` : 'Doctor', consultationId ? `ID: ${consultationId}` : '', createdAt ? new Date(createdAt).toLocaleString() : '']
      .filter(Boolean)
      .join(' • '),
  };
}

export default function DoctorAssistantChat({ consultations = [], defaultConsultationId = '' }) {
  const consultationOptions = useMemo(
    () => (Array.isArray(consultations) ? consultations : []).map(normalizeConsultationLabel).filter((item) => item.id),
    [consultations],
  );
  const [selectedConsultationId, setSelectedConsultationId] = useState(defaultConsultationId || consultationOptions[0]?.id || '');
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const messageEndRef = useRef(null);

  const selectedTargetPatientId = useMemo(
    () => consultationOptions.find((item) => item.id === selectedConsultationId)?.patientId || '',
    [consultationOptions, selectedConsultationId],
  );

  useEffect(() => {
    if (!selectedConsultationId && consultationOptions[0]?.id) {
      setSelectedConsultationId(consultationOptions[0].id);
    }
  }, [consultationOptions, selectedConsultationId]);

  useEffect(() => {
    if (!selectedConsultationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;

    const loadHistory = async () => {
      setLoadingHistory(true);
      setError('');
      try {
        const data = await patientApi.getConsultationMessages(selectedConsultationId, 1, 20, 'doctor');
        if (cancelled) return;
        const items = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : [];
        const history = items.map(normalizeMessage);
        setMessages(history);
      } catch (err) {
        if (!cancelled) setError(err?.message || 'Failed to load assistant chat history');
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    };

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [selectedConsultationId]);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, status]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const text = String(inputValue || '').trim();
    if (!text || !selectedConsultationId || !selectedTargetPatientId) return;

    const token = localStorage.getItem('doctalk_token');
    if (!token) {
      setError('Missing session token');
      return;
    }

    const userMessage = {
      id: `user-${Date.now()}`,
      senderId: 'doctor',
      senderRole: 'doctor',
      text,
      timestamp: new Date().toISOString(),
    };

    setMessages((current) => [...current, userMessage]);
    setIsAiProcessing(true);
    setInputValue('');
    setSending(true);
    setStatus('connecting');
    setError('');

    const wsUrl = buildAiChatWebSocketUrl({
      role: 'doctor',
      token,
      targetPatientId: selectedTargetPatientId,
    });
    const socket = new WebSocket(wsUrl);
    let finalText = '';
    let completed = false;
    let settleTimeout = null;

    try {
    await new Promise((resolve, reject) => {
      const cleanupTimeout = () => {
        if (settleTimeout) {
          clearTimeout(settleTimeout);
          settleTimeout = null;
        }
      };

      const resolveOnce = () => {
        if (completed) return;
        completed = true;
        cleanupTimeout();
        resolve();
      };

      const rejectOnce = (nextError) => {
        if (completed) return;
        completed = true;
        cleanupTimeout();
        reject(nextError);
      };

      settleTimeout = setTimeout(() => {
        try { socket.close(); } catch (e) {}
        rejectOnce(new Error('Doctor assistant response timed out'));
      }, 25000);

      socket.onopen = () => {
        setStatus('connected');
        socket.send(text);
      };

      socket.onmessage = (event) => {
        let payload;
        try {
          payload = JSON.parse(event.data);
        } catch (err) {
          payload = { type: 'token', content: String(event.data || '') };
        }

        const eventType = String(payload?.type || payload?.status || '').toLowerCase();
        const chunkText = String(payload?.content || payload?.text || payload?.chunk || '');

        if ((eventType === 'token' || eventType === 'message') && chunkText) {
          setIsAiProcessing(false);
          console.log('[FE-DR] TOKEN_RAW:', JSON.stringify(chunkText));
          const sanitizedChunk = sanitizeAiMessage(chunkText);
          console.log('[FE-DR] TOKEN_SANITIZED:', JSON.stringify(sanitizedChunk));
          finalText += sanitizedChunk;
          console.log('[FE-DR] FINAL_ACCUMULATED:', JSON.stringify(finalText));
          setMessages((current) => {
            const filtered = current.filter((item) => item.id !== 'assistant-loading');
            const assistantMessage = {
              id: 'assistant-stream',
              senderId: 'doctalk-ai',
              senderRole: 'doctor',
              text: finalText,
              timestamp: new Date().toISOString(),
            };
            const existingIndex = filtered.findIndex((item) => item.id === 'assistant-stream');
            if (existingIndex >= 0) {
              const nextMessages = [...filtered];
              nextMessages[existingIndex] = assistantMessage;
              return nextMessages;
            }
            return [...filtered, assistantMessage];
          });
        }

        // The backend signals completion in several ways — an explicit
        // done/final/end event, a payload flag, or by closing the socket.
        // Treat all of them as "stream finished" so the input box unlocks.
        const isDoneEvent = eventType === 'final'
          || eventType === 'done'
          || eventType === 'end'
          || eventType === 'complete'
          || payload?.isFinal === true
          || payload?.done === true
          || payload?.finished === true;

        if (isDoneEvent) {
          setIsAiProcessing(false);
          console.log('[FE-DR] DONE_EVENT_RAW:', JSON.stringify(String(chunkText || finalText || '')));
          const textReply = sanitizeAiMessage(String(chunkText || finalText || '').trim() || 'Doctor Copilot Scaffold Online');
          console.log('[FE-DR] DONE_EVENT_SANITIZED:', JSON.stringify(textReply));
          setMessages((current) => {
            const filtered = current.filter((item) => item.id !== 'assistant-loading' && item.id !== 'assistant-stream');
            return [...filtered, {
              id: `assistant-final-${Date.now()}`,
              senderId: 'doctalk-ai',
              senderRole: 'doctor',
              text: textReply,
              timestamp: new Date().toISOString(),
            }];
          });
          try { socket.close(); } catch (e) {}
          resolveOnce();
          return;
        }

        if (eventType === 'error') {
          setIsAiProcessing(false);
          try { socket.close(); } catch (e) {}
          rejectOnce(new Error(chunkText || 'Doctor assistant stream failed'));
        }
      };

      socket.onerror = () => {
        rejectOnce(new Error('Doctor assistant websocket connection failed'));
      };

      socket.onclose = () => {
        if (completed) return;
        if (finalText) {
          // Stream produced tokens before closing — finalize the
          // message list and resolve so the input unlocks cleanly.
          console.log('[FE-DR] ONCLOSE_ACCUMULATED_RAW:', JSON.stringify(finalText));
          const sanitizedFinal = sanitizeAiMessage(finalText);
          console.log('[FE-DR] ONCLOSE_SANITIZED:', JSON.stringify(sanitizedFinal));
          setMessages((current) => {
            const filtered = current.filter((item) => item.id !== 'assistant-loading' && item.id !== 'assistant-stream');
            return [...filtered, {
              id: `assistant-final-${Date.now()}`,
              senderId: 'doctalk-ai',
              senderRole: 'doctor',
              text: sanitizedFinal,
              timestamp: new Date().toISOString(),
            }]});
          resolveOnce();
          return;
        }
        // Socket closed without any tokens — reject so the catch
        // block can show a user-friendly fallback message.
        rejectOnce(new Error('Doctor assistant websocket closed unexpectedly'));
      };
    });
    } catch (err) {
      const errText = String(err?.message || '');
      const shouldShowFallback = /timed out|closed unexpectedly/i.test(errText);
      setMessages((current) => {
        const filtered = current.filter((item) => item.id !== 'assistant-loading' && item.id !== 'assistant-stream');
        if (shouldShowFallback) {
          return [...filtered, {
            id: `assistant-final-${Date.now()}`,
            senderId: 'doctalk-ai',
            senderRole: 'doctor',
            text: sanitizeAiMessage('I am sorry, the connection timed out. Please try again.'),
            timestamp: new Date().toISOString(),
          }];
        }
        return filtered;
      });
      setIsAiProcessing(false);
      setError(err?.message || 'Failed to send assistant message');
    } finally {
      setSending(false);
      setStatus('idle');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '16px', border: '1px solid #e2e8f0', borderRadius: '16px', background: 'linear-gradient(180deg, #ffffff 0%, #f8fbff 100%)', boxShadow: '0 12px 28px rgba(15, 23, 42, 0.06)', flexWrap: 'wrap' }}>
        <div style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a' }}>Doctor AI Assistant</div>
        <div style={{ minWidth: '280px', flex: '1 1 320px' }}>
          <select
            value={selectedConsultationId}
            onChange={(event) => setSelectedConsultationId(event.target.value)}
            style={{ width: '100%', padding: '12px 14px', border: '1px solid #cbd5e1', borderRadius: '12px', background: '#fff', outline: 'none', fontSize: '13px', color: '#0f172a' }}
          >
            {!consultationOptions.length && <option value="">No consultations available</option>}
            {consultationOptions.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', border: '1px solid #e2e8f0', borderRadius: '18px', background: '#fff', overflow: 'hidden', boxShadow: '0 18px 36px rgba(15, 23, 42, 0.08)' }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid #eef2f7', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
          <div>
            <div style={{ fontSize: '14px', fontWeight: 700, color: '#1e293b' }}>Conversation</div>
            <div style={{ fontSize: '12px', color: '#64748b' }}>{selectedConsultationId ? `Consultation ${selectedConsultationId}` : 'Select a consultation to begin'}</div>
          </div>
          <div style={{ fontSize: '12px', color: status === 'connected' ? '#10b981' : '#64748b' }}>
            {loadingHistory ? 'Loading history...' : sending ? 'Streaming...' : status === 'connected' ? '🟢 Connected' : '🟢 Ready'}
          </div>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '18px', background: 'linear-gradient(180deg, #fbfdff 0%, #f8fafc 100%)' }}>
          {error && (
            <div style={{ marginBottom: '12px', padding: '10px 12px', borderRadius: '12px', background: '#fff1f2', border: '1px solid #fecdd3', color: '#9f1239', fontSize: '13px' }}>
              {error}
            </div>
          )}

          {!selectedConsultationId && (
            <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '14px' }}>
              Pick a consultation from the dropdown above to start the doctor assistant chat.
            </div>
          )}

          {selectedConsultationId && messages.length === 0 && !loadingHistory && !isAiProcessing && (
            <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', fontSize: '14px' }}>
              No messages yet. Send a prompt to the doctor AI assistant.
            </div>
          )}

          {messages.map((message) => {
            const isAssistant = message.senderId === 'doctalk-ai' || message.senderRole === 'doctor' && message.id.toString().includes('assistant');
            const isOutgoing = !isAssistant;
            return (
              <div key={message.id} style={{ display: 'flex', justifyContent: isOutgoing ? 'flex-end' : 'flex-start', marginBottom: '12px' }}>
                <div style={{ maxWidth: '82%', padding: '12px 14px', borderRadius: '16px', background: isOutgoing ? 'linear-gradient(135deg, #8B7EFF 0%, #6C5CE7 100%)' : '#ffffff', color: isOutgoing ? '#fff' : '#1e293b', border: isOutgoing ? 'none' : '1px solid #e2e8f0', boxShadow: '0 8px 18px rgba(15, 23, 42, 0.06)' }}>
                  {isOutgoing ? (
                    <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, fontSize: '14px' }}>{message.text}</div>
                  ) : (
                    <div style={{ lineHeight: 1.6, fontSize: '14px' }}>{renderMessageContent(message.text)}</div>
                  )}
                  <div style={{ marginTop: '8px', fontSize: '11px', opacity: 0.72, display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                    <span>{isOutgoing ? 'Doctor' : 'Doctor Copilot'}</span>
                    <span>{message.timestamp ? new Date(message.timestamp).toLocaleString() : ''}</span>
                  </div>
                </div>
              </div>
            );
          })}
          {isAiProcessing && <AiProcessingCard active={isAiProcessing} />}
          <div ref={messageEndRef} />
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '14px', borderTop: '1px solid #eef2f7', background: '#fff' }}>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '18px', padding: '10px 10px 10px 14px' }}>
            <textarea
              rows={2}
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder={selectedConsultationId ? 'Ask the doctor AI assistant...' : 'Select a consultation first'}
              disabled={!selectedConsultationId || sending}
              style={{ flex: 1, resize: 'none', border: 'none', outline: 'none', background: 'transparent', fontSize: '14px', lineHeight: 1.5, color: '#0f172a', minHeight: '48px' }}
            />
            <button
              type="submit"
              disabled={!selectedConsultationId || sending || !inputValue.trim()}
              style={{ padding: '12px 18px', borderRadius: '14px', border: 'none', background: (!selectedConsultationId || sending || !inputValue.trim()) ? '#cbd5e1' : 'linear-gradient(135deg, #8B7EFF 0%, #6C5CE7 100%)', color: '#fff', fontWeight: 700, cursor: (!selectedConsultationId || sending || !inputValue.trim()) ? 'not-allowed' : 'pointer', boxShadow: (!selectedConsultationId || sending || !inputValue.trim()) ? 'none' : '0 10px 20px rgba(108, 92, 231, 0.22)' }}
            >
              {sending ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}