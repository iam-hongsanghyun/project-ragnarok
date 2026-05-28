/**
 * Per-user layout state that survives a page reload.
 *
 * Currently persists: side-panel width, active activity, sidebar
 * collapsed flag, model + analytics sub-tab choices. Stored as a
 * single JSON blob under one key so additions don't fragment storage.
 */
import { useEffect, useState } from 'react';

const STORAGE_KEY = 'ragnarok.layout.v1';

export type ActivityId = 'model' | 'solve' | 'analytics' | 'plugins' | 'settings';
export type ModelSubTab = 'Map' | 'Table';
export type AnalyticsSubTab = 'Validation' | 'Result' | 'Analytics' | 'Comparison';

export interface PersistedLayout {
  sidebarWidth: number;
  sidebarOpen: boolean;
  activity: ActivityId;
  modelSubTab: ModelSubTab;
  analyticsSubTab: AnalyticsSubTab;
}

const DEFAULT_LAYOUT: PersistedLayout = {
  sidebarWidth: 272,
  sidebarOpen: true,
  activity: 'model',
  modelSubTab: 'Map',
  analyticsSubTab: 'Result',
};

function read(): PersistedLayout {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_LAYOUT };
    const parsed = JSON.parse(raw) as Partial<PersistedLayout>;
    return {
      sidebarWidth: typeof parsed.sidebarWidth === 'number' ? parsed.sidebarWidth : DEFAULT_LAYOUT.sidebarWidth,
      sidebarOpen: typeof parsed.sidebarOpen === 'boolean' ? parsed.sidebarOpen : DEFAULT_LAYOUT.sidebarOpen,
      activity: (['model', 'solve', 'analytics', 'plugins', 'settings'] as ActivityId[]).includes(parsed.activity as ActivityId)
        ? (parsed.activity as ActivityId)
        : DEFAULT_LAYOUT.activity,
      modelSubTab: (['Map', 'Table'] as ModelSubTab[]).includes(parsed.modelSubTab as ModelSubTab)
        ? (parsed.modelSubTab as ModelSubTab)
        : DEFAULT_LAYOUT.modelSubTab,
      analyticsSubTab: (['Validation', 'Result', 'Analytics', 'Comparison'] as AnalyticsSubTab[]).includes(parsed.analyticsSubTab as AnalyticsSubTab)
        ? (parsed.analyticsSubTab as AnalyticsSubTab)
        : DEFAULT_LAYOUT.analyticsSubTab,
    };
  } catch {
    return { ...DEFAULT_LAYOUT };
  }
}

function write(layout: PersistedLayout): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch {
    // ignore quota / privacy errors
  }
}

/** Hook returning persisted layout + a patch setter. */
export function usePersistedLayout(): [PersistedLayout, (patch: Partial<PersistedLayout>) => void] {
  const [layout, setLayout] = useState<PersistedLayout>(read);
  useEffect(() => {
    write(layout);
  }, [layout]);
  const patch = (next: Partial<PersistedLayout>) => setLayout((prev) => ({ ...prev, ...next }));
  return [layout, patch];
}
