/**
 * Command palette — modal opened by Cmd+K / Cmd+Shift+P.
 *
 * Fuzzy-search over title + keywords; recent commands surface at the
 * top of the unfiltered view. Arrow keys + Enter to invoke; Esc to
 * dismiss.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Command, CommandCategory, formatShortcut } from './types';

const RECENT_STORAGE_KEY = 'ragnarok.command-palette.recent';
const MAX_RECENT = 8;

function loadRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

function saveRecent(ids: string[]): void {
  try { localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(ids.slice(0, MAX_RECENT))); } catch { /* ignore */ }
}

/** Lightweight fuzzy score: each query character must appear in order in
 *  the haystack; sequential matches score higher. Returns null for misses. */
function fuzzyScore(query: string, haystack: string): number | null {
  if (!query) return 0;
  const q = query.toLowerCase();
  const h = haystack.toLowerCase();
  let score = 0;
  let qi = 0;
  let lastMatchAt = -1;
  for (let i = 0; i < h.length && qi < q.length; i++) {
    if (h[i] === q[qi]) {
      score += 10;
      if (lastMatchAt >= 0 && i === lastMatchAt + 1) score += 5;
      lastMatchAt = i;
      qi += 1;
    }
  }
  if (qi < q.length) return null;
  return score - haystack.length * 0.01;
}

interface Props {
  open: boolean;
  commands: Command[];
  onClose: () => void;
}

export function CommandPalette({ open, commands, onClose }: Props) {
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const [recent, setRecent] = useState<string[]>(loadRecent);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // Filter + score commands. With no query, sort by recent + category.
  const filtered = useMemo(() => {
    const visible = commands.filter((c) => !c.paletteHidden && !c.disabled);
    if (!query.trim()) {
      // No query: recent first, then category order
      const recentSet = new Set(recent);
      const recentMatches = recent
        .map((id) => visible.find((c) => c.id === id))
        .filter((c): c is Command => Boolean(c));
      const others = visible.filter((c) => !recentSet.has(c.id));
      return [...recentMatches, ...others].map((cmd) => ({ cmd, score: 0 }));
    }
    return visible
      .map((cmd) => {
        const haystack = `${cmd.title} ${cmd.keywords ?? ''} ${cmd.category}`;
        const score = fuzzyScore(query, haystack);
        return score === null ? null : { cmd, score };
      })
      .filter((x): x is { cmd: Command; score: number } => x !== null)
      .sort((a, b) => b.score - a.score);
  }, [commands, query, recent]);

  // Clamp active index when filter results change.
  useEffect(() => {
    if (activeIdx >= filtered.length) setActiveIdx(Math.max(0, filtered.length - 1));
  }, [filtered.length, activeIdx]);

  const invoke = (cmd: Command) => {
    const nextRecent = [cmd.id, ...recent.filter((id) => id !== cmd.id)].slice(0, MAX_RECENT);
    setRecent(nextRecent);
    saveRecent(nextRecent);
    onClose();
    // Defer the handler so the palette has time to unmount.
    setTimeout(() => cmd.handler(), 0);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { e.preventDefault(); onClose(); return; }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => Math.min(filtered.length - 1, i + 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => Math.max(0, i - 1));
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const target = filtered[activeIdx];
      if (target) invoke(target.cmd);
      return;
    }
  };

  // Group by category for header rendering.
  const grouped: Array<{ category: CommandCategory; rows: Array<{ cmd: Command; flatIdx: number }> }> = useMemo(() => {
    const byCat = new Map<CommandCategory, Array<{ cmd: Command; flatIdx: number }>>();
    filtered.forEach((entry, i) => {
      const cat = query.trim() && i === 0 ? entry.cmd.category : entry.cmd.category;
      void cat;
      if (!byCat.has(entry.cmd.category)) byCat.set(entry.cmd.category, []);
      byCat.get(entry.cmd.category)!.push({ cmd: entry.cmd, flatIdx: i });
    });
    return Array.from(byCat.entries()).map(([category, rows]) => ({ category, rows }));
  }, [filtered, query]);

  // Scroll the active item into view.
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const node = list.querySelector<HTMLElement>(`[data-cmd-idx="${activeIdx}"]`);
    if (node) node.scrollIntoView({ block: 'nearest' });
  }, [activeIdx]);

  if (!open) return null;

  return (
    <div className="command-palette-backdrop" onClick={onClose} role="presentation">
      <div className="command-palette" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Command palette">
        <input
          ref={inputRef}
          className="command-palette-input"
          type="text"
          placeholder="Type a command…"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setActiveIdx(0); }}
          onKeyDown={onKeyDown}
          autoFocus
        />
        <div ref={listRef} className="command-palette-list">
          {filtered.length === 0 && (
            <p className="command-palette-empty">No matching commands.</p>
          )}
          {grouped.map(({ category, rows }) => (
            <div key={category}>
              <div className="command-palette-category">{category}</div>
              {rows.map(({ cmd, flatIdx }) => {
                const isActive = flatIdx === activeIdx;
                return (
                  <button
                    key={cmd.id}
                    data-cmd-idx={flatIdx}
                    className={`command-palette-row${isActive ? ' command-palette-row--active' : ''}`}
                    onMouseEnter={() => setActiveIdx(flatIdx)}
                    onClick={() => invoke(cmd)}
                  >
                    <span className="command-palette-title">{cmd.title}</span>
                    {cmd.hint && <span className="command-palette-hint">{cmd.hint}</span>}
                    {cmd.shortcut && (
                      <span className="command-palette-shortcut">{formatShortcut(cmd.shortcut)}</span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
