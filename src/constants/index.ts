export { API_BASE, MAX_UNPINNED_HISTORY, MODULES_CONFIG, RUN_POLLING, RUN_WINDOW, SETTINGS_CONFIG, SETTINGS_DEFAULTS, CURRENCIES } from './config';

import { ConstraintMetric, CustomConstraint, GridRow, SheetName, TsSheetName } from '../shared/types';
export { SHEETS, TS_SHEETS } from './sheets';

// ── Default row templates ─────────────────────────────────────────────────────

// Row templates used when the user clicks "Add row" on an empty sheet.
// Only the `name` field is populated as a placeholder. All other fields are
// blank — the user must fill them. We avoid any opinionated default
// (no region-specific coordinates, no implicit carrier, no default voltage).
export const DEFAULT_SHEET_ROWS: Record<SheetName, GridRow> = {
  network: { name: '' },
  snapshots: { snapshot: '' },
  carriers: { name: '', color: '' },
  buses: { name: '' },
  generators: { name: '' },
  loads: { name: '' },
  links: { name: '' },
  lines: { name: '' },
  stores: { name: '' },
  storage_units: { name: '' },
  transformers: { name: '' },
  shunt_impedances: { name: '' },
  global_constraints: { name: '' },
  shapes: { name: '' },
  processes: { name: '' },
};

// ── Carrier colors ────────────────────────────────────────────────────────────

// Only the system-injected "LoadShedding" carrier has a built-in colour.
// All real carrier colours come from the user's workbook (`carriers.color`
// column) or are auto-assigned by hashColor() when the column is blank.
export const CARRIER_COLORS: Record<string, string> = {
  LoadShedding: '#991b1b',
};

// ── Constraint definitions ────────────────────────────────────────────────────

export const METRIC_DEFS: Record<ConstraintMetric, { label: string; description: string; unit: string; needsCarrier: boolean; sense: string }> = {
  co2_cap:          { label: 'CO₂ Intensity Cap',       description: 'Avg emission intensity ≤ value (kg CO₂e/MWh)', unit: 'kg CO₂e/MWh', needsCarrier: false, sense: '≤' },
  max_load_shed:    { label: 'Max Load Shedding',      description: 'Total unserved energy ≤ value',             unit: 'MWh',    needsCarrier: false, sense: '≤' },
  carrier_max_gen:  { label: 'Max Carrier Generation', description: 'Total output of carrier ≤ value (MWh)',     unit: 'MWh',    needsCarrier: true,  sense: '≤' },
  carrier_min_gen:  { label: 'Min Carrier Generation', description: 'Total output of carrier ≥ value (MWh)',     unit: 'MWh',    needsCarrier: true,  sense: '≥' },
  carrier_max_share:{ label: 'Max Carrier Share',      description: 'Carrier dispatch / total dispatch ≤ value', unit: '%',      needsCarrier: true,  sense: '≤' },
  carrier_min_share:{ label: 'Min Carrier Share',      description: 'Carrier dispatch / total dispatch ≥ value', unit: '%',      needsCarrier: true,  sense: '≥' },
  carrier_max_cf:   { label: 'Max Carrier Capacity Factor', description: 'Weighted generation / (carrier capacity × modeled hours) ≤ value', unit: '%', needsCarrier: true, sense: '≤' },
  carrier_min_cf:   { label: 'Min Carrier Capacity Factor', description: 'Weighted generation / (carrier capacity × modeled hours) ≥ value', unit: '%', needsCarrier: true, sense: '≥' },
};

export const DEFAULT_CONSTRAINTS: CustomConstraint[] = [];

export const EMPTY_METRIC_KEY = '__empty__';

// ── Tables pane groups ────────────────────────────────────────────────────────

export const TABLE_GROUPS: Array<{ label: string; sheet: SheetName; tsSheet?: TsSheetName }> = [
  { label: 'Network',            sheet: 'network' },
  { label: 'Snapshots',          sheet: 'snapshots' },
  { label: 'Carriers',           sheet: 'carriers' },
  { label: 'Buses',              sheet: 'buses' },
  { label: 'Generators',         sheet: 'generators',    tsSheet: 'generators-p_max_pu' },
  { label: 'Loads',              sheet: 'loads',         tsSheet: 'loads-p_set' },
  { label: 'Lines',              sheet: 'lines' },
  { label: 'Links',              sheet: 'links',         tsSheet: 'links-p_max_pu' },
  { label: 'Stores',             sheet: 'stores' },
  { label: 'Storage Units',      sheet: 'storage_units', tsSheet: 'storage_units-inflow' },
  { label: 'Transformers',       sheet: 'transformers' },
  { label: 'Shunt Impedances',   sheet: 'shunt_impedances' },
  { label: 'Global Constraints', sheet: 'global_constraints' },
  { label: 'Processes',          sheet: 'processes' },
];
