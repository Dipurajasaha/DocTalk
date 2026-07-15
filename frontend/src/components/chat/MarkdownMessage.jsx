import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
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

  const components = {
    a: ({ node, ...props }) => {
      if (props.href && props.href.startsWith('doctalk-payment://')) {
        return (
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              const payload = decodeURIComponent(props.href.replace('doctalk-payment://', ''));
              window.dispatchEvent(new CustomEvent('ai-payment-click', { detail: payload }));
            }}
            style={{ fontWeight: 'bold', color: '#6C5CE7', textDecoration: 'underline' }}
          >
            {props.children}
          </a>
        );
      }
      return <a {...props} target="_blank" rel="noopener noreferrer" />;
    }
  };

  return (
    <div className="markdown-body chat-markdown">
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]} 
        components={components}
        urlTransform={(value) => {
          if (value && value.startsWith('doctalk-payment://')) {
            return value;
          }
          return defaultUrlTransform(value);
        }}
      >
        {cleanedText}
      </ReactMarkdown>
    </div>
  );
}
