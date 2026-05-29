/**
 * Tabular editor for PyPSA native `global_constraints` rows.
 *
 * The semantics of the `carrier_attribute` column depend on `type`:
 *   - primary_energy: a NUMERIC COLUMN on the carriers sheet (the weight),
 *     e.g. `co2_emissions`, `max_growth`.
 *   - operational_limit, tech_capacity_expansion_limit,
 *     transmission_volume_expansion_limit, transmission_expansion_cost_limit:
 *     a CARRIER NAME, e.g. `coal`, `AC`, `DC`.
 * We swap the dropdown contents accordingly so the user only sees valid
 * options for the type they picked.
 */
import React from 'react';
import { GridRow, Primitive } from '../../../shared/types';
import { stringValue } from '../../../shared/utils/helpers';

const NATIVE_TYPES = [
  'primary_energy',
  'transmission_volume_expansion_limit',
  'transmission_expansion_cost_limit',
  'operational_limit',
  'tech_capacity_expansion_limit',
] as const;

type NativeType = typeof NATIVE_TYPES[number];

const NATIVE_SENSES = ['<=', '==', '>='] as const;

const ATTRIBUTE_TYPES: ReadonlySet<NativeType> = new Set<NativeType>(['primary_energy']);

interface Props {
  rows: GridRow[];
  carriers: string[];
  carrierAttributes: string[];
  onAdd: () => void;
  onDelete: (rowIndex: number) => void;
  onSet: (rowIndex: number, key: string, value: Primitive) => void;
}

function carrierAttributeOptions(
  type: string,
  carriers: string[],
  carrierAttributes: string[],
): string[] {
  if (ATTRIBUTE_TYPES.has(type as NativeType)) {
    return carrierAttributes.length > 0 ? carrierAttributes : ['co2_emissions'];
  }
  return carriers;
}

export function GlobalConstraintsTableEditor({
  rows,
  carriers,
  carrierAttributes,
  onAdd,
  onDelete,
  onSet,
}: Props) {
  if (rows.length === 0) {
    return (
      <div className="constraints-empty">
        <p>No global constraints yet. Add one below to cap primary energy, transmission expansion, or other PyPSA-native limits.</p>
        <button className="tb-btn" onClick={onAdd}>+ Add global constraint</button>
      </div>
    );
  }
  return (
    <div className="constraints-table-wrap">
      <table className="constraints-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Sense</th>
            <th>Constant</th>
            <th>Carrier attribute</th>
            <th>Investment period</th>
            <th>Bus</th>
            <th aria-label="actions" />
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const type = stringValue(row.type) || 'primary_energy';
            const attrOptions = carrierAttributeOptions(type, carriers, carrierAttributes);
            const isAttrType = ATTRIBUTE_TYPES.has(type as NativeType);
            const currentAttr = stringValue(row.carrier_attribute);
            const attrValue = currentAttr || (isAttrType ? (attrOptions[0] ?? '') : '');
            return (
              <tr key={i}>
                <td>
                  <input
                    className="constraints-cell-input"
                    value={stringValue(row.name)}
                    onChange={(e) => onSet(i, 'name', e.target.value)}
                    placeholder="name"
                  />
                </td>
                <td>
                  <select
                    className="constraints-cell-input"
                    value={type}
                    onChange={(e) => {
                      const nextType = e.target.value;
                      onSet(i, 'type', nextType);
                      // Reset the carrier_attribute to a sensible default for
                      // the new type so the visible dropdown value stays in
                      // sync with what we will save.
                      const nextOptions = carrierAttributeOptions(nextType, carriers, carrierAttributes);
                      if (!nextOptions.includes(stringValue(row.carrier_attribute))) {
                        onSet(i, 'carrier_attribute', nextOptions[0] ?? '');
                      }
                    }}
                  >
                    {NATIVE_TYPES.map((t) => (<option key={t}>{t}</option>))}
                  </select>
                </td>
                <td>
                  <select
                    className="constraints-cell-input"
                    value={stringValue(row.sense) || '<='}
                    onChange={(e) => onSet(i, 'sense', e.target.value)}
                  >
                    {NATIVE_SENSES.map((s) => (<option key={s}>{s}</option>))}
                  </select>
                </td>
                <td>
                  <input
                    type="number"
                    className="constraints-cell-input constraints-cell-input--num"
                    value={Number(row.constant ?? 0)}
                    onChange={(e) => onSet(i, 'constant', parseFloat(e.target.value) || 0)}
                  />
                </td>
                <td>
                  <select
                    className="constraints-cell-input"
                    value={attrOptions.includes(attrValue) ? attrValue : ''}
                    onChange={(e) => onSet(i, 'carrier_attribute', e.target.value)}
                  >
                    {!isAttrType && <option value="">— any —</option>}
                    {attrOptions.map((opt) => (<option key={opt} value={opt}>{opt}</option>))}
                  </select>
                </td>
                <td>
                  <input
                    type="number"
                    className="constraints-cell-input constraints-cell-input--num"
                    value={row.investment_period === undefined || row.investment_period === null || row.investment_period === '' ? '' : Number(row.investment_period)}
                    onChange={(e) => onSet(i, 'investment_period', e.target.value === '' ? '' : (parseFloat(e.target.value) || 0))}
                    placeholder="—"
                  />
                </td>
                <td>
                  <input
                    className="constraints-cell-input"
                    value={stringValue(row.bus)}
                    onChange={(e) => onSet(i, 'bus', e.target.value)}
                    placeholder="—"
                  />
                </td>
                <td>
                  <button className="gcc-del" onClick={() => onDelete(i)} title="Delete row">x</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <button className="tb-btn" style={{ marginTop: 12 }} onClick={onAdd}>+ Add global constraint</button>
    </div>
  );
}
