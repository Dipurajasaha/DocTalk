import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Shared markdown renderer for all AI chat UIs.
 *
 * Strips markdown fence wrappers (```markdown ... ```) that the AI
 * sometimes emits around its entire response, then renders the
 * remaining content with full GitHub-Flavoured Markdown support.
 *
 * Scoped typography ensures consistent, compact rendering
 * regardless of where the component is used.
 *
 * Usage:
 *   <MarkdownMessage text={message.text} />
 */
export default function MarkdownMessage({ text }) {
  const cleanedText = String(text || '')
    .replace(/^\uFEFF/, '')
    .replace(/^```(?:markdown|md)?\s*\n?/i, '')
    .replace(/\n?```\s*$/, '')
    .trim();

  return (
    <div className="markdown-body chat-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {cleanedText}
      </ReactMarkdown>
    </div>
  );
}
