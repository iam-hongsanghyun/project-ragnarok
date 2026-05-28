/**
 * Generic Command type used by the palette and keyboard-shortcut hook.
 *
 * The same Command can be invoked three ways:
 *   1. From the palette (Cmd+K → search → Enter)
 *   2. From a global keyboard shortcut (`shortcut` string parsed by
 *      `useKeyboardShortcuts`)
 *   3. From a button that calls `runCommand(id)` or invokes `handler`
 *      directly
 */
export type CommandCategory =
  | 'File'
  | 'Run'
  | 'Navigate'
  | 'View'
  | 'Edit'
  | 'Scenarios'
  | 'Help';

export interface Command {
  /** Stable id for analytics / introspection. e.g. `file.save`. */
  id: string;
  /** Title shown in the palette. */
  title: string;
  /** Extra terms folded into the fuzzy search. */
  keywords?: string;
  /** Group header in the palette. */
  category: CommandCategory;
  /**
   * Keyboard shortcut as a `+`-joined string, with `Mod` for the
   * platform-default modifier (Cmd on macOS, Ctrl elsewhere).
   * Examples: `Mod+S`, `Mod+Shift+P`, `Mod+,`.
   */
  shortcut?: string;
  /** Optional one-line hint shown to the right of the title. */
  hint?: string;
  /** Disabled commands are visible but unselectable. */
  disabled?: boolean;
  /** Skip showing in the palette (still bound to shortcut). */
  paletteHidden?: boolean;
  /** What to do when invoked. */
  handler: () => void;
}

/** Format a shortcut string for display: `Mod+S` → `⌘S` on Mac, `Ctrl+S`
 *  on other platforms. */
export function formatShortcut(shortcut: string): string {
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/i.test(navigator.platform);
  return shortcut
    .split('+')
    .map((key) => {
      if (key === 'Mod') return isMac ? '⌘' : 'Ctrl';
      if (key === 'Shift') return isMac ? '⇧' : 'Shift';
      if (key === 'Alt') return isMac ? '⌥' : 'Alt';
      if (key === 'Enter') return '↵';
      if (key === 'Escape') return 'Esc';
      return key.length === 1 ? key.toUpperCase() : key;
    })
    .join(isMac ? '' : '+');
}
