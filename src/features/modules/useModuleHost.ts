import { useCallback, useEffect, useMemo, useState } from 'react';
import { API_BASE, MODULES_CONFIG } from '../../constants';
import { ModuleDescriptor, ModuleHostInventory } from '../../shared/types';

const STORAGE_KEY = MODULES_CONFIG.storageKey;

function loadEnabledIds(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
  } catch {
    return [];
  }
}

function saveEnabledIds(ids: string[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    // ignore
  }
}

function isEnableEligible(module: ModuleDescriptor): boolean {
  return module.status === 'ready' && module.valid && module.compatible && module.entryExists;
}

export function useModuleHost() {
  const [inventory, setInventory] = useState<ModuleHostInventory | null>(null);
  const [enabledIds, setEnabledIds] = useState<string[]>(loadEnabledIds);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/modules`);
      if (!resp.ok) {
        throw new Error(`Module discovery failed with status ${resp.status}.`);
      }
      const data = await resp.json() as ModuleHostInventory;
      setInventory(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Module discovery failed.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!inventory) return;
    const eligibleIds = new Set(inventory.modules.filter(isEnableEligible).map((item) => item.id));
    setEnabledIds((prev) => {
      const next = prev.filter((id) => eligibleIds.has(id));
      if (next.length !== prev.length) saveEnabledIds(next);
      return next;
    });
  }, [inventory]);

  const toggleEnabled = useCallback((moduleId: string, enabled: boolean) => {
    setEnabledIds((prev) => {
      const next = enabled
        ? Array.from(new Set([...prev, moduleId]))
        : prev.filter((id) => id !== moduleId);
      saveEnabledIds(next);
      return next;
    });
  }, []);

  const discoveredModules = inventory?.modules ?? [];
  const enabledSet = useMemo(() => new Set(enabledIds), [enabledIds]);
  const effectiveEnabledIds = useMemo(
    () => discoveredModules.filter((module) => enabledSet.has(module.id) && isEnableEligible(module)).map((module) => module.id),
    [discoveredModules, enabledSet],
  );

  return {
    inventory,
    modules: discoveredModules,
    loading,
    error,
    refresh,
    enabledIds: effectiveEnabledIds,
    isEnabled: (moduleId: string) => enabledSet.has(moduleId),
    isEnableEligible,
    toggleEnabled,
  };
}
