// Chat (C12): fold one answer's AgentEvents into a message. Contract: `step` =
// progress, `text` = answer chunks to append in order, `done` = end, carrying the
// citations that [n] in the text points into. There is no chat history in the
// contract, so every question is answered on its own, scoped to the page.

import type { AgentEvent, Source } from "./types";

export interface ChatAnswer {
  steps: string[];
  text: string;
  citations: Source[];
  done: boolean;
  error: string | null;
}

export const emptyAnswer = (): ChatAnswer => ({ steps: [], text: "", citations: [], done: false, error: null });

/**
 * Append a text chunk. Chunks may be word pieces with their own spacing (the
 * recorded stream) or whole sentences without a trailing space (live, one per
 * sentence), so add a space only between a finished sentence and a new word.
 */
export function joinChunk(text: string, chunk: string): string {
  if (!text || !chunk) return text + chunk;
  const needsSpace = /[.!?:;\])]$/.test(text) && /^[\p{L}\p{N}(“"'*]/u.test(chunk);
  return text + (needsSpace ? " " : "") + chunk;
}

export function applyChatEvent(a: ChatAnswer, e: AgentEvent): ChatAnswer {
  switch (e.type) {
    case "step":
      return e.message ? { ...a, steps: [...a.steps, e.message] } : a;
    case "text":
      return e.message ? { ...a, text: joinChunk(a.text, e.message) } : a;
    case "error":
      return { ...a, error: e.message ?? "Something failed." };
    case "done":
      return { ...a, done: true, citations: e.citations };
    default:
      return a;
  }
}
