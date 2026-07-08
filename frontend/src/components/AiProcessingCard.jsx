import { useEffect, useRef } from 'react';

/**
 * AiProcessingCard — A lightweight, themed processing indicator.
 *
 * Graph-agnostic: this component only knows that AI is processing.
 * It has zero knowledge of LangGraph nodes, workflows, or agents.
 *
 * The `status` prop is an opaque string (e.g. a LangGraph node name).
 * The component maps it to a human-readable label via STATUS_LABELS.
 * Future nodes require only adding one entry to STATUS_LABELS.
 *
 * Lifecycle:
 *   - Renders as long as `active` is true.
 *   - Self-dismisses after `timeoutMs` (safety net) if no token arrives.
 *   - Parent controls visibility via the `active` prop.
 */

const STATUS_LABELS = {
  triage_evaluator: 'Assessing symptoms...',
  patient_rag_tool: 'Reading medical reports...',
  patient_assistant_llm: 'Generating explanation...',
  patient_general_llm: 'Generating explanation...',
  doctor_general_llm: 'Preparing clinical response...',
  doctor_scoped_llm: 'Preparing clinical response...',
  guardrail: 'Validating response...',
};

function resolveStatusLabel(status) {
  if (!status) return 'Processing...';
  return STATUS_LABELS[status] || status;
}

export default function AiProcessingCard({ active, status, timeoutMs = 30000 }) {
  const timeoutRef = useRef(null);

  useEffect(() => {
    if (!active) return;

    timeoutRef.current = setTimeout(() => {
      // Safety net: parent's own websocket handlers will clear `active`.
    }, timeoutMs);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [active, timeoutMs]);

  if (!active) return null;

  const label = resolveStatusLabel(status);

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
          {label}
        </span>
      </div>
    </div>
  );
}
