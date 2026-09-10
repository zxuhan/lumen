const KEY = 'retouch:prompt-draft'

/**
 * Prompt draft saved by the landing page and restored later; it only lives in the current tab.
 */
export function savePromptDraft(text: string): void {
  const value = text.trim()
  try {
    if (value) sessionStorage.setItem(KEY, value)
    else sessionStorage.removeItem(KEY)
  } catch {
    // sessionStorage isn't writable in private mode; losing the draft doesn't affect the main flow
  }
}

export function readPromptDraft(): string {
  try {
    return sessionStorage.getItem(KEY) ?? ''
  } catch {
    return ''
  }
}
