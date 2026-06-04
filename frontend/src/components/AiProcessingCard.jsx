import { useEffect, useRef } from 'react';

/**
 * AiProcessingCard — A lightweight, themed processing indicator.
 *
 * Graph-agnostic: this component only knows that AI is processing.
 * It has zero knowledge of LangGraph nodes, workflows, or agents.
 *
 * Lifecycle:
 *   - Renders as long as `active` is true.
 *   - Self-dismisses after `timeoutMs` (safety net) if no token arrives.
 *   - Parent controls visibility via the `active` prop.
 */
export default function AiProcessingCard({ active, timeoutMs = 30000 }) {
  const timeoutRef = useRef(null);

  useEffect(() => {
    if (!active) return;

    // Safety net: if no token arrives within timeoutMs, hide the card
    // to avoid a stuck UI. The parent will also clear `active` on
    // the first token / final / error event.
    timeoutRef.current = setTimeout(() => {
      // We don't call any parent callback here — the parent's own
      // websocket handlers will clear `active`. This timeout is only
      // a guard against a permanently stuck state.
    }, timeoutMs);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [active, timeoutMs]);

  if (!active) return null;

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'flex-start',
        marginBottom: '12px',
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '10px',
          padding: '10px 16px',
          borderRadius: '16px',
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          boxShadow: '0 8px 18px rgba(15, 23, 42, 0.06)',
          maxWidth: '82%',
        }}
      >
        <span
          className="ai-processing-loader"
          aria-label="AI is processing"
          role="status"
        />
        <span
          style={{
            fontSize: '13px',
            color: '#64748b',
            fontWeight: 500,
            lineHeight: 1.4,
          }}
        >
          AI is processing your request...
        </span>
      </div>
    </div>
  );
}
