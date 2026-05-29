/**
 * Build-mode network map.
 *
 * Renders the model's buses/branches as geographic context and makes the
 * active step's component layer clickable: clicking a node/line selects that
 * row, which drives the attribute form on the right and highlights the row in
 * the table below. Editing the model live re-draws the map.
 *
 * Unlike the analytics map this is results-agnostic — it only knows the
 * `WorkbookModel` and the sheet the current Build step is editing.
 */
import React, { useEffect } from 'react';
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from 'react-leaflet';
import { LatLngBoundsExpression } from 'leaflet';
import { GridRow, WorkbookModel } from '../../shared/types';
import { numberValue, stringValue, resolvedColor } from '../../shared/utils/helpers';
import { FitToBounds } from '../map/FitToBounds';

const POINT_SHEETS = new Set(['generators', 'loads', 'storage_units', 'stores']);
const BRANCH_SHEETS = new Set(['lines', 'links', 'transformers']);

/** Sheets the map can geo-locate; other steps render no map. */
export function isGeoSheet(sheet: string): boolean {
  return sheet === 'buses' || POINT_SHEETS.has(sheet) || BRANCH_SHEETS.has(sheet);
}

function ownCoords(row: GridRow): [number, number] | null {
  const x = row.x;
  const y = row.y;
  if (x === undefined || x === null || x === '' || y === undefined || y === null || y === '') return null;
  return [numberValue(y), numberValue(x)];
}

function busCoords(row: GridRow, busIndex: Record<string, GridRow>, offset = 0.07): [number, number] | null {
  const bus = busIndex[stringValue(row.bus)];
  if (!bus) return null;
  const c = ownCoords(bus);
  return c ? [c[0] + offset, c[1] + offset] : null;
}

function branchPositions(
  row: GridRow,
  busIndex: Record<string, GridRow>,
): [number, number][] | null {
  const b0 = busIndex[stringValue(row.bus0)];
  const b1 = busIndex[stringValue(row.bus1)];
  if (!b0 || !b1) return null;
  const c0 = ownCoords(b0);
  const c1 = ownCoords(b1);
  if (!c0 || !c1) return null;
  return [c0, c1];
}

/** Leaflet measures its container once on mount; the Build panel resolves its
 *  flex height after that, so remeasure on every container resize. */
function InvalidateOnResize() {
  const map = useMap();
  useEffect(() => {
    const el = map.getContainer();
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(el);
    const t = window.setTimeout(() => map.invalidateSize(), 0);
    return () => { ro.disconnect(); window.clearTimeout(t); };
  }, [map]);
  return null;
}

interface Props {
  model: WorkbookModel;
  bounds: LatLngBoundsExpression | null;
  busIndex: Record<string, GridRow>;
  /** Sheet the current step edits — its rows are the clickable layer. */
  activeSheet: string;
  selectedRowIndex: number | null;
  onSelectRow: (rowIndex: number) => void;
}

export function BuildNetworkMap({
  model, bounds, busIndex, activeSheet, selectedRowIndex, onSelectRow,
}: Props) {
  const rows: GridRow[] = (model as Record<string, GridRow[]>)[activeSheet] ?? [];
  const busActive = activeSheet === 'buses';
  const pointActive = POINT_SHEETS.has(activeSheet);
  const branchActive = BRANCH_SHEETS.has(activeSheet);

  // Faint geographic context: every bus, plus lines as thin grey links.
  const contextLines = model.lines
    .map((line) => branchPositions(line, busIndex))
    .filter(Boolean) as [number, number][][];

  return (
    <div className="build-map-frame">
      <MapContainer center={[36.35, 127.9]} zoom={7} className="leaflet-map" scrollWheelZoom>
        <InvalidateOnResize />
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          subdomains="abcd"
        />
        <FitToBounds bounds={bounds} />

        {/* Context lines (non-active sheets) */}
        {!branchActive && contextLines.map((positions, i) => (
          <Polyline key={`ctx-line-${i}`} positions={positions} pathOptions={{ color: '#cbd5e1', weight: 2, opacity: 0.7 }} />
        ))}

        {/* Active branch layer — clickable */}
        {branchActive && rows.map((row, index) => {
          const positions = branchPositions(row, busIndex);
          if (!positions) return null;
          const sel = index === selectedRowIndex;
          return (
            <Polyline
              key={`branch-${index}`}
              positions={positions}
              pathOptions={{ color: sel ? '#f59e0b' : '#0f766e', weight: sel ? 7 : 3, opacity: sel ? 1 : 0.85 }}
              eventHandlers={{ click: () => onSelectRow(index) }}
            >
              <Tooltip>{stringValue(row.name) || `row ${index + 1}`}</Tooltip>
            </Polyline>
          );
        })}

        {/* Buses — context, or the active+clickable layer */}
        {model.buses.map((bus, index) => {
          const coords = ownCoords(bus);
          if (!coords) return null;
          const sel = busActive && index === selectedRowIndex;
          return (
            <CircleMarker
              key={`bus-${index}`}
              center={coords}
              radius={sel ? 11 : busActive ? 8 : 6}
              pathOptions={{
                color: sel ? '#f59e0b' : '#ffffff',
                weight: sel ? 3 : 2,
                fillColor: '#0f766e',
                fillOpacity: busActive ? 0.95 : 0.5,
              }}
              eventHandlers={busActive ? { click: () => onSelectRow(index) } : undefined}
            >
              <Tooltip>
                <strong>{stringValue(bus.name)}</strong><br />
                {numberValue(bus.v_nom)} kV · {stringValue(bus.carrier)}
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* Active point layer (generators / loads / storage / stores) — clickable */}
        {pointActive && rows.map((row, index) => {
          const coords = busCoords(row, busIndex);
          if (!coords) return null;
          const sel = index === selectedRowIndex;
          const fill = activeSheet === 'generators'
            ? resolvedColor(row.color, row.carrier)
            : '#14b8a6';
          return (
            <CircleMarker
              key={`pt-${index}`}
              center={coords}
              radius={sel ? 10 : 6}
              pathOptions={{ color: sel ? '#f59e0b' : '#ffffff', weight: sel ? 3 : 1.5, fillColor: fill, fillOpacity: 0.95 }}
              eventHandlers={{ click: () => onSelectRow(index) }}
            >
              <Tooltip>{stringValue(row.name) || `row ${index + 1}`} · {stringValue(row.bus)}</Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
