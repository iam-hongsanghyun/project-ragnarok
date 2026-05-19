import { useState, useCallback } from 'react';

export type DateFormat = 'auto' | 'dmy' | 'mdy' | 'ymd';
export type SolverType = 'simplex' | 'ipm';

export interface AppSettings {
  dateFormat: DateFormat;
  solverThreads: number;   // 0 = let HiGHS decide (all cores)
  solverType: SolverType;
  currencyCode: string;      // ISO 4217 code, e.g. "USD"
  currencySymbol: string;    // display symbol, e.g. "$"
  enableLoadShedding: boolean;
  loadSheddingCost: number;   // VOLL in the currently-selected currency, per MWh
  discountRate: number;       // Used to annualise CAPEX for extendable assets
}

const STORAGE_KEY = 'pypsa_gui_settings';

function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<AppSettings>;
      return {
        dateFormat: parsed.dateFormat ?? 'auto',
        solverThreads: parsed.solverThreads ?? 0,
        solverType: parsed.solverType ?? 'simplex',
        currencyCode: parsed.currencyCode ?? 'USD',
        currencySymbol: parsed.currencySymbol ?? '$',
        enableLoadShedding: parsed.enableLoadShedding ?? false,
        loadSheddingCost: parsed.loadSheddingCost ?? 2000,
        discountRate: parsed.discountRate ?? 0.05,
      };
    }
  } catch {
    // ignore
  }
  return { dateFormat: 'auto', solverThreads: 0, solverType: 'simplex', currencyCode: 'USD', currencySymbol: '$', enableLoadShedding: false, loadSheddingCost: 2000, discountRate: 0.05 };
}

function saveSettings(s: AppSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // ignore
  }
}

export function useSettings(): [AppSettings, (patch: Partial<AppSettings>) => void] {
  const [settings, setSettings] = useState<AppSettings>(loadSettings);

  const updateSettings = useCallback((patch: Partial<AppSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      saveSettings(next);
      return next;
    });
  }, []);

  return [settings, updateSettings];
}
