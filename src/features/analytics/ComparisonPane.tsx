import React from 'react';
import { RunHistoryEntry, RunResults } from '../../shared/types';
import { RunComparisonTable } from '../run-history/RunComparisonTable';

// ── Mini horizontal-bar chart ─────────────────────────────────────────────────

interface BarEntry { id: string; label: string; value: number; active: boolean }

function MiniBarChart({ title, unit, entries }: { title: string; unit: string; entries: BarEntry[] }) {
  const maxAbs = Math.max(...entries.map((e) => Math.abs(e.value)), 0.001);
  return (
    <div className="cmp-bar-chart">
      <div className="cmp-bar-chart-title">{title}</div>
      {entries.map((e) => (
        <div key={e.id} className="cmp-bar-row">
          <div className="cmp-bar-label" title={e.label}>{e.label}</div>
          <div className="cmp-bar-track">
            <div
              className={`cmp-bar-fill${e.active ? ' cmp-bar-fill--active' : ''}`}
              style={{ width: `${(Math.abs(e.value) / maxAbs) * 100}%` }}
            />
          </div>
          <div className="cmp-bar-value">
            {e.value.toLocaleString(undefined, { maximumFractionDigits: 1 })}{unit}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function firstNumericSummary(entry: RunHistoryEntry, predicate: (label: string) => boolean): number {
  const s = entry.results.summary.find((x) => predicate(x.label));
  if (!s) return 0;
  const m = s.value.replace(/,/g, '').match(/[-+]?[0-9]*\.?[0-9]+/);
  const n = m ? parseFloat(m[0]) : NaN;
  return isNaN(n) ? 0 : n;
}

// ── Comparison pane ───────────────────────────────────────────────────────────

interface Props {
  runHistory: RunHistoryEntry[];
  activeResults: RunResults | null;
  onToggleComparison: (id: string, inComparison: boolean) => void;
  currencySymbol?: string;
}

export function ComparisonPane({ runHistory, activeResults, onToggleComparison, currencySymbol = '$' }: Props) {
  // Only show runs the user has opted into comparison
  const included = runHistory.filter((e) => e.inComparison);

  if (included.length < 2) {
    return (
      <div className="analytics-empty">
        <h3>No runs to compare yet</h3>
        <p>
          Run the model at least twice. Use the checkboxes in the run history sidebar
          to control which runs appear here — unchecking a run removes it from history.
        </p>
      </div>
    );
  }

  // ── KPI bar data ────────────────────────────────────────────────────────────

  const dispatchEntries: BarEntry[] = included.map((e) => ({
    id: e.id,
    label: e.label,
    value: e.results.carrierMix.reduce((s, m) => s + m.value, 0) / 1000,
    active: e.results === activeResults,
  }));

  const emissionsEntries: BarEntry[] = included.map((e) => ({
    id: e.id,
    label: e.label,
    value: firstNumericSummary(e, (l) => l.toLowerCase().includes('emission')),
    active: e.results === activeResults,
  }));

  const priceEntries: BarEntry[] = included.map((e) => ({
    id: e.id,
    label: e.label,
    value: firstNumericSummary(e, (l) => l.toLowerCase().includes('price')),
    active: e.results === activeResults,
  }));

  const showKpiCharts = included.some((e) => e.results.carrierMix.length > 0);

  return (
    <div className="results-dashboard">

      {/* ── KPI bar charts ────────────────────────────────────────────────── */}
      {showKpiCharts && (
        <div className="cmp-bar-strip">
          <MiniBarChart title="Total dispatch" unit=" GWh" entries={dispatchEntries} />
          <MiniBarChart title="Emissions" unit="" entries={emissionsEntries} />
          <MiniBarChart title="Avg system price" unit="" entries={priceEntries} />
        </div>
      )}

      {/* ── Comparison table ──────────────────────────────────────────────── */}
      <RunComparisonTable
        runHistory={included}
        activeResults={activeResults ?? included[0].results}
        onToggleComparison={onToggleComparison}
        currencySymbol={currencySymbol}
      />
    </div>
  );
}
