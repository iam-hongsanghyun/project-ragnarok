/**
 * Bind every command with a `shortcut` to a global `keydown` listener.
 *
 * Skips when the user is typing in an input / textarea / contenteditable
 * so Cmd+S in a comment field still selects all (in browsers that do
 * that) rather than triggering Save.
 */
import { useEffect, useRef } from 'react';
import { Command } from './types';

interface ParsedShortcut {
  key: string;
  mod: boolean;
  shift: boolean;
  alt: boolean;
}

function parse(shortcut: string): ParsedShortcut | null {
  const parts = shortcut.split('+');
  const result: ParsedShortcut = { key: '', mod: false, shift: false, alt: false };
  for (const part of parts) {
    if (part === 'Mod') result.mod = true;
    else if (part === 'Shift') result.shift = true;
    else if (part === 'Alt') result.alt = true;
    else result.key = part;
  }
  return result.key ? result : null;
}

function eventMatches(event: KeyboardEvent, parsed: ParsedShortcut): boolean {
  const platformMod = event.metaKey || event.ctrlKey;
  if (parsed.mod !== platformMod) return false;
  if (parsed.shift !== event.shiftKey) return false;
  if (parsed.alt !== event.altKey) return false;
  if (parsed.key.length === 1) {
    return event.key.toLowerCase() === parsed.key.toLowerCase();
  }
  return event.key === parsed.key;
}

function isEditingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useKeyboardShortcuts(commands: Command[]): void {
  // Keep an up-to-date ref so the listener (registered once) always sees
  // the latest handler closures without rebinding on every render.
  const commandsRef = useRef(commands);
  commandsRef.current = commands;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      for (const command of commandsRef.current) {
        if (!command.shortcut || command.disabled) continue;
        const parsed = parse(command.shortcut);
        if (!parsed) continue;
        if (!eventMatches(event, parsed)) continue;
        // Cmd+K / palette toggles work even from inside inputs.
        const isPaletteToggle = command.id.startsWith('view.commandPalette');
        if (!isPaletteToggle && isEditingTarget(event.target)) continue;
        event.preventDefault();
        command.handler();
        return;
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
