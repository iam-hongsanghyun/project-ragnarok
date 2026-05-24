import { useState } from 'react';
import { SHEETS } from '../../constants';
import { CustomConstraint, RunHistoryEntry, RunResults, WorkbookModel } from '../../shared/types';

export const MAX_UNPINNED = 5;

interface AddHistoryEntryParams {
  runCount: number;
  filename: string;
  carbonPrice: number;
  snapshotStart: number;
  snapshotEnd: number;
  snapshotWeight: number;
  constraints: CustomConstraint[];
  model: WorkbookModel;
  results: RunResults;
}

export function useRunHistory() {
  const [runHistory, setRunHistory] = useState<RunHistoryEntry[]>([]);
  const [runCount, setRunCount] = useState(0);

  const handleRestoreRun = (entry: RunHistoryEntry, cb: (entry: RunHistoryEntry) => void) => {
    cb(entry);
  };

  const handleRenameHistoryEntry = (id: string, label: string) => {
    setRunHistory((h) => h.map((e) => (e.id === id ? { ...e, label } : e)));
  };

  const handlePinHistoryEntry = (id: string, pinned: boolean) => {
    setRunHistory((h) => {
      const updated = h.map((e) => (e.id === id ? { ...e, pinned } : e));
      const pinnedEntries = updated.filter((e) => e.pinned);
      const unpinnedEntries = updated.filter((e) => !e.pinned).slice(0, MAX_UNPINNED);
      return [...pinnedEntries, ...unpinnedEntries];
    });
  };

  const handleDeleteHistoryEntry = (id: string) => {
    setRunHistory((h) => h.filter((e) => e.id !== id));
  };

  const addHistoryEntry = ({
    filename,
    carbonPrice,
    snapshotStart,
    snapshotEnd,
    snapshotWeight,
    constraints,
    model,
    results,
  }: Omit<AddHistoryEntryParams, 'runCount'>): number => {
    let nextCount = 0;
    setRunCount((n) => {
      nextCount = n + 1;
      const entry: RunHistoryEntry = {
        id: Date.now().toString(),
        label: `Run ${nextCount}`,
        savedAt: new Date().toISOString(),
        filename,
        carbonPrice,
        snapshotStart,
        snapshotEnd,
        snapshotWeight,
        activeConstraints: constraints.filter((c) => c.enabled),
        componentCounts: Object.fromEntries(
          SHEETS.map((sheet) => [sheet, model[sheet]?.length ?? 0]).filter(([, n]) => n > 0),
        ),
        pinned: false,
        inComparison: true,
        results,
      };
      setRunHistory((hist) => {
        const withNew = [entry, ...hist];
        const pinned = withNew.filter((e) => e.pinned);
        const unpinned = withNew.filter((e) => !e.pinned).slice(0, MAX_UNPINNED);
        return [...pinned, ...unpinned];
      });
      return nextCount;
    });
    return nextCount;
  };

  return {
    runHistory,
    runCount,
    handleRenameHistoryEntry,
    handlePinHistoryEntry,
    handleDeleteHistoryEntry,
    addHistoryEntry,
  };
}
