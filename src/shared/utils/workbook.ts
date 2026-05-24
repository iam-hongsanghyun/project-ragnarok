import * as XLSX from 'xlsx';
import { SHEETS, TS_SHEETS } from '../../constants';
import {
  isInputTemporalSheet,
  normalizeSheetName,
  stripOutputStaticAttributes,
} from '../../constants/pypsa_schema';
import { GridRow, Primitive, WorkbookModel } from '../types';

export function normalizeCell(value: unknown): Primitive {
  if (value === undefined || value === null) return null;
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'string') return value;
  return String(value);
}

export function createEmptyWorkbook(): WorkbookModel {
  const base = Object.fromEntries(SHEETS.map((s) => [s, []]));
  const ts = Object.fromEntries(TS_SHEETS.map((s) => [s, []]));
  return { ...base, ...ts } as unknown as WorkbookModel;
}

export function parseSheets(workbook: ReturnType<typeof XLSX.read>): WorkbookModel {
  const model = createEmptyWorkbook();
  workbook.SheetNames.forEach((sheetName) => {
    const canonical = normalizeSheetName(sheetName);
    const ws = workbook.Sheets[sheetName];
    if (!ws) return;
    const rows = XLSX.utils.sheet_to_json<Record<string, unknown>>(ws, { defval: null });
    (model as any)[canonical] = rows.map((row) =>
      Object.fromEntries(Object.entries(row).map(([key, value]) => [key, normalizeCell(value)])),
    );
  });
  return model;
}

export async function loadSampleWorkbook(): Promise<WorkbookModel> {
  const res = await fetch('/sample_model.xlsx');
  if (!res.ok) throw new Error('Could not load sample_model.xlsx');
  const arrayBuffer = await res.arrayBuffer();
  return parseSheets(XLSX.read(arrayBuffer, { type: 'array' }));
}

export function parseWorkbook(file: File): Promise<WorkbookModel> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const arrayBuffer = event.target?.result;
        if (!(arrayBuffer instanceof ArrayBuffer)) {
          reject(new Error('Could not read workbook.'));
          return;
        }
        const wb = XLSX.read(arrayBuffer, { type: 'array' });
        resolve(parseSheets(wb));
      } catch (error) {
        reject(error instanceof Error ? error : new Error('Workbook import failed.'));
      }
    };
    reader.onerror = () => reject(new Error('Workbook import failed.'));
    reader.readAsArrayBuffer(file);
  });
}

/** Filter rows that are effectively empty (no `name`, or every cell blank). */
function nonEmptyRows(rows: GridRow[]): GridRow[] {
  return rows.filter((r) => {
    const nameRaw = r['name'];
    const name = typeof nameRaw === 'string' ? nameRaw.trim() : nameRaw;
    if (name !== undefined && name !== null && name !== '') return true;
    // No name — keep only if some other cell has a non-empty value (e.g. snapshots
    // sheet uses `snapshot` column instead of `name`).
    return Object.values(r).some((v) => v !== null && v !== undefined && v !== '');
  });
}

export function buildWorkbook(model: WorkbookModel) {
  const workbook = XLSX.utils.book_new();
  SHEETS.forEach((sheet) => {
    const rows = nonEmptyRows((model[sheet] ?? []).map((row) => stripOutputStaticAttributes(sheet, row)));
    if (rows.length === 0) return;   // skip empty sheets entirely; PyPSA will treat them as absent
    const ws = XLSX.utils.json_to_sheet(rows);
    XLSX.utils.book_append_sheet(workbook, ws, sheet);
  });

  [...TS_SHEETS, ...Object.keys(model).filter((sheet) => isInputTemporalSheet(sheet) && !TS_SHEETS.includes(sheet))].forEach((sheet) => {
    const rows = (model as any)[sheet] as GridRow[] | undefined;
    if (!rows || rows.length === 0) return;
    const ws = XLSX.utils.json_to_sheet(rows);
    XLSX.utils.book_append_sheet(workbook, ws, sheet);
  });
  return workbook;
}

export function exportWorkbook(model: WorkbookModel, filename = 'ragnarok_case.xlsx') {
  XLSX.writeFile(buildWorkbook(model), filename);
}

export function workbookToArrayBuffer(model: WorkbookModel): ArrayBuffer {
  return XLSX.write(buildWorkbook(model), { bookType: 'xlsx', type: 'array' }) as ArrayBuffer;
}

/**
 * Parse a CSV (or TSV) file into GridRow[] for use as a time-series sheet.
 *
 * Expected shape:
 *   Column 0  — snapshot label (string, e.g. "2019-01-01 00:00")
 *   Columns 1+ — component names → numeric values
 *
 * SheetJS auto-detects comma vs tab delimiter.  BOM-prefixed files are handled
 * transparently.  All numeric cells are cast to `number`; the label column is
 * kept as `string`.  Unparseable numeric cells become `null`.
 */
export async function parseCsvToGridRows(file: File): Promise<GridRow[]> {
  const text = await file.text();
  const wb = XLSX.read(text, { type: 'string', raw: false });
  const ws = wb.Sheets[wb.SheetNames[0]];
  const raw = XLSX.utils.sheet_to_json<Record<string, unknown>>(ws, { defval: null });

  return raw.map((row) => {
    const entries = Object.entries(row).map(([k, v], i): [string, Primitive] => {
      if (i === 0) {
        // Snapshot label — keep as string
        return [k, v == null ? '' : String(v)];
      }
      // Numeric value column
      const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''));
      return [k, Number.isFinite(n) ? n : null];
    });
    return Object.fromEntries(entries) as GridRow;
  });
}
