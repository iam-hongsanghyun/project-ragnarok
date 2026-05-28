/**
 * Activity bar — thin vertical icon strip on the far left of the workbench.
 *
 * Selecting an activity:
 *   - highlights the icon
 *   - swaps the side-panel content (Model / Solve / Analytics / Plugins / Settings)
 *   - sets the main-canvas top-level tab (Model → 'Model', Solve → 'Analytics'
 *     with Validation sub-tab, Analytics → 'Analytics', Plugins → 'Plugins')
 *
 * Mirrors the VS Code / Figma pattern: navigation is anchored on the left,
 * the side panel is context-sensitive, and the main canvas reflects the
 * activity. Replaces the old "all groups stacked in a 252-px rail" sidebar.
 */
import React from 'react';
import { ActivityId } from '../shared/utils/persistedLayout';

interface ActivityItem {
  id: ActivityId;
  label: string;
  shortcut?: string;
  glyph: string;             // single-character glyph; no external icon library
  hidden?: boolean;
}

interface Props {
  active: ActivityId;
  onSelect: (id: ActivityId) => void;
  pluginsAvailable: boolean;
}

export function ActivityBar({ active, onSelect, pluginsAvailable }: Props) {
  const items: ActivityItem[] = [
    { id: 'model',     label: 'Model',     shortcut: 'M', glyph: 'M' },
    { id: 'solve',     label: 'Run setup', shortcut: 'R', glyph: 'R' },
    { id: 'analytics', label: 'Analytics', shortcut: 'A', glyph: 'A' },
    { id: 'plugins',   label: 'Plugins',   shortcut: 'P', glyph: 'P', hidden: !pluginsAvailable },
    { id: 'settings',  label: 'Settings',  shortcut: ',', glyph: '⚙' },
  ];
  return (
    <nav className="activity-bar" aria-label="Activity bar">
      {items.filter((i) => !i.hidden).map((item) => {
        const isActive = item.id === active;
        const title = item.shortcut ? `${item.label} (${item.shortcut})` : item.label;
        return (
          <button
            key={item.id}
            type="button"
            className={`activity-bar-btn${isActive ? ' activity-bar-btn--active' : ''}`}
            onClick={() => onSelect(item.id)}
            title={title}
            aria-label={title}
            aria-pressed={isActive}
          >
            <span className="activity-bar-glyph" aria-hidden>{item.glyph}</span>
            <span className="activity-bar-label">{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
