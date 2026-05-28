/**
 * Status bar — thin footer always visible at the bottom of the workbench.
 *
 * Each cell shows a single live datum about the project state; clicking
 * a cell navigates the user to the editor for that datum (open the
 * Run-setup overlay's Carbon tab, switch to Analytics → Validation,
 * etc.). The bar is the canonical "where am I" indicator.
 */
import React from 'react';
import {
  CarbonPriceScheduleEntry,
  CustomConstraint,
  PathwayConfig,
  RollingHorizonConfig,
  SecurityConstrainedConfig,
  StochasticConfig,
} from '../shared/types';

type RunState = 'idle' | 'running' | 'done' | 'error';

interface Props {
  filename: string;
  activeScenarioLabel: string | null;
  pathwayConfig: PathwayConfig;
  rollingConfig: RollingHorizonConfig;
  stochasticConfig: StochasticConfig;
  sclopfConfig: SecurityConstrainedConfig;
  snapshotStart: number;
  snapshotEnd: number;
  snapshotWeight: number;
  carbonPrice: number;
  carbonPriceSchedule: CarbonPriceScheduleEntry[];
  currencySymbol: string;
  constraints: CustomConstraint[];
  globalConstraintCount: number;
  validationErrors: number;
  validationWarnings: number;
  runStatus: RunState;
  runElapsedSec: number;
  onOpenRunSetup: () => void;
  onOpenConstraints: () => void;
  onJumpToValidation: () => void;
}

export function StatusBar(props: Props) {
  const planningLabel = props.pathwayConfig.enabled
    ? `Pathway · ${props.pathwayConfig.periods.length}p`
    : 'Single period';

  const windowLabel = props.pathwayConfig.enabled
    ? 'Full horizon'
    : `${props.snapshotEnd - props.snapshotStart}×${props.snapshotWeight}h`;

  let carbonLabel: string;
  if (props.carbonPriceSchedule.length >= 2) {
    const prices = props.carbonPriceSchedule.map((r) => r.price);
    const minP = Math.min(...prices);
    const maxP = Math.max(...prices);
    carbonLabel = minP === maxP
      ? `${props.currencySymbol}${minP}/t`
      : `${props.currencySymbol}${minP}→${maxP}/t`;
  } else if (props.carbonPriceSchedule.length === 1) {
    carbonLabel = `${props.currencySymbol}${props.carbonPriceSchedule[0].price}/t`;
  } else {
    carbonLabel = props.carbonPrice > 0 ? `${props.currencySymbol}${props.carbonPrice}/t` : 'no carbon price';
  }

  const enabledConstraints = props.constraints.filter((c) => c.enabled).length;
  const constraintsLabel = `${enabledConstraints} custom · ${props.globalConstraintCount} global`;

  const modeFlags: string[] = [];
  if (props.rollingConfig.enabled) modeFlags.push('rolling');
  if (props.stochasticConfig.enabled && props.stochasticConfig.scenarios.length >= 2) modeFlags.push('stochastic');
  if (props.sclopfConfig.enabled) modeFlags.push('SCLOPF');

  let solveLabel: string;
  let solveTone: 'idle' | 'busy' | 'ok' | 'err' = 'idle';
  switch (props.runStatus) {
    case 'running':
      solveLabel = `solving · ${Math.floor(props.runElapsedSec / 60)}m ${(props.runElapsedSec % 60).toString().padStart(2, '0')}s`;
      solveTone = 'busy';
      break;
    case 'done':
      solveLabel = 'solved';
      solveTone = 'ok';
      break;
    case 'error':
      solveLabel = 'solve failed';
      solveTone = 'err';
      break;
    default:
      solveLabel = 'idle';
      solveTone = 'idle';
  }

  return (
    <footer className="status-bar" role="contentinfo">
      <span className="status-bar-cell" title={`Workbook: ${props.filename}`}>{props.filename}</span>
      <span className="status-bar-sep" />
      <span className="status-bar-cell" title="Active scenario preset">
        {props.activeScenarioLabel ?? 'no scenario'}
      </span>
      <span className="status-bar-sep" />
      <button
        type="button"
        className="status-bar-cell status-bar-cell--button"
        onClick={props.onOpenRunSetup}
        title="Open run setup (planning mode)"
      >
        {planningLabel}
      </button>
      <button
        type="button"
        className="status-bar-cell status-bar-cell--button"
        onClick={props.onOpenRunSetup}
        title="Open run setup (window)"
      >
        {windowLabel}
      </button>
      <button
        type="button"
        className="status-bar-cell status-bar-cell--button"
        onClick={props.onOpenRunSetup}
        title="Open run setup (carbon price)"
      >
        {carbonLabel}
      </button>
      <button
        type="button"
        className="status-bar-cell status-bar-cell--button"
        onClick={props.onOpenConstraints}
        title="Open constraints editor"
      >
        {constraintsLabel}
      </button>
      {modeFlags.length > 0 && (
        <>
          <span className="status-bar-sep" />
          <span className="status-bar-cell status-bar-cell--accent">
            {modeFlags.join(' · ')}
          </span>
        </>
      )}
      <span className="status-bar-spacer" />
      <button
        type="button"
        className={`status-bar-cell status-bar-cell--button status-bar-cell--validation${
          props.validationErrors > 0 ? ' status-bar-cell--err' : props.validationWarnings > 0 ? ' status-bar-cell--warn' : ''
        }`}
        onClick={props.onJumpToValidation}
        title="Open validation results"
      >
        {props.validationErrors > 0
          ? `${props.validationErrors} error${props.validationErrors === 1 ? '' : 's'}`
          : props.validationWarnings > 0
            ? `${props.validationWarnings} warning${props.validationWarnings === 1 ? '' : 's'}`
            : 'validation ok'}
      </button>
      <span className="status-bar-sep" />
      <span className={`status-bar-cell status-bar-cell--${solveTone}`} title="Last solve state">
        {solveLabel}
      </span>
    </footer>
  );
}
