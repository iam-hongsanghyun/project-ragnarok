/**
 * Dashboard layout types.
 *
 * The Analytics view's "Analytics" sub-tab is a Bloomberg-style
 * editable grid: rows of cards with resizable column widths and
 * variable cell counts per row. Layouts are persisted to
 * localStorage and can be named / switched.
 *
 * Card content is decoupled from layout: each cell points at a Card
 * via `cardId`; the Card carries its own typed config. This means the
 * layout JSON is small and stable, and individual cards can be
 * re-rendered as their config (e.g. a chart's metric, timeframe)
 * changes without touching the grid structure.
 */
import { ChartSectionConfig } from '../../../shared/types';

export type CardKind = 'chart' | 'map' | 'notes';

interface CardBase {
  id: string;
}

export interface ChartCard extends CardBase {
  kind: 'chart';
  config: ChartSectionConfig;
}

export interface MapCard extends CardBase {
  kind: 'map';
}

export interface NotesCard extends CardBase {
  kind: 'notes';
}

export type Card = ChartCard | MapCard | NotesCard;

export interface Cell {
  id: string;
  /** flex-grow weight inside the row. 1 = equal share. */
  flex: number;
  /** Id of the card rendered in this cell. */
  cardId: string;
}

export interface Row {
  id: string;
  /** Row height in pixels. Used when `autoHeight` is false (or unset and the
   *  user has dragged the resize handle). */
  height: number;
  /** When true, the renderer computes height from the dashboard width and
   *  the cell count using the rule:
   *    1 cell  → 0.5 × containerWidth
   *    N ≥ 2   → containerWidth / N   (square cells)
   *  Toggling cells in the row adapts the height automatically. Dragging
   *  the row-resize handle switches this to false (manual height). */
  autoHeight?: boolean;
  cells: Cell[];
}

export interface DashboardLayout {
  rows: Row[];
  cards: Card[];
}

export interface NamedLayout {
  name: string;
  layout: DashboardLayout;
  updatedAt: number;
}

/** Storage key for the active layout + named layouts list. */
export const STORAGE_KEY = 'ragnarok:dashboard:analytics:v1';

/** A drag payload carries the cell being moved. */
export interface DragPayload {
  rowId: string;
  cellId: string;
}
