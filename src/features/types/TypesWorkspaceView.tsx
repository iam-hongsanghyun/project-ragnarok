/**
 * TypesWorkspaceView — read-only catalogue view for `line_types` and
 * `transformer_types`.
 *
 * Both sheets are pass-through type catalogues that ``lines`` /
 * ``transformers`` reference by name to pull in pre-set electrical
 * parameters. This view surfaces what's in the model so users can audit
 * which types are available without scrolling through the workbook grid.
 * Editing happens through the regular Model → Table tab.
 */
import React, { useEffect } from 'react';
import { GridRow, WorkbookModel } from '../../shared/types';
import { stringValue } from '../../shared/utils/helpers';

const LINE_TYPE_COLS: Array<{ key: string; label: string; unit?: string }> = [
  { key: 'name', label: 'Name' },
  { key: 'f_nom', label: 'f_nom', unit: 'Hz' },
  { key: 'r_per_length', label: 'r/length', unit: 'Ω/km' },
  { key: 'x_per_length', label: 'x/length', unit: 'Ω/km' },
  { key: 'c_per_length', label: 'c/length', unit: 'nF/km' },
  { key: 'i_nom', label: 'i_nom', unit: 'kA' },
  { key: 'mounting', label: 'Mounting' },
  { key: 'cross_section', label: 'Cross section', unit: 'mm²' },
];

const TRANSFORMER_TYPE_COLS: Array<{ key: string; label: string; unit?: string }> = [
  { key: 'name', label: 'Name' },
  { key: 's_nom', label: 's_nom', unit: 'MVA' },
  { key: 'v_nom_0', label: 'v_nom_0', unit: 'kV' },
  { key: 'v_nom_1', label: 'v_nom_1', unit: 'kV' },
  { key: 'vsc', label: 'vsc', unit: '%' },
  { key: 'vscr', label: 'vscr', unit: '%' },
  { key: 'pfe', label: 'pfe', unit: 'kW' },
  { key: 'i0', label: 'i0', unit: '%' },
];

interface Props {
  model: WorkbookModel;
  onClose: () => void;
  onOpenTable: (sheet: 'line_types' | 'transformer_types') => void;
}

export function TypesWorkspaceView({ model, onClose, onOpenTable }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const lineTypes = (model.line_types ?? []) as GridRow[];
  const transformerTypes = (model.transformer_types ?? []) as GridRow[];

  const lineUsage = countUsage(model, 'lines', lineTypes);
  const xfmrUsage = countUsage(model, 'transformers', transformerTypes);

  return (
    <div className="constraints-workspace">
      <div className="constraints-workspace-header">
        <div className="constraints-workspace-title">
          <h2>Component types</h2>
          <p>PyPSA-native <code>line_types</code> and <code>transformer_types</code> catalogues. Used by <code>lines.type</code> and <code>transformers.type</code> to pull in pre-set electrical parameters.</p>
        </div>
        <button className="tb-btn tb-btn--muted" onClick={onClose} title="Close (Esc)">Close</button>
      </div>

      <div className="constraints-workspace-body" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <CatalogueSection
          title="Line types"
          sheet="line_types"
          cols={LINE_TYPE_COLS}
          rows={lineTypes}
          usage={lineUsage}
          referencingSheet="lines"
          onOpenTable={onOpenTable}
        />
        <CatalogueSection
          title="Transformer types"
          sheet="transformer_types"
          cols={TRANSFORMER_TYPE_COLS}
          rows={transformerTypes}
          usage={xfmrUsage}
          referencingSheet="transformers"
          onOpenTable={onOpenTable}
        />
      </div>
    </div>
  );
}

function countUsage(model: WorkbookModel, sheet: 'lines' | 'transformers', types: GridRow[]): Record<string, number> {
  const counts: Record<string, number> = {};
  const known = new Set(types.map((row) => stringValue(row.name)));
  for (const row of (model[sheet] ?? []) as GridRow[]) {
    const t = stringValue(row.type);
    if (!t) continue;
    if (!known.has(t)) continue;
    counts[t] = (counts[t] ?? 0) + 1;
  }
  return counts;
}

function CatalogueSection({
  title,
  sheet,
  cols,
  rows,
  usage,
  referencingSheet,
  onOpenTable,
}: {
  title: string;
  sheet: 'line_types' | 'transformer_types';
  cols: Array<{ key: string; label: string; unit?: string }>;
  rows: GridRow[];
  usage: Record<string, number>;
  referencingSheet: string;
  onOpenTable: (sheet: 'line_types' | 'transformer_types') => void;
}) {
  return (
    <section className="constraints-workspace-section">
      <header className="constraints-workspace-section-header" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <h3>{title} <span style={{ color: 'var(--muted)', fontWeight: 400 }}>· {rows.length} row{rows.length === 1 ? '' : 's'}</span></h3>
          <p>Referenced by <code>{referencingSheet}.type</code>. Edit in Model → Table → <code>{sheet}</code>.</p>
        </div>
        <button className="tb-btn" onClick={() => onOpenTable(sheet)}>Edit in table →</button>
      </header>
      {rows.length === 0 ? (
        <div className="constraints-empty">
          <p>No rows in <code>{sheet}</code>. Add rows in Model → Table to use <code>{referencingSheet}.type</code> references.</p>
        </div>
      ) : (
        <div className="constraints-table-wrap">
          <table className="constraints-table">
            <thead>
              <tr>
                {cols.map((c) => (
                  <th key={c.key}>
                    {c.label}{c.unit ? <span style={{ color: 'var(--muted)', fontWeight: 400 }}> ({c.unit})</span> : null}
                  </th>
                ))}
                <th>Usage</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const name = stringValue(row.name);
                return (
                  <tr key={i}>
                    {cols.map((c) => (
                      <td key={c.key}>{stringValue(row[c.key]) || <span style={{ color: 'var(--muted)' }}>—</span>}</td>
                    ))}
                    <td>
                      {usage[name] ? (
                        <span style={{ color: 'var(--accent)' }}>{usage[name]} {referencingSheet}</span>
                      ) : (
                        <span style={{ color: 'var(--muted)' }}>unused</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
