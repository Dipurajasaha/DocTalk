/**
 * Sanitize AI-generated message text before it reaches the UI.
 *
 * The AI sometimes emits structured metadata alongside (or wrapping) its
 * human-readable reply — e.g. a leading JSON object, a markdown json code
 * fence, or XML tags. Users must never see that metadata.
 *
 * Stripping order matters:
 *   1. Remove markdown json code fences (```json … ```).
 *   2. Remove any XML/HTML-like tags (<tag>…</tag>).
 *   3. Remove a single leading JSON object that wraps the real text.
 */

const JSON_CODE_FENCE_RE = /^```json\s*\n?/i;

const XML_TAG_RE = /<\/?[a-z][\w-]*[^>]*>/gi;

/**
 * Try to remove a single leading JSON object (e.g. `{"is_emergency":false}`)
 * that is immediately followed by the real reply text. Only strips when the
 * remainder is non-empty so we don't discard a legit standalone JSON reply.
 */
function stripLeadingJsonObject(text) {
  const trimmed = text.trimStart();
  if (!trimmed.startsWith("{")) return text;

  // Find the matching closing brace at depth 1.
  let depth = 0;
  let closeIndex = -1;
  for (let i = 0; i < trimmed.length; i++) {
    const ch = trimmed[i];
    if (ch === "{") depth += 1;
    else if (ch === "}") depth -= 1;
    if (depth === 0) {
      closeIndex = i;
      break;
    }
  }

  if (closeIndex === -1) return text;

  const remainder = trimmed.slice(closeIndex + 1).trim();
  if (!remainder) return text;

  // Validate the leading chunk is actually JSON.
  try {
    JSON.parse(trimmed.slice(0, closeIndex + 1));
  } catch {
    return text;
  }

  return remainder;
}

/**
 * Remove markdown json code fences (with or without a trailing fence).
 */
function stripJsonCodeFence(text) {
  if (!/^```json/i.test(text)) return text;
  return text.replace(JSON_CODE_FENCE_RE, "").replace(/\n?```\s*$/, "");
}

/**
 * Remove XML / HTML-like tags from text.
 */
function stripXmlTags(text) {
  if (!/<[a-z][\w-]*[^>]*>/i.test(text)) return text;
  return text.replace(XML_TAG_RE, "");
}

/**
 * Sanitize a raw AI message string for display to the user.
 *
 * @param {string} text
 * @returns {string}
 */
export function sanitizeAiMessage(text) {
  if (!text || typeof text !== "string") return "";

  let cleaned = text.trim();
  cleaned = stripJsonCodeFence(cleaned);
  cleaned = stripXmlTags(cleaned);
  cleaned = stripLeadingJsonObject(cleaned);

  return cleaned.trim();
}
